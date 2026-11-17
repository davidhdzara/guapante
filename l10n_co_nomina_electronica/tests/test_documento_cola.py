# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 7b (doc 53 §23.17): cola de envío del documento mensual y su cron. Todo con *mock*: ``send_nomina_sync``
se parchea (nada llama a la DIAN), el bus y ``_trigger`` también; ``_ne_commit`` no hace commit dentro de una prueba."""

import copy
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION, PENDIENTE, RECHAZO
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo

LOGGER_DOCUMENTO = 'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento'


@tagged('post_install', '-at_install')
class TestDocumentoCola(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Cola Envío')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE cola', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
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
        self.soap = MagicMock(name='send_nomina_sync', return_value=ACEPTADA)
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.trigger = MagicMock(name='_trigger')
        self._patch(type(self.env['ir.cron']), '_trigger', self.trigger)
        self.bus = MagicMock(name='_sendone')
        self._patch(type(self.env['bus.bus']), '_sendone', self.bus)
        self.Doc = self.env['l10n.co.ne.documento']

    def _listo(self, **kwargs):
        doc = self._documento(date(2024, 3, 1), **kwargs)
        doc._ne_validar()
        doc.action_generar_xml()
        return doc

    def _encolados(self, n):
        docs = self.Doc
        for _i in range(n):
            docs |= self._listo()
        docs._ne_encolar()
        self.trigger.reset_mock()
        return docs

    def _cron(self):
        self.Doc._cron_enviar_cola()

    # ── encolar ──────────────────────────────────────────────────────
    def test_encolar_escribe_autor_y_dispara_una_vez(self):
        a, b = self._listo(), self._listo()
        (a | b)._ne_encolar()
        for doc in (a, b):
            self.assertTrue(doc.is_being_sent)
            self.assertEqual(doc.sending_data['author_user_id'], self.env.user.id)
            self.assertEqual(doc.sending_data['author_partner_id'], self.env.user.partner_id.id)
            self.assertEqual(doc.sending_data['intentos'], 0)
            self.assertTrue(doc.sending_data['proximo'])
        self.assertEqual(self.trigger.call_count, 1)
        self.soap.assert_not_called()                       # encolar NO envía

    def test_encolar_dos_veces_no_duplica(self):
        doc = self._listo()
        doc._ne_encolar()
        with self.assertRaisesRegex(UserError, 'ya está en la cola'):
            doc._ne_encolar()
        self.assertEqual(self.trigger.call_count, 1)

    def test_encolar_con_precondicion_incumplida_no_encola_ninguno(self):
        bueno, malo = self._listo(), self._listo()
        malo.xml_attachment_id = False
        with self.assertRaisesRegex(UserError, 'Genere el XML'):
            (bueno | malo)._ne_encolar()
        self.assertFalse(bueno.is_being_sent or malo.is_being_sent)
        self.trigger.assert_not_called()

    def test_encolar_en_habilitacion_da_error(self):
        doc = self._listo()
        self.company.l10n_co_ne_environment = '2'
        with self.assertRaisesRegex(UserError, 'habilitación'):
            doc._ne_encolar()
        self.assertFalse(doc.is_being_sent)

    def test_encolar_con_el_cron_archivado_da_error_claro(self):
        doc = self._listo()
        self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_documento_send').active = False
        with self.assertRaisesRegex(UserError, 'archivada'):
            doc._ne_encolar()
        self.assertFalse(doc.is_being_sent)

    # ── cron: lote, orden, aislamiento ───────────────────────────────
    def test_el_cron_respeta_el_tamano_del_lote_y_se_redispara(self):
        docs = self._encolados(3)
        self.env['ir.config_parameter'].sudo().set_param('l10n_co_nomina_electronica.send_batch_size', '2')
        self._cron()
        self.assertEqual(self.soap.call_count, 2)
        self.assertEqual(docs[:2].mapped('state'), ['invoice_accepted'] * 2)     # orden mes/id
        self.assertTrue(docs[2].is_being_sent)
        self.assertEqual(self.trigger.call_count, 1)                             # re-dispara: quedan

    def test_commit_previo_antes_de_la_llamada_y_otro_despues(self):
        doc = self._encolados(1)
        eventos = []
        self._patch(type(self.Doc), '_ne_commit', lambda s: eventos.append('commit'))

        def envio(**kwargs):
            eventos.append('soap')
            return ACEPTADA
        self.soap.side_effect = envio
        self._cron()
        self.assertEqual(eventos[:3], ['commit', 'soap', 'commit'])
        self.assertEqual(doc.state, 'invoice_accepted')

    def test_aislamiento_un_fallo_de_conexion_no_frena_a_los_demas(self):
        a, b, c = self._encolados(3)
        self.soap.side_effect = [ACEPTADA, CONEXION, ACEPTADA]
        consecutivo_b = b.consecutive
        self._cron()
        self.assertEqual(a.state, 'invoice_accepted')
        self.assertEqual(b.state, 'invoice_sending_failed')
        self.assertEqual(b.consecutive, consecutivo_b)                           # consecutivo intacto
        self.assertTrue(b.is_being_sent)
        self.assertEqual(b.sending_data['intentos'], 1)
        self.assertGreater(fields.Datetime.to_datetime(b.sending_data['proximo']), fields.Datetime.now())
        self.assertEqual(c.state, 'invoice_accepted')

    def test_rechazo_y_pendiente_no_se_reintentan(self):
        a, b = self._encolados(2)
        self.soap.side_effect = [RECHAZO, PENDIENTE]
        self._cron()
        self.assertEqual((a.state, b.state), ('invoice_rejected', 'invoice_pending'))
        self.assertFalse(a.is_being_sent or b.is_being_sent)

    def test_espera_creciente_con_tope(self):
        self.assertEqual([self.Doc._ne_espera_reintento(n, self.company) for n in range(1, 7)],
                         [5, 10, 20, 40, 60, 60])

    def test_agotados_los_reintentos_se_limpia_la_cola(self):
        doc = self._encolados(1)
        datos = dict(doc.sending_data, intentos=5)
        doc.sending_data = datos
        self.soap.return_value = CONEXION
        self._cron()
        self.assertEqual(doc.state, 'invoice_sending_failed')
        self.assertFalse(doc.is_being_sent)
        self.assertTrue(doc.message_ids.filtered(lambda m: 'agotaron los reintentos' in str(m.body)))

    def test_no_procesa_antes_de_proximo(self):
        doc = self._encolados(1)
        doc.sending_data = dict(doc.sending_data, proximo=fields.Datetime.to_string(
            fields.Datetime.now() + timedelta(hours=1)))
        self._cron()
        self.soap.assert_not_called()
        self.assertTrue(doc.is_being_sent)

    def test_error_local_no_se_reintenta_y_queda_en_el_chatter(self):
        doc = self._encolados(1)
        doc.etapa = 'draft'                       # la configuración cambió desde que se encoló
        self._cron()
        self.soap.assert_not_called()
        self.assertFalse(doc.intento_ids)
        self.assertFalse(doc.is_being_sent)       # el error se notificó y se limpió
        self.assertTrue(doc.message_ids.filtered(lambda m: 'No se envió el documento desde la cola' in str(m.body)))

    def test_excepcion_inesperada_deja_incierto(self):
        doc = self._encolados(1)
        self.soap.side_effect = RuntimeError('se cayó')
        with mute_logger(LOGGER_DOCUMENTO):
            self._cron()
        self.assertTrue(doc.incierto)
        self.assertFalse(doc.is_being_sent)
        self.assertFalse(doc.intento_ids)

    # ── barrido ──────────────────────────────────────────────────────
    def _en_curso(self, doc, minutos):
        doc.sending_data = dict(doc.sending_data, en_curso=fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(minutes=minutos)))

    def test_barrido_en_curso_viejo_sin_intento_pasa_a_incierto(self):
        doc = self._encolados(1)
        self._en_curso(doc, 30)
        self._cron()
        self.assertTrue(doc.incierto)
        self.assertFalse(doc.is_being_sent)
        self.soap.assert_not_called()
        self.bus.assert_called()                            # aviso al autor

    def test_barrido_con_intento_posterior_solo_limpia(self):
        doc = self._encolados(1)
        self._en_curso(doc, 30)
        doc.sending_data = dict(doc.sending_data, en_curso=fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(minutes=30)))
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_pending', 'identifier': doc.cune,
            'numero': doc.consecutive, 'datetime': datetime.now()})
        self._cron()
        self.assertFalse(doc.incierto)
        self.assertFalse(doc.is_being_sent)

    def test_barrido_en_curso_reciente_no_se_toca(self):
        doc = self._encolados(1)
        self._en_curso(doc, 1)
        self._cron()
        self.assertFalse(doc.incierto)
        self.assertTrue(doc.is_being_sent)

    # ── multiempresa, habilitación, notificación ─────────────────────
    def test_solo_se_procesa_la_compania_colombiana(self):
        doc = self._encolados(1)
        self.company.partner_id.country_id = self.env.ref('base.mx')
        self._cron()
        self.soap.assert_not_called()
        self.assertTrue(doc.is_being_sent)

    def test_una_compania_en_habilitacion_se_salta(self):
        doc = self._encolados(1)
        self.company.l10n_co_ne_environment = '2'
        self._cron()
        self.soap.assert_not_called()
        self.assertTrue(doc.is_being_sent)

    def test_el_cron_no_encola_por_su_cuenta(self):
        doc = self._listo()
        self._cron()
        self.soap.assert_not_called()
        self.assertFalse(doc.is_being_sent)

    def test_notifica_al_autor_con_los_conteos(self):
        self._encolados(2)
        self.soap.side_effect = [ACEPTADA, RECHAZO]
        self._cron()
        mensaje = self.bus.call_args.args[2]['message']
        self.assertIn('1 aceptado', mensaje)
        self.assertIn('1 rechazado', mensaje)
        self.assertEqual(self.bus.call_args.args[1], 'simple_notification')

    # ── datos del módulo y recibo intacto ────────────────────────────
    def test_parametros_y_cron_son_datos_del_modulo(self):
        esperados = {'send_batch_size': '10', 'send_max_retries': '5', 'send_retry_minutes': '5',
                     'send_retry_max_minutes': '60', 'send_stale_minutes': '15'}
        for clave, valor in esperados.items():
            self.assertEqual(
                self.env['ir.config_parameter'].sudo().get_param('l10n_co_nomina_electronica.%s' % clave), valor)
        cron = self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_documento_send')
        self.assertEqual((cron.interval_number, cron.interval_type), (5, 'minutes'))
        self.assertEqual(cron.model_id.model, 'l10n.co.ne.documento')

    def test_el_cron_del_recibo_queda_intacto(self):
        cron = self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_dian_status_recheck')
        self.assertEqual(cron.code, 'model._cron_recheck_sent_status()')
        self.assertEqual((cron.interval_number, cron.interval_type), (10, 'minutes'))
