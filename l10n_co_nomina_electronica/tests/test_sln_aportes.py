# -*- coding: utf-8 -*-
"""SLN (suspensión / licencia no remunerada): sobre la base SLN el trabajador no paga su cuota;
el empleador paga salud (la exoneración del Art. 114-1 no la cubre) y pensión patronal solo si la
compañía lo decide. Nómina y PILA deben coincidir. Nivel de verificación: recibos reales con
compute_sheet y las fuentes de SLN simuladas (mock); PILA vía su función de aportes."""
from datetime import date
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

_PAYSLIP = 'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.HrPayslip'
_SLN = 400000.0


@tagged('post_install', '-at_install')
class TestSlnAportes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba SLN'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura SLN', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.Consolidado = cls.env['l10n.co.ibc.mensual']

    def _recibo(self, name, wage, con_sln=True):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open'})
        slip = self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        if con_sln:
            with mock.patch(_PAYSLIP + '._ne_ibc_sln', return_value=_SLN), \
                    mock.patch(_PAYSLIP + '._ne_dias_sln', return_value=10):
                slip.compute_sheet()
        else:
            slip.compute_sheet()
        return slip

    def _linea(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def _pct(self, slip, code):
        return slip._rule_parameter(code, slip.date_from) / 100

    def test_consolidado_guarda_ibc_y_dias_sln(self):
        slip = self._recibo('Cons', 3000000.0)
        slip.state = 'done'
        with mock.patch(_PAYSLIP + '._ne_dias_sln', return_value=10):
            slip._ne_refrescar_ibc_mensual()
        cons = self.Consolidado.search([('employee_id', '=', slip.employee_id.id)])
        self.assertAlmostEqual(cons.ibc_sln, _SLN, delta=0.01)
        self.assertEqual(cons.dias_sln, 10)

    def test_trabajador_no_paga_cuota_sobre_sln_y_empleador_si_su_tarifa(self):
        slip = self._recibo('Cuota', 3000000.0)
        ibc_sp = self._linea(slip, 'CO_IBC_SP')
        self.assertAlmostEqual(
            -self._linea(slip, 'CO_SALUD_EMP'),
            (ibc_sp - _SLN) * self._pct(slip, 'l10n_co_pct_salud_empleado'), delta=1)
        self.assertAlmostEqual(
            self._linea(slip, 'CO_SALUD_CIA'),
            ibc_sp * self._pct(slip, 'l10n_co_pct_salud_empleador'), delta=1)

    def test_pension_patronal_sobre_sln_por_defecto(self):
        slip = self._recibo('PenDef', 3000000.0)
        self.assertTrue(self.company.l10n_co_ne_pension_patronal_sln)
        self.assertAlmostEqual(
            self._linea(slip, 'CO_PENSION_CIA'),
            self._linea(slip, 'CO_IBC_SP') * self._pct(slip, 'l10n_co_pct_pension_empleador'),
            delta=1)

    def test_pension_patronal_sin_sln_si_la_compania_no_cotiza(self):
        self.company.l10n_co_ne_pension_patronal_sln = False
        slip = self._recibo('PenNo', 3000000.0)
        self.assertAlmostEqual(
            self._linea(slip, 'CO_PENSION_CIA'),
            (self._linea(slip, 'CO_IBC_SP') - _SLN)
            * self._pct(slip, 'l10n_co_pct_pension_empleador'), delta=1)

    def test_exonerado_con_sln_salud_patronal_cero_en_laborados_y_sln(self):
        """Guía Min. Salud: exonerado + SLN => tarifa de salud patronal cero (todo el IBC)."""
        self.company.l10n_co_ne_exoneration_1607 = True
        slip = self._recibo('Exon', 3000000.0)  # < 10 SMMLV: exonerado
        self.assertEqual(self._linea(slip, 'CO_SALUD_CIA'), 0.0)

    def test_exonerado_sin_sln_no_paga_salud_patronal_como_antes(self):
        self.company.l10n_co_ne_exoneration_1607 = True
        slip = self._recibo('ExonSinSln', 3000000.0, con_sln=False)
        self.assertEqual(self._linea(slip, 'CO_SALUD_CIA'), 0.0)

    def test_sin_exoneracion_y_sin_sln_igual_que_antes(self):
        slip = self._recibo('Normal', 3000000.0, con_sln=False)
        self.assertAlmostEqual(
            self._linea(slip, 'CO_SALUD_CIA'),
            self._linea(slip, 'CO_IBC_SP') * self._pct(slip, 'l10n_co_pct_salud_empleador'),
            delta=1)

    def test_el_umbral_de_exoneracion_excluye_la_base_sln(self):
        """Un salario justo bajo 10 SMMLV que con la base SLN lo superaría sigue exonerado."""
        self.company.l10n_co_ne_exoneration_1607 = True
        probe = self._recibo('Umbral0', 3000000.0, con_sln=False)
        tope = probe._rule_parameter('l10n_co_smmlv', probe.date_from) * probe._rule_parameter(
            'l10n_co_tope_exoneracion_smmlv', probe.date_from)
        salario = tope - _SLN / 2
        slip = self._recibo('Umbral', salario)
        self.assertGreater(self._linea(slip, 'CO_IBC_SP'), 0)
        # sin la base SLN el IBC < tope: sigue exonerado, aunque con la base lo superaría
        self.assertEqual(self._linea(slip, 'CO_SALUD_CIA'), 0.0)

    # ── PILA ──
    def _pila(self, cotiza, ibc_sp=3000000.0, exonerado=False):
        self.company.l10n_co_ne_pension_patronal_sln = cotiza
        wizard = self.env['l10n.co.hr.pila.wizard.v2'].new({'company_id': self.company.id})
        params = {'l10n_co_pct_pension_empleado': 4.0, 'l10n_co_pct_pension_empleador': 12.0,
                  'l10n_co_pct_salud_empleado': 4.0, 'l10n_co_pct_salud_empleador': 8.5}
        return wizard._aportes_salud_pension(
            ibc_sp, _SLN, 30, 10, 0.16, 0.125, lambda code: params[code],
            exonerado=exonerado)

    def test_pila_sln_sin_cuota_del_trabajador(self):
        r = self._pila(True)
        ibc_normal = 3000000.0 - _SLN
        self.assertEqual(r['cotizacion_salud'], round(ibc_normal * 0.125 + _SLN * 0.085))
        self.assertEqual(r['cotizacion_pension'], round(ibc_normal * 0.16 + _SLN * 0.12))
        self.assertEqual((r['ibc_pension'], r['dias_pension']), (3000000.0, 30))

    def test_pila_sin_pension_sln_excluye_base_y_dias(self):
        r = self._pila(False)
        ibc_normal = 3000000.0 - _SLN
        self.assertEqual(r['cotizacion_pension'], round(ibc_normal * 0.16))
        self.assertEqual((r['ibc_pension'], r['dias_pension']), (ibc_normal, 20))
        self.assertEqual(r['cotizacion_salud'], round(ibc_normal * 0.125 + _SLN * 0.085))

    def test_pila_sin_sln_igual_que_antes(self):
        self.company.l10n_co_ne_pension_patronal_sln = True
        wizard = self.env['l10n.co.hr.pila.wizard.v2'].new({'company_id': self.company.id})
        r = wizard._aportes_salud_pension(3000000.0, 0.0, 30, 0, 0.16, 0.125, lambda c: 0.0)
        self.assertEqual(r['cotizacion_salud'], round(3000000.0 * 0.125))
        self.assertEqual(r['cotizacion_pension'], round(3000000.0 * 0.16))

    def test_pila_exonerado_con_sln_salud_patronal_cero_en_sln(self):
        r = self._pila(True, exonerado=True)
        ibc_normal = 3000000.0 - _SLN
        self.assertEqual(r['cotizacion_salud'], round(ibc_normal * 0.125))

    def test_pila_exonerado_mes_100_por_ciento_sln_salud_cero(self):
        """Caso del ejemplo oficial: exonerado y todo el mes SLN => cotización de salud 0."""
        self.company.l10n_co_ne_pension_patronal_sln = True
        wizard = self.env['l10n.co.hr.pila.wizard.v2'].new({'company_id': self.company.id})
        params = {'l10n_co_pct_pension_empleador': 12.0, 'l10n_co_pct_salud_empleador': 8.5}
        r = wizard._aportes_salud_pension(
            _SLN, _SLN, 30, 30, 0.16, 0.125, lambda code: params[code], exonerado=True)
        self.assertEqual(r['cotizacion_salud'], 0)
        # la pensión patronal sigue su regla propia
        self.assertEqual(r['cotizacion_pension'], round(_SLN * 0.12))

    def test_nomina_exonerado_con_sln_salud_cero(self):
        self.company.l10n_co_ne_exoneration_1607 = True
        slip = self._recibo('Exon100', 3000000.0)
        self.assertEqual(self._linea(slip, 'CO_SALUD_CIA'), 0.0)
