# -*- coding: utf-8 -*-
"""Clase A (.335; QA P5, P9, N4 y N5): ningún XML del documento mensual se genera ni se envía con un pago anulado, con las dos fuentes de la fecha de pago. Todo con *mock*: nada llama a la DIAN."""

import copy
from datetime import date, datetime
from unittest.mock import MagicMock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, ne_xml_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION
from .test_documento_generar import FECHA, HORA, PIN, _quincena_con_prima
from .test_documento_merge import _recibo
from .test_envio_ya_procesado import NO_CONOCIDA
from .test_nota_ajuste import NS_AJUSTE, NS_NOMINA


def _nodo_de_pagos(datos):
    return '<FechasPagos>%s</FechasPagos>' % ''.join('<FechaPago>%s</FechaPago>' % f for f in datos.get('fechas_pagos', []))


def _xml_nomina(datos):
    return ('<NominaIndividual xmlns="%s">%s<InformacionGeneral FechaGen="2026-04-01"/></NominaIndividual>' % (NS_NOMINA, _nodo_de_pagos(datos))).encode()


def _xml_nota(datos):
    seccion = 'Reemplazar' if 'reemplazar' in datos else 'Eliminar'
    return ('<NominaIndividualDeAjuste xmlns="%s"><%s>%s<InformacionGeneral/></%s></NominaIndividualDeAjuste>'
            % (NS_AJUSTE, seccion, _nodo_de_pagos(datos.get('reemplazar', {})), seccion)).encode()


@tagged('post_install', '-at_install')
class TestPagoAnuladoDocumento(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Pago Anulado Documento')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.company.l10n_co_ne_sequence_id = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE pago anulado', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        cls.env['ir.sequence'].search([
            ('code', '=', 'l10n_co_nomina.ajuste'), ('company_id', '=', cls.company.id)], limit=1).write(
            {'prefix': 'NA', 'padding': 8, 'number_next': 7, 'implementation': 'no_gap'})

    def setUp(self):
        super().setUp()

        def fabrica(slip):
            datos = copy.deepcopy(_quincena_con_prima() if slip.date_to.day > 15 else _recibo())
            datos['informacion_general'] = dict(datos['informacion_general'], FechaGen=FECHA, HoraGen=HORA)
            datos['lugar_generacion'] = {'Pais': 'CO', 'DepartamentoEstado': '11', 'MunicipioCiudad': '11001', 'Idioma': 'es'}
            datos['numero_secuencia'] = dict(datos['numero_secuencia'], CodigoTrabajador='1020304050')
            return datos
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: fabrica(s))
        self._patch(dian_utils, 'compute_software_security_code', lambda *a: 'SC')
        self._patch(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        self._patch(type(self.env['l10n.co.ne.documento']), '_ne_validar_datos_recibo', lambda s, slip: None)
        self._patch(type(self.company), '_get_ne_certificate', lambda s: True)
        self._patch(dian_utils, 'clean_nit', lambda *a, **k: '900123456')
        self._patch(xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None))
        self._patch(xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)
        self._patch(nomina_xml_builder, 'build_nomina_individual_v2', _xml_nomina)
        self._patch(nomina_xml_builder, 'build_nota_ajuste_v2', _xml_nota)
        self.soap = MagicMock(name='send_nomina_sync', return_value=ACEPTADA)
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.consulta = MagicMock(name='get_status', return_value=NO_CONOCIDA)
        self._patch(soap_client, 'get_status', self.consulta)
        self._patch(type(self.env['ir.cron']), '_trigger', MagicMock(name='_trigger'))
        self._patch(type(self.env['bus.bus']), '_sendone', MagicMock(name='_sendone'))
        self.Doc = self.env['l10n.co.ne.documento']

    # ── apoyo ────────────────────────────────────────────────────────
    def _listo(self):
        """Documento de marzo con XML generado y sus dos quincenas (pagadas el 15 y el 31)."""
        doc = self._documento(date(2024, 3, 1))
        doc._ne_validar()
        doc.action_generar_xml()
        recibos = doc.payslip_ids.sorted('date_to')
        self.assertEqual(self._pagos_del_xml(doc), ['2026-03-15', '2026-03-31'], 'Premisa')
        return doc, recibos

    def _pagos_del_xml(self, doc):
        return sorted(ne_xml_utils.fechas_de_pago_de_xml(doc.xml_attachment_id.raw))

    def _pagar(self, recibo, fecha):
        self.env['hr.payslip.registrar.pago'].create({'payslip_ids': [(6, 0, recibo.ids)], 'fecha': fecha}).action_registrar_pago()

    def _aceptar(self, doc):
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'identifier': doc.cune, 'numero': doc.consecutive, 'datetime': datetime(2026, 4, 2)})

    def _nota_en_chatter(self, doc, texto):
        return doc.message_ids.filtered(lambda m: texto in str(m.body))

    def _cron(self):
        self.Doc._cron_enviar_cola()

    # ── QA P9: en la cola y después se anula el pago ──────────────────
    def test_anular_el_pago_saca_de_la_cola_y_descarta_el_xml_sin_enviar(self):
        doc, (_primero, segundo) = self._listo()
        doc._ne_encolar()
        segundo.write({'name': 'Otro nombre'})
        self.assertTrue(doc.is_being_sent and doc.xml_attachment_id, 'Premisa: un cambio que no toca el pago no mueve nada')
        segundo.action_payslip_unpaid()
        self.assertEqual((doc.is_being_sent, doc.xml_attachment_id.id, doc.cune, doc.etapa), (False, False, False, 'draft'))
        self.assertTrue(self._nota_en_chatter(doc, 'perdió su pago'))
        self._cron()
        self.soap.assert_not_called()
        with self.assertRaisesRegex(UserError, 'Genere el XML'):
            doc._ne_encolar()

    def test_con_el_envio_en_curso_no_se_puede_anular(self):
        doc, (_primero, segundo) = self._listo()
        doc._ne_encolar()
        doc.sending_data = dict(doc.sending_data, en_curso=fields.Datetime.to_string(fields.Datetime.now()))
        with self.assertRaises(UserError) as exc:                  # el de Odoo deshace lo escrito antes del error
            segundo.action_payslip_unpaid()
        self.assertIn('se está enviando', str(exc.exception))
        self.assertEqual((segundo.state, segundo.paid_date), ('paid', date(2026, 3, 31)))
        self.assertTrue(doc.is_being_sent and doc.xml_attachment_id)

    def _fallido_en_cola(self):
        doc, recibos = self._listo()
        doc._ne_encolar()
        self.soap.return_value = CONEXION
        self._cron()
        self.assertEqual((doc.state, doc.is_being_sent), ('invoice_sending_failed', True), 'Premisa: queda en cola para reintentar')
        self.soap.reset_mock()
        self.consulta.reset_mock()
        doc.sending_data = dict(doc.sending_data, proximo=fields.Datetime.to_string(fields.Datetime.now()))
        return doc, recibos

    def test_el_reintento_consulta_por_cune_y_no_reenvia_un_pago_anulado(self):
        doc, (_primero, segundo) = self._fallido_en_cola()
        xml, cune = doc.xml_attachment_id, doc.cune
        segundo.action_payslip_unpaid()
        self.assertEqual((doc.is_being_sent, doc.xml_attachment_id, doc.cune), (True, xml, cune))
        self.assertIn('pago_perdido', doc.sending_data)
        self._cron()
        self.consulta.assert_called_once()
        self.soap.assert_not_called()
        self.assertEqual((doc.state, doc.is_being_sent, doc.xml_attachment_id), ('invoice_sending_failed', False, xml))
        self.assertTrue(self._nota_en_chatter(doc, 'no se reenvió'))
        with self.assertRaisesRegex(UserError, 'CUNE'):
            doc._ne_encolar()

    def test_el_reintento_aplica_el_veredicto_si_la_dian_ya_lo_tenia(self):
        doc, (_primero, segundo) = self._fallido_en_cola()
        segundo.action_payslip_unpaid()
        self.consulta.return_value = dict(ACEPTADA, XmlDocumentKey=doc.cune)
        self._cron()
        self.soap.assert_not_called()
        self.assertEqual((doc.state, doc.is_being_sent), ('invoice_accepted', False))

    def test_un_documento_aceptado_o_incierto_conserva_su_xml(self):
        aceptado, (_primero, recibo_aceptado) = self._listo()
        self._aceptar(aceptado)
        incierto, (primero, segundo) = self._listo()
        incierto.incierto = True
        xml = (aceptado.xml_attachment_id, incierto.xml_attachment_id)
        recibo_aceptado.action_payslip_unpaid()
        segundo.action_payslip_unpaid()
        self._pagar(segundo, date(2026, 4, 5))
        self.Doc._ne_preparar(primero | segundo)
        self.assertEqual((aceptado.xml_attachment_id, incierto.xml_attachment_id), xml)

    def test_el_cron_salta_un_documento_que_salio_de_la_cola_en_mitad_del_lote(self):
        primero, _recibos = self._listo()
        segundo, (_quincena, recibo) = self._listo()
        (primero | segundo)._ne_encolar()

        def envio(**kwargs):
            recibo.action_payslip_unpaid()
            return ACEPTADA
        self.soap.side_effect = envio
        self._cron()
        self.assertEqual((self.soap.call_count, primero.state, segundo.state, segundo.is_being_sent), (1, 'invoice_accepted', False, False))

    # ── QA P5: anulado y pagado en otro mes ───────────────────────────
    def test_regenerar_sin_preparar_no_sale_con_un_pago_de_otro_mes(self):
        doc, (primero, segundo) = self._listo()
        segundo.action_payslip_unpaid()
        self._pagar(segundo, date(2026, 4, 5))
        with self.assertRaisesRegex(UserError, 'fuera del mes 2026-03'):
            doc.action_generar_xml()
        self.assertFalse(doc.xml_attachment_id)
        self.Doc._ne_preparar(primero | segundo)
        self.assertEqual(doc.payslip_ids, primero)
        doc.action_generar_xml()
        self.assertEqual(self._pagos_del_xml(doc), ['2026-03-15'])

    def test_cancelar_el_recibo_o_devolver_el_lote_a_borrador_descarta_el_xml(self):
        doc, (_primero, segundo) = self._listo()
        segundo.action_payslip_cancel()
        self.assertFalse(doc.xml_attachment_id)
        with self.assertRaisesRegex(UserError, 'ya no está confirmado'):
            doc.action_generar_xml()
        otro, recibos = self._listo()
        recibos.write({'state': 'done'})
        self.assertTrue(otro.xml_attachment_id, 'Premisa: de pagado a hecho con la misma fecha no se pierde el pago')
        lote = self.env['hr.payslip.run'].create({'name': 'Lote pago anulado documento', 'state': 'close', 'company_id': self.company.id})
        recibos.write({'payslip_run_id': lote.id})
        lote.action_draft()
        self.assertFalse(otro.xml_attachment_id)

    # ── fuente «Pagos de Contabilidad» ────────────────────────────────
    def test_con_pagos_de_contabilidad_un_pago_desconciliado_o_con_otra_fecha_no_se_envia(self):
        """Contabilidad no escribe en el recibo: lo detiene la comprobación al enviar y al generar."""
        pagos = {}
        self._patch(type(self.env['hr.payslip']), '_ne_fechas_pagos_contables', lambda s: list(pagos.get(s.id, [])))
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        doc = self._documento(date(2024, 3, 1))
        primero, segundo = doc.payslip_ids.sorted('date_to')
        pagos.update({primero.id: [date(2026, 3, 15)], segundo.id: [date(2026, 3, 31)]})
        doc._ne_validar()
        doc.action_generar_xml()
        doc._ne_encolar()
        pagos[segundo.id] = []
        self._cron()
        self.soap.assert_not_called()
        self.assertFalse(doc.is_being_sent)
        self.assertTrue(self._nota_en_chatter(doc, 'No se envió el documento desde la cola'))
        with self.assertRaisesRegex(UserError, 'no tiene pagos conciliados'):
            doc._ne_encolar()
        pagos[segundo.id] = [date(2026, 3, 28)]                     # mismo mes, otra fecha: el XML lleva la anulada
        with self.assertRaisesRegex(UserError, 'lleva un pago del 2026-03-31'):
            doc._ne_encolar()
        doc.action_generar_xml()
        self.assertEqual(self._pagos_del_xml(doc), ['2026-03-15', '2026-03-28'])
        pagos[segundo.id] = [date(2026, 3, 28), date(2026, 3, 30)]  # un abono más no anula lo que el XML ya lleva
        doc._ne_encolar()
        self.assertTrue(doc.is_being_sent)
        doc.sending_data = False
        pagos[segundo.id] = [date(2026, 4, 5)]
        with self.assertRaisesRegex(UserError, 'fuera del mes 2026-03'):
            doc.action_generar_xml()

    def test_neto_cero_la_fecha_registrada_es_el_pago(self):
        """QA N4 y N5: con «Pagos de Contabilidad», la fecha registrada a mano de un recibo de neto 0 entra en la misma comprobación."""
        self._patch(type(self.env['hr.payslip']), '_ne_neto_en_cero', lambda s: True)
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        doc = self._documento(date(2024, 3, 1))
        primero, segundo = doc.payslip_ids.sorted('date_to')
        primero.l10n_co_ne_fecha_pago_registrada = date(2026, 3, 15)
        segundo.l10n_co_ne_fecha_pago_registrada = date(2026, 3, 31)
        doc._ne_validar()
        doc.action_generar_xml()
        doc._ne_encolar()
        segundo.action_payslip_unpaid()                             # N5
        self.assertEqual((segundo.l10n_co_ne_fecha_pago_registrada, doc.is_being_sent, doc.xml_attachment_id.id), (False, False, False))
        self._cron()
        self.soap.assert_not_called()
        self._pagar(segundo, date(2026, 4, 5))                      # N4
        with self.assertRaisesRegex(UserError, 'fuera del mes 2026-03'):
            doc.action_generar_xml()
        self.Doc._ne_preparar(primero | segundo)
        doc.action_generar_xml()
        self.assertEqual(self._pagos_del_xml(doc), ['2026-03-15'])

    # ── notas de ajuste ───────────────────────────────────────────────
    def test_la_nota_reemplazar_sin_enviar_pierde_su_xml_y_el_original_aceptado_no_se_toca(self):
        doc, (_primero, segundo) = self._listo()
        self._aceptar(doc)
        nota = doc.action_crear_ajuste('1')
        nota._ne_validar()
        nota.action_generar_xml()
        nota._ne_encolar()
        original = doc.xml_attachment_id
        segundo.action_payslip_unpaid()
        self.assertEqual((nota.is_being_sent, nota.xml_attachment_id.id), (False, False))
        self.assertEqual(doc.xml_attachment_id, original)
        with self.assertRaisesRegex(UserError, 'no tiene fecha de pago'):
            nota.action_generar_xml()
        segundo.write({'state': 'cancel'})                          # el recibo que no se pagará sale de la nota
        nota.action_generar_xml()
        self.assertEqual(self._pagos_del_xml(nota), ['2026-03-15'])

    def test_la_nota_eliminar_se_genera_y_se_envia_con_los_pagos_anulados_o_cancelados(self):
        doc, recibos = self._listo()
        self._aceptar(doc)
        recibos.action_payslip_unpaid()
        recibos.write({'state': 'cancel'})
        nota = doc.action_crear_ajuste('2')
        nota._ne_validar()
        nota.action_generar_xml()
        nota._ne_encolar()
        self._cron()
        self.assertEqual(nota.state, 'invoice_accepted')
        self.assertTrue(doc.eliminado)
