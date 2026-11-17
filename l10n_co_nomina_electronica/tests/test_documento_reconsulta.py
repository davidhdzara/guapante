# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 7c (doc 53 §23.17): cron de reconsulta de los documentos mensuales pendientes. Todo con *mock*:
``get_status_zip`` se parchea (nada llama a la DIAN) y ``_ne_commit`` no hace commit dentro de una prueba."""

import copy
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import CONEXION, PENDIENTE
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo
from .test_documento_enviar import ACEPTADA

LOGGER_DOCUMENTO = 'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento'


@tagged('post_install', '-at_install')
class TestDocumentoReconsulta(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Reconsulta CO')
        cls.company_co = cls.company
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE reconsulta', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
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
        self.consulta = MagicMock(name='get_status_zip', return_value=dict(PENDIENTE))
        self._patch(soap_client, 'get_status_zip', self.consulta)
        self.Doc = self.env['l10n.co.ne.documento']
        self.n_doc = 0

    def _pendiente(self, estado='invoice_pending', zip_key=None, hace=timedelta(hours=1), **doc_vals):
        """Documento listo con un intento ``estado`` enviado ``hace`` atrás."""
        self.n_doc += 1
        doc = self._documento(date(2024, 3, 1))
        doc._ne_validar()
        doc.action_generar_xml()
        zip_key = 'Z%s' % self.n_doc if zip_key is None else zip_key
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': estado, 'identifier': doc.cune, 'numero': doc.consecutive,
            'zip_key': zip_key or False, 'datetime': fields.Datetime.now() - hace})
        if doc_vals:
            doc.write(doc_vals)
        return doc

    def _cron(self):
        self.Doc._cron_reconsultar_pendientes()

    def _zips_consultados(self):
        return [llamada.kwargs['track_id'] for llamada in self.consulta.call_args_list]

    # ── elegibilidad ─────────────────────────────────────────────────
    def test_elegibilidad(self):
        elegible = self._pendiente()
        fallido_con_zip = self._pendiente('invoice_sending_failed', zip_key='ZF')
        self._pendiente(zip_key='')                                  # sin ZipKey: no hay con qué consultar
        self._pendiente(incierto=True)
        self._pendiente(legacy=True)
        self._pendiente(eliminado=True)
        self._pendiente('invoice_accepted')
        self._cron()
        self.assertCountEqual(self._zips_consultados(), [
            elegible._ultimo_intento().zip_key, fallido_con_zip._ultimo_intento().zip_key])

    # ── una consulta por intervalo y espera creciente ────────────────
    def test_una_consulta_por_documento_por_intervalo(self):
        doc = self._pendiente()
        self._cron()
        self._cron()
        self.assertEqual(self.consulta.call_count, 1)
        self.assertGreater(doc.proxima_consulta, fields.Datetime.now() + timedelta(minutes=25))
        self.assertEqual(doc.fallos_consulta, 0)

    def test_espera_creciente_tras_fallos_de_transporte_y_reinicio(self):
        doc = self._pendiente()
        self.consulta.return_value = dict(CONEXION)
        self._cron()
        self.assertEqual(doc.fallos_consulta, 1)
        self.assertGreater(doc.proxima_consulta, fields.Datetime.now() + timedelta(minutes=55))   # 30 × 2 = 60
        doc.proxima_consulta = fields.Datetime.now() - timedelta(minutes=1)
        self._cron()
        self.assertEqual(doc.fallos_consulta, 2)
        self.assertLessEqual(doc.proxima_consulta, fields.Datetime.now() + timedelta(minutes=61))  # tope compartido: 60
        doc.proxima_consulta = fields.Datetime.now() - timedelta(minutes=1)
        self.consulta.return_value = dict(PENDIENTE)                  # una respuesta (aunque pendiente) reinicia
        self._cron()
        self.assertEqual(doc.fallos_consulta, 0)
        self.assertLess(doc.proxima_consulta, fields.Datetime.now() + timedelta(minutes=35))

    def test_veredicto_limpia_los_contadores(self):
        doc = self._pendiente(fallos_consulta=3)
        self.consulta.return_value = dict(ACEPTADA, ZipKey=doc._ultimo_intento().zip_key, XmlDocumentKey=doc.cune)
        self._cron()
        self.assertEqual(doc.state, 'invoice_accepted')
        self.assertEqual(doc.fallos_consulta, 0)
        self.assertFalse(doc.proxima_consulta)

    def test_pasado_el_maximo_de_horas_queda_incierto_y_sale_del_cron(self):
        doc = self._pendiente(hace=timedelta(hours=100))
        self._cron()
        self.assertTrue(doc.incierto)
        doc.proxima_consulta = False
        self.consulta.reset_mock()
        self._cron()
        self.consulta.assert_not_called()

    # ── orden, lote, commit y aislamiento ────────────────────────────
    def test_orden_de_antiguedad_y_limite_del_lote(self):
        reciente = self._pendiente(hace=timedelta(hours=1))
        viejo = self._pendiente(hace=timedelta(hours=5))
        medio = self._pendiente(hace=timedelta(hours=3))
        self.env['ir.config_parameter'].sudo().set_param('l10n_co_nomina_electronica.recheck_batch_limit', '2')
        self._cron()
        self.assertEqual(self._zips_consultados(), [
            viejo._ultimo_intento().zip_key, medio._ultimo_intento().zip_key])
        self.assertFalse(reciente.proxima_consulta)

    def test_commit_por_documento(self):
        self._pendiente()
        self._pendiente()
        eventos = []
        self._patch(type(self.Doc), '_ne_commit', lambda s: eventos.append('commit'))
        self._cron()
        self.assertEqual(eventos, ['commit', 'commit'])

    def test_un_error_no_frena_a_los_demas(self):
        a, b = self._pendiente(), self._pendiente()
        self.consulta.side_effect = [RuntimeError('boom'), dict(PENDIENTE)]
        with mute_logger(LOGGER_DOCUMENTO):
            self._cron()
        self.assertEqual(self.consulta.call_count, 2)
        self.assertTrue(a.proxima_consulta and b.proxima_consulta)

    # ── multiempresa y habilitación ──────────────────────────────────
    def test_solo_se_reconsulta_la_compania_colombiana(self):
        co = self._pendiente()
        # Segunda compañía: nace colombiana (el documento no se crea en otra) y luego pasa a México.
        mx = self.env['res.company'].create({
            'name': 'Compañía Reconsulta MX', 'country_id': self.env.ref('base.co').id,
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_fuente_fecha_pago': 'recibo', 'l10n_co_ne_payroll_prefix': 'NE',
            'l10n_co_ne_environment': '1'})
        self.company = mx
        doc_mx = self._pendiente(zip_key='ZMX')
        self.company = self.company_co
        mx.partner_id.country_id = self.env.ref('base.mx')
        self._cron()
        self.assertEqual(self._zips_consultados(), [co._ultimo_intento().zip_key])
        self.assertFalse(doc_mx.proxima_consulta)

    def test_una_compania_en_habilitacion_se_excluye(self):
        self._pendiente()
        self.company.l10n_co_ne_environment = '2'
        self._cron()
        self.consulta.assert_not_called()

    # ── datos del módulo y recibo intacto ────────────────────────────
    def test_el_cron_es_un_dato_de_30_minutos_y_el_del_recibo_queda_intacto(self):
        cron = self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_documento_recheck')
        self.assertEqual((cron.interval_number, cron.interval_type), (30, 'minutes'))
        self.assertEqual(cron.model_id.model, 'l10n.co.ne.documento')
        self.assertEqual(self.Doc._ne_intervalo_reconsulta(), 30)
        recibo = self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_dian_status_recheck')
        self.assertEqual(recibo.code, 'model._cron_recheck_sent_status()')
        self.assertEqual((recibo.interval_number, recibo.interval_type), (10, 'minutes'))

    def test_los_campos_son_solo_tecnicos(self):
        for vista in ('view_l10n_co_ne_documento_form', 'view_l10n_co_ne_documento_list'):
            arch = self.env.ref('l10n_co_nomina_electronica.%s' % vista).arch_db
            self.assertNotIn('proxima_consulta', arch)
            self.assertNotIn('fallos_consulta', arch)
