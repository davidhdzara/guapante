# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 7a (doc 53 §23.17): ``GetStatus`` por CUNE (Anexo §9.8) y ``documento._ne_reconsultar_por_cune``.

Todo con *mock*: ``requests.post`` y ``soap_client.get_status`` se parchean, nada llama a la DIAN. El formato REAL de la
respuesta contra la DIAN es NO VERIFICADO (D-A): se confirma en el piloto de producción; aquí solo el ejemplo del Anexo.
"""

import copy
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import BaseCase, TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION, PENDIENTE, RECHAZO
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo

# Respuesta de GetStatus del Anexo §9.8.2: UN resultado, sin ZipKey, con XmlDocumentKey = CUNE consultado.
RESPUESTA_ANEXO = (
    b'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body>'
    b'<GetStatusResponse xmlns="http://wcf.dian.colombia">'
    b'<GetStatusResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse" '
    b'xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
    b'<b:IsValid>false</b:IsValid><b:StatusCode>99</b:StatusCode>'
    b'<b:StatusDescription>Validacion contiene errores en campos mandatorios.</b:StatusDescription>'
    b'<b:XmlDocumentKey>660ebb7f</b:XmlDocumentKey></GetStatusResult>'
    b'</GetStatusResponse></s:Body></s:Envelope>')


@tagged('post_install', '-at_install')
class TestSoapGetStatus(BaseCase):

    def _llamar(self, contenido=RESPUESTA_ANEXO, status=200):
        respuesta = MagicMock(status_code=status, content=contenido)
        with patch.object(soap_client, '_build_envelope', return_value=b'<envelope/>') as envelope, \
                patch.object(soap_client.requests, 'post', return_value=respuesta) as post:
            resultado = soap_client.get_status('660ebb7f', cert_der_b64='AAAA', endpoint='https://dian.test/ws')
        return resultado, envelope, post

    def test_arma_el_request_con_el_cune_como_track_id(self):
        _resultado, envelope, post = self._llamar()
        accion, endpoint, cuerpo = envelope.call_args.args[:3]
        self.assertEqual(accion, soap_client.SOAP_ACTION_GET_STATUS_CUNE)
        self.assertTrue(accion.endswith('/GetStatus'))
        self.assertNotEqual(accion, soap_client.SOAP_ACTION_GET_STATUS)   # esa es GetStatusZip
        self.assertIn('<wcf:GetStatus ', cuerpo)
        self.assertIn('<wcf:trackId>660ebb7f</wcf:trackId>', cuerpo)
        self.assertEqual(post.call_args.args[0], 'https://dian.test/ws')

    def test_parsea_el_resultado_unico_del_anexo(self):
        resultado, _envelope, _post = self._llamar()
        self.assertEqual(resultado['StatusCode'], '99')
        self.assertEqual(resultado['XmlDocumentKey'], '660ebb7f')
        self.assertEqual(len(resultado['DianResponses']), 1)

    def test_sin_certificado_no_llama(self):
        with patch.object(soap_client.requests, 'post') as post:
            resultado = soap_client.get_status('x')
        post.assert_not_called()
        self.assertEqual(resultado['StatusCode'], 'ERROR')

    def test_fallo_de_conexion_es_error_de_transporte(self):
        with patch.object(soap_client, '_build_envelope', return_value=b'<e/>'), \
                patch.object(soap_client.requests, 'post', side_effect=soap_client.requests.ConnectionError('x')), \
                mute_logger('odoo.addons.l10n_co_nomina_electronica.services.soap_client'):
            resultado = soap_client.get_status('x', cert_der_b64='AAAA')
        self.assertEqual(resultado['StatusCode'], 'CONNECTION_ERROR')


@tagged('post_install', '-at_install')
class TestDocumentoReconsultarPorCune(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Consulta CUNE')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE cune', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
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
        self.consulta = MagicMock(name='get_status')
        self._patch(soap_client, 'get_status', self.consulta)
        self.doc = self._documento(date(2024, 3, 1))
        self.doc._ne_validar()
        self.doc.action_generar_xml()
        self.doc.incierto = True      # el proceso murió tras el envío: sin intento ni ZipKey

    def _respuesta(self, base, **extra):
        return dict(base, XmlDocumentKey=self.doc.cune, **extra)

    def test_aceptado_sin_intento_crea_el_intento_y_limpia_incierto(self):
        self.consulta.return_value = self._respuesta(ACEPTADA)
        resultado = self.doc._ne_reconsultar_por_cune()
        self.assertEqual(resultado.veredicto, 'aceptado')
        self.assertEqual(self.consulta.call_args.kwargs['track_id'], self.doc.cune)
        self.assertEqual(len(self.doc.intento_ids), 1)
        intento = self.doc.intento_ids
        self.assertEqual((intento.state, intento.identifier, intento.numero),
                         ('invoice_accepted', self.doc.cune, self.doc.consecutive))
        self.assertTrue(intento.exchange_id)
        self.assertEqual(intento.exchange_id.operation, 'get_status')
        self.assertEqual(self.doc.state, 'invoice_accepted')
        self.assertFalse(self.doc.incierto)

    def test_rechazado_sin_intento_crea_intento_rechazado(self):
        self.consulta.return_value = self._respuesta(RECHAZO)
        self.doc._ne_reconsultar_por_cune()
        self.assertEqual(self.doc.state, 'invoice_rejected')
        self.assertFalse(self.doc.incierto)

    def test_con_intento_pendiente_se_actualiza_el_mismo(self):
        pendiente = self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.doc.id, 'state': 'invoice_pending', 'identifier': self.doc.cune,
            'numero': self.doc.consecutive, 'datetime': datetime(2026, 4, 1)})
        self.consulta.return_value = self._respuesta(ACEPTADA)
        self.doc._ne_reconsultar_por_cune()
        self.assertEqual(len(self.doc.intento_ids), 1)
        self.assertEqual(pendiente.state, 'invoice_accepted')

    def test_cune_ajeno_no_cambia_estado_y_sigue_incierto(self):
        self.consulta.return_value = dict(ACEPTADA, XmlDocumentKey='z' * 96)
        self.doc._ne_reconsultar_por_cune()
        self.assertFalse(self.doc.intento_ids)
        self.assertFalse(self.doc.state)
        self.assertTrue(self.doc.incierto)

    def test_respuesta_sin_identificador_no_cambia_estado_y_sigue_incierto(self):
        self.consulta.return_value = dict(ACEPTADA)
        self.doc._ne_reconsultar_por_cune()
        self.assertFalse(self.doc.intento_ids)
        self.assertTrue(self.doc.incierto)

    def test_varios_resultados_no_cambian_estado_y_siguen_inciertos(self):
        uno = self._respuesta(ACEPTADA)
        self.consulta.return_value = dict(uno, DianResponses=[uno, dict(uno)])
        self.doc._ne_reconsultar_por_cune()
        self.assertFalse(self.doc.intento_ids)
        self.assertFalse(self.doc.state)
        self.assertTrue(self.doc.incierto)

    def test_pendiente_y_error_de_transporte_no_cambian_nada(self):
        for respuesta in (self._respuesta(PENDIENTE), CONEXION):
            self.consulta.return_value = respuesta
            self.doc._ne_reconsultar_por_cune()
            self.assertFalse(self.doc.intento_ids)
            self.assertTrue(self.doc.incierto)
        # la evidencia se guarda siempre
        self.assertEqual(len(self.doc.exchange_ids.filtered(lambda e: e.operation == 'get_status')), 2)

    def test_precondiciones_no_llaman_a_la_dian(self):
        casos = {}
        self.doc.eliminado = True
        casos['eliminado'] = 'eliminado'
        with self.assertRaisesRegex(UserError, casos['eliminado']):
            self.doc._ne_reconsultar_por_cune()
        self.doc.eliminado = False
        self.doc.cune = False
        with self.assertRaisesRegex(UserError, 'no tiene CUNE'):
            self.doc._ne_reconsultar_por_cune()
        self.doc.cune = 'x' * 96
        self.company.l10n_co_ne_environment = '2'          # habilitación
        with self.assertRaisesRegex(UserError, 'habilitación'):
            self.doc._ne_reconsultar_por_cune()
        self.consulta.assert_not_called()

    def test_con_veredicto_ya_registrado_no_se_consulta(self):
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.doc.id, 'state': 'invoice_accepted', 'identifier': self.doc.cune,
            'numero': self.doc.consecutive, 'datetime': datetime(2026, 4, 1)})
        with self.assertRaisesRegex(UserError, 'ya tiene veredicto'):
            self.doc._ne_reconsultar_por_cune()
        self.consulta.assert_not_called()

    def test_wizard_del_cune_usa_el_documento_mensual(self):
        self.consulta.return_value = self._respuesta(ACEPTADA)
        wizard = self.env['l10n.co.ne.status.cune.wizard'].create({'cune': self.doc.cune})
        accion = wizard.action_check_status()
        self.assertEqual(accion['res_model'], 'l10n.co.ne.documento')
        self.assertEqual(accion['res_id'], self.doc.id)
        self.assertEqual(self.doc.state, 'invoice_accepted')
