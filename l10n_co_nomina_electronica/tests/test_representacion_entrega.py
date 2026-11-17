# -*- coding: utf-8 -*-
"""Frente 5, C6c (doc 58 §16): entrega de la representación gráfica y el XML al empleado: ZIP (PDF + XML validado), correo
apagado por defecto, intención registrada y envío al recibir la aceptación de la DIAN; un fallo de correo no cambia el estado
DIAN. Sin SMTP (cola nativa de correo) y con el PDF parchado."""
import base64
import io
import zipfile
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from .common_documento import DocumentoFixture
from .test_representacion_grafica import CUNE, _xml


@tagged('post_install', '-at_install')
class TestRepresentacionEntrega(DocumentoFixture, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Entrega Representación')
        cls.company.l10n_co_ne_environment = '1'

    def setUp(self):
        super().setUp()
        self._patch(type(self.env['ir.actions.report']), '_render_qweb_pdf', lambda s, *a, **k: (b'%PDF-1.4 rep', 'pdf'))
        self.doc = self._documento(date(2024, 3, 1))
        contacto = self.env['res.partner'].create({'name': 'Contacto empleado', 'email': 'empleado@ejemplo.co'})
        self.doc.employee_id.write({'work_contact_id': contacto.id})
        self.doc.write({'cune': CUNE, 'consecutive': 'NE15'})
        self.doc.xml_attachment_id = self.env['ir.attachment'].create({
            'name': 'ne_xml.xml', 'raw': _xml(), 'res_model': 'l10n.co.ne.documento', 'res_id': self.doc.id})

    def _intento(self, estado, hora):
        return self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.doc.id, 'state': estado, 'identifier': CUNE, 'numero': 'NE15', 'datetime': hora})

    def _correos(self):
        return self.env['mail.mail'].search([('model', '=', 'l10n.co.ne.documento'), ('res_id', '=', self.doc.id)])

    def _asistente(self, **vals):
        datos = {'documento_ids': [(6, 0, self.doc.ids)], 'checkbox_send_dian': False, 'checkbox_send_mail': False,
                 'checkbox_send_representacion': True}
        datos.update(vals)
        return self.env['hr.payslip.send'].create(datos)

    def _ejecutar(self, asistente):
        with patch.object(type(self.env['l10n.co.ne.documento.send']), '_ne_procesar',
                          lambda s, *a, **k: {'preparados': [], 'encolados': [], 'bloqueados': []}), \
                mute_logger('odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento'):
            return asistente.action_send_and_print()

    # ── ZIP ──────────────────────────────────────────────────────────
    def test_el_zip_lleva_el_pdf_y_el_xml_validado_con_los_nombres_propuestos(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        zip_adjunto = self.doc._ne_zip_representacion()
        self.assertEqual(zip_adjunto.name, 'Nomina_electronica_NE15.zip')
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(zip_adjunto.datas))) as zf:
            self.assertEqual(sorted(zf.namelist()), ['NE15.xml', 'Representacion_grafica_NE15.pdf'])
            self.assertEqual(zf.read('NE15.xml'), _xml())                    # el XML validado, tal cual
            self.assertEqual(zf.read('Representacion_grafica_NE15.pdf'), b'%PDF-1.4 rep')

    def test_el_zip_se_reutiliza_y_no_deja_adjuntos_temporales(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        primero = self.doc._ne_zip_representacion()
        segundo = self.doc._ne_zip_representacion()
        self.assertEqual(primero, segundo)
        self.assertFalse(self.env['ir.attachment'].search([
            ('name', 'in', ('Representacion_grafica_NE15.pdf', 'NE15.xml'))]))

    def test_sin_aceptacion_no_hay_zip(self):
        self._intento('invoice_pending', '2026-04-06 10:00:00')
        from odoo.exceptions import UserError
        with self.assertRaisesRegex(UserError, 'no está aceptado'):
            self.doc._ne_zip_representacion()

    # ── casilla, intención y envío ───────────────────────────────────
    def test_la_casilla_esta_apagada_por_defecto_y_con_la_etiqueta_nativa(self):
        campo = self.env['hr.payslip.send']._fields['checkbox_send_representacion']
        self.assertEqual(campo.string, 'Correo: representación gráfica y XML')
        # El VALOR por defecto, no `campo.default` (en Odoo 18 es siempre un callable envuelto).
        self.assertFalse(self.env['hr.payslip.send'].default_get(['checkbox_send_representacion'])
                         .get('checkbox_send_representacion'))
        arch = self.env.ref('l10n_co_nomina_electronica.hr_payslip_send_view_form').arch_db
        self.assertLess(arch.index('checkbox_send_dian'), arch.index('checkbox_send_representacion'))
        self.assertLess(arch.index('checkbox_send_representacion'), arch.index('checkbox_send_mail'))

    def test_documento_ya_aceptado_se_envia_al_momento_con_asunto_y_zip(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        self._ejecutar(self._asistente())
        correos = self._correos()
        self.assertEqual(len(correos), 1)
        self.assertEqual(correos.state, 'outgoing')                          # cola nativa
        self.assertIn('empleado@ejemplo.co', (correos.email_to or '') + ' '.join(correos.recipient_ids.mapped('email')))
        self.assertIn('NE15', correos.subject)
        self.assertIn(self.company.name, correos.subject)
        self.assertEqual(correos.attachment_ids.mapped('name'), ['Nomina_electronica_NE15.zip'])
        self.assertFalse(self.doc.entregar_representacion)                    # la intención se consumió
        self.assertTrue(self.doc.message_ids.filtered(lambda m: self.doc.NE_MARCA_REPRESENTACION in str(m.body)))

    def test_el_remitente_es_el_usuario_que_envia_y_la_plantilla_usa_el_idioma_del_empleado(self):
        """Doc 59 §9 (4): email_from = usuario que envía; lang = idioma del empleado (patrón nativo)."""
        plantilla = self.env.ref(self.doc.NE_PLANTILLA_REPRESENTACION_XMLID)
        self.assertEqual(plantilla.lang, '{{ object.employee_id.lang }}')
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Remitente Entrega', 'login': 'remitente_entrega', 'email': 'remitente_entrega@example.com',
            'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr_payroll.group_hr_payroll_manager').id])]})
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        self.doc.with_user(usuario).with_context(allowed_company_ids=self.company.ids)._ne_enviar_representacion()
        self.assertIn('remitente_entrega@example.com', self._correos().email_from)

    def test_enviado_por_el_sistema_no_fuerza_un_remitente(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        capturado = {}
        original = type(self.env['mail.template']).send_mail

        def captura(plantilla, res_id, *args, **kwargs):
            capturado.update(kwargs.get('email_values') or {})
            return original(plantilla, res_id, *args, **kwargs)
        self._patch(type(self.env['mail.template']), 'send_mail', captura)
        self.doc.with_user(self.env.ref('base.user_root'))._ne_enviar_representacion()
        self.assertIn('email_to', capturado)
        self.assertNotIn('email_from', capturado)

    def test_documento_pendiente_registra_la_intencion_y_se_envia_al_aceptar(self):
        self._intento('invoice_pending', '2026-04-05 10:00:00')
        self._ejecutar(self._asistente())
        self.assertTrue(self.doc.entregar_representacion)                     # intención registrada
        self.assertFalse(self._correos())                                     # nada sale antes de la aceptación
        self.assertFalse(self.doc.is_being_sent)                              # no entra a la cola de envío a la DIAN
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        self.doc._ne_tras_veredicto()                                         # lo que corre al recibir el veredicto
        self.assertEqual(len(self._correos()), 1)
        self.assertFalse(self.doc.entregar_representacion)
        self.doc._ne_tras_veredicto()
        self.assertEqual(len(self._correos()), 1)                             # no se duplica

    def test_un_documento_rechazado_no_envia_nada_y_conserva_la_intencion(self):
        self._intento('invoice_pending', '2026-04-05 10:00:00')
        self._ejecutar(self._asistente())
        self._intento('invoice_rejected', '2026-04-06 10:00:00')
        self.doc._ne_tras_veredicto()
        self.assertFalse(self._correos())
        self.assertTrue(self.doc.entregar_representacion)                      # si luego lo aceptan, se envía

    def test_un_fallo_de_correo_no_cambia_el_estado_dian_y_deja_nota(self):
        self._intento('invoice_pending', '2026-04-05 10:00:00')
        self._ejecutar(self._asistente())
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        with patch.object(type(self.env['mail.template']), 'send_mail', side_effect=ValueError('cola caída')), \
                mute_logger('odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento'):
            self.doc._ne_tras_veredicto()
        self.assertEqual(self.doc.state, 'invoice_accepted')                  # el estado DIAN no cambia
        self.assertTrue(self.doc.message_ids.filtered(lambda m: 'cola caída' in str(m.body)))
        self.assertFalse(self.doc.entregar_representacion)

    def test_empleado_sin_correo_deja_nota_y_no_envia(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        self.doc.employee_id.work_contact_id.email = False
        self._ejecutar(self._asistente())
        self.assertFalse(self._correos())
        self.assertTrue(self.doc.message_ids.filtered(lambda m: 'no tiene correo' in str(m.body)))

    def test_aviso_si_ya_se_habia_enviado(self):
        self._intento('invoice_accepted', '2026-04-06 10:00:00')
        self._ejecutar(self._asistente())
        accion = self._ejecutar(self._asistente())
        self.assertIn('ya se había enviado la representación', accion['params']['message'])
        self.assertEqual(len(self._correos()), 2)                              # sin bloqueo

    def test_la_plantilla_es_generica_y_traducible(self):
        plantilla = self.env.ref('l10n_co_nomina_electronica.mail_template_representacion_grafica')
        self.assertEqual(plantilla.model, 'l10n.co.ne.documento')
        self.assertIn('El archivo XML es el documento con validez legal', plantilla.body_html)
        self.assertNotIn('Guapante', plantilla.body_html + plantilla.subject)
