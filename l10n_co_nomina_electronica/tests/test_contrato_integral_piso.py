# -*- coding: utf-8 -*-
"""Piso del salario integral: 13 SMMLV (CST art. 132 num. 2), con el SMMLV de la fecha.

SMMLV: 2024 = 1.300.000 -> piso 16.900.000; 2025 = 1.423.500 -> piso 18.505.500;
2026 = 1.750.905 -> piso 22.761.765. Un cambio de salario se valida con el SMMLV de hoy; un alta o
un cambio de ingreso/marca integral, con el SMMLV de la fecha de inicio. Los borradores tambien.
"""

from datetime import date
from unittest import mock

from odoo.exceptions import ValidationError
from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import format_amount


@tagged('post_install', '-at_install')
class TestContratoIntegralPiso(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN',
            'name': 'Compañía de Prueba Piso Integral'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Piso Integral', 'country_id': cls.env.ref('base.co').id})
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Piso Integral', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})

    def _vals(self, wage, date_start, integral=True, state='open'):
        return {
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Piso Integral', 'employee_id': self.employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date_start, 'state': state,
            'l10n_co_ne_integral_salary': integral}

    def _contrato(self, *args, **kwargs):
        return self.env['hr.contract'].create(self._vals(*args, **kwargs))

    def test_en_el_piso_exacto_guarda(self):
        self.assertTrue(self._contrato(22761765.0, date(2026, 1, 1)))

    def test_un_peso_bajo_el_piso_falla_nombrando_contrato_y_piso(self):
        with self.assertRaises(ValidationError) as exc:
            self._contrato(22761764.0, date(2026, 1, 1))
        msg = str(exc.exception)
        self.assertIn('Contrato Piso Integral', msg)
        self.assertIn('Piso Integral', msg)  # empleado
        # con la moneda y el idioma del usuario: se compara contra format_amount del mismo entorno
        self.assertIn(format_amount(self.env, 22761765.0, self.company.currency_id), msg)
        self.assertIn('13', msg)

    def test_contrato_de_2025_usa_el_smmlv_de_su_fecha_de_inicio(self):
        self.assertTrue(self._contrato(19000000.0, date(2025, 3, 1)))  # piso 18.505.500
        with self.assertRaises(ValidationError):
            self._contrato(18505499.0, date(2025, 3, 1))

    def test_no_integral_con_salario_bajo_guarda(self):
        self.assertTrue(self._contrato(1800000.0, date(2026, 1, 1), integral=False))

    def test_en_borrador_tambien_valida(self):
        with self.assertRaises(ValidationError):
            self._contrato(5000000.0, date(2026, 1, 1), state='draft')

    def test_marcar_integral_un_contrato_con_salario_bajo_falla(self):
        contrato = self._contrato(5000000.0, date(2026, 1, 1), integral=False)
        with self.assertRaises(ValidationError):
            contrato.l10n_co_ne_integral_salary = True

    def test_bajar_el_salario_usa_el_smmlv_de_hoy(self):
        """Ingreso en 2024 (piso 16.900.000) pero hoy simulado 2026 (piso 22.761.765): 20M
        bajo el salario vigente falla; el mismo salario en un alta de 2024 sí guardaba."""
        contrato = self._contrato(30000000.0, date(2024, 1, 1))
        with mock.patch.object(Date, 'context_today', return_value=date(2026, 6, 1)):
            with self.assertRaises(ValidationError):
                contrato.wage = 20000000.0
            contrato.wage = 23000000.0  # sobre el piso de 2026: guarda

    def test_tocar_otro_campo_no_valida_el_piso(self):
        """Un contrato integral historico bajo el piso se puede editar en otros campos."""
        contrato = self._contrato(30000000.0, date(2026, 1, 1))
        self.env.cr.execute(
            'UPDATE hr_contract SET wage = 1000000 WHERE id = %s', (contrato.id,))
        contrato.invalidate_recordset()
        contrato.name = 'Contrato renombrado'
        self.assertEqual(contrato.name, 'Contrato renombrado')
