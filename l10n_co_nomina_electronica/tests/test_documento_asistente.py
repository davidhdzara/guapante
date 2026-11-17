# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 8a (doc 53 §23.17): asistente "Enviar y Procesar" sobre documentos mensuales (producción) con
``hr.payslip.send`` como capa de interfaz y ``l10n.co.ne.documento.send`` como lógica. Todo con *mock*: nada llama a la
DIAN ni se encola de verdad (``_trigger`` parcheado)."""

import copy
from datetime import date
from unittest.mock import MagicMock

from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils, nomina_xml_builder, xml_signer

from .common_documento import DocumentoFixture
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo


@tagged('post_install', '-at_install')
class TestDocumentoAsistente(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Asistente Documentos')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE asistente', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
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
        self.trigger = MagicMock(name='_trigger')
        self._patch(type(self.env['ir.cron']), '_trigger', self.trigger)
        self.Doc = self.env['l10n.co.ne.documento']
        self.Wizard = self.env['hr.payslip.send']

    def _recibos(self, mes=3, **kwargs):
        """Recibos pagados de un empleado nuevo y SIN documento (el asistente aún no preparó nada)."""
        doc = self._documento(date(2024, 3, 1), mes=mes, **kwargs)
        recibos = doc.payslip_ids
        recibos.write({'l10n_co_ne_documento_id': False})
        doc.unlink()
        return recibos

    def _asistente(self, recibos=None, documentos=None, enviar=False, confirmo=False):
        return self.Wizard.create({
            'payslip_ids': [(6, 0, (recibos or self.Wizard.env['hr.payslip']).ids)],
            'documento_ids': [(6, 0, (documentos or self.Doc).ids)],
            'checkbox_send_dian': enviar, 'checkbox_send_mail': False, 'confirmo_mes_incompleto': confirmo})

    def _mensaje(self, accion):
        return accion['params']['message']

    # ── abrir: solo calcula ──────────────────────────────────────────
    def test_abrir_agrupa_por_empleado_y_mes_sin_crear_documentos(self):
        recibos = self._recibos()
        antes = self.Doc.search_count([])
        asistente = self._asistente(recibos)
        self.assertEqual(self.Doc.search_count([]), antes)
        self.assertIn(recibos.employee_id.display_name, asistente.resumen)
        self.assertIn('2026-03', asistente.resumen)
        self.assertFalse(recibos.l10n_co_ne_documento_id)

    def test_alertas_sin_fecha_y_no_confirmado(self):
        sin_fecha = self._recibos()
        sin_fecha.write({'paid_date': False})
        self.assertIn('no tiene fecha de pago', self._asistente(sin_fecha).resumen)
        borrador = self._recibos()
        borrador.write({'state': 'draft'})
        self.assertIn('no está confirmado', self._asistente(borrador).resumen)

    def test_alerta_documento_ya_enviado(self):
        doc = self._documento(date(2024, 3, 1))
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'identifier': 'x' * 96, 'numero': 'NE1'})
        asistente = self._asistente(documentos=doc)
        self.assertIn('ya fue enviado', asistente.resumen)

    def test_alerta_de_habilitacion_desde_documentos(self):
        doc = self._documento(date(2024, 3, 1))
        self.company.l10n_co_ne_environment = '2'
        self.assertIn('habilitación', self._asistente(documentos=doc).resumen)

    def test_alerta_de_mes_incompleto_es_confirmable(self):
        recibos = self._recibos(mes=12)
        asistente = self._asistente(recibos)
        self.assertIn('no ha terminado', asistente.resumen)
        self.assertTrue(asistente.hay_confirmable)

    def test_cron_archivado_redirige_al_administrador_y_da_error_al_usuario(self):
        self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_documento_send').active = False
        with self.assertRaises(RedirectWarning):
            self.env['l10n.co.ne.documento.send']._ne_exigir_cron_activo()
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario nómina', 'login': 'usuario_asistente', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr_payroll.group_hr_payroll_user').id])]})
        with self.assertRaises(UserError):
            self.env['l10n.co.ne.documento.send'].with_user(usuario)._ne_exigir_cron_activo()

    # ── ejecutar ─────────────────────────────────────────────────────
    def test_solo_preparar_crea_el_documento_y_no_encola(self):
        recibos = self._recibos()
        accion = self._asistente(recibos, enviar=False).action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertTrue(doc)
        self.assertFalse(doc.sending_data)
        self.assertFalse(doc.cune)                               # no gastó consecutivo
        self.trigger.assert_not_called()
        self.assertIn('1 preparados, 0 encolados', self._mensaje(accion))

    def test_con_la_casilla_dian_prepara_genera_y_encola(self):
        recibos = self._recibos()
        accion = self._asistente(recibos, enviar=True).action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertTrue(doc.is_being_sent)
        self.assertTrue(doc.cune and doc.xml_attachment_id)
        self.assertEqual(self.trigger.call_count, 1)
        self.assertIn('1 encolados', self._mensaje(accion))

    def test_un_grupo_bloqueado_no_aborta_a_los_demas(self):
        bueno = self._recibos()
        malo = self._recibos()
        malo.write({'paid_date': False})
        accion = self._asistente(bueno | malo, enviar=True).action_send_and_print()
        self.assertTrue(bueno.l10n_co_ne_documento_id.is_being_sent)
        self.assertFalse(malo.l10n_co_ne_documento_id)
        self.assertIn('1 encolados', self._mensaje(accion))
        self.assertIn('1 bloqueados', self._mensaje(accion))
        self.assertIn('no tiene fecha de pago', self._mensaje(accion))
        self.assertEqual(accion['params']['type'], 'warning')

    def test_mes_incompleto_sin_confirmar_no_encola_y_confirmado_si_con_constancia(self):
        recibos = self._recibos(mes=12)
        accion = self._asistente(recibos, enviar=True, confirmo=False).action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertFalse(doc.is_being_sent)                    # preparado pero no encolado
        self.assertIn('confirmar el mes incompleto', self._mensaje(accion))
        self._asistente(recibos, enviar=True, confirmo=True).action_send_and_print()
        self.assertTrue(doc.is_being_sent)
        self.assertTrue(doc.message_ids.filtered(lambda m: 'Mes incompleto confirmado' in str(m.body)))

    def test_cron_archivado_con_envio_da_redirect_y_no_crea_nada(self):
        recibos = self._recibos()
        self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_documento_send').active = False
        antes = self.Doc.search_count([])
        with self.assertRaises(RedirectWarning):
            self._asistente(recibos, enviar=True).action_send_and_print()
        self.assertEqual(self.Doc.search_count([]), antes)

    def test_entrada_desde_documentos_encola_el_documento(self):
        doc = self._documento(date(2024, 3, 1))
        doc._ne_validar()
        self._asistente(documentos=doc, enviar=True).action_send_and_print()
        self.assertTrue(doc.is_being_sent)

    def test_la_accion_del_menu_existe_para_documentos_y_recibos(self):
        accion = self.env.ref('l10n_co_nomina_electronica.action_hr_payslip_send_documento')
        self.assertEqual(accion.binding_model_id.model, 'l10n.co.ne.documento')
        self.assertEqual(accion.res_model, 'hr.payslip.send')
        recibo = self.env.ref('l10n_co_nomina_electronica.action_hr_payslip_send')
        self.assertEqual(recibo.binding_model_id.model, 'hr.payslip')

    def test_default_get_desde_documentos(self):
        doc = self._documento(date(2024, 3, 1))
        valores = self.Wizard.with_context(active_model='l10n.co.ne.documento', active_ids=doc.ids).default_get(
            ['documento_ids', 'payslip_ids'])
        self.assertEqual(valores['documento_ids'], [(6, 0, doc.ids)])

    # ── acceso y multiempresa ────────────────────────────────────────
    def test_solo_el_administrador_de_nomina_prepara_documentos(self):
        recibos = self._recibos()
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario sin admin', 'login': 'usuario_sin_admin', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr_payroll.group_hr_payroll_user').id])]})
        # El usuario del grupo de nómina SÍ puede abrir el asistente (lee documentos y recibos): el error sale del
        # ``has_group`` del propio botón, no de la creación. Si algún día se le retirara la lectura, el origen cambiaría.
        asistente = self.Wizard.with_user(usuario).create({
            'payslip_ids': [(6, 0, recibos.ids)], 'checkbox_send_dian': False})
        self.assertTrue(asistente.resumen)
        self.assertFalse(usuario.has_group('hr_payroll.group_hr_payroll_manager'))
        with self.assertRaisesRegex(AccessError, 'administrador de nómina'):
            asistente.action_send_and_print()
        self.assertFalse(recibos.l10n_co_ne_documento_id)

    def test_compania_no_colombiana_da_error_y_no_crea_nada(self):
        recibos = self._recibos()
        self.company.partner_id.country_id = self.env.ref('base.mx')
        antes = self.Doc.search_count([])
        with self.assertRaisesRegex(UserError, 'no es colombiana'):
            self._asistente(recibos, enviar=True).action_send_and_print()
        self.assertEqual(self.Doc.search_count([]), antes)

    # ── D5 (doc 53 §28.7): XML ya generado + recibo nuevo ─────────────
    def _documento_con_xml(self):
        recibos = self._recibos()
        self._asistente(recibos, enviar=False).action_send_and_print()      # solo preparar: crea el documento
        doc = recibos.l10n_co_ne_documento_id
        doc.action_generar_xml()
        self.assertTrue(doc.xml_attachment_id and doc.cune)
        return recibos, doc

    def _recibo_tardio(self, doc, dia_pago=20):
        slip = self.env['hr.payslip'].create({
            'name': 'Recibo tardío', 'employee_id': doc.employee_id.id, 'contract_id': doc.contract_id.id,
            'company_id': self.company.id, 'struct_id': self.struct.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        slip.write({'state': 'paid', 'paid_date': date(2026, 3, dia_pago)})
        return slip

    def test_un_recibo_nuevo_descarta_el_xml_viejo_y_conserva_el_consecutivo(self):
        recibos, doc = self._documento_con_xml()
        consecutivo = doc.consecutive
        nuevo = self._recibo_tardio(doc)
        self._asistente(recibos | nuevo, enviar=False).action_send_and_print()   # solo preparar
        self.assertIn(nuevo, doc.payslip_ids)
        self.assertFalse(doc.xml_attachment_id)                 # el XML viejo ya no corresponde a los recibos
        self.assertFalse(doc.cune)
        self.assertEqual(doc.consecutive, consecutivo)           # el consecutivo no usado se conserva
        with self.assertRaisesRegex(UserError, 'Genere el XML'):
            doc._ne_encolar()                                   # nada inconsistente entra a la cola
        self.assertFalse(doc.is_being_sent)

    def test_enviar_despues_de_un_recibo_nuevo_regenera_el_xml_con_el_mismo_consecutivo(self):
        recibos, doc = self._documento_con_xml()
        consecutivo, adjunto_viejo = doc.consecutive, doc.xml_attachment_id
        nuevo = self._recibo_tardio(doc)
        self._asistente(recibos | nuevo, enviar=True).action_send_and_print()
        self.assertTrue(doc.is_being_sent)
        self.assertEqual(doc.consecutive, consecutivo)
        self.assertTrue(doc.xml_attachment_id and doc.cune)
        self.assertNotEqual(doc.xml_attachment_id, adjunto_viejo)   # XML nuevo, con el recibo incluido
