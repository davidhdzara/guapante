# -*- coding: utf-8 -*-
"""Clase A (.335; consultor v19, registro §75): con la fuente «Fecha de pago del recibo», anular el pago («Unpaid») o volver a borrador no puede dejar la fecha de pago, porque el documento de nómina electrónica
toma los recibos confirmados por esa fecha y reportaría a la DIAN un pago anulado."""

from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestPagoAnulado(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Pago Anulado')

    def _recibos(self):
        """Las dos quincenas de marzo, pagadas y con su fecha."""
        recibos = self._documento(date(2024, 3, 1)).payslip_ids.sorted('date_to')
        self.assertEqual(self._del_mes(recibos), recibos, 'Premisa: las dos entran al mes')
        return recibos

    def _del_mes(self, recibos):
        return self.env['l10n.co.ne.documento']._ne_recibos_del_mes(self.company, recibos.employee_id, date(2026, 3, 1)).sorted('date_to')

    def test_unpaid_borra_la_fecha_y_el_recibo_sale_del_mes(self):
        primero, segundo = self._recibos()
        segundo.action_payslip_unpaid()
        self.assertEqual((segundo.state, segundo.paid_date), ('done', False))
        self.assertEqual(self._del_mes(primero | segundo), primero)

    def test_volver_a_borrador_el_recibo_borra_la_fecha_y_al_confirmar_no_entra(self):
        primero, segundo = self._recibos()
        segundo.state = 'cancel'
        segundo.action_payslip_draft()
        self.assertFalse(segundo.paid_date)
        segundo.state = 'done'
        self.assertEqual(self._del_mes(primero | segundo), primero)

    def test_volver_a_borrador_el_lote_borra_la_fecha(self):
        recibos = self._recibos()
        recibos.write({'state': 'done'})          # confirmados que conservan su fecha (asi los dejaba «Unpaid»)
        lote = self.env['hr.payslip.run'].create({'name': 'Lote pago anulado %s' % self.n, 'state': 'close', 'company_id': self.company.id})
        recibos.write({'payslip_run_id': lote.id})
        lote.action_draft()
        self.assertEqual((set(recibos.mapped('state')), recibos.mapped('paid_date')), ({'draft'}, [False, False]))
        recibos.write({'state': 'done'})
        self.assertFalse(self._del_mes(recibos))

    def test_con_pagos_de_contabilidad_la_fecha_del_recibo_no_se_toca(self):
        _primero, segundo = self._recibos()
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        fecha = segundo.paid_date
        segundo.action_payslip_unpaid()
        self.assertEqual(segundo.paid_date, fecha)

    def test_una_compania_no_colombiana_conserva_el_nativo(self):
        _primero, segundo = self._recibos()
        fecha = segundo.paid_date
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            segundo.action_payslip_unpaid()
        self.assertEqual(segundo.paid_date, fecha)
