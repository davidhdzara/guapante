# -*- coding: utf-8 -*-
"""CC-08 (.332): con la fecha de pago desde «Pagos de Contabilidad», un recibo de neto 0 no tiene pago que conciliar y quedaba fuera del documento
mensual. Su fecha se registra a mano con «Registrar fecha de pago»; nunca se asigna sola."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFechaPagoNetoCero(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compania = cls.env['res.company'].create({
            'name': 'Compañía Neto Cero', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_tipo_aportante': '1',
            'l10n_co_pila_forma_presentacion': 'U', 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_fuente_fecha_pago': 'contabilidad'})
        tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Tipo Neto Cero', 'country_id': cls.env.ref('base.co').id})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Neto Cero', 'company_id': cls.compania.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato Neto Cero', 'employee_id': cls.empleado.id, 'company_id': cls.compania.id, 'structure_type_id': tipo.id,
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, neto=0.0):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Neto Cero', 'employee_id': self.empleado.id, 'contract_id': self.contrato.id, 'company_id': self.compania.id,
            'struct_id': self.estructura.id, 'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 15)})
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_NETO'), ('struct_id', '=', self.estructura.id)], limit=1)
        self.env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': 'CO_NETO', 'name': regla.name, 'contract_id': self.contrato.id,
            'employee_id': self.empleado.id, 'quantity': 1.0, 'rate': 100.0, 'amount': neto, 'total': neto})
        recibo.state = 'done'
        return recibo

    def _registrar(self, recibo, fecha=date(2026, 3, 16)):
        return self.env['hr.payslip.registrar.pago'].create({'payslip_ids': [(6, 0, recibo.ids)], 'fecha': fecha}).action_registrar_pago()

    def _del_mes(self, mes):
        return self.env['l10n.co.ne.documento']._ne_recibos_del_mes(self.compania, self.empleado, date(2026, mes, 1))

    def test_sin_registrarla_no_hay_fecha_ni_con_el_boton_nativo_de_pagado(self):
        recibo = self._recibo()
        with self.assertRaisesRegex(UserError, 'neto 0'):
            recibo._ne_fechas_pago()
        recibo.action_payslip_paid()                        # el nativo pone ``paid_date`` = hoy: no cuenta como fecha elegida
        self.assertTrue(recibo.paid_date)
        self.assertFalse(recibo.l10n_co_ne_fecha_pago_registrada)
        with self.assertRaisesRegex(UserError, 'Registrar fecha de pago'):
            recibo._ne_fechas_pago()
        self.assertFalse(recibo._ne_fecha_pago_o_falso())

    def test_registrada_entra_al_documento_de_ese_mes(self):
        recibo = self._recibo()
        self.assertNotIn(recibo, self._del_mes(3))
        self._registrar(recibo)
        self.assertEqual(recibo.state, 'paid')
        self.assertEqual((recibo.paid_date, recibo.l10n_co_ne_fecha_pago_registrada), (date(2026, 3, 16), date(2026, 3, 16)))
        self.assertEqual(recibo._ne_fechas_pago(), [date(2026, 3, 16)])
        self.assertIn(recibo, self._del_mes(3))
        self.assertNotIn(recibo, self._del_mes(4))

    def test_ya_marcado_pagado_se_registra_una_sola_vez(self):
        recibo = self._recibo()
        recibo.action_payslip_paid()
        self._registrar(recibo)
        self.assertEqual(recibo._ne_fechas_pago(), [date(2026, 3, 16)])
        with self.assertRaisesRegex(UserError, 'estado "Hecho"'):
            self._registrar(recibo, date(2026, 3, 20))

    def test_con_neto_mayor_que_cero_la_fecha_sigue_saliendo_de_contabilidad(self):
        recibo = self._recibo(neto=1000000.0)
        with self.assertRaisesRegex(UserError, 'no sale del recibo'):
            self._registrar(recibo)
        with self.assertRaisesRegex(UserError, 'no tiene pagos conciliados'):
            recibo._ne_fechas_pago()
        self.assertEqual(recibo.state, 'done')

    def test_desmarcar_el_pago_borra_la_fecha_registrada(self):
        """.334: tras «Unpaid» el recibo sigue Hecho y no puede entrar al documento mensual con la fecha del pago anulado."""
        recibo = self._recibo()
        self._registrar(recibo)
        self.assertIn(recibo, self._del_mes(3), 'Premisa')
        recibo.action_payslip_unpaid()
        self.assertEqual((recibo.state, recibo.l10n_co_ne_fecha_pago_registrada), ('done', False))
        self.assertNotIn(recibo, self._del_mes(3))

    def test_volver_a_borrador_borra_la_fecha_registrada(self):
        recibo = self._recibo()
        self._registrar(recibo)
        recibo.state = 'cancel'
        recibo.action_payslip_draft()
        self.assertFalse(recibo.l10n_co_ne_fecha_pago_registrada)
