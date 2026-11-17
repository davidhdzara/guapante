# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 4 (doc 53 §23.12 3.1, §23.15): ``l10n.co.ne.documento._ne_enviar_uno()``.

Todo con *mock*: NINGUNA prueba llama a la DIAN real (``soap_client.send_nomina_sync`` está parchado).
Valores a mano: el documento de marzo 2026 con dos quincenas del fixture de ``test_documento_generar``.
"""

import base64
import copy
import hashlib
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo

ACEPTADA = {'IsValid': 'true', 'StatusCode': '00', 'StatusDescription': 'Procesado Correctamente.',
            'ZipKey': 'Z1', 'RawRequest': b'<req/>', 'RawResponse': b'<resp/>'}
RECHAZO = {'IsValid': 'false', 'StatusCode': '99', 'ErrorMessages': ['Regla: NIAE191a, Rechazo: x'],
           'RawRequest': b'<req/>', 'RawResponse': b'<resp/>'}
PENDIENTE = {'IsValid': 'false', 'StatusCode': '0', 'StatusDescription': 'Batch en proceso de validación.',
             'ZipKey': 'abc', 'RawRequest': b'<req/>', 'RawResponse': b'<resp/>'}
CONEXION = {'StatusCode': 'CONNECTION_ERROR', 'ErrorMessage': 'timeout', 'TransportError': 'timeout',
            'RawRequest': b'<req/>'}
HTTP_404 = {'HttpStatus': 404, 'StatusCode': '404', 'ErrorMessage': 'HTTP 404: respuesta no SOAP',
            'RawRequest': b'<req/>'}
HTTP_503 = {'HttpStatus': 503, 'IsValid': 'false', 'StatusCode': '503', 'RawRequest': b'<req/>'}


@tagged('post_install', '-at_install')
class TestDocumentoEnviar(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Enviar Documento')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'          # Producción: el documento solo transmite aquí (D-b)
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE enviar', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        # Al crear una compañía colombiana el módulo le crea su PROPIA secuencia (relleno 10, desde 1): la prueba
        # usa la suya, como ``test_documento_generar``.
        cls.company.l10n_co_ne_sequence_id = cls.secuencia

    def setUp(self):
        super().setUp()

        def fabrica(slip):
            datos = copy.deepcopy(_quincena_con_prima() if slip.date_to.day > 15 else _recibo())
            datos['informacion_general'] = dict(datos['informacion_general'], FechaGen=FECHA, HoraGen=HORA)
            return datos
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: fabrica(s))
        self._patch(dian_utils, 'compute_software_security_code', lambda *a: 'SC')
        self._patch(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        self._patch(type(self.env['l10n.co.ne.documento']), '_ne_validar_datos_recibo', lambda s, slip: None)
        self._patch(type(self.company), '_get_ne_certificate', lambda s: True)
        self._patch(dian_utils, 'clean_nit', lambda *a, **k: '900123456')
        self._patch(xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None))
        self._patch(xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)
        self._patch(nomina_xml_builder, 'build_nomina_individual_v2', lambda datos: XML_STUB)
        self.soap = MagicMock(name='send_nomina_sync')
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.consulta = MagicMock(name='get_status_zip')
        self._patch(soap_client, 'get_status_zip', self.consulta)
        self.doc = self._documento(date(2024, 3, 1))
        self.doc._ne_validar()
        self.doc.action_generar_xml()                     # NE00000015, listo para enviar

    # ── utilidades ───────────────────────────────────────────────────
    def _enviar(self, respuesta):
        self.soap.return_value = respuesta
        return self.doc._ne_enviar_uno()

    def _intento(self, estado, dt=datetime(2026, 4, 1, 10, 0), **vals):
        datos = {'documento_id': self.doc.id, 'state': estado, 'datetime': dt,
                 'identifier': self.doc.cune, 'numero': self.doc.consecutive}
        datos.update(vals)
        return self.env['l10n.co.ne.documento.intento'].create(datos)

    def _no_envia(self):
        """Una precondición incumplida: UserError, sin llamar a la DIAN, sin intento nuevo, sin gastar número."""
        intentos = len(self.doc.intento_ids)
        siguiente = self.secuencia.number_next_actual
        with self.assertRaises(UserError) as exc:
            self.doc._ne_enviar_uno()
        self.soap.assert_not_called()
        self.assertEqual(len(self.doc.intento_ids), intentos)
        self.assertEqual(self.secuencia.number_next_actual, siguiente)
        return str(exc.exception)

    # ── precondiciones ───────────────────────────────────────────────
    def test_sin_xml_no_se_envia(self):
        self.doc.xml_attachment_id = False
        self.assertIn('Genere el XML', self._no_envia())

    def test_falta_cune_o_consecutivo(self):
        self.doc.cune = False
        self.assertIn('Genere el XML', self._no_envia())
        self.doc.cune = 'x' * 96
        self.doc.consecutive = False
        self.assertIn('Genere el XML', self._no_envia())

    def test_pendiente_no_se_reenvia(self):
        self._intento('invoice_pending')
        self.assertIn('ya fue enviado', self._no_envia())

    def test_aceptado_no_se_reenvia(self):
        self._intento('invoice_accepted')
        self.assertIn('ya fue enviado', self._no_envia())

    def test_incierto_y_eliminado_no_se_envian(self):
        self.doc.incierto = True
        self.assertIn('incierto', self._no_envia())
        self.doc.incierto = False
        self.doc.eliminado = True
        self.assertIn('eliminado', self._no_envia())

    def test_rechazado_vigente_no_se_reenvia_y_remite_a_regenerar(self):
        self._intento('invoice_rejected')
        mensaje = self._no_envia()
        self.assertIn('genere el XML otra vez', mensaje)
        self.assertIn('consecutivo nuevo', mensaje)

    def test_rechazado_ya_regenerado_si_se_envia(self):
        """Regenerado con consecutivo nuevo, el XML vigente no fue rechazado: vuelve a 'Listo' y se envía."""
        self._intento('invoice_rejected')
        self.doc.action_generar_xml()                      # NE00000016
        self.assertEqual(self.doc.etapa, 'ready')
        self.assertFalse(self.doc.state)
        intento = self._enviar(ACEPTADA)
        self.assertEqual(intento.numero, 'NE00000016')
        self.assertEqual(self.doc.state, 'invoice_accepted')

    def test_nota_de_ajuste_no_se_envia_aqui(self):
        # is_adjustment exige el CUNE de referencia en la MISMA escritura (constraint del documento)
        self.doc.write({'is_adjustment': True, 'adjustment_ref_cune': 'x' * 96})
        self.assertIn('ajuste', self._no_envia())

    def test_documento_migrado_legacy_no_se_envia(self):
        self.doc.legacy = True
        self.assertIn('migrado', self._no_envia())

    def test_habilitacion_por_ambiente_bloquea_y_nombra_la_compania(self):
        self.company.l10n_co_ne_environment = '2'
        mensaje = self._no_envia()
        self.assertIn(self.company.name, mensaje)
        self.assertIn('habilitación', mensaje)

    def test_habilitacion_por_proceso_de_certificacion_bloquea(self):
        self.company.l10n_co_ne_certification_process = True
        self.assertIn(self.company.name, self._no_envia())

    def test_configuracion_incompleta_propaga_el_error(self):
        with patch.object(type(self.company), '_l10n_co_ne_validar_config',
                          side_effect=UserError('config incompleta')):
            self.assertIn('config incompleta', self._no_envia())

    # ── resultados (mock de la DIAN) ─────────────────────────────────
    def test_aceptado(self):
        mensajes = len(self.doc.message_ids)
        intento = self._enviar(ACEPTADA)
        xml = base64.b64decode(self.doc.xml_attachment_id.datas)
        self.assertEqual(intento.state, 'invoice_accepted')
        self.assertEqual(intento.identifier, self.doc.cune)
        self.assertEqual(intento.numero, 'NE00000015')
        self.assertEqual(intento.file_name, 'ne_SIN_NIT_NE00000015.xml')
        self.assertEqual(intento.sha256, hashlib.sha256(xml).hexdigest())
        self.assertEqual(intento.attachment_id, self.doc.xml_attachment_id)
        self.assertEqual(intento.zip_key, 'Z1')
        self.assertTrue(intento.message_json['is_valid'])
        self.assertFalse(intento.test_environment)
        self.assertEqual(self.doc.state, 'invoice_accepted')
        self.assertEqual(self.doc.zip_key, 'Z1')
        self.assertIn('Procesado Correctamente.', self.doc.message)
        self.assertFalse(self.doc.sending_data)
        self.assertEqual(len(self.doc.message_ids), mensajes + 1)

    def test_rechazado_con_la_regla_y_el_mismo_consecutivo(self):
        intento = self._enviar(RECHAZO)
        self.assertEqual(intento.state, 'invoice_rejected')
        self.assertIn('NIAE191a', self.doc.message)
        self.assertEqual(self.doc.state, 'invoice_rejected')
        self.assertEqual(self.doc.consecutive, 'NE00000015')

    def test_pendiente_con_zip_key_no_es_rechazo(self):
        intento = self._enviar(PENDIENTE)
        self.assertEqual(intento.state, 'invoice_pending')
        self.assertEqual(intento.zip_key, 'abc')
        self.assertEqual(self.doc.zip_key, 'abc')
        self.assertTrue(intento.show_button_get_status)
        self.assertEqual(self.doc.state, 'invoice_pending')

    def test_fallo_de_conexion_es_reintentable_y_no_es_rechazo(self):
        intento = self._enviar(CONEXION)
        self.assertEqual(intento.state, 'invoice_sending_failed')
        self.assertEqual(intento.message_json['transport'], 'CONNECTION_ERROR')
        self.assertEqual(self.doc.state, 'invoice_sending_failed')
        self.assertNotEqual(self.doc.state, 'invoice_rejected')

    def test_http_4xx_sin_veredicto_es_fallo_de_envio(self):
        self.assertEqual(self._enviar(HTTP_404).state, 'invoice_sending_failed')

    def test_http_5xx_es_fallo_de_envio(self):
        self.assertEqual(self._enviar(HTTP_503).state, 'invoice_sending_failed')

    # ── reintento ────────────────────────────────────────────────────
    def test_reintento_conserva_consecutivo_cune_y_xml(self):
        cune, adjunto = self.doc.cune, self.doc.xml_attachment_id
        siguiente = self.secuencia.number_next_actual
        self._enviar(CONEXION)
        self.assertEqual(self.doc.state, 'invoice_sending_failed')
        self._enviar(ACEPTADA)
        self.assertEqual(len(self.doc.intento_ids), 2)                  # el fallido queda en el historial
        self.assertEqual(self.doc.consecutive, 'NE00000015')
        self.assertEqual(self.doc.cune, cune)
        self.assertEqual(self.doc.xml_attachment_id, adjunto)
        self.assertEqual(self.secuencia.number_next_actual, siguiente)  # no se gastó otro número
        self.assertEqual(self.doc.state, 'invoice_accepted')

    def test_solo_se_reintenta_desde_fallo_de_envio(self):
        self._enviar(CONEXION)
        self._enviar(PENDIENTE)                                         # desde "Envío fallido" se puede
        self.assertEqual(self.doc.state, 'invoice_pending')
        self.soap.reset_mock()                                          # lo anterior ya llamó a la DIAN dos veces
        self.assertIn('ya fue enviado', self._no_envia())               # desde "Pendiente" no

    # ── la llamada a la DIAN ─────────────────────────────────────────
    def test_llama_a_send_nomina_sync_con_el_xml_el_endpoint_y_el_timeout(self):
        self._enviar(ACEPTADA)
        self.soap.assert_called_once()
        kwargs = self.soap.call_args.kwargs
        self.assertEqual(kwargs['xml_bytes'], base64.b64decode(self.doc.xml_attachment_id.datas))
        self.assertEqual(kwargs['filename'], 'ne_SIN_NIT_NE00000015.xml')
        self.assertEqual(kwargs['endpoint'], self.company._ne_dian_endpoint())
        self.assertEqual(kwargs['timeout'], self.company._ne_config_int_param(
            'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT))

    # ── Modo Demo ────────────────────────────────────────────────────
    def test_modo_demo_no_llama_a_la_dian(self):
        self.company.l10n_co_ne_demo_mode = True
        intento = self.doc._ne_enviar_uno()
        self.soap.assert_not_called()
        self.assertEqual(intento.state, 'invoice_accepted')
        self.assertIn('Modo Demo', intento.message)
        self.assertFalse(intento.exchange_id)

    # ── evidencia (exchange) ─────────────────────────────────────────
    def test_crea_la_evidencia_enlazada_sin_filas_de_manifiesto(self):
        exchanges = self.env['l10n.co.ne.exchange'].search_count([])
        manifiestos = self.env['l10n.co.ne.exchange.document'].search_count([])
        intento = self._enviar(ACEPTADA)
        self.assertEqual(self.env['l10n.co.ne.exchange'].search_count([]), exchanges + 1)
        self.assertEqual(self.env['l10n.co.ne.exchange.document'].search_count([]), manifiestos)   # 0 filas nuevas
        exchange = intento.exchange_id
        self.assertEqual(exchange.operation, 'send_sync')
        self.assertEqual(exchange.company_id, self.company)
        self.assertEqual(exchange.payslip_ids, self.doc.payslip_ids)
        self.assertIn(exchange, self.doc.exchange_ids)

    def test_create_exchange_documento_es_solo_por_nombre(self):
        with self.assertRaises(TypeError):
            self.env['l10n.co.ne.exchange'].create_exchange(
                self.company, 'send_sync', 'http://x', {}, self.doc.payslip_ids, None, None, None, 0, self.doc)

    def test_create_exchange_documento_con_manifiesto_falla(self):
        slip = self.doc.payslip_ids[:1]
        with self.assertRaises(ValueError):
            self.env['l10n.co.ne.exchange'].create_exchange(
                self.company, 'send_sync', 'http://x', {}, self.doc.payslip_ids,
                manifest=[{'payslip': slip, 'filename': 'a.xml', 'xml': b'<x/>'}], documento=self.doc)

    def test_create_exchange_documento_de_otra_compania_falla(self):
        otra = self.env['res.company'].create({'name': 'Otra compañía evidencia',
                                               'country_id': self.env.ref('base.co').id})
        with self.assertRaises(AccessError):
            self.env['l10n.co.ne.exchange'].create_exchange(
                otra, 'send_sync', 'http://x', {}, self.env['hr.payslip'], documento=self.doc)

    def test_create_exchange_sin_documento_no_cambia(self):
        """La llamada de siempre (recibo con manifiesto) sigue creando la fila de manifiesto."""
        slip = self.doc.payslip_ids[:1]
        antes = self.env['l10n.co.ne.exchange.document'].search_count([])
        exchange = self.env['l10n.co.ne.exchange'].create_exchange(
            self.company, 'send_sync', 'http://x', {'RawRequest': b'<r/>'}, slip,
            manifest=[{'payslip': slip, 'filename': 'a.xml', 'xml': b'<x/>'}])
        self.assertEqual(self.env['l10n.co.ne.exchange.document'].search_count([]), antes + 1)
        self.assertEqual(exchange.payslip_ids, slip)
        self.assertFalse(self.doc.exchange_ids)

    # ── E-1: el ApplicationResponse decodificado queda como adjunto del intento ──────────────────────
    APPLICATION_RESPONSE = '<ApplicationResponse><cbc:ID>NE00000015</cbc:ID><cbc:Note>Documento validado por la DIAN</cbc:Note></ApplicationResponse>'

    def test_envio_con_application_response_adjunta_el_xml_decodificado_al_intento(self):
        intento = self._enviar(dict(ACEPTADA, ApplicationResponse=self.APPLICATION_RESPONSE))
        adjunto = intento.respuesta_attachment_id
        self.assertTrue(adjunto)
        self.assertEqual(adjunto.raw.decode('utf-8'), self.APPLICATION_RESPONSE)
        self.assertEqual(adjunto.name, 'ApplicationResponse_%s_%s.xml' % (intento.numero, intento.id))
        self.assertEqual((adjunto.res_model, adjunto.res_id), ('l10n.co.ne.documento.intento', intento.id))
        self.assertEqual(adjunto.mimetype, 'application/xml')

    def test_envio_sin_application_response_no_crea_adjunto(self):
        self.assertFalse(self._enviar(ACEPTADA).respuesta_attachment_id)

    def test_el_application_response_de_un_resultado_de_la_lista_tambien_se_adjunta(self):
        respuesta = dict(ACEPTADA, DianResponses=[{'ApplicationResponse': self.APPLICATION_RESPONSE}])
        self.assertTrue(self._enviar(respuesta).respuesta_attachment_id)

    def test_la_consulta_que_da_veredicto_adjunta_el_application_response_al_mismo_intento(self):
        intento = self._pendiente()
        self.assertFalse(intento.respuesta_attachment_id)
        self._consultar(dict(self._aceptada_de_este_documento(), ApplicationResponse=self.APPLICATION_RESPONSE))
        self.assertEqual(intento.respuesta_attachment_id.raw.decode('utf-8'), self.APPLICATION_RESPONSE)

    # ── multiempresa ─────────────────────────────────────────────────
    def test_el_envio_usa_la_compania_del_documento_no_la_activa(self):
        otra = self.env['res.company'].create({'name': 'Compañía activa distinta',
                                               'country_id': self.env.ref('base.co').id})
        self.soap.return_value = ACEPTADA
        intento = self.doc.with_company(otra)._ne_enviar_uno()
        self.assertEqual(intento.exchange_id.company_id, self.company)
        self.assertEqual(self.soap.call_args.kwargs['endpoint'], self.company._ne_dian_endpoint())

    # ══ Reconsultar (commit 5, doc 53 §23.12 3.2): contexto 'consulta' ═══════════════════════════════════
    def _pendiente(self):
        """Documento enviado con respuesta "en proceso" (ZipKey 'abc'): un intento pendiente."""
        return self._enviar(PENDIENTE)

    def _consultar(self, respuesta):
        self.consulta.return_value = respuesta
        return self.doc._ne_reconsultar()

    def _aceptada_de_este_documento(self):
        return dict(ACEPTADA, ZipKey='abc', XmlDocumentKey=self.doc.cune)

    def _no_consulta(self):
        intentos = len(self.doc.intento_ids)
        with self.assertRaises(UserError) as exc:
            self.doc._ne_reconsultar()
        self.consulta.assert_not_called()
        self.assertEqual(len(self.doc.intento_ids), intentos)
        return str(exc.exception)

    def test_consulta_pendiente_pasa_a_aceptado_en_el_mismo_intento(self):
        intento = self._pendiente()
        resultado = self._consultar(self._aceptada_de_este_documento())
        self.assertEqual(resultado.veredicto, 'aceptado')
        self.assertEqual(len(self.doc.intento_ids), 1)                   # NO crea otro intento
        self.assertEqual(intento.state, 'invoice_accepted')
        self.assertTrue(intento.message_json['is_valid'])
        self.assertEqual(self.doc.state, 'invoice_accepted')
        self.assertIn('Procesado Correctamente.', self.doc.message)

    def test_consulta_guarda_la_evidencia_enlazada_a_la_del_envio(self):
        intento = self._pendiente()
        self._consultar(self._aceptada_de_este_documento())
        consulta = self.doc.exchange_ids.filtered(lambda e: e.operation == 'get_status_zip')
        self.assertEqual(len(consulta), 1)
        self.assertEqual(consulta.queried_zip_key, 'abc')
        self.assertEqual(consulta.parent_exchange_id, intento.exchange_id)
        self.assertEqual(consulta.payslip_ids, self.doc.payslip_ids)
        self.assertEqual(len(self.doc.exchange_ids), 2)                  # envío + consulta

    def test_consulta_pendiente_a_rechazado_con_la_regla(self):
        intento = self._pendiente()
        self._consultar(dict(RECHAZO, ZipKey='abc'))
        self.assertEqual(intento.state, 'invoice_rejected')
        self.assertIn('NIAE191a', self.doc.message)
        self.assertEqual(self.doc.state, 'invoice_rejected')
        self.assertEqual(len(self.doc.intento_ids), 1)

    def test_consulta_que_sigue_pendiente_no_cambia_nada(self):
        intento = self._pendiente()
        resultado = self._consultar(PENDIENTE)
        self.assertEqual(resultado.veredicto, 'pendiente')
        self.assertEqual(intento.state, 'invoice_pending')
        self.assertEqual(self.doc.state, 'invoice_pending')
        self.assertFalse(self.doc.incierto)
        self.assertEqual(len(self.doc.intento_ids), 1)

    def test_respuesta_de_nivel_set_no_resuelve_y_avisa_una_sola_vez(self):
        intento = self._pendiente()
        conjunto = {'StatusCode': '2', 'IsValid': 'false', 'ZipKey': 'abc',
                    'StatusDescription': 'Set de prueba con identificador e07c1748 se encuentra Aceptado.',
                    'DianResponses': [{'StatusCode': '2', 'IsValid': 'false', 'ErrorMessages': []}]}
        self.assertEqual(self._consultar(conjunto).veredicto, 'nivel_set')
        self.assertEqual(intento.state, 'invoice_pending')
        self.assertFalse(self.doc.incierto)
        avisos = len(self.doc.message_ids)
        self._consultar(conjunto)
        self.assertEqual(len(self.doc.message_ids), avisos)              # el aviso no se repite en cada consulta

    def test_fallo_de_transporte_en_la_consulta_no_cambia_el_estado(self):
        intento = self._pendiente()
        self.assertEqual(self._consultar(CONEXION).veredicto, 'error_transporte')
        self.assertEqual(intento.state, 'invoice_pending')
        self.assertEqual(self.doc.state, 'invoice_pending')
        self.assertTrue(self.doc.exchange_ids.filtered(lambda e: e.operation == 'get_status_zip'))

    def test_respuesta_con_el_cune_de_otro_documento_no_resuelve(self):
        intento = self._pendiente()
        self._consultar(dict(ACEPTADA, ZipKey='abc', XmlDocumentKey='OTRO-CUNE'))
        self.assertEqual(intento.state, 'invoice_pending')
        self.assertEqual(self.doc.state, 'invoice_pending')
        self.assertTrue(any('corresponde a otro documento' in str(m.body) for m in self.doc.message_ids))

    def test_varios_resultados_para_un_documento_no_resuelve(self):
        intento = self._pendiente()
        uno = {'IsValid': 'true', 'StatusCode': '00'}
        self._consultar({'DianResponses': [uno, dict(uno)], 'ZipKey': 'abc', 'IsValid': 'true', 'StatusCode': '00'})
        self.assertEqual(intento.state, 'invoice_pending')

    def test_pasadas_las_horas_maximas_sin_veredicto_queda_incierto(self):
        intento = self._pendiente()
        self.env['ir.config_parameter'].sudo().set_param('l10n_co_nomina_electronica.recheck_max_hours', '1')
        self._consultar(PENDIENTE)
        self.assertFalse(self.doc.incierto)                              # recién enviado: todavía dentro del plazo
        intento.datetime = fields.Datetime.now() - timedelta(hours=2)
        self._consultar(PENDIENTE)
        self.assertTrue(self.doc.incierto)
        self.assertEqual(self.doc.state, 'invoice_pending')          # incierto = pendiente + bandera

    def test_un_veredicto_concilia_el_envio_incierto(self):
        self._pendiente()
        self.doc.incierto = True
        self.assertEqual(self.doc.state, 'invoice_pending')
        self._consultar(self._aceptada_de_este_documento())
        self.assertFalse(self.doc.incierto)
        self.assertEqual(self.doc.state, 'invoice_accepted')

    def test_desde_un_fallo_de_envio_con_zip_key_pasa_a_pendiente(self):
        # Envío reciente: con la fecha por defecto (2026-04-01) ya pasaron las horas de reconsulta y el documento
        # quedaría 'incierto' (otro comportamiento, cubierto aparte).
        fallido = self._intento('invoice_sending_failed', fields.Datetime.now() - timedelta(hours=1), zip_key='z9',
                                identifier=self.doc.cune, numero=self.doc.consecutive)
        self._consultar(dict(PENDIENTE, ZipKey='z9'))
        self.assertEqual(fallido.state, 'invoice_pending')
        self.assertEqual(self.doc.state, 'invoice_pending')

    def test_la_consulta_llama_a_get_status_zip_con_el_zip_key_y_no_envia(self):
        self._pendiente()
        self.soap.reset_mock()
        self._consultar(PENDIENTE)
        self.consulta.assert_called_once()
        kwargs = self.consulta.call_args.kwargs
        self.assertEqual(kwargs['track_id'], 'abc')
        self.assertEqual(kwargs['endpoint'], self.company._ne_dian_endpoint())
        self.soap.assert_not_called()

    # ── precondiciones de la consulta ────────────────────────────────
    def test_consulta_de_un_documento_no_enviado(self):
        self.assertIn('no se ha enviado', self._no_consulta())

    def test_consulta_sin_zip_key(self):
        self._enviar(CONEXION)                                           # fallo de envío: sin ZipKey
        self.assertIn('ZipKey', self._no_consulta())

    def test_consulta_con_veredicto_ya_dado(self):
        self._enviar(ACEPTADA)
        self.assertIn('ya tiene veredicto', self._no_consulta())

    def test_consulta_de_legacy_y_eliminado(self):
        self._pendiente()
        self.doc.legacy = True
        self.assertIn('migrado', self._no_consulta())
        self.doc.legacy = False
        self.doc.eliminado = True
        self.assertIn('eliminado', self._no_consulta())

    def test_consulta_en_habilitacion_se_bloquea_y_nombra_la_compania(self):
        self._pendiente()
        self.company.l10n_co_ne_environment = '2'
        self.assertIn(self.company.name, self._no_consulta())

    def test_consulta_con_configuracion_incompleta_propaga_el_error(self):
        self._pendiente()
        with patch.object(type(self.company), '_l10n_co_ne_validar_config',
                          side_effect=UserError('config incompleta')):
            self.assertIn('config incompleta', self._no_consulta())

    # ── D6 (doc 53 §28.7): un documento con envío fallido NO se recompone ──────────────────────────────────
    def _recibo_nuevo_del_mes(self):
        slip = self.env['hr.payslip'].create({
            'name': 'Recibo tardío', 'employee_id': self.doc.employee_id.id, 'contract_id': self.doc.contract_id.id,
            'company_id': self.company.id, 'struct_id': self.struct.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        slip.write({'state': 'paid', 'paid_date': date(2026, 3, 20)})
        return slip

    def test_envio_fallido_no_se_recompone_y_alerta(self):
        self._enviar(CONEXION)
        self.assertEqual(self.doc.state, 'invoice_sending_failed')
        originales, xml, cune = self.doc.payslip_ids, self.doc.xml_attachment_id, self.doc.cune
        nuevo = self._recibo_nuevo_del_mes()
        self.env['l10n.co.ne.documento']._ne_preparar(nuevo)
        self.assertEqual(self.doc.payslip_ids, originales)             # la composición no cambia
        self.assertFalse(nuevo.l10n_co_ne_documento_id)
        self.assertEqual((self.doc.xml_attachment_id, self.doc.cune), (xml, cune))   # el XML sigue siendo el mismo
        alerta = [a for a in self.doc.alertas if a['key'] == 'fallo_envio_composicion']
        self.assertEqual(len(alerta), 1)
        self.assertEqual(alerta[0]['level'], 'warning')
        self.assertIn(nuevo.display_name, alerta[0]['message'])

    def test_envio_fallido_se_reintenta_con_el_mismo_xml_aunque_haya_recibo_nuevo(self):
        self._enviar(CONEXION)
        consecutivo = self.doc.consecutive
        self.env['l10n.co.ne.documento']._ne_preparar(self._recibo_nuevo_del_mes())
        intento = self._enviar(ACEPTADA)
        self.assertEqual(intento.numero, consecutivo)
        self.assertEqual(self.doc.state, 'invoice_accepted')

    def _sigue_sin_recomponerse(self, estado):
        self._intento(estado)
        originales = self.doc.payslip_ids
        nuevo = self._recibo_nuevo_del_mes()
        self.env['l10n.co.ne.documento']._ne_preparar(nuevo)
        self.assertEqual(self.doc.payslip_ids, originales)
        self.assertFalse(nuevo.l10n_co_ne_documento_id)

    def test_pendiente_sigue_sin_recomponerse(self):
        self._sigue_sin_recomponerse('invoice_pending')

    def test_rechazado_sigue_sin_recomponerse(self):
        self._sigue_sin_recomponerse('invoice_rejected')

    def test_documento_sin_estado_dian_si_se_recompone(self):
        originales = self.doc.payslip_ids
        nuevo = self._recibo_nuevo_del_mes()
        self.env['l10n.co.ne.documento']._ne_preparar(nuevo)
        self.assertEqual(self.doc.payslip_ids, originales | nuevo)
        self.assertFalse(self.doc.xml_attachment_id)                    # D5: el XML viejo ya no corresponde
