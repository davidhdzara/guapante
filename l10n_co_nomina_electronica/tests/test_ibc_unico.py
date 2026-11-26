# -*- coding: utf-8 -*-
"""IBC unico del recibo (H-017b, commit 1): regla del 40% (Ley 1393/2010 Art. 30,
SU 25185/2021), techo de 25 SMMLV sin prorratear, piso de 1 SMMLV prorrateado por
dias, salario integral, y exclusion del auxilio de transporte.

Nivel de verificacion: funcion de limites (pura) + compute_sheet real sobre la
estructura general. La consolidacion mensual, los dias por novedad y PILA/UGPP
llegan en commits siguientes."""

from collections import defaultdict
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class IbcBase(TransactionCase):
    """Fixtures comunes (sin tests propios)."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba IBC'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura IBC', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _payslip(self, name, wage, integral=False):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_integral_salary': integral})
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})

    def _linea(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def _smmlv(self, slip):
        return slip._rule_parameter('l10n_co_smmlv', slip.date_from)


@tagged('post_install', '-at_install')
class TestIbcUnico(IbcBase):

    # ── funcion de limites (pura) ──
    def test_40_por_ciento_excedente_suma_al_ibc(self):
        slip = self._payslip('Lim1', 3000000.0)
        # salarial 3.000.000 + pactado 3.000.000: tope 40% de 6.000.000 = 2.400.000 -> excedente 600.000
        ibc = slip._ne_ibc_limites(3000000.0, 0.0, 3000000.0, 3000000.0, 30)
        self.assertAlmostEqual(ibc, 3600000.0, delta=0.01)

    def test_pactados_bajo_el_40_no_suman(self):
        slip = self._payslip('Lim2', 3000000.0)
        ibc = slip._ne_ibc_limites(3000000.0, 0.0, 3000000.0, 500000.0, 30)
        self.assertAlmostEqual(ibc, 3000000.0, delta=0.01)

    def test_integral_70_mas_excedente_sobre_integral_completo(self):
        slip = self._payslip('Lim3', 20000000.0, integral=True)
        # integral 20.000.000 -> IBC salarial 14.000.000; pactado 10.000.000 sobre
        # remuneracion (20.000.000 + 10.000.000)=30.000.000 -> tope 12.000.000 -> excedente 0
        self.assertAlmostEqual(
            slip._ne_ibc_limites(14000000.0, 0.0, 20000000.0, 10000000.0, 30), 14000000.0, delta=0.01)
        # pactado 15.000.000: tope 40% de 35.000.000 = 14.000.000 -> excedente 1.000.000
        self.assertAlmostEqual(
            slip._ne_ibc_limites(14000000.0, 0.0, 20000000.0, 15000000.0, 30), 15000000.0, delta=0.01)

    def test_techo_25_smmlv_no_se_prorratea(self):
        slip = self._payslip('Lim4', 3000000.0)
        smmlv = self._smmlv(slip)
        self.assertAlmostEqual(
            slip._ne_ibc_limites(100 * smmlv, 0.0, 100 * smmlv, 0.0, 10), 25 * smmlv, delta=0.01)

    def test_piso_se_prorratea_por_dias(self):
        slip = self._payslip('Lim5', 3000000.0)
        smmlv = self._smmlv(slip)
        self.assertAlmostEqual(
            slip._ne_ibc_limites(100000.0, 0.0, 100000.0, 0.0, 15), smmlv / 2, delta=0.01)

    # ── clasificacion de no salariales ──
    def _rr(self, **totales):
        rr = defaultdict(lambda: {'total': 0.0})
        for k, v in totales.items():
            rr[k] = {'total': v}
        return rr

    def test_pactados_cuenta_pacto_y_excluye_naturaleza(self):
        slip = self._payslip('Pac1', 3000000.0)
        rr = self._rr(CO_AUX_TRANS=200000.0, CO_AUX_ALIM=150000.0)
        self.assertAlmostEqual(slip._ne_ibc_pactados(rr), 150000.0, delta=0.01)

    def test_no_salarial_sin_clasificar_es_error_claro(self):
        slip = self._payslip('Pac2', 3000000.0)
        regla = self.structure.rule_ids.filtered(lambda r: r.code == 'CO_AUX_ALIM')
        regla.l10n_co_pila_origen_no_salarial = False
        with self.assertRaises(UserError) as e:
            slip._ne_ibc_pactados(self._rr(CO_AUX_ALIM=100000.0))
        self.assertIn('Origen del Pago No Salarial', str(e.exception))

    def test_clasificacion_cargada_para_las_reglas_del_modulo(self):
        mapa = {r.code: r.l10n_co_pila_origen_no_salarial for r in self.structure.rule_ids}
        self.assertEqual(mapa['CO_AUX_TRANS'], 'naturaleza')
        self.assertEqual(mapa['CO_AUX_ALIM'], 'pacto')

    # ── compute_sheet real ──
    def test_ibc_no_incluye_auxilio_de_transporte_y_alimenta_la_deduccion(self):
        slip = self._payslip('Real1', 1800000.0)
        slip.compute_sheet()
        ibc = self._linea(slip, 'CO_IBC_SP')
        self.assertTrue(ibc)
        self.assertAlmostEqual(ibc.total, 1800000.0, delta=0.01)
        self.assertTrue(self._linea(slip, 'CO_AUX_TRANS'))   # el auxilio existe...
        self.assertGreater(self._linea(slip, 'CO_BRUTO').total, ibc.total)  # ...y no entra
        pct = slip._rule_parameter('l10n_co_pct_salud_empleado', slip.date_from)
        self.assertAlmostEqual(-self._linea(slip, 'CO_SALUD_EMP').total, ibc.total * pct / 100, delta=1.0)

    def test_techo_en_nomina_real(self):
        slip = self._payslip('Real2', 60000000.0)
        slip.compute_sheet()
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, 25 * self._smmlv(slip), delta=0.01)

    def test_piso_en_nomina_real(self):
        slip = self._payslip('Real3', 1000000.0)
        slip.compute_sheet()
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, self._smmlv(slip), delta=0.01)

    def test_integral_en_nomina_real_es_70_por_ciento(self):
        slip = self._payslip('Real4', 20000000.0, integral=True)
        slip.compute_sheet()
        factor = slip._rule_parameter('l10n_co_factor_integral_salary', slip.date_from)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, 20000000.0 * factor, delta=0.01)


@tagged('post_install', '-at_install')
class TestIbcUnicoCiaYLiquidacion(IbcBase):
    """Commit 3a: los aportes patronales y la liquidacion leen el IBC unico."""

    def test_aportes_patronales_usan_el_ibc_unico_no_el_bruto(self):
        slip = self._payslip('Cia1', 1800000.0)   # con auxilio de transporte
        slip.compute_sheet()
        ibc = self._linea(slip, 'CO_IBC_SP').total
        self.assertAlmostEqual(ibc, 1800000.0, delta=0.01)
        pension = self._linea(slip, 'CO_PENSION_CIA')
        pct = slip._rule_parameter('l10n_co_pct_pension_empleador', slip.date_from)
        self.assertAlmostEqual(pension.total, ibc * pct / 100, delta=1.0)
        arl = self._linea(slip, 'CO_ARL_CIA')
        self.assertAlmostEqual(arl.total, self._linea(slip, 'CO_IBC_ARL').total * slip._ne_pct_arl() / 100, delta=1.0)
        ccf = self._linea(slip, 'CO_CCF_CIA')
        pct_ccf = slip._rule_parameter('l10n_co_pct_ccf', slip.date_from)
        self.assertAlmostEqual(ccf.total, self._linea(slip, 'CO_IBC_PARAF').total * pct_ccf / 100, delta=1.0)

    def test_aportes_patronales_con_piso_y_techo(self):
        alto = self._payslip('Cia2', 60000000.0)
        alto.compute_sheet()
        self.assertAlmostEqual(
            self._linea(alto, 'CO_PENSION_CIA').total,
            25 * self._smmlv(alto) * alto._rule_parameter('l10n_co_pct_pension_empleador', alto.date_from) / 100,
            delta=1.0)
