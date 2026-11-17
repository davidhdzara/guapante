# -*- coding: utf-8 -*-
"""Dias cotizados por subsistema (H-017b, commit 2): mes comercial de 30 dias
(febrero completo = 30), ING/RET delimitan el rango, y las novedades suman o no
segun la tabla de David (IGE/IRL/LMA/SLN: solo salud y pension; VAC/LR: todos).

Nivel de verificacion: metodos _ne_dias_cotizados/_ne_ibc_sln con las fuentes de
ausencias simuladas (mock) + compute_sheet real de un mes completo; las ausencias
reales (hr.leave) ya estan cubiertas por test_ausencias_nomina."""

from datetime import date
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDiasCotizados(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba Días Cotizados'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Días', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _payslip(self, name, ini, fin, contrato_ini=date(2024, 1, 1), wage=3000000.0):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': contrato_ini, 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.structure.id, 'date_from': ini, 'date_to': fin})

    def test_febrero_completo_cotiza_30_dias(self):
        slip = self._payslip('Feb', date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(slip._ne_dias_cotizados(), {'sp': 30, 'arl': 30, 'paraf': 30})

    def test_mes_de_31_dias_cotiza_30(self):
        slip = self._payslip('Mes31', date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(slip._ne_dias_cotizados()['sp'], 30)

    def test_ingreso_a_mitad_de_mes_delimita_el_rango(self):
        slip = self._payslip('Ingreso', date(2026, 9, 1), date(2026, 9, 30),
                             contrato_ini=date(2026, 9, 16))
        self.assertEqual(slip._ne_dias_cotizados()['sp'], 15)

    def test_novedades_cuentan_a_salud_pension_pero_no_a_arl_ni_parafiscales(self):
        slip = self._payslip('Nov', date(2026, 9, 1), date(2026, 9, 30))
        cls = type(slip)
        with mock.patch.object(
                cls, '_ne_ausencia_calendario',
                side_effect=lambda codigo: (10 if codigo == 'CO_INC_COMUN' else 0, [])), \
                mock.patch.object(cls, '_ne_dias_sln', return_value=5):
            dias = slip._ne_dias_cotizados()
        self.assertEqual(dias['sp'], 30)       # IGE y SLN cotizan a salud y pension
        self.assertEqual(dias['arl'], 15)      # ARL: 30 - 10 (IGE) - 5 (SLN)
        self.assertEqual(dias['paraf'], 15)

    def test_ibc_sln_es_ibc_anterior_prorrateado_por_dias(self):
        slip = self._payslip('Sln', date(2026, 9, 1), date(2026, 9, 30))
        cls = type(slip)
        with mock.patch.object(cls, '_ne_dias_sln', return_value=5), \
                mock.patch.object(cls, '_ne_ultimo_ibc_anterior', return_value=3000000.0):
            self.assertAlmostEqual(slip._ne_ibc_sln(slip.contract_id), 500000.0, delta=0.01)

    def test_sin_sln_no_consulta_ibc_anterior(self):
        slip = self._payslip('SinSln', date(2026, 9, 1), date(2026, 9, 30))
        cls = type(slip)
        with mock.patch.object(cls, '_ne_dias_sln', return_value=0), \
                mock.patch.object(cls, '_ne_ultimo_ibc_anterior', side_effect=AssertionError):
            self.assertEqual(slip._ne_ibc_sln(slip.contract_id), 0.0)

    def test_compute_sheet_febrero_completo_reporta_30_dias_y_el_salario_como_ibc(self):
        slip = self._payslip('FebReal', date(2026, 2, 1), date(2026, 2, 28), wage=3000000.0)
        slip.compute_sheet()
        linea = lambda c: slip.line_ids.filtered(lambda l: l.code == c)
        self.assertAlmostEqual(linea('CO_DIAS_SP').total, 30.0, delta=0.001)
        self.assertAlmostEqual(linea('CO_DIAS_ARL').total, 30.0, delta=0.001)
        self.assertAlmostEqual(linea('CO_IBC_SP').total, 3000000.0, delta=0.01)
