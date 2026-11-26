# -*- coding: utf-8 -*-
"""M1-2 (doc 61 §10): consolidado mensual de IBC con calendarios de pago que no son mensuales.

* SEMANAL (David, 2026-11-14): se PAGAN todos los dias (5 pagos de 7 = 35) pero PILA siempre tiene 30 dias comerciales: el
  IBC del mes = valor del dia x 30, dias cotizados 30, con piso de 1 SMMLV y techo de 25 SMMLV. El texto normativo lo
  aporta David (NO VERIFICADO). 5/20 y quincenal ya suman 30. Cotizante tipo 51 (Decreto 2616/2013): limitacion
  documentada, no implementada.
* BI-WEEKLY = quincena (David): dias comerciales; solo ``weekly`` cuenta dias calendario.
* ``DiasTrabajados`` del documento DIAN NO se topa a 30 (Anexo V1.0 NIE069, dias laborados reales)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import documento_merge as dm

from .test_documento_merge import PERIODO, _recibo as _datos_recibo


@tagged('post_install', '-at_install')
class TestPeriodosIbcSemanal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía IBC Semanal'})
        cls.env = cls.company.with_company(cls.company).env
        cls.tipos = {
            clave: cls.env['hr.payroll.structure.type'].create({
                'name': 'Tipo IBC %s' % clave, 'country_id': cls.env.ref('base.co').id,
                'default_schedule_pay': clave})
            for clave in ('weekly', 'bi-weekly', 'semi-monthly')}
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.n = 0

    def _empleado(self, periodicidad, wage=3000000.0):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado IBC %s %s' % (periodicidad, self.n), 'company_id': self.company.id,
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato IBC %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.tipos[periodicidad].id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return empleado, contrato

    def _recibo(self, empleado, contrato, ini, fin):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo IBC %s' % fin, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': self.estructura.id, 'date_from': ini, 'date_to': fin})
        recibo.compute_sheet()
        return recibo

    def _consolidado(self, empleado, recibos, mes):
        for recibo in recibos:
            recibo.state = 'done'
        recibos[0]._ne_refrescar_ibc_mensual()
        return self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', empleado.id), ('period', '=', mes)])

    def _semanas_de_mayo(self, empleado, contrato):
        """5 viernes de mayo de 2026 (1, 8, 15, 22 y 29): la primera semana empieza el 25-abr y cruza de mes."""
        return [self._recibo(empleado, contrato, ini, fin) for ini, fin in (
            (date(2026, 4, 25), date(2026, 5, 1)), (date(2026, 5, 2), date(2026, 5, 8)),
            (date(2026, 5, 9), date(2026, 5, 15)), (date(2026, 5, 16), date(2026, 5, 22)),
            (date(2026, 5, 23), date(2026, 5, 29)))]

    # ── semanal ──────────────────────────────────────────────────────
    def test_semanal_con_5_pagos_se_pagan_35_dias_y_el_ibc_es_30_dias(self):
        empleado, contrato = self._empleado('weekly')
        recibos = self._semanas_de_mayo(empleado, contrato)
        for recibo in recibos:
            self.assertEqual(recibo._ne_dias_pagables(), 7)
        cons = self._consolidado(empleado, recibos, date(2026, 5, 1))
        self.assertEqual(cons.dias_sp, 30)
        self.assertAlmostEqual(cons.ibc_sp, 3000000.0, delta=1.0)      # valor del dia (100.000) x 30, no 35 dias

    def test_semanal_con_4_pagos_cotiza_28_dias_sin_escalar(self):
        empleado, contrato = self._empleado('weekly')
        recibos = [self._recibo(empleado, contrato, ini, fin) for ini, fin in (
            (date(2026, 2, 28), date(2026, 3, 6)), (date(2026, 3, 7), date(2026, 3, 13)),
            (date(2026, 3, 14), date(2026, 3, 20)), (date(2026, 3, 21), date(2026, 3, 27)))]
        cons = self._consolidado(empleado, recibos, date(2026, 3, 1))
        self.assertEqual(cons.dias_sp, 28)
        self.assertAlmostEqual(cons.ibc_sp, 2800000.0, delta=1.0)

    def test_semanal_con_5_pagos_respeta_el_techo_de_25_smmlv(self):
        empleado, contrato = self._empleado('weekly', wage=80000000.0)
        recibos = self._semanas_de_mayo(empleado, contrato)
        cons = self._consolidado(empleado, recibos, date(2026, 5, 1))
        smmlv = recibos[0]._rule_parameter('l10n_co_smmlv', recibos[0].date_from)
        self.assertEqual(cons.dias_sp, 30)
        self.assertAlmostEqual(cons.ibc_sp, 25 * smmlv, delta=1.0)

    # ── pagos los 5 y 20: 30/30 sin escalar ──────────────────────────
    def test_5_y_20_cotiza_30_dias_y_el_ibc_de_un_mes_completo(self):
        empleado, contrato = self._empleado('semi-monthly')
        recibos = [self._recibo(empleado, contrato, ini, fin) for ini, fin in (
            (date(2026, 2, 21), date(2026, 3, 5)), (date(2026, 3, 6), date(2026, 3, 20)))]
        cons = self._consolidado(empleado, recibos, date(2026, 3, 1))
        self.assertEqual(cons.dias_sp, 30)
        self.assertAlmostEqual(cons.ibc_sp, 3000000.0, delta=1.0)

    # ── bi-weekly = quincena ─────────────────────────────────────────
    def test_bi_weekly_y_semi_monthly_no_son_semanales(self):
        for clave in ('bi-weekly', 'semi-monthly'):
            empleado, contrato = self._empleado(clave)
            recibo = self._recibo(empleado, contrato, date(2026, 3, 16), date(2026, 3, 31))
            self.assertFalse(recibo._ne_es_semanal(), clave)
            self.assertEqual(recibo._ne_dias_pagables(), 15, clave)      # quincena: dias comerciales, no 16 calendario
        empleado, contrato = self._empleado('weekly')
        self.assertTrue(self._recibo(empleado, contrato, date(2026, 3, 2), date(2026, 3, 8))._ne_es_semanal())

    # ── documento DIAN: DiasTrabajados sin tope ──────────────────────
    def test_documento_mensual_suma_los_dias_reales_sin_topar_a_30(self):
        recibos = [_datos_recibo(dias='7', sueldo='700000.00') for _i in range(5)]
        doc = dm.fusionar_documento(
            recibos, fechas_pagos=['2026-05-01', '2026-05-08', '2026-05-15', '2026-05-22', '2026-05-29'], periodo=PERIODO)
        self.assertEqual(doc['devengados']['Basico'], {'DiasTrabajados': '35', 'SueldoTrabajado': '3500000.00'})
