# -*- coding: utf-8 -*-
"""E-1, pieza ``.xml``: la solicitud y la respuesta SOAP de un intercambio DIAN se descargan con nombre ``.xml`` (antes el
nombre era el ``zip_key`` a secas: sin extension, igual para los dos archivos y vacio en una consulta por CUNE)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestExchangeNombreDescarga(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Nombre Descarga Intercambio')

    def _intercambio(self, operacion='send_sync', respuesta=None, **extra):
        recibo = self._documento(date(2024, 3, 1)).payslip_ids[:1]
        return self.env['l10n.co.ne.exchange'].create_exchange(
            self.company, operacion, 'https://dian.test/ws',
            dict({'RawRequest': b'<soap:Envelope/>', 'RawResponse': b'<soap:Envelope/>'}, **(respuesta or {})),
            recibo, **extra)

    def test_un_envio_se_descarga_con_el_zip_key_y_extension_xml(self):
        intercambio = self._intercambio(respuesta={'ZipKey': 'zip-123'})
        self.assertEqual(intercambio.request_filename, 'zip-123_solicitud.xml')
        self.assertEqual(intercambio.response_filename, 'zip-123_respuesta.xml')

    def test_solicitud_y_respuesta_no_se_descargan_con_el_mismo_nombre(self):
        intercambio = self._intercambio(respuesta={'ZipKey': 'zip-123'})
        self.assertNotEqual(intercambio.request_filename, intercambio.response_filename)

    def test_una_consulta_por_zip_key_usa_el_zip_key_consultado(self):
        intercambio = self._intercambio('get_status_zip', queried_zip_key='zip-consultado')
        self.assertFalse(intercambio.zip_key)
        self.assertEqual(intercambio.request_filename, 'zip-consultado_solicitud.xml')
        self.assertEqual(intercambio.response_filename, 'zip-consultado_respuesta.xml')

    def test_una_consulta_por_cune_sin_zip_key_usa_el_id_del_intercambio(self):
        intercambio = self._intercambio('get_status')
        self.assertFalse(intercambio.zip_key or intercambio.queried_zip_key)
        self.assertEqual(intercambio.request_filename, 'intercambio_%s_solicitud.xml' % intercambio.id)
        self.assertEqual(intercambio.response_filename, 'intercambio_%s_respuesta.xml' % intercambio.id)

    def test_los_nombres_son_calculados_y_no_almacenados(self):
        """Calculados y NO almacenados: el historial DIAN es inmutable (``write`` lanza AccessError) y no se le agrega columna."""
        intercambio = self._intercambio(respuesta={'ZipKey': 'zip-123'})
        self.assertTrue(intercambio.request_filename)
        self.assertFalse(self.env['l10n.co.ne.exchange']._fields['request_filename'].store)
        self.assertFalse(self.env['l10n.co.ne.exchange']._fields['response_filename'].store)

    def test_la_vista_descarga_con_los_nombres_calculados(self):
        arch = self.env.ref('l10n_co_nomina_electronica.view_l10n_co_ne_exchange_form').arch
        self.assertIn('filename="request_filename"', arch)
        self.assertIn('filename="response_filename"', arch)
        self.assertIn('name="request_filename" invisible="1"', arch)
        self.assertIn('name="response_filename" invisible="1"', arch)
        self.assertNotIn('filename="zip_key"', arch)
