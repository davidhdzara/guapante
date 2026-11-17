# -*- coding: utf-8 -*-
"""E-5 (doc 59 §22): «Marcar como pagado» del lote no fija la fecha de pago = hoy sin preguntar. Con la fuente «Fecha de pago del recibo» el
boton abre el asistente «Registrar fecha de pago» con los recibos del lote; al confirmar queda la fecha elegida y el lote «pagado». Con la
fuente «contabilidad» o una compania no colombiana se conserva el comportamiento nativo (hoy)."""

from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestMarcarLotePagado(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Marcar Lote Pagado')

    def _lote(self):
        """Lote cerrado con los recibos del fixture en estado Hecho y sin fecha de pago."""
        recibos = self._documento(date(2024, 3, 1)).payslip_ids
        recibos.write({'state': 'done', 'paid_date': False})
        lote = self.env['hr.payslip.run'].create({'name': 'Lote E-5 %s' % self.n, 'state': 'close'})
        recibos.write({'payslip_run_id': lote.id})
        return lote

    def _asistente(self, lote, fecha):
        return self.env['hr.payslip.registrar.pago'].with_context(
            active_model='hr.payslip', active_ids=lote.slip_ids.ids, ne_payslip_run_ids=lote.ids).create({'fecha': fecha})

    def test_el_boton_del_lote_con_fuente_recibo_abre_el_asistente_y_no_marca_nada(self):
        lote = self._lote()
        accion = lote.action_paid()
        self.assertEqual(accion['res_model'], 'hr.payslip.registrar.pago')
        self.assertEqual(accion['target'], 'new')
        self.assertEqual(sorted(accion['context']['active_ids']), sorted(lote.slip_ids.ids))
        self.assertEqual(accion['context']['ne_payslip_run_ids'], lote.ids)
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'done'})        # nada se marco
        self.assertEqual(lote.state, 'close')
        self.assertFalse(lote.slip_ids.filtered('paid_date'))

    def test_confirmar_el_asistente_deja_la_fecha_elegida_y_el_lote_pagado(self):
        lote = self._lote()
        self._asistente(lote, date(2026, 3, 31)).action_registrar_pago()
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'paid'})
        self.assertEqual(set(lote.slip_ids.mapped('paid_date')), {date(2026, 3, 31)})     # no la de hoy
        self.assertEqual(lote.state, 'paid')

    def test_una_fecha_futura_se_rechaza(self):
        lote = self._lote()
        manana = fields.Date.context_today(lote) + timedelta(days=1)
        with self.assertRaises(UserError):
            self._asistente(lote, manana).action_registrar_pago()
        self.assertEqual(lote.state, 'close')

    def test_con_fuente_contabilidad_se_conserva_el_comportamiento_nativo(self):
        lote = self._lote()
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        self.assertIsNot(type(lote.action_paid()), dict)        # sin asistente: el nativo marca y devuelve None/True
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'paid'})
        self.assertEqual(set(lote.slip_ids.mapped('paid_date')), {fields.Date.context_today(lote)})
        self.assertEqual(lote.state, 'paid')

    def test_una_compania_no_colombiana_conserva_el_comportamiento_nativo(self):
        lote = self._lote()
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            self.assertIsNot(type(lote.action_paid()), dict)
        self.assertEqual(lote.state, 'paid')

    def test_el_asistente_avisa_que_la_fecha_decide_el_mes_del_documento(self):
        vista = self.env.ref('l10n_co_nomina_electronica.hr_payslip_registrar_pago_view_form')
        self.assertIn('mes del documento', vista.arch_db)
