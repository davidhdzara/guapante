# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-DIAN-03 (doc 107): una respuesta perdida no convierte en rechazado ni duplica un documento que la DIAN ya tiene.

(a) antes de reintentar un envío fallido se consulta por CUNE y solo se reenvía si la DIAN dice EXPLÍCITAMENTE que no lo conoce (``StatusCode`` 66);
(b) la regla 90 de un ENVÍO no es un rechazo: se concilia por CUNE y, sin un aceptado, el documento queda incierto y por conciliar; solo el administrador de nómina pasa al número siguiente (.337).

Las respuestas de la DIAN son las medidas en HABILITACIÓN (doc 103 §8 y doc 107 §5.3), con un CUNE sintético. Todo con *mock*: nada llama a la DIAN. Producción: NO VERIFICADO."""

from datetime import date
from unittest.mock import MagicMock

from lxml import etree

from odoo.exceptions import UserError
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

    # ── regla 90: la DIAN ya tiene ese número; nada automático salvo un aceptado (.337) ────────
    def _vuelto_a_usar(self):
        """El documento rechazado por su contenido y generado otra vez con el MISMO número."""
        self._enviar(RECHAZO)
        numero, cune = self.doc.consecutive, self.doc.cune
        self.hora = '11:00:00-05:00'
        self.doc.action_generar_xml()
        self.assertEqual((self.doc.consecutive, self.doc.state), (numero, False))
        self.assertNotEqual(self.doc.cune, cune)
        self.soap.reset_mock()
        self.consulta_cune.reset_mock()
        return numero

    def _por_conciliar(self, intento):
        """Pendiente, incierto y marcado: ni se reenvía ni se genera otro XML, y la consulta que no lo conoce no lo libera."""
        self.assertEqual((intento.state, self.doc.state, self.doc.incierto, intento.ya_procesado), ('invoice_pending', 'invoice_pending', True, True))
        self.assertTrue(self.doc.regla_90_sin_conciliar)
        self.assertTrue(self.doc.message_ids.filtered(lambda m: 'por conciliar' in str(m.body)))
        envios, cune, numero = self.soap.call_count, self.doc.cune, self.doc.consecutive
        self.consulta_cune.side_effect = None
        self.consulta_cune.return_value = NO_CONOCIDA
        self.doc._ne_reconsultar_por_cune()
        self.assertEqual((self.doc.state, self.doc.incierto, self.doc.intento_ids.filtered(lambda i: i.identifier == cune).mapped('state').count('invoice_pending')), ('invoice_pending', True, 1))
        with self.assertRaises(UserError):
            self.doc._ne_enviar_uno()
        self.hora = '11:30:00-05:00'
        with self.assertRaisesRegex(UserError, 'no se haya enviado'):
            self.doc.action_generar_xml()
        self.assertEqual((self.soap.call_count, self.doc.cune, self.doc.consecutive), (envios, cune, numero))

    def _usar_el_siguiente(self, intento):
        numero = intento.numero
        self.doc.action_usar_numero_siguiente()
        self.assertEqual((intento.state, self.doc.state, self.doc.incierto, self.doc.regla_90_sin_conciliar), ('invoice_rejected', 'invoice_rejected', False, False))
        nota = self.doc.message_ids.filtered(lambda m: 'Verifiqué en la DIAN que no hay documento aceptado con este número: usar el siguiente' in str(m.body))
        self.assertEqual(len(nota), 1)
        self.assertIn(numero, str(nota.body))
        self.hora = '12:00:00-05:00'
        self.doc.action_generar_xml()
        self.assertNotEqual(self.doc.consecutive, numero)

    def test_regla_90_con_consulta_aceptada_en_un_numero_vuelto_a_usar_queda_aceptado(self):
        numero = self._vuelto_a_usar()
        self.consulta_cune.side_effect = lambda **kw: self._del_cune(ACEPTADA)
        intento = self._enviar(REGLA_90)
        self.assertEqual((intento.state, self.doc.state, intento.numero, intento.ya_procesado, self.doc.regla_90_sin_conciliar), ('invoice_accepted', 'invoice_accepted', numero, True, False))

    def test_regla_90_con_cune_no_conocido_queda_por_conciliar_y_solo_el_administrador_pasa_al_siguiente(self):
        self._vuelto_a_usar()
        self.consulta_cune.return_value = NO_CONOCIDA
        intento = self._enviar(REGLA_90)
        self._por_conciliar(intento)
        self._usar_el_siguiente(intento)

    def test_regla_90_en_un_numero_nuevo_con_consulta_rechazada_tampoco_pasa_solo_al_siguiente(self):
        self.consulta_cune.side_effect = lambda **kw: self._del_cune(RECHAZO)
        intento = self._enviar(REGLA_90)
        self._por_conciliar(intento)
        self._usar_el_siguiente(intento)

    def test_regla_90_sin_consulta_y_despues_aceptado_queda_aceptado(self):
        self.consulta_cune.return_value = CONEXION
        intento = self._enviar(REGLA_90)
        self.assertEqual((intento.state, self.doc.incierto, self.doc.regla_90_sin_conciliar), ('invoice_pending', True, True))
        self.consulta_cune.return_value = self._del_cune(ACEPTADA)
        self.doc._ne_reconsultar_por_cune()
        self.assertEqual((intento.state, self.doc.state, self.doc.incierto, self.doc.regla_90_sin_conciliar), ('invoice_accepted', 'invoice_accepted', False, False))
        with self.assertRaisesRegex(UserError, 'regla 90 por conciliar'):
            self.doc.action_usar_numero_siguiente()

    def test_la_regla_90_del_reenvio_tras_un_fallo_queda_por_conciliar_y_se_puede_pasar_al_siguiente(self):
        self._vuelto_a_usar()
        self._enviar(CONEXION)
        self.consulta_cune.return_value = NO_CONOCIDA          # el reintento consulta, no lo conoce, reenvía: regla 90
        intento = self._enviar(REGLA_90)
        self._por_conciliar(intento)
        self._usar_el_siguiente(intento)

    def test_una_consulta_del_reintento_que_trae_la_regla_90_deja_por_conciliar_sin_reenviar(self):
        self._fallo_previo()
        self.consulta_cune.return_value = self._del_cune(REGLA_90)
        intento = self._enviar()
        self.soap.assert_not_called()
        self.assertEqual(len(self.doc.intento_ids), 1)
        self._por_conciliar(intento)

    def test_un_incierto_sin_intento_cuya_consulta_trae_la_regla_90_queda_por_conciliar(self):
        self.doc.incierto = True
        self.consulta_cune.return_value = self._del_cune(REGLA_90)
        self.doc._ne_reconsultar_por_cune()
        self._por_conciliar(self.doc.intento_ids)

    def test_usar_el_siguiente_exige_la_regla_90_y_al_administrador(self):
        self._enviar(PENDIENTE)
        self.doc.incierto = True
        with self.assertRaisesRegex(UserError, 'regla 90 por conciliar'):
            self.doc.action_usar_numero_siguiente()
        oficial = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Oficial regla 90', 'login': 'oficial_regla_90', 'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr_payroll.group_hr_payroll_user').id])]})
        with self.assertRaisesRegex(UserError, 'Solo el administrador de nómina'):
            self.doc.with_user(oficial).action_usar_numero_siguiente()
        self.assertEqual((self.doc.state, self.doc.incierto), ('invoice_pending', True))

    def test_el_boton_pide_confirmacion_y_es_solo_del_administrador(self):
        arch = etree.fromstring(self.env.ref('l10n_co_nomina_electronica.view_l10n_co_ne_documento_form').arch_db)
        boton = arch.find('.//header/button[@name="action_usar_numero_siguiente"]')
        self.assertEqual((boton.get('groups'), boton.get('invisible')), ('hr_payroll.group_hr_payroll_manager', 'not regla_90_sin_conciliar'))
        self.assertIn('Verifiqué en la DIAN', boton.get('confirm'))

    def test_en_un_numero_vuelto_a_usar_el_numero_no_identifica_la_respuesta(self):
        self._enviar(RECHAZO)
        self._patch(dian_respuesta, 'candidatos_numero', lambda respuesta: {self.doc.consecutive})
        self.assertTrue(self.doc._ne_respuesta_es_de_este_documento({}, self.doc._ultimo_intento()), 'Un solo envío con el número: sirve de respaldo')
        self.hora = '11:00:00-05:00'
        self.doc.action_generar_xml()
        intento = self._enviar(PENDIENTE)
        self.assertFalse(self.doc._ne_respuesta_es_de_este_documento({}, intento))
        self.assertTrue(self.doc._ne_respuesta_es_de_este_documento({'XmlDocumentKey': self.doc.cune}, intento))

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
