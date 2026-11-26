# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
""".328 (pedido de David, 26-nov): (1) la liquidación paga el auxilio de transporte de los días que ningún recibo de nómina haya pagado (QA c327_b: faltaban 41.515,83); (2) prima, cesantías, intereses
y vacaciones compensadas se pueden ajustar a mano y el valor ajustado llega al neto, al XML, al asiento y a lo que depende de él.

SMMLV 2026 1.750.905 y auxilio 249.095 (mes de 30 días). Los esperados se calculan a mano."""

from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase, tagged

SMMLV = 1750905.0
AUXILIO = 249095.0
INGRESO = date(2025, 1, 1)
PREFIJO = 'l10n_co_nomina_electronica.'
AJUSTABLES = (('CO_PRIMA_VALOR', 'prima'), ('CO_LIQ_PRIMA', 'liquidacion'), ('CO_LIQ_CESANTIAS', 'liquidacion'), ('CO_LIQ_INT_CES', 'liquidacion'), ('CO_LIQ_VACACIONES', 'liquidacion'))


@tagged('post_install', '-at_install')
class TestLiquidacionAuxYPrestacionesAjustables(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Auxilio y Ajustes'})
        cls.env = cls.company.with_company(cls.company).env
        cls.env.user.groups_id = [Command.link(cls.env.ref('hr_payroll.group_hr_payroll_manager').id)]
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Auxilio y Ajustes', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_nomina')
        cls.liquidacion = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_liquidacion')
        cls.prima = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_prima')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _contrato(self, **extra):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Auxilio %s' % self.n, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        return self.env['hr.contract'].create(dict({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Auxilio %s' % self.n, 'employee_id': empleado.id,
            'company_id': self.company.id, 'structure_type_id': self.tipo.id, 'wage': SMMLV, 'date_start': INGRESO, 'state': 'open'}, **extra))

    def _recibo(self, contrato, desde, hasta, estructura=None):
        type(self).n += 1
        return self.env['hr.payslip'].create({
            'name': 'Recibo Auxilio %s' % self.n, 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})

    def _liq(self, contrato, retiro=date(2026, 5, 20), quincena=False):
        if quincena:
            self._recibo(contrato, date(2026, 5, 1), date(2026, 5, 15)).write({'state': 'done'})
        recibo = self._recibo(contrato, contrato.date_start, retiro, estructura=self.liquidacion)
        recibo.compute_sheet()
        return recibo

    def _lineas(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _total(self, recibo, codigo):
        return sum(self._lineas(recibo, codigo).mapped('total'))

    def _regla(self, codigo, estructura=None):
        regla = self.env['hr.salary.rule'].search([('code', '=', codigo), ('struct_id', '=', (estructura or self.liquidacion).id)])
        self.assertEqual(len(regla), 1, codigo)
        return regla

    def _ajustar(self, recibo, codigo, cantidad, importe):
        self.env['l10n.co.payslip.ajuste'].create({
            'slip_id': recibo.id, 'salary_rule_id': self._regla(codigo, recibo.struct_id).id, 'quantity': cantidad, 'rate': 100.0, 'amount': importe})
        recibo.compute_sheet()

    # ── (1) auxilio de transporte en la liquidación ──────────────────
    def test_paga_el_auxilio_de_los_dias_pendientes_sin_repetir_lo_pagado(self):
        recibo = self._liq(self._contrato(), quincena=True)
        linea = self._lineas(recibo, 'CO_AUX_TRANS')
        self.assertEqual(len(linea), 1)
        self.assertEqual(linea.quantity, 5)
        self.assertAlmostEqual(linea.total, 41515.83, delta=0.01)

    def test_sin_recibos_del_mes_paga_el_auxilio_de_todos_los_dias(self):
        recibo = self._liq(self._contrato())
        self.assertEqual(self._lineas(recibo, 'CO_AUX_TRANS').quantity, 20)
        self.assertAlmostEqual(self._total(recibo, 'CO_AUX_TRANS'), AUXILIO * 20 / 30, delta=0.01)

    def test_sin_dias_pendientes_o_sobre_el_tope_no_hay_linea(self):
        self.assertFalse(self._lineas(self._liq(self._contrato(), retiro=date(2026, 5, 15), quincena=True), 'CO_AUX_TRANS'))
        self.assertFalse(self._lineas(self._liq(self._contrato(wage=4000000.0)), 'CO_AUX_TRANS'))

    def test_llega_al_neto_y_al_xml_y_no_cambia_las_bases_ni_la_retencion(self):
        """Origen no salarial «por naturaleza»: la regla del 40 % no lo toma (``_ne_ibc_pactados`` no lanza) y las bases que leen salud, pensión, ARL, parafiscales y PILA no cambian."""
        regla = self._regla('CO_AUX_TRANS')
        self.assertEqual((regla.l10n_co_pila_origen_no_salarial, regla.l10n_co_liq_tratamiento, regla.l10n_co_ne_ajustable), ('naturaleza', 'salario', False))
        recibo = self._liq(self._contrato(), quincena=True)
        auxilio = self._total(recibo, 'CO_AUX_TRANS')
        devengados, _deducciones = recibo._map_salary_rules_to_xml()
        self.assertEqual(devengados['Transporte']['AuxilioTransporte'], '41515.83')

        def bases(r):
            return {l.code: l.total for l in r.line_ids if l.code.startswith(('CO_IBC', 'CO_DIAS')) or l.code in ('CO_LIQ_SALUD', 'CO_LIQ_PENSION', 'CO_LIQ_RETE')}

        con, neto = bases(recibo), self._total(recibo, 'CO_LIQ_NETO')
        self.assertEqual(con['CO_IBC_PACTADOS'], 0.0)
        regla.active = False
        recibo.compute_sheet()
        self.assertEqual(bases(recibo), con)
        self.assertAlmostEqual(neto - self._total(recibo, 'CO_LIQ_NETO'), auxilio, delta=0.01)

    # ── (2) prestaciones ajustables ──────────────────────────────────
    def test_las_cinco_reglas_son_ajustables_y_sus_recibos_usan_conceptos_sin_perder_la_pestana_nativa(self):
        for codigo, estructura in AJUSTABLES:
            self.assertTrue(self._regla(codigo, getattr(self, estructura)).l10n_co_ne_ajustable, codigo)
        for codigo in ('CO_LIQ_SALARIOS', 'CO_LIQ_INDEMNIZACION', 'CO_LIQ_RETE', 'CO_LIQ_SALUD'):
            self.assertFalse(self._regla(codigo).l10n_co_ne_ajustable, codigo)
        recibo = self._liq(self._contrato(wage=3000000.0))
        self.assertTrue(recibo.l10n_co_ne_usa_conceptos)
        self.assertFalse(recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'dias'))
        self.assertFalse(recibo.l10n_co_ne_oculta_pagina_novedades)
        fila = recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id.code == 'CO_LIQ_CESANTIAS')
        self.assertTrue(fila.edita_importe and fila.edita_cantidad)
        self.assertTrue(self._recibo(self._contrato(), date(2026, 5, 1), date(2026, 5, 31)).l10n_co_ne_oculta_pagina_novedades)

    def test_ajustar_las_cesantias_arrastra_intereses_retencion_neto_y_xml(self):
        recibo = self._liq(self._contrato(wage=3000000.0))
        antes = {c: self._total(recibo, c) for c in ('CO_LIQ_CESANTIAS', 'CO_LIQ_INT_CES', 'CO_LIQ_RETE', 'CO_LIQ_NETO')}
        self.assertGreater(antes['CO_LIQ_CESANTIAS'], 0.0)
        self._ajustar(recibo, 'CO_LIQ_CESANTIAS', 1.0, 1000000.0)
        despues = {c: self._total(recibo, c) for c in antes}
        self.assertAlmostEqual(despues['CO_LIQ_CESANTIAS'], 1000000.0, delta=0.01)
        self.assertAlmostEqual(despues['CO_LIQ_INT_CES'], antes['CO_LIQ_INT_CES'] * 1000000.0 / antes['CO_LIQ_CESANTIAS'], delta=0.05)
        self.assertAlmostEqual(despues['CO_LIQ_NETO'] - antes['CO_LIQ_NETO'], sum(despues[c] - antes[c] for c in ('CO_LIQ_CESANTIAS', 'CO_LIQ_INT_CES', 'CO_LIQ_RETE')), delta=0.02)
        devengados, _deducciones = recibo._map_salary_rules_to_xml()
        self.assertEqual(devengados['Cesantias']['Pago'], '1000000.00')
        self.assertEqual(devengados['Cesantias']['PagoIntereses'], '%.2f' % despues['CO_LIQ_INT_CES'])

    def test_ajustar_prima_y_vacaciones_compensadas_llega_al_neto_al_xml_y_al_asiento(self):
        recibo = self._liq(self._contrato(wage=3000000.0))
        cuentas = {}
        for numero, codigo in enumerate(('CO_LIQ_PRIMA', 'CO_LIQ_VACACIONES')):
            cuentas[codigo] = self.env['account.account'].create({
                'code': '51059%s' % numero, 'name': 'Gasto %s' % codigo, 'account_type': 'expense', 'company_ids': [(6, 0, [self.company.id])]})
            self._regla(codigo).with_company(self.company).write({'account_debit': cuentas[codigo].id})
        antes = {c: self._total(recibo, c) for c in ('CO_LIQ_PRIMA', 'CO_LIQ_VACACIONES', 'CO_LIQ_RETE', 'CO_LIQ_NETO')}
        self._ajustar(recibo, 'CO_LIQ_PRIMA', 10.0, 50000.0)
        self._ajustar(recibo, 'CO_LIQ_VACACIONES', 3.0, 100000.0)
        despues = {c: self._total(recibo, c) for c in antes}
        self.assertAlmostEqual(despues['CO_LIQ_PRIMA'], 500000.0, delta=0.01)
        self.assertAlmostEqual(despues['CO_LIQ_VACACIONES'], 300000.0, delta=0.01)
        self.assertAlmostEqual(despues['CO_LIQ_NETO'] - antes['CO_LIQ_NETO'], sum(despues[c] - antes[c] for c in ('CO_LIQ_PRIMA', 'CO_LIQ_VACACIONES', 'CO_LIQ_RETE')), delta=0.02)
        devengados, _deducciones = recibo._map_salary_rules_to_xml()
        self.assertEqual((devengados['Primas']['Cantidad'], devengados['Primas']['Pago']), ('10', '500000.00'))
        self.assertEqual(devengados['Vacaciones']['VacacionesCompensadas'], [{'Cantidad': '3', 'Pago': '300000.00'}])
        asiento = recibo._prepare_slip_lines(recibo.date_to, [])
        for codigo, cuenta in cuentas.items():
            self.assertAlmostEqual(sum(e['debit'] - e['credit'] for e in asiento if e['account_id'] == cuenta.id), despues[codigo], delta=0.01, msg=codigo)

    def test_ajustar_la_prima_semestral_llega_al_neto_y_al_xml(self):
        recibo = self._recibo(self._contrato(wage=3000000.0), date(2026, 1, 1), date(2026, 6, 30), estructura=self.prima)
        recibo.compute_sheet()
        self._ajustar(recibo, 'CO_PRIMA_VALOR', 1.0, 500000.0)
        self.assertAlmostEqual(self._total(recibo, 'CO_PRIMA_VALOR'), 500000.0, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_PRIMA_NETO'), 500000.0 + self._total(recibo, 'CO_PRIMA_RETE'), delta=0.01)
        devengados, _deducciones = recibo._map_salary_rules_to_xml()
        self.assertEqual(devengados['Primas']['Pago'], '500000.00')

    # ── (b) las novedades de la liquidación se siguen registrando ────
    def test_la_indemnizacion_se_registra_desde_el_asistente_y_se_cambia_en_el_recibo(self):
        contrato = self._contrato(wage=3000000.0, l10n_co_ne_contract_type='1', date_end=date(2026, 5, 20))
        accion = self.env['l10n.co.hr.liquidacion.wizard'].create({
            'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'date_end': date(2026, 5, 20), 'cause': 'sin_justa_causa',
            'dias_restantes_contrato': 60}).action_create_liquidacion()
        recibo = self.env['hr.payslip'].browse(accion['res_id'])
        recibo.compute_sheet()
        novedad = recibo.input_line_ids.filtered(lambda i: i.code == 'CO_LIQ_INDEMNIZ')
        self.assertEqual(novedad.amount, 60)
        self.assertAlmostEqual(self._total(recibo, 'CO_LIQ_INDEMNIZACION'), 6000000.0, delta=0.01)
        self.assertTrue(recibo.l10n_co_concepto_ids)
        self.assertFalse(recibo.l10n_co_ne_oculta_pagina_novedades)
        recibo.write({'input_line_ids': [Command.update(novedad.id, {'amount': 30})]})          # la pestaña nativa del recibo
        recibo.compute_sheet()
        self.assertAlmostEqual(self._total(recibo, 'CO_LIQ_INDEMNIZACION'), 3000000.0, delta=0.01)

    def test_una_liquidacion_creada_a_mano_admite_novedades_nuevas(self):
        recibo = self._liq(self._contrato(wage=3000000.0, l10n_co_ne_contract_type='1', date_end=date(2026, 5, 20)))
        recibo.l10n_co_ne_liquidacion_cause = 'sin_justa_causa'
        recibo.write({'input_line_ids': [Command.create({'input_type_id': self.env.ref(PREFIJO + 'input_co_liq_indemniz').id, 'amount': 60})]})
        recibo.compute_sheet()
        self.assertAlmostEqual(self._total(recibo, 'CO_LIQ_INDEMNIZACION'), 6000000.0, delta=0.01)
