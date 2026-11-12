# -*- coding: utf-8 -*-
"""Embargos y libranzas en la liquidacion, por tipo de concepto.

Nivel de verificacion: metodos hr.payslip._ne_liq_* con totales de concepto
sinteticos (result_rules simulado) y aplicacion/cierre sobre asignaciones
reales; el compute_sheet completo de una liquidacion se prueba en servidor.
"""

from collections import defaultdict

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLiquidacionEmbargoLibranza(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Liquidación Terceros'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Liquidación', 'company_id': cls.company.id})
        contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Liquidación', 'employee_id': cls.employee.id,
            'company_id': cls.company.id, 'wage': 3000000,
            'date_start': '2025-01-01', 'state': 'draft'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Liquidación', 'employee_id': cls.employee.id,
            'contract_id': contract.id, 'company_id': cls.company.id,
            'struct_id': cls.structure.id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31'})
        cls.entidad = cls.env['res.partner'].create({'name': 'Banco Liquidación'})
        cls.juzgado = cls.env['res.partner'].create({'name': 'Juzgado Liquidación'})

    def _rr(self, **totales):
        """result_rules simulado: salario/vacaciones/prestacion/indemnizacion."""
        codigos = {'salario': ['CO_LIQ_SALARIOS'], 'vacaciones': ['CO_LIQ_VACACIONES'],
                   'prestacion': ['CO_LIQ_PRIMA'], 'indemnizacion': ['CO_LIQ_INDEMNIZACION']}
        rr = defaultdict(lambda: {'total': 0.0})
        for k, v in totales.items():
            rr[codigos[k][0]] = {'total': v}
        return rr

    def _libranza(self, saldo=10000000.0, autoriza=True):
        vals = {
            'description': 'Libranza liquidación',
            'employee_ids': [(6, 0, [self.employee.id])],
            'company_id': self.company.id,
            'other_input_type_id': self.env.ref('l10n_co_nomina_electronica.input_l10n_co_libranza').id,
            'monthly_amount': 500000.0, 'date_start': '2026-01-01', 'no_end_date': True,
            'l10n_co_partner_id': self.entidad.id, 'l10n_co_saldo_pendiente': saldo}
        if autoriza:
            vals.update(l10n_co_autoriza_liquidacion=True, attachment=b'ZG9j',
                        attachment_name='autorizacion.pdf')
        return self.env['hr.salary.attachment'].create(vals)

    def _embargo(self, xmlid, **extra):
        vals = {
            'description': 'Embargo liquidación',
            'employee_ids': [(6, 0, [self.employee.id])],
            'company_id': self.company.id,
            'other_input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id,
            'monthly_amount': 500000.0, 'date_start': '2026-01-01', 'no_end_date': True,
            'l10n_co_partner_id': self.juzgado.id}
        vals.update(extra)
        return self.env['hr.salary.attachment'].create(vals)

    def test_reglas_nuevas_y_clasificacion_cargada(self):
        Rule = self.env['hr.salary.rule']
        emb = Rule.search([('code', '=', 'CO_LIQ_EMBARGO'), ('struct_id', '=', self.structure.id)])
        lib = Rule.search([('code', '=', 'CO_LIQ_LIBRANZAS'), ('struct_id', '=', self.structure.id)])
        rete = Rule.search([('code', '=', 'CO_LIQ_RETE'), ('struct_id', '=', self.structure.id)])
        neto = Rule.search([('code', '=', 'CO_LIQ_NETO'), ('struct_id', '=', self.structure.id)])
        self.assertTrue(emb and lib)
        self.assertLess(rete.sequence, emb.sequence)
        self.assertLess(emb.sequence, lib.sequence)
        self.assertLess(lib.sequence, neto.sequence)
        tr = {r.code: r.l10n_co_liq_tratamiento for r in self.structure.rule_ids}
        self.assertEqual(tr['CO_LIQ_SALARIOS'], 'salario')
        self.assertEqual(tr['CO_LIQ_VACACIONES'], 'vacaciones')
        self.assertEqual(tr['CO_LIQ_CESANTIAS'], 'prestacion')
        self.assertEqual(tr['CO_LIQ_INDEMNIZACION'], 'indemnizacion')

    def test_libranza_salario_con_tope_y_prestaciones_sin_tope(self):
        self._libranza()
        rr = self._rr(salario=3000000.0, prestacion=2000000.0)
        # salario: 50% x (3.000.000 - 240.000) = 1.380.000 ; prestaciones: 2.000.000 completas
        total = self.slip._ne_liq_libranzas_calcular(rr, 240000.0)
        self.assertAlmostEqual(total, 3380000.0, delta=0.01)

    def test_libranza_limitada_por_la_deuda(self):
        self._libranza(saldo=1000000.0)
        rr = self._rr(salario=3000000.0, prestacion=2000000.0)
        self.assertAlmostEqual(
            self.slip._ne_liq_libranzas_calcular(rr, 240000.0), 1000000.0, delta=0.01)

    def test_libranza_sin_autorizacion_no_se_descuenta(self):
        self._libranza(autoriza=False)
        self.assertFalse(self.slip._ne_liq_libranzas_aplican())

    def test_autorizacion_exige_documento(self):
        with self.assertRaises(ValidationError):
            self.env['hr.salary.attachment'].create({
                'description': 'Sin documento',
                'employee_ids': [(6, 0, [self.employee.id])],
                'company_id': self.company.id,
                'other_input_type_id': self.env.ref('l10n_co_nomina_electronica.input_l10n_co_libranza').id,
                'monthly_amount': 1.0, 'date_start': '2026-01-01', 'no_end_date': True,
                'l10n_co_partner_id': self.entidad.id, 'l10n_co_autoriza_liquidacion': True})

    def test_embargo_civil_no_toca_prestaciones_aunque_este_marcado(self):
        self._embargo('input_l10n_co_embargo_civil', l10n_co_alcanza_prestaciones=True)
        filas, disp = self.slip._ne_liq_embargos_distribuir(
            self.slip._ne_liq_montos(self._rr(salario=5000000.0, prestacion=2000000.0)), 400000.0)
        self.assertEqual(disp['prestacion'], 2000000.0)
        self.assertLessEqual(filas[0]['amount'], 500000.0)
        self.assertGreater(filas[0]['amount'], 0.0)

    def test_embargo_alimentos_con_orden_sobre_prestaciones_toma_50_por_ciento(self):
        self._embargo('input_l10n_co_embargo_alimentos', l10n_co_alcanza_prestaciones=True,
                      l10n_co_embargo_porcentaje=30.0)
        filas, disp = self.slip._ne_liq_embargos_distribuir(
            self.slip._ne_liq_montos(self._rr(prestacion=2000000.0)), 0.0)
        self.assertAlmostEqual(filas[0]['amount'], 1000000.0, delta=0.01)
        self.assertAlmostEqual(disp['prestacion'], 1000000.0, delta=0.01)

    def test_embargo_sin_marca_de_prestaciones_no_las_toca(self):
        self._embargo('input_l10n_co_embargo_alimentos', l10n_co_embargo_porcentaje=30.0)
        filas, disp = self.slip._ne_liq_embargos_distribuir(
            self.slip._ne_liq_montos(self._rr(prestacion=2000000.0)), 0.0)
        self.assertAlmostEqual(filas[0]['amount'], 0.0, delta=0.01)
        self.assertAlmostEqual(disp['prestacion'], 2000000.0, delta=0.01)

    def test_libranza_se_calcula_despues_del_embargo(self):
        self._embargo('input_l10n_co_embargo_alimentos', l10n_co_embargo_porcentaje=40.0)
        self._libranza()
        rr = self._rr(salario=4600000.0)
        # embargo alimentos 40% de 4.600.000 = 1.840.000 (tope 50%); cupo libranza
        # = 50% x 4.600.000 - 1.840.000 = 460.000
        self.assertAlmostEqual(self.slip._ne_liq_embargos_calcular(rr, 0.0), 1840000.0, delta=1.0)
        self.assertAlmostEqual(self.slip._ne_liq_libranzas_calcular(rr, 0.0), 460000.0, delta=1.0)

    def test_confirmar_cierra_la_libranza_con_nota_y_revertir_la_reabre(self):
        att = self._libranza(saldo=5000000.0)
        rr = self._rr(salario=3000000.0, prestacion=2000000.0)
        self.slip._ne_liq_libranzas_calcular(rr, 240000.0)  # 3.380.000
        self.slip._ne_aplicar_libranzas()
        self.assertEqual(att.state, 'close')
        self.assertAlmostEqual(att.l10n_co_saldo_pendiente, 5000000.0 - 3380000.0, delta=0.01)
        self.assertTrue(any('saldo no cubierto' in (m.body or '') for m in att.message_ids))
        self.slip._ne_aplicar_libranzas(revertir=True)
        self.assertEqual(att.state, 'open')
        self.assertAlmostEqual(att.l10n_co_saldo_pendiente, 5000000.0, delta=0.01)
