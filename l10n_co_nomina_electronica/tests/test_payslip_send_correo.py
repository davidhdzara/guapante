# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 8b (doc 53 §23.17) y Frente 5, C5 (doc 58): el comprobante de pago por correo (UN correo por empleado
y fecha de pago) desacoplado de la DIAN y los 5 defectos del asistente
``hr.payslip.send`` (cada prueba ``test_defecto_*`` falla contra el código anterior). Sin SMTP: la cola nativa de
correo (``mail.mail`` en ``outgoing``); el PDF se parchea."""

import re
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from .common_documento import DocumentoFixture

EMOJIS = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿]')


@tagged('post_install', '-at_install')
class TestPayslipSendCorreo(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Colilla')
        modelo = cls.env['ir.model']._get('hr.payslip')
        # Una plantilla que se ordena PRIMERO por nombre ("la primera" del código viejo) y la nativa de la prueba.
        cls.primera = cls.env['mail.template'].create({
            'name': 'AAA primera plantilla', 'model_id': modelo.id, 'subject': 'Otra', 'body_html': '<p>Otra</p>'})
        cls.nativa = cls.env['mail.template'].create({
            'name': 'ZZZ colilla', 'model_id': modelo.id, 'subject': 'Colilla', 'body_html': '<p>Colilla</p>'})
        cls.env['ir.model.data'].create({
            'module': 'l10n_co_nomina_electronica', 'name': 'tpl_colilla_prueba', 'model': 'mail.template',
            'res_id': cls.nativa.id})

    def setUp(self):
        super().setUp()
        self._patch(type(self.env['hr.payslip']), 'NE_MAIL_TEMPLATE_XMLID',
                    'l10n_co_nomina_electronica.tpl_colilla_prueba')
        self._patch(type(self.env['ir.actions.report']), '_render_qweb_pdf', lambda s, *a, **k: (b'%PDF-1.4', 'pdf'))
        self.doc = self._documento(date(2024, 3, 1))
        self.recibos = self.doc.payslip_ids
        self.recibos.write({'l10n_co_ne_documento_id': False})
        self.slip = self.recibos[0]
        contacto = self.env['res.partner'].create({'name': 'Contacto trabajo', 'email': 'contacto@ejemplo.co'})
        # En Odoo 18 work_email ES el email del contacto de trabajo (related con inverse): no son dos datos distintos.
        # Escribir un work_email distinto junto con el contacto pisaba el correo del contacto (causa de reg_ak).
        self.slip.employee_id.write({'work_contact_id': contacto.id})
        self.assertEqual(self.slip.employee_id.work_contact_id.email, 'contacto@ejemplo.co')

    def _asistente(self, recibos=None, **vals):
        datos = {'payslip_ids': [(6, 0, (recibos or self.slip).ids)], 'checkbox_send_dian': False,
                 'checkbox_send_mail': True}
        datos.update(vals)
        return self.env['hr.payslip.send'].create(datos)

    def _ejecutar(self, asistente):
        """Los fallos simulados se registran con ``_logger.error`` a propósito: se silencian aquí para no dejar ERROR
        inesperado en el log de la regresión."""
        with mute_logger('odoo.addons.l10n_co_nomina_electronica.wizard.hr_payslip_send'):
            return asistente.action_send_and_print()

    def _mensaje(self, accion):
        return accion['params']['message']

    def _correos(self, destino='contacto@ejemplo.co'):
        """Correos en cola de los recibos de la prueba cuyo destinatario es ``destino``. Se busca por modelo y recibo (no
        por el literal de ``email_to``, que Odoo puede normalizar) y se compara el destinatario por ``email_to`` o por
        ``recipient_ids``."""
        correos = self.env['mail.mail'].search([('model', '=', 'hr.payslip'), ('res_id', 'in', self.recibos.ids)])
        return correos.filtered(lambda m: destino in (m.email_to or '') or destino in m.recipient_ids.mapped('email'))

    # ── destinatario, cola y estado ──────────────────────────────────
    def test_el_correo_creado_tiene_el_destinatario_y_queda_en_cola(self):
        """Lectura directa del mail.mail que crea la plantilla (sin pasar por el asistente)."""
        self.slip.action_send_comprobante_email(self.nativa)
        correos = self.env['mail.mail'].search([('model', '=', 'hr.payslip'), ('res_id', '=', self.slip.id)])
        self.assertEqual(len(correos), 1, 'La plantilla no dejó ningún mail.mail para el recibo')
        self.assertIn('contacto@ejemplo.co', (correos.email_to or '') + ' '.join(correos.recipient_ids.mapped('email')))
        self.assertEqual(correos.state, 'outgoing')

    def test_destinatario_es_el_contacto_de_trabajo_y_sale_por_la_cola(self):
        self._ejecutar(self._asistente())
        correo = self._correos()
        self.assertEqual(len(correo), 1)
        self.assertEqual(correo.state, 'outgoing')                  # cola nativa, sin force_send

    def test_defecto_correo_condicionado_al_estado_dian(self):
        """El recibo NO está aceptado por la DIAN (ciclo por recibo en borrador): la colilla sale igual."""
        self.assertEqual(self.slip.l10n_co_ne_state, 'draft')
        self._ejecutar(self._asistente())
        self.assertEqual(len(self._correos()), 1)

    def test_recibo_en_borrador_da_error_por_recibo_y_no_aborta_a_los_demas(self):
        otro = self.recibos[1]
        otro.employee_id.write({'work_contact_id': self.slip.employee_id.work_contact_id.id})
        self.slip.state = 'draft'
        accion = self._ejecutar(self._asistente(self.slip | otro))
        self.assertIn('no está confirmado', self._mensaje(accion))
        self.assertEqual(len(self._correos()), 1)                    # el otro sí salió

    def test_empleado_sin_correo_se_lista(self):
        self.slip.employee_id.work_contact_id.email = False
        accion = self._ejecutar(self._asistente())
        self.assertIn('no tiene correo', self._mensaje(accion))
        self.assertFalse(self._correos())

    def test_aviso_sin_bloqueo_si_ya_se_envio(self):
        self._ejecutar(self._asistente())
        accion = self._ejecutar(self._asistente())
        self.assertIn('ya se había enviado', self._mensaje(accion))
        self.assertEqual(len(self._correos()), 2)

    # ── plantilla ────────────────────────────────────────────────────
    def test_defecto_plantilla_la_primera(self):
        """El valor por defecto es la plantilla por xmlid, no la primera de la base (que aquí es otra)."""
        valores = self.env['hr.payslip.send'].with_context(
            active_model='hr.payslip', active_ids=self.slip.ids).default_get(['mail_template_id'])
        self.assertEqual(valores['mail_template_id'], self.nativa.id)
        self.assertNotEqual(self.nativa, self.primera)

    def test_sin_plantilla_elegida_se_usa_la_del_xmlid(self):
        self._ejecutar(self._asistente())
        self.assertEqual(self._correos().subject, 'Colilla')

    def test_plantilla_faltante_error_con_el_xmlid(self):
        self._patch(type(self.env['hr.payslip']), 'NE_MAIL_TEMPLATE_XMLID', 'hr_payroll.no_existe_colilla')
        with self.assertRaisesRegex(UserError, 'hr_payroll.no_existe_colilla'):
            self._ejecutar(self._asistente())
        self.assertFalse(self._correos())

    def test_otra_plantilla_elegida_funciona(self):
        self._ejecutar(self._asistente(mail_template_id=self.primera.id))
        self.assertEqual(self._correos().subject, 'Otra')

    # ── adjunto ──────────────────────────────────────────────────────
    def test_el_adjunto_se_reutiliza_entre_envios(self):
        self._ejecutar(self._asistente())
        self._ejecutar(self._asistente())
        adjuntos = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.payslip'), ('res_id', '=', self.slip.id), ('mimetype', '=', 'application/pdf')])
        self.assertEqual(len(adjuntos), 1)

    def test_sin_reporte_error_claro_que_nombra_estructura_y_reporte(self):
        self._patch(type(self.env['hr.payslip']), 'NE_REPORT_COMPROBANTE_XMLID',
                    'l10n_co_nomina_electronica.no_existe_reporte')
        accion = self._ejecutar(self._asistente())
        self.assertIn('no_existe_reporte', self._mensaje(accion))
        self.assertIn(self.slip.display_name, self._mensaje(accion))

    # ── errores: no se tragan ni abortan, sin emojis ─────────────────
    def test_defecto_error_tragado_sin_aviso(self):
        """Un error de render en un recibo queda en el resultado y en el chatter; los demás siguen."""
        otro = self.recibos[1]
        otro.employee_id.write({'work_contact_id': self.slip.employee_id.work_contact_id.id})

        def render(modelo, reporte_id, ids, *a, **k):
            if self.slip.id in ids:
                raise ValueError('fallo de render')
            return b'%PDF-1.4', 'pdf'
        self._patch(type(self.env['ir.actions.report']), '_render_qweb_pdf', render)
        accion = self._ejecutar(self._asistente(self.slip | otro))
        self.assertIn('fallo de render', self._mensaje(accion))
        self.assertEqual(accion['params']['type'], 'warning')
        self.assertEqual(len(self._correos()), 1)
        self.assertTrue(self.slip.message_ids.filtered(lambda m: 'fallo de render' in str(m.body)))

    def test_defecto_emojis_en_el_chatter(self):
        self._patch(type(self.env['ir.actions.report']), '_render_qweb_pdf',
                    lambda s, *a, **k: (_ for _ in ()).throw(ValueError('boom')))
        self._ejecutar(self._asistente())
        cuerpos = ' '.join(str(m.body) for m in self.slip.message_ids)
        self.assertIn('boom', cuerpos)
        self.assertFalse(EMOJIS.search(cuerpos))

    def test_defecto_transmision_dian_fallida_se_avisa_y_sin_emojis(self):
        def falla(slip):
            raise UserError('rechazo local')
        self._patch(type(self.env['hr.payslip']), 'action_generate_ne_xml', falla)
        accion = self._ejecutar(self._asistente(checkbox_send_dian=True, checkbox_send_mail=False))
        self.assertIn('rechazo local', self._mensaje(accion))
        cuerpos = ' '.join(str(m.body) for m in self.slip.message_ids)
        self.assertIn('rechazo local', cuerpos)
        self.assertFalse(EMOJIS.search(cuerpos))

    def test_recibo_con_documento_no_se_transmite_por_recibo(self):
        self.slip.l10n_co_ne_documento_id = self.doc      # el documento del mes ya existe (setUp)
        llamado = []
        self._patch(type(self.env['hr.payslip']), 'action_generate_ne_xml', lambda s: llamado.append(1))
        accion = self._ejecutar(self._asistente(checkbox_send_dian=True, checkbox_send_mail=False))
        self.assertFalse(llamado)
        self.assertIn('se transmite desde el documento mensual', self._mensaje(accion))

    def test_el_asistente_tiene_pruebas_y_ya_no_tiene_los_campos_retirados(self):
        campos = self.env['hr.payslip.send']._fields
        self.assertNotIn('enable_send_mail', campos)
        self.assertIn('checkbox_send_mail', campos)

    # ── Regla de negocio de David (2026-11-14): el empleado recibe SU colilla quincenal (una por recibo) y la DIAN un
    #    documento MENSUAL por empleado. La colilla sale aunque el recibo ya vaya dentro del documento. ──
    def _quincenales_en_el_documento(self):
        """Los dos recibos quincenales del mismo empleado y mes, ya dentro de un documento mensual no legacy."""
        self.recibos.write({'l10n_co_ne_documento_id': self.doc.id})
        self.assertEqual(len(self.recibos), 2)
        self.assertEqual(len(self.recibos.employee_id), 1)
        return self.recibos

    def _correos_de(self, recibos):
        return self.env['mail.mail'].search([('model', '=', 'hr.payslip'), ('res_id', 'in', recibos.ids)])

    def _afirmar_un_correo_por_recibo_con_su_pdf(self, recibos, esperados=1):
        for slip in recibos:
            correos = self._correos_de(slip)
            self.assertEqual(len(correos), esperados, 'Recibo %s: un correo por envío' % slip.display_name)
            for correo in correos:
                pdfs = correo.attachment_ids.filtered(lambda a: a.mimetype == 'application/pdf')
                self.assertEqual(len(pdfs), 1)
                self.assertEqual((pdfs.res_model, pdfs.res_id), ('hr.payslip', slip.id))   # SU colilla, no la del otro

    def test_dos_quincenas_en_un_documento_salen_dos_correos_con_su_pdf_sin_dian(self):
        recibos = self._quincenales_en_el_documento()
        self._ejecutar(self._asistente(recibos, checkbox_send_dian=False))
        self.assertEqual(len(self._correos_de(recibos)), 2)
        self._afirmar_un_correo_por_recibo_con_su_pdf(recibos)

    def test_dos_quincenas_en_un_documento_con_dian_marcada_en_produccion(self):
        """Producción con "Enviar a la DIAN" marcada: el documento se prepara y se encola (aquí con el procesamiento
        simulado) pero NO se transmite por recibo, y la colilla de cada quincena sale igual."""
        recibos = self._quincenales_en_el_documento()
        self.company.l10n_co_ne_environment = '1'
        procesado = []
        self._patch(type(self.env['l10n.co.ne.documento.send']), '_ne_procesar',
                    lambda s, *a, **k: procesado.append(1) or {'preparados': [], 'encolados': [], 'bloqueados': []})
        transmitidos = []
        self._patch(type(self.env['hr.payslip']), 'action_generate_ne_xml', lambda s: transmitidos.append(s.id))
        self._patch(type(self.env['hr.payslip']), 'action_send_ne_dian', lambda s: transmitidos.append(s.id))
        self._ejecutar(self._asistente(recibos, checkbox_send_dian=True))
        self.assertTrue(procesado)                       # el documento sí se atendió
        self.assertFalse(transmitidos)                   # ningún recibo se transmitió por su cuenta
        self._afirmar_un_correo_por_recibo_con_su_pdf(recibos)

    def test_la_colilla_sale_con_el_documento_en_cualquier_estado(self):
        """El correo no depende del estado del documento: borrador, en cola, pendiente, aceptado y rechazado."""
        recibos = self._quincenales_en_el_documento()
        self.doc.write({'cune': 'c' * 96, 'consecutive': 'NE00000099'})
        intento = self.env['l10n.co.ne.documento.intento']
        estados = [
            ('borrador', lambda: None),
            ('en cola', lambda: self.doc.write({'sending_data': {'author_user_id': self.env.user.id}})),
            ('pendiente', lambda: intento.create({'documento_id': self.doc.id, 'state': 'invoice_pending',
                                                  'identifier': self.doc.cune, 'numero': 'NE00000099',
                                                  'datetime': '2026-04-02 10:00:00'})),
            ('aceptado', lambda: intento.create({'documento_id': self.doc.id, 'state': 'invoice_accepted',
                                                 'identifier': self.doc.cune, 'numero': 'NE00000099',
                                                 'datetime': '2026-04-03 10:00:00'})),
            ('rechazado', lambda: intento.create({'documento_id': self.doc.id, 'state': 'invoice_rejected',
                                                  'identifier': self.doc.cune, 'numero': 'NE00000099',
                                                  'datetime': '2026-04-04 10:00:00'})),
        ]
        for orden, (nombre, preparar) in enumerate(estados, start=1):
            with self.subTest(estado=nombre):
                preparar()
                self._ejecutar(self._asistente(recibos, checkbox_send_dian=False))
                self._afirmar_un_correo_por_recibo_con_su_pdf(recibos, esperados=orden)
        self.assertEqual(self.doc.state, 'invoice_rejected')   # el último estado probado fue de verdad el rechazo

    # ── C5: UN correo por (empleado, fecha de pago) ──────────────────
    def test_dos_recibos_del_mismo_pago_salen_en_un_solo_correo_con_un_pdf(self):
        otro = self.recibos[1]
        mismo_dia = self.slip.paid_date
        otro.write({'paid_date': mismo_dia})
        self._ejecutar(self._asistente(self.slip | otro))
        correos = self._correos_de(self.recibos)
        self.assertEqual(len(correos), 1)                                  # un correo por grupo, no por recibo
        pdfs = correos.attachment_ids.filtered(lambda a: a.mimetype == 'application/pdf')
        self.assertEqual(len(pdfs), 1)
        self.assertIn('Comprobante_de_pago_%s' % mismo_dia, pdfs.name)

    def test_el_comprobante_enviado_deja_constancia_en_cada_recibo_del_grupo(self):
        otro = self.recibos[1]
        otro.write({'paid_date': self.slip.paid_date})
        self._ejecutar(self._asistente(self.slip | otro))
        for recibo in (self.slip, otro):
            self.assertTrue(recibo.message_ids.filtered(
                lambda m: 'Comprobante de pago enviado por correo' in str(m.body)), recibo.display_name)

    def test_seleccionar_un_solo_recibo_envia_el_pago_completo(self):
        otro = self.recibos[1]
        otro.write({'paid_date': self.slip.paid_date})
        self._ejecutar(self._asistente(self.slip))                          # solo uno seleccionado
        self.assertEqual(len(self._correos_de(self.recibos)), 1)
        pdf = self._correos_de(self.recibos).attachment_ids.filtered(lambda a: a.mimetype == 'application/pdf')
        self.assertIn(str(otro.id), pdf.name)                               # el nombre incluye los recibos del grupo

    def test_pagos_en_fechas_distintas_son_correos_distintos(self):
        self._ejecutar(self._asistente(self.recibos))
        self.assertEqual(len(self._correos_de(self.recibos)), 2)

    def test_un_recibo_sin_fecha_de_pago_no_recibe_comprobante_y_se_lista(self):
        self.slip.paid_date = False
        accion = self._ejecutar(self._asistente(self.slip))
        self.assertIn('fecha de pago', self._mensaje(accion))
        self.assertFalse(self._correos_de(self.recibos))

    def test_las_casillas_del_asistente_usan_las_etiquetas_nativas(self):
        campos = self.env['hr.payslip.send']._fields
        self.assertEqual(campos['checkbox_send_dian'].string, 'DIAN')
        self.assertEqual(campos['checkbox_send_mail'].string, 'Correo: comprobante de pago')

