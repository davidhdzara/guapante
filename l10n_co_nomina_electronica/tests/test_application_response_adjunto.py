# -*- coding: utf-8 -*-
"""E-1 (doc 59 §18.11-18.12): ciclo por RECIBO (habilitacion): el ApplicationResponse decodificado de un envio o consulta queda como
adjunto `.xml` del recibo; sin ApplicationResponse no se crea nada; un intercambio de varios recibos no adjunta."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture

XML = '<ApplicationResponse><cbc:Note>Regla NIE044</cbc:Note></ApplicationResponse>'


@tagged('post_install', '-at_install')
class TestApplicationResponseAdjunto(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Application Response')

    def _recibo(self):
        return self._documento(date(2024, 3, 1)).payslip_ids[:1]

    def test_un_recibo_adjunta_el_application_response_decodificado(self):
        recibo = self._recibo()
        adjunto = recibo._ne_guardar_application_response({'ApplicationResponse': XML}, self.env['l10n.co.ne.exchange'])
        self.assertEqual(adjunto.raw.decode('utf-8'), XML)
        self.assertEqual((adjunto.res_model, adjunto.res_id), ('hr.payslip', recibo.id))
        self.assertTrue(adjunto.name.startswith('ApplicationResponse_') and adjunto.name.endswith('.xml'))

    def test_sin_application_response_no_crea_nada(self):
        recibo = self._recibo()
        self.assertFalse(recibo._ne_guardar_application_response({'StatusCode': '00'}, self.env['l10n.co.ne.exchange']))

    def test_un_intercambio_de_varios_recibos_no_adjunta(self):
        recibos = self._documento(date(2024, 3, 1)).payslip_ids
        self.assertGreater(len(recibos), 1)
        self.assertFalse(recibos._ne_guardar_application_response({'ApplicationResponse': XML},
                                                                   self.env['l10n.co.ne.exchange']))

    def test_el_resultado_de_la_lista_de_respuestas_tambien_cuenta(self):
        recibo = self._recibo()
        adjunto = recibo._ne_guardar_application_response(
            {'DianResponses': [{'ApplicationResponse': XML}]}, self.env['l10n.co.ne.exchange'])
        self.assertTrue(adjunto)
