# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Servicio ``services/dian_respuesta`` (parte A: commit 1; parte B: commit 2, doc 53 §23.12-§23.14).

Clases:
- ``TestDianRespuestaPura`` (``BaseCase``, sin base de datos): los 4 helpers con valores a mano.
- ``TestInterpretarRespuesta`` (``BaseCase``): veredicto neutral, ``es_rechazo`` y ``diagnosticar``
  (parte B; todavía no la usa ningún modelo).
- ``TestMixinEnvoltorios`` (``TransactionCase``): los 4 nombres que conserva el mixin del recibo
  devuelven EXACTAMENTE lo mismo que el servicio (el recibo no cambió).
"""

from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_respuesta

_NS = ('xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
       'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"')

# ApplicationResponse real: el CUNE viaja en DocumentReference/UUID (AUD-DIAN-34).
_APP_CON_CUNE = (
    '<ApplicationResponse %s><cac:DocumentResponse><cac:DocumentReference>'
    '<cbc:UUID schemeName="CUNE-SHA384">abc123cune</cbc:UUID>'
    '</cac:DocumentReference></cac:DocumentResponse></ApplicationResponse>' % _NS)
# Solo el NÚMERO (cbc:ID bajo DocumentReference).
_APP_CON_NUMERO = (
    '<ApplicationResponse %s><cac:DocumentResponse><cac:DocumentReference>'
    '<cbc:ID>NE0000000009</cbc:ID>'
    '</cac:DocumentReference></cac:DocumentResponse></ApplicationResponse>' % _NS)
# UUID/ID de nivel raíz: identidad de la respuesta, NO del documento referenciado.
_APP_SOLO_RAIZ = '<ApplicationResponse><UUID>RESP-UUID</UUID><ID>RESP-ID</ID></ApplicationResponse>'

# Respuesta de nivel SET (H-012): StatusCode 2, IsValid false, sin datos del documento.
_RESPUESTA_SET = {
    'StatusCode': '2',
    'IsValid': 'false',
    'StatusDescription': 'Set de prueba con identificador e07c1748-0000-0000-0000-000000000000 '
                         'se encuentra Aceptado.',
}


@tagged('post_install', '-at_install')
class TestDianRespuestaPura(BaseCase):

    # --- texto_respuesta ---------------------------------------------------------------------
    def test_texto_vacio_o_none_devuelve_cadena_vacia(self):
        self.assertEqual(dian_respuesta.texto_respuesta(None), '')
        self.assertEqual(dian_respuesta.texto_respuesta(''), '')
        self.assertEqual(dian_respuesta.texto_respuesta(b''), '')

    def test_texto_bytes_con_acentos_se_decodifica_utf8(self):
        self.assertEqual(
            dian_respuesta.texto_respuesta('Validación Nómina'.encode('utf-8')),
            'Validación Nómina')

    def test_texto_bytes_invalidos_se_reemplazan_no_fallan(self):
        self.assertEqual(dian_respuesta.texto_respuesta(b'\xff'), '�')

    def test_texto_se_recorta_exactamente_a_5000(self):
        self.assertEqual(len(dian_respuesta.texto_respuesta('a' * 6000)), 5000)
        exacto = 'b' * 5000
        self.assertEqual(dian_respuesta.texto_respuesta(exacto), exacto)
        self.assertEqual(len(dian_respuesta.texto_respuesta('c' * 4999)), 4999)

    def test_texto_limite_personalizado(self):
        self.assertEqual(dian_respuesta.texto_respuesta('abcdef', limite=3), 'abc')

    # --- candidatos_cune ---------------------------------------------------------------------
    def test_cune_sin_datos_es_conjunto_vacio(self):
        self.assertEqual(dian_respuesta.candidatos_cune({}), set())

    def test_cune_de_cada_una_de_las_tres_claves_con_espacios(self):
        for clave in ('XmlDocumentKey', 'CUNE', 'DocumentKey'):
            self.assertEqual(
                dian_respuesta.candidatos_cune({clave: '  abc  '}), {'abc'}, clave)

    def test_cune_tres_claves_distintas_y_una_repetida(self):
        result = {'XmlDocumentKey': 'a', 'CUNE': 'b', 'DocumentKey': 'a'}
        self.assertEqual(dian_respuesta.candidatos_cune(result), {'a', 'b'})

    def test_cune_desde_application_response(self):
        self.assertEqual(
            dian_respuesta.candidatos_cune({'ApplicationResponse': _APP_CON_CUNE}),
            {'abc123cune'})

    def test_cune_une_claves_y_application_response(self):
        result = {'XmlDocumentKey': 'otro', 'ApplicationResponse': _APP_CON_CUNE}
        self.assertEqual(dian_respuesta.candidatos_cune(result), {'otro', 'abc123cune'})

    def test_cune_ignora_uuid_de_nivel_raiz(self):
        self.assertEqual(
            dian_respuesta.candidatos_cune({'ApplicationResponse': _APP_SOLO_RAIZ}), set())

    # --- candidatos_numero -------------------------------------------------------------------
    def test_numero_sin_application_response_es_vacio(self):
        self.assertEqual(dian_respuesta.candidatos_numero({}), set())
        self.assertEqual(dian_respuesta.candidatos_numero({'ApplicationResponse': ''}), set())

    def test_numero_desde_document_reference_id(self):
        self.assertEqual(
            dian_respuesta.candidatos_numero({'ApplicationResponse': _APP_CON_NUMERO}),
            {'NE0000000009'})

    def test_numero_no_confunde_el_cune_ni_el_id_raiz(self):
        self.assertEqual(
            dian_respuesta.candidatos_numero({'ApplicationResponse': _APP_CON_CUNE}), set())
        self.assertEqual(
            dian_respuesta.candidatos_numero({'ApplicationResponse': _APP_SOLO_RAIZ}), set())

    # --- es_respuesta_de_set -----------------------------------------------------------------
    def test_set_es_detectado(self):
        self.assertTrue(dian_respuesta.es_respuesta_de_set(_RESPUESTA_SET))

    def test_set_con_espacios_en_el_codigo(self):
        self.assertTrue(dian_respuesta.es_respuesta_de_set(dict(_RESPUESTA_SET, StatusCode=' 2 ')))

    def test_set_sin_is_valid_cuenta_como_no_valido(self):
        self.assertTrue(dian_respuesta.es_respuesta_de_set({'StatusCode': '2'}))

    def test_documento_aceptado_no_es_de_set(self):
        normal = {'StatusCode': '00', 'IsValid': 'true', 'XmlDocumentKey': 'CUNE-X'}
        self.assertFalse(dian_respuesta.es_respuesta_de_set(normal))

    def test_rechazo_no_es_de_set(self):
        rechazo = {'StatusCode': '99', 'IsValid': 'false', 'ErrorMessages': ['x']}
        self.assertFalse(dian_respuesta.es_respuesta_de_set(rechazo))

    def test_set_is_valid_true_en_cualquier_mayuscula_no_es_de_set(self):
        for valor in ('true', 'True', 'TRUE'):
            self.assertFalse(
                dian_respuesta.es_respuesta_de_set(dict(_RESPUESTA_SET, IsValid=valor)), valor)

    def test_set_con_datos_del_documento_no_es_de_set(self):
        self.assertFalse(dian_respuesta.es_respuesta_de_set(
            dict(_RESPUESTA_SET, XmlDocumentKey='CUNE-X')))
        self.assertFalse(dian_respuesta.es_respuesta_de_set(
            dict(_RESPUESTA_SET, ApplicationResponse=_APP_CON_CUNE)))


@tagged('post_install', '-at_install')
class TestInterpretarRespuesta(BaseCase):
    """Parte B (commit 2): veredicto neutral. Valores a mano; ningún modelo la usa todavía."""

    def _v(self, response, contexto='envio'):
        return dian_respuesta.interpretar_respuesta(response, contexto=contexto)

    # --- aceptado ------------------------------------------------------------------------------
    def test_aceptado_con_mensaje_y_zip_key(self):
        r = self._v({'IsValid': 'true', 'StatusCode': '00',
                     'StatusDescription': 'Procesado Correctamente.', 'ZipKey': 'z1'})
        self.assertEqual(r.veredicto, 'aceptado')
        self.assertEqual(r.mensaje, 'Procesado Correctamente.')
        self.assertEqual(r.zip_key, 'z1')
        self.assertEqual(r.errores, ())
        self.assertIsNone(r.diagnostico)

    def test_is_valid_true_en_cualquier_mayuscula_es_aceptado(self):
        for valor in ('true', 'True', 'TRUE'):
            for contexto in ('envio', 'consulta'):
                self.assertEqual(
                    self._v({'IsValid': valor, 'StatusCode': '00'}, contexto).veredicto,
                    'aceptado', '%s/%s' % (valor, contexto))

    # --- rechazado -----------------------------------------------------------------------------
    def test_rechazo_con_regla_en_error_messages(self):
        r = self._v({'IsValid': 'false', 'StatusCode': '99',
                     'ErrorMessages': ['Regla: NIAE191a, Rechazo: valor inválido']})
        self.assertEqual(r.veredicto, 'rechazado')
        self.assertEqual(r.errores, ('Regla: NIAE191a, Rechazo: valor inválido',))
        self.assertEqual(r.mensaje, 'Regla: NIAE191a, Rechazo: valor inválido')
        self.assertIsNone(r.diagnostico)

    def test_rechazo_solo_por_error_messages_sin_status_99(self):
        r = self._v({'IsValid': 'false', 'StatusCode': '', 'ErrorMessages': ['x', 'y']})
        self.assertEqual(r.veredicto, 'rechazado')
        self.assertEqual(r.errores, ('x', 'y'))
        self.assertEqual(r.mensaje, 'x; y')

    def test_rechazo_con_error_message_unico(self):
        r = self._v({'IsValid': 'false', 'StatusCode': '99', 'ErrorMessage': 'NIE072 falla'})
        self.assertEqual(r.veredicto, 'rechazado')
        self.assertEqual(r.errores, ('NIE072 falla',))

    def test_rechazo_lleva_el_diagnostico(self):
        r = self._v({'IsValid': 'false', 'StatusCode': '99',
                     'ErrorMessages': ['El NIT del empleador es inválido']})
        self.assertEqual(r.veredicto, 'rechazado')
        self.assertEqual(r.diagnostico, 'identificacion')

    def test_http_4xx_con_veredicto_dian_si_es_rechazo(self):
        """Un HTTP 4xx que SÍ trae IsValid es un veredicto de la DIAN, no un fallo de transporte."""
        r = self._v({'HttpStatus': 400, 'IsValid': 'false', 'StatusCode': '99',
                     'ErrorMessages': ['x']})
        self.assertEqual(r.veredicto, 'rechazado')

    # --- pendiente -----------------------------------------------------------------------------
    def test_pendiente_batch_en_proceso(self):
        r = self._v({'IsValid': 'false', 'StatusCode': '0', 'ZipKey': 'abc',
                     'StatusDescription': 'Batch en proceso de validación.'})
        self.assertEqual(r.veredicto, 'pendiente')
        self.assertEqual(r.zip_key, 'abc')
        self.assertEqual(r.mensaje, 'Batch en proceso de validación.')

    def test_pendiente_nunca_es_rechazo_aunque_no_sea_valido(self):
        for contexto in ('envio', 'consulta'):
            self.assertEqual(
                self._v({'IsValid': 'false', 'StatusCode': '90'}, contexto).veredicto, 'pendiente')

    # --- error_transporte ----------------------------------------------------------------------
    def test_transporte_connection_error(self):
        r = self._v({'StatusCode': 'CONNECTION_ERROR', 'ErrorMessage': 'timeout',
                     'TransportError': 'timeout'})
        self.assertEqual(r.veredicto, 'error_transporte')
        self.assertEqual(r.errores, ('timeout',))
        self.assertIsNone(r.diagnostico)

    def test_transporte_solo_con_transport_error_o_solo_con_status(self):
        self.assertEqual(self._v({'TransportError': 'x'}).veredicto, 'error_transporte')
        self.assertEqual(self._v({'StatusCode': 'CONNECTION_ERROR'}).veredicto, 'error_transporte')

    def test_transporte_http_5xx_aunque_traiga_is_valid_false(self):
        self.assertEqual(
            self._v({'HttpStatus': 503, 'IsValid': 'false', 'StatusCode': '503'}).veredicto,
            'error_transporte')
        self.assertEqual(self._v({'HttpStatus': 500}).veredicto, 'error_transporte')

    def test_transporte_http_4xx_sin_is_valid(self):
        """Decisión TL: un HTTP 4xx no es un veredicto sobre el documento. ``soap_client`` rellena
        StatusCode con el código HTTP, así que el StatusCode '404' no cuenta como veredicto."""
        for http in (400, 401, 403, 404, 429):
            r = self._v({'HttpStatus': http, 'StatusCode': str(http),
                         'ErrorMessage': 'HTTP %d: respuesta no SOAP' % http})
            self.assertEqual(r.veredicto, 'error_transporte', http)

    def test_transporte_falla_soap(self):
        self.assertEqual(self._v({'SOAPFault': True, 'FaultDetails': ['SOAP failed']}).veredicto,
                         'error_transporte')
        self.assertEqual(self._v({'FaultDetails': ['x']}).veredicto, 'error_transporte')

    def test_transporte_sin_is_valid_ni_status_code(self):
        self.assertEqual(self._v({}).veredicto, 'error_transporte')
        self.assertEqual(self._v({'StatusDescription': 'algo'}).veredicto, 'error_transporte')

    def test_transporte_http_invalido_no_revienta(self):
        self.assertEqual(
            self._v({'HttpStatus': 'x', 'IsValid': 'true', 'StatusCode': '00'}).veredicto,
            'aceptado')

    # --- nivel_set -----------------------------------------------------------------------------
    def test_nivel_set_solo_en_consulta(self):
        self.assertEqual(self._v(_RESPUESTA_SET, 'consulta').veredicto, 'nivel_set')
        self.assertEqual(self._v(_RESPUESTA_SET, 'envio').veredicto, 'pendiente')

    def test_transporte_va_antes_que_nivel_set(self):
        r = self._v(dict(_RESPUESTA_SET, TransportError='x'), 'consulta')
        self.assertEqual(r.veredicto, 'error_transporte')

    # --- contexto ------------------------------------------------------------------------------
    def test_contexto_invalido_lanza_value_error(self):
        with self.assertRaises(ValueError):
            dian_respuesta.interpretar_respuesta({'IsValid': 'true'}, contexto='otro')

    def test_contexto_es_obligatorio_y_solo_por_nombre(self):
        with self.assertRaises(TypeError):
            dian_respuesta.interpretar_respuesta({'IsValid': 'true'})
        with self.assertRaises(TypeError):
            dian_respuesta.interpretar_respuesta({'IsValid': 'true'}, 'envio')

    def test_mensaje_prefiere_status_description_y_luego_status_message(self):
        self.assertEqual(
            self._v({'IsValid': 'true', 'StatusDescription': 'a', 'StatusMessage': 'b'}).mensaje, 'a')
        self.assertEqual(
            self._v({'IsValid': 'true', 'StatusMessage': 'b'}).mensaje, 'b')
        self.assertEqual(self._v({'IsValid': 'true'}).mensaje, '')

    # --- es_rechazo ----------------------------------------------------------------------------
    def test_es_rechazo(self):
        self.assertTrue(dian_respuesta.es_rechazo({'StatusCode': '99'}))
        self.assertTrue(dian_respuesta.es_rechazo({'StatusCode': ' 99 '}))
        self.assertTrue(dian_respuesta.es_rechazo({'ErrorMessages': ['x']}))
        self.assertFalse(dian_respuesta.es_rechazo({'StatusCode': '90'}))
        self.assertFalse(dian_respuesta.es_rechazo({'ErrorMessages': []}))
        self.assertFalse(dian_respuesta.es_rechazo({}))

    # --- diagnosticar --------------------------------------------------------------------------
    def test_diagnosticar_las_cuatro_clasificaciones(self):
        self.assertEqual(dian_respuesta.diagnosticar('NIT inválido'), 'identificacion')
        self.assertEqual(dian_respuesta.diagnosticar('falta el documento'), 'identificacion')
        self.assertEqual(dian_respuesta.diagnosticar('identificacion errada'), 'identificacion')
        self.assertEqual(dian_respuesta.diagnosticar('Correo mal formado'), 'correo')
        self.assertEqual(dian_respuesta.diagnosticar('email vacío'), 'correo')
        self.assertEqual(dian_respuesta.diagnosticar('Cuenta bancaria'), 'cuenta')
        self.assertEqual(dian_respuesta.diagnosticar('banco no válido'), 'cuenta')
        self.assertEqual(dian_respuesta.diagnosticar('metodo de pago'), 'cuenta')
        self.assertEqual(dian_respuesta.diagnosticar('Salario menor al minimo'), 'salario')
        self.assertEqual(dian_respuesta.diagnosticar('IBC distinto'), 'salario')

    def test_diagnosticar_la_primera_coincidencia_gana(self):
        self.assertEqual(dian_respuesta.diagnosticar('NIT y correo'), 'identificacion')
        self.assertEqual(dian_respuesta.diagnosticar('correo y cuenta'), 'correo')
        self.assertEqual(dian_respuesta.diagnosticar('cuenta y salario'), 'cuenta')

    def test_diagnosticar_sin_coincidencia_o_vacio(self):
        self.assertIsNone(dian_respuesta.diagnosticar('Regla: NIAE191a'))
        self.assertIsNone(dian_respuesta.diagnosticar(''))
        self.assertIsNone(dian_respuesta.diagnosticar(None))

    def test_diagnosticar_conserva_la_regla_actual_sin_tilde(self):
        """Defecto menor registrado (§23.13): 'identificación' CON tilde no coincide; se conserva."""
        self.assertIsNone(dian_respuesta.diagnosticar('error de identificación'))


@tagged('post_install', '-at_install')
class TestMixinEnvoltorios(TransactionCase):
    """Los 4 nombres del mixin del recibo devuelven lo mismo que el servicio."""

    def setUp(self):
        super().setUp()
        self.payslip = self.env['hr.payslip']

    def test_envoltorio_response_text(self):
        for valor in (None, '', 'texto', 'ñ'.encode('utf-8'), 'z' * 6000):
            self.assertEqual(
                self.payslip._ne_response_text(valor), dian_respuesta.texto_respuesta(valor))

    def test_envoltorio_cune_candidates(self):
        for result in ({}, {'CUNE': ' x '}, {'ApplicationResponse': _APP_CON_CUNE}):
            self.assertEqual(
                self.payslip._ne_cune_candidates(result), dian_respuesta.candidatos_cune(result))

    def test_envoltorio_number_candidates(self):
        for result in ({}, {'ApplicationResponse': _APP_CON_NUMERO}):
            self.assertEqual(
                self.payslip._ne_number_candidates(result),
                dian_respuesta.candidatos_numero(result))

    def test_envoltorio_is_set_level_status(self):
        for response in (_RESPUESTA_SET, {'StatusCode': '00', 'IsValid': 'true'},
                         {'StatusCode': '99', 'IsValid': 'false', 'ErrorMessages': ['x']}):
            self.assertEqual(
                self.payslip._ne_is_set_level_status(response),
                dian_respuesta.es_respuesta_de_set(response))
