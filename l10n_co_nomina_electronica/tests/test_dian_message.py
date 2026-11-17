# -*- coding: utf-8 -*-
"""Motivo del envio a la DIAN (doc 53 §16.5): funciones puras con respuestas REALES de staging como fixtures."""

from odoo.tests.common import BaseCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_message as dm


@tagged('post_install', '-at_install')
class TestDianMessage(BaseCase):

    def test_aceptado_00(self):
        mj = dm.build_message_json({
            'StatusCode': '00', 'IsValid': 'true', 'StatusDescription': 'Procesado Correctamente.',
            'StatusMessage': 'La Nomima Individual De Ajustes NA-22, ha sido autorizada.', 'ErrorMessages': []})
        self.assertTrue(mj['is_valid'])
        self.assertFalse(mj['transport'])
        html = dm.render_message_html(mj)
        self.assertIn('Procesado Correctamente.', html)
        self.assertIn('ha sido autorizada.', html)
        self.assertNotIn('<ul>', html)

    def test_rechazado_99_con_regla_y_causa(self):
        error = 'Regla: NIAE191a, Rechazo: Documento a Reemplazar no se encuentra recibido en la Base de Datos.'
        mj = dm.build_message_json({
            'StatusCode': '99', 'IsValid': 'false', 'ErrorMessages': [error],
            'StatusDescription': 'Validación contiene errores en campos mandatorios.',
            'StatusMessage': 'Documento con errores en campos mandatorios.'})
        self.assertFalse(mj['is_valid'])
        self.assertEqual(mj['errors'], [error])
        html = dm.render_message_html(mj)
        self.assertIn('<li>Regla: NIAE191a, Rechazo:', html)
        self.assertIn('Documento con errores en campos mandatorios.', html)

    def test_en_proceso_pide_consultar_de_nuevo(self):
        mj = dm.build_message_json({'IsValid': 'false', 'StatusCode': '', 'StatusDescription': 'Batch en proceso de validación.'})
        html = dm.render_message_html(mj)
        self.assertIn('Batch en proceso de validación.', html)
        self.assertIn('Consulte de nuevo en unos minutos.', html)

    def test_error_de_transporte_y_fault(self):
        mj = dm.build_message_json({'StatusCode': 'CONNECTION_ERROR', 'ErrorMessage': 'timeout'})
        self.assertEqual(mj['transport'], 'CONNECTION_ERROR')
        self.assertEqual(dm.render_message_html(mj), '<p>El servidor de la DIAN no respondió: CONNECTION_ERROR timeout</p>')
        mj = dm.build_message_json({'SOAPFault': True, 'FaultDetails': ['Sender', 'boom']})
        self.assertEqual(mj['fault'], ['Sender', 'boom'])
        self.assertIn('Error del servicio de la DIAN: Sender boom', dm.render_message_html(mj))
        mj = dm.build_message_json({'HttpStatus': 503})
        self.assertEqual(mj['transport'], 'HTTP 503')

    def test_html_se_escapa(self):
        mj = dm.build_message_json({'StatusCode': '99', 'ErrorMessages': ['<script>alert(1)</script>'], 'StatusDescription': 'a&b'})
        html = dm.render_message_html(mj)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertIn('a&amp;b', html)

    def test_vacio(self):
        self.assertEqual(dm.render_message_html(dm.build_message_json(None)), '<p>Consulte de nuevo en unos minutos.</p>')
