# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-DIAN-02 (doc 105 §2): en el ciclo POR RECIBO (habilitación) un tiempo de espera, un fallo SOAP o una respuesta sin veredicto no marcan el recibo «rechazado» ni dejan gastar otro consecutivo: queda
«incierto» y se concilia por CUNE. Todo con *mock*: nada llama a la DIAN."""

import base64
from datetime import date
from unittest.mock import MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils, soap_client, xml_signer

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION, PENDIENTE, RECHAZO
from .test_envio_ya_procesado import NO_CONOCIDA, REGLA_90

FALLA_SOAP = {'HttpStatus': 200, 'SOAPFault': 'fault', 'StatusCode': 'ERROR', 'RawRequest': b'<req/>'}


@tagged('post_install', '-at_install')
class TestEnvioPorReciboIncierto(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Envío por Recibo')

    def setUp(self):
        super().setUp()
        self._patch(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        self._patch(type(self.company), '_get_ne_certificate', lambda s: True)
        self._patch(dian_utils, 'clean_nit', lambda *a, **k: '900123456')
        self._patch(xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None))
        self.soap = MagicMock(name='send_nomina_sync', return_value=ACEPTADA)
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.consulta = MagicMock(name='get_status', return_value=PENDIENTE)
        self._patch(soap_client, 'get_status', self.consulta)
        self.company.write({'l10n_co_ne_environment': '2', 'l10n_co_ne_certification_process': False})
        self.slip = self._documento(date(2024, 3, 1)).payslip_ids[:1]
        self.slip.write({'l10n_co_ne_documento_id': False})
        adjunto = self.env['ir.attachment'].create({'name': 'ne.xml', 'datas': base64.b64encode(b'<NominaIndividual/>'), 'res_model': 'hr.payslip', 'res_id': self.slip.id})
        self.slip.write({'l10n_co_ne_state': 'generated', 'l10n_co_ne_consecutive': 'NE00009001', 'l10n_co_ne_cune': 'ab' * 48, 'l10n_co_ne_xml_attachment_id': adjunto.id})

    def _identidad(self):
        return self.slip.l10n_co_ne_consecutive, self.slip.l10n_co_ne_cune, self.slip.l10n_co_ne_xml_attachment_id

    def _enviar(self, respuesta):
        self.soap.return_value = respuesta
        self.slip.action_send_ne_dian()
        return self.slip.l10n_co_ne_state

    def _del_cune(self, base):
        return dict(base, XmlDocumentKey=self.slip.l10n_co_ne_cune)

    # ── el envío ─────────────────────────────────────────────────────
    def test_aceptado_con_cualquier_escritura_de_verdadero(self):
        self.assertEqual(self._enviar(dict(ACEPTADA, IsValid='TRUE')), 'accepted')
        self.assertEqual(self.slip.number, 'NE00009001')

    def test_un_rechazo_real_queda_rechazado_y_remite_a_regenerar(self):
        self.assertEqual(self._enviar(RECHAZO), 'rejected')
        self.assertTrue(self.slip.message_ids.filtered(lambda m: 'Regenerar XML' in str(m.body)))

    def test_sin_veredicto_queda_incierto_y_conserva_numero_cune_y_xml(self):
        antes = self._identidad()
        for nombre, respuesta in (('transporte', CONEXION), ('falla SOAP', FALLA_SOAP), ('pendiente', PENDIENTE)):
            with self.subTest(nombre):
                self.slip.l10n_co_ne_state = 'generated'
                self.assertEqual(self._enviar(respuesta), 'uncertain')
                self.assertEqual(self._identidad(), antes)
        self.assertEqual(self.env['l10n.co.ne.exchange'].search_count([('payslip_ids', 'in', self.slip.ids), ('operation', '=', 'send_sync')]), 3)

    def test_un_incierto_no_se_regenera_ni_se_reenvia(self):
        self._enviar(CONEXION)
        self.soap.reset_mock()
        antes = self._identidad()
        with self.assertRaisesRegex(UserError, 'consulte'):
            self.slip.action_regenerate_ne_xml()
        with self.assertRaises(UserError):
            self.slip.action_send_ne_dian()
        with self.assertRaises(UserError):
            self.slip.action_mass_send_ne_dian()
        self.soap.assert_not_called()
        self.assertEqual(self._identidad(), antes)

    # ── conciliación por CUNE ────────────────────────────────────────
    def test_la_consulta_por_cune_concilia_aceptado_y_rechazado(self):
        for respuesta, estado in ((ACEPTADA, 'accepted'), (RECHAZO, 'rejected')):
            with self.subTest(estado):
                self.slip.l10n_co_ne_state = 'generated'
                self._enviar(CONEXION)
                self.consulta.return_value = self._del_cune(respuesta)
                self.slip.action_check_dian_status()
                self.assertEqual(self.slip.l10n_co_ne_state, estado)
                self.assertEqual(self.consulta.call_args.kwargs['track_id'], self.slip.l10n_co_ne_cune)

    def test_una_consulta_no_concluyente_deja_el_recibo_incierto(self):
        self._enviar(CONEXION)
        aceptado = self._del_cune(ACEPTADA)
        casos = (('transporte', CONEXION), ('pendiente', PENDIENTE), ('otro CUNE', dict(ACEPTADA, XmlDocumentKey='z' * 96)), ('sin identificar', dict(ACEPTADA)),
                 ('varios', dict(aceptado, DianResponses=[aceptado, dict(aceptado)])))
        for nombre, respuesta in casos:
            with self.subTest(nombre):
                self.consulta.return_value = respuesta
                self.slip.action_check_dian_status()
                self.assertEqual(self.slip.l10n_co_ne_state, 'uncertain')

    def test_si_la_dian_no_conoce_el_cune_puede_enviarse_otra_vez_el_mismo_xml(self):
        self._enviar(CONEXION)
        antes = self._identidad()
        self.consulta.return_value = NO_CONOCIDA
        self.slip.action_check_dian_status()
        self.assertEqual(self.slip.l10n_co_ne_state, 'generated')
        self.assertEqual(self._identidad(), antes)
        self.assertEqual(self._enviar(ACEPTADA), 'accepted')

    def test_la_regla_90_se_concilia_en_el_acto(self):
        self.consulta.side_effect = lambda **kw: self._del_cune(ACEPTADA)
        self.assertEqual(self._enviar(REGLA_90), 'accepted')

    def test_la_regla_90_sin_veredicto_queda_incierto(self):
        self.consulta.return_value = CONEXION
        self.assertEqual(self._enviar(REGLA_90), 'uncertain')

    # ── el motor de habilitación (condición para no romperlo) ────────
    def test_el_motor_no_regenera_un_incierto(self):
        self._enviar(CONEXION)
        motor = self.env['l10n.co.ne.habilitacion']
        self._patch(type(motor), '_set_slips', lambda s, company: self.slip)
        self.assertEqual(motor._replace_failed(self.company), 0)
        self.assertEqual(self.slip.l10n_co_ne_state, 'uncertain')
