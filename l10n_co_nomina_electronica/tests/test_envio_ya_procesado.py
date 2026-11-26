# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-DIAN-03 (doc 107): una respuesta perdida no convierte en rechazado ni duplica un documento que la DIAN ya tiene.

(a) antes de reintentar un envío fallido se consulta por CUNE y solo se reenvía si la DIAN dice EXPLÍCITAMENTE que no lo conoce (``StatusCode`` 66);
(b) la regla 90 de un ENVÍO no es un rechazo: se concilia por CUNE y, sin veredicto, el documento queda incierto.

Las respuestas de la DIAN son las medidas en HABILITACIÓN (doc 103 §8 y doc 107 §5.3), con un CUNE sintético. Todo con *mock*: nada llama a la DIAN. Producción: NO VERIFICADO."""

from datetime import date
from unittest.mock import MagicMock

from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_respuesta, soap_client

from . import test_documento_enviar as envio          # el modulo, no la clase: importarla la correria dos veces
from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION, PENDIENTE, RECHAZO

# E-1: reenvío por SendNominaSync de un XML ya aceptado.
REGLA_90 = {'HttpStatus': 200, 'IsValid': 'false', 'StatusCode': '99', 'StatusDescription': 'Documento NE0000000011 procesado anteriormente.',
            'ErrorMessages': ['Regla: 90, Rechazo: Documento procesado anteriormente.'], 'RawRequest': b'<req/>', 'RawResponse': b'<resp/>'}
# E-3: GetStatus de un CUNE que la DIAN nunca recibió.
NO_CONOCIDA = {'HttpStatus': 200, 'IsValid': 'false', 'StatusCode': '66', 'StatusDescription': 'TrackId no existe en los registros de la DIAN.',
               'ErrorMessages': [], 'XmlDocumentKey': '', 'RawRequest': b'<req/>', 'RawResponse': b'<resp/>'}


@tagged('post_install', '-at_install')
class TestVeredictosReintento(BaseCase):

    def _veredicto(self, respuesta, contexto):
        return dian_respuesta.interpretar_respuesta(respuesta, contexto=contexto).veredicto

    def test_la_regla_90_de_un_envio_es_ya_procesado_y_no_rechazo(self):
        self.assertEqual(self._veredicto(REGLA_90, dian_respuesta.CONTEXTO_ENVIO), dian_respuesta.YA_PROCESADO)
        self.assertEqual(self._veredicto(REGLA_90, dian_respuesta.CONTEXTO_CONSULTA), dian_respuesta.RECHAZADO, 'En una consulta no cambia nada')
        singular = {'IsValid': 'false', 'StatusCode': '99', 'ErrorMessage': 'Regla: 90, Rechazo: Documento Procesado Anteriormente.'}
        self.assertTrue(dian_respuesta.es_ya_procesado(singular))

    def test_otro_rechazo_sigue_siendo_rechazo(self):
        self.assertFalse(dian_respuesta.es_ya_procesado(RECHAZO))
        self.assertEqual(self._veredicto(RECHAZO, dian_respuesta.CONTEXTO_ENVIO), dian_respuesta.RECHAZADO)
        novecientos = {'IsValid': 'false', 'StatusCode': '99', 'ErrorMessages': ['Regla: 900, Rechazo: otra cosa']}
        self.assertFalse(dian_respuesta.es_ya_procesado(novecientos))

    def test_solo_el_codigo_66_explicito_es_no_conocido(self):
        self.assertEqual(self._veredicto(NO_CONOCIDA, dian_respuesta.CONTEXTO_CONSULTA), dian_respuesta.NO_CONOCIDO)
        for codigo in ('65', '67', '0'):
            with self.subTest(codigo=codigo):
                self.assertNotEqual(self._veredicto(dict(NO_CONOCIDA, StatusCode=codigo), dian_respuesta.CONTEXTO_CONSULTA), dian_respuesta.NO_CONOCIDO)
        self.assertEqual(self._veredicto(NO_CONOCIDA, dian_respuesta.CONTEXTO_ENVIO), dian_respuesta.PENDIENTE, 'En un envío no se usa y tampoco es rechazo')
        self.assertEqual(self._veredicto(PENDIENTE, dian_respuesta.CONTEXTO_CONSULTA), dian_respuesta.PENDIENTE)


@tagged('post_install', '-at_install')
class TestDocumentoReintentoSeguro(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        envio.TestDocumentoEnviar._preparar_compania(cls, 'Compañía Reintento Seguro')

    def setUp(self):
        super().setUp()
        envio.TestDocumentoEnviar._simular_dian(self)
        self.doc = self._documento(date(2024, 3, 1))
        self.doc._ne_validar()
        self.doc.action_generar_xml()

    def _enviar(self, respuesta=ACEPTADA):
        self.soap.return_value = respuesta
        return self.doc._ne_enviar_uno()

    def _del_cune(self, base):
        return dict(base, XmlDocumentKey=self.doc.cune)

    def _fallo_previo(self):
        self._enviar(CONEXION)
        self.soap.reset_mock()

    # ── (a) consultar antes de reintentar ────────────────────────────
    def test_el_reintento_consulta_primero_y_si_esta_aceptado_no_reenvia(self):
        self._fallo_previo()
        self.consulta_cune.return_value = self._del_cune(ACEPTADA)
        intento = self._enviar()
        self.soap.assert_not_called()
        self.assertEqual((intento.state, self.doc.state, len(self.doc.intento_ids)), ('invoice_accepted', 'invoice_accepted', 1))
        self.assertFalse(self.doc.incierto)
        self.assertFalse(self.doc.sending_data)
        self.assertEqual(self.consulta_cune.call_args.kwargs['track_id'], self.doc.cune)

    def test_si_la_dian_no_conoce_el_cune_se_reenvia_el_mismo_xml(self):
        self._fallo_previo()
        adjunto, consecutivo = self.doc.xml_attachment_id, self.doc.consecutive
        self.consulta_cune.return_value = NO_CONOCIDA
        intento = self._enviar()
        self.soap.assert_called_once()
        self.assertEqual((intento.state, intento.attachment_id, intento.numero), ('invoice_accepted', adjunto, consecutivo))

    def test_sin_respuesta_concluyente_no_se_reenvia(self):
        otro = dict(ACEPTADA, XmlDocumentKey='cune-de-otro-documento')
        for nombre, respuesta in (('transporte', CONEXION), ('pendiente', PENDIENTE), ('otro documento', otro)):
            with self.subTest(nombre):
                doc = self.doc
                if not doc.intento_ids:
                    self._fallo_previo()
                self.consulta_cune.return_value = respuesta
                intento = self._enviar()
                self.soap.assert_not_called()
                self.assertEqual((intento.state, doc.state, len(doc.intento_ids)), ('invoice_sending_failed', 'invoice_sending_failed', 1))

    def test_el_primer_envio_no_consulta(self):
        self._enviar()
        self.consulta_cune.assert_not_called()

    def test_en_modo_demo_no_se_consulta(self):
        self._fallo_previo()
        self.company.l10n_co_ne_demo_mode = True
        self.doc._ne_enviar_uno()
        self.consulta_cune.assert_not_called()
        self.soap.assert_not_called()

    # ── (b) la regla 90 de un envío ──────────────────────────────────
    def test_regla_90_con_consulta_aceptada_queda_aceptado_y_nunca_rechazado(self):
        self.consulta_cune.side_effect = lambda **kw: self._del_cune(ACEPTADA)
        intento = self._enviar(REGLA_90)
        self.assertEqual((intento.state, self.doc.state), ('invoice_accepted', 'invoice_accepted'))
        self.assertEqual(self.doc.intento_ids.mapped('state'), ['invoice_accepted'])
        self.assertFalse(self.doc.incierto)

    def test_regla_90_sin_veredicto_deja_el_documento_incierto(self):
        for nombre, respuesta in (('transporte', CONEXION), ('no conocido', NO_CONOCIDA)):
            with self.subTest(nombre):
                doc = self._documento(date(2024, 3, 1))
                doc._ne_validar()
                doc.action_generar_xml()
                self.consulta_cune.return_value = respuesta
                self.soap.return_value = REGLA_90
                intento = doc._ne_enviar_uno()
                self.assertEqual((intento.state, doc.state), ('invoice_pending', 'invoice_pending'))
                self.assertTrue(doc.incierto)

    # ── liberar un incierto que la DIAN no tiene ─────────────────────
    def test_un_incierto_sin_intento_que_la_dian_no_conoce_queda_listo_para_reenviar_el_mismo_xml(self):
        adjunto, cune = self.doc.xml_attachment_id, self.doc.cune
        self.doc.incierto = True                                  # el proceso murió durante el envío
        self.consulta_cune.return_value = NO_CONOCIDA
        self.doc._ne_reconsultar_por_cune()
        self.assertFalse(self.doc.incierto)
        self.assertEqual(self.doc.state, 'invoice_sending_failed')
        intento = self._enviar()
        self.assertEqual((intento.attachment_id, self.doc.cune, self.doc.state), (adjunto, cune, 'invoice_accepted'))

    def test_un_incierto_con_envio_pendiente_no_se_libera(self):
        self._enviar(PENDIENTE)
        self.doc.incierto = True
        self.consulta_cune.return_value = NO_CONOCIDA
        self.doc._ne_reconsultar_por_cune()
        self.assertTrue(self.doc.incierto)
        self.assertEqual(self.doc.state, 'invoice_pending')

    def test_con_otra_respuesta_el_incierto_sigue_incierto(self):
        self.doc.incierto = True
        for respuesta in (CONEXION, PENDIENTE):
            self.consulta_cune.return_value = respuesta
            self.doc._ne_reconsultar_por_cune()
            self.assertTrue(self.doc.incierto)
            self.assertFalse(self.doc.intento_ids)
