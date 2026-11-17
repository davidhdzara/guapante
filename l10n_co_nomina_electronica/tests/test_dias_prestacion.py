# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""HrPayslip._ne_dias_prestacion: dias de prima, cesantias, intereses, indemnizacion y vacaciones.

Decision de David (febrero): "debe contar los dias reales que se tienen ni mas ni menos". Modo
'real' (Guapante): febrero cuenta 28 (29 si es bisiesto), completo o parcial; el dia 31 no cuenta.
Modo '30': mes comercial (cada mes, febrero incluido, cuenta 30). El divisor del anio es 360 en ambos.
Valores a mano, extremos incluidos. No afecta _ne_dias_bajo_contrato (sueldo y PILA: febrero = 30)."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDiasPrestacion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'name': 'Compañía de Prueba Días Prestación'})
        structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Días Prestación',
            'country_id': cls.env.ref('base.co').id})
        employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Días Prestación', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Días Prestación', 'employee_id': employee.id,
            'company_id': cls.company.id, 'structure_type_id': structure_type.id,
            'wage': 3000000.0, 'date_start': date(2023, 1, 1), 'state': 'open'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Nómina Días Prestación', 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': cls.company.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31)})

    def _dias(self, ini, fin, modo='real'):
        self.company.l10n_co_ne_febrero_modo = modo
        return self.slip._ne_dias_prestacion(ini, fin)

    # ── Modo "Días reales" ──────────────────────────────────────────
    def test_real_febrero_completo_cuenta_28_y_bisiesto_29(self):
        self.assertEqual(self._dias(date(2026, 2, 1), date(2026, 2, 28)), 28)
        self.assertEqual(self._dias(date(2024, 2, 1), date(2024, 2, 29)), 29)

    def test_real_ingreso_el_15_de_febrero_hasta_el_28_cuenta_14(self):
        self.assertEqual(self._dias(date(2026, 2, 15), date(2026, 2, 28)), 14)

    def test_real_el_dia_31_no_cuenta(self):
        self.assertEqual(self._dias(date(2026, 1, 1), date(2026, 1, 31)), 30)
        self.assertEqual(self._dias(date(2026, 1, 30), date(2026, 1, 31)), 1)
        self.assertEqual(self._dias(date(2026, 1, 31), date(2026, 1, 31)), 0)

    def test_real_ingreso_a_mitad_de_mes(self):
        # 16-mar a 31-mar: 16 reales - el 31 = 15; 15-mar a 15-abr: 32 reales - el 31 = 31.
        self.assertEqual(self._dias(date(2026, 3, 16), date(2026, 3, 31)), 15)
        self.assertEqual(self._dias(date(2026, 3, 15), date(2026, 4, 15)), 31)

    def test_real_semestres_y_anio(self):
        self.assertEqual(self._dias(date(2026, 1, 1), date(2026, 6, 30)), 178)   # 181 - 3
        self.assertEqual(self._dias(date(2026, 7, 1), date(2026, 12, 31)), 180)  # 184 - 4
        self.assertEqual(self._dias(date(2026, 1, 1), date(2026, 12, 31)), 358)  # 365 - 7
        self.assertEqual(self._dias(date(2024, 1, 1), date(2024, 12, 31)), 359)  # 366 - 7

    def test_real_rango_largo_e_invertido(self):
        # 1-mar-2024 a 15-ago-2026: 898 reales - 17 treintaiunos = 881.
        self.assertEqual(self._dias(date(2024, 3, 1), date(2026, 8, 15)), 881)
        self.assertEqual(self._dias(date(2026, 3, 2), date(2026, 3, 1)), 0)

    # ── Modo "Mes de 30 días" ───────────────────────────────────────
    def test_mes_de_30_febrero_cuenta_30_y_el_31_no_suma(self):
        self.assertEqual(self._dias(date(2026, 2, 1), date(2026, 2, 28), '30'), 30)
        self.assertEqual(self._dias(date(2024, 2, 1), date(2024, 2, 29), '30'), 30)
        self.assertEqual(self._dias(date(2026, 1, 30), date(2026, 1, 31), '30'), 1)

    def test_mes_de_30_semestres_y_anio_comerciales(self):
        self.assertEqual(self._dias(date(2026, 1, 1), date(2026, 6, 30), '30'), 180)
        self.assertEqual(self._dias(date(2026, 1, 1), date(2026, 12, 31), '30'), 360)
        self.assertEqual(self._dias(date(2024, 3, 1), date(2026, 8, 15), '30'), 885)

    # ── Sin parámetro ───────────────────────────────────────────────
    def test_sin_el_parametro_falla_con_mensaje_claro(self):
        self.company.l10n_co_ne_febrero_modo = False
        with self.assertRaises(UserError) as exc:
            self.slip._ne_dias_prestacion(date(2026, 1, 1), date(2026, 1, 31))
        self.assertIn(self.company.name, str(exc.exception))
        self.assertIn('Febrero en prestaciones', str(exc.exception))

    def test_el_sueldo_mensual_sigue_con_febrero_30(self):
        """_ne_dia_comercial (sueldo y PILA) no cambia: el ultimo dia de febrero es el dia 30."""
        self.assertEqual(self.slip._ne_dia_comercial(date(2026, 2, 28), 30), 30)
        self.assertEqual(self.slip._ne_dia_comercial(date(2024, 2, 29), 30), 30)
