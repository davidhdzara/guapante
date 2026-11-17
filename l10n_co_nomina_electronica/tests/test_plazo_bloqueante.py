# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 3, D7 (doc 53 §28.8): bloqueo por PLAZO VENCIDO, configurable por compañía y APAGADO por defecto. Es una política
propia de la compañía, NO un rechazo de la DIAN (el Anexo no valida el plazo). Con el bloqueo activo, un documento fuera de
plazo solo se encola/envía si un administrador de nómina confirma el envío extemporáneo; el cron no puede saltárselo.
Sin llamar a la DIAN."""

import copy
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, CONEXION
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo


@tagged('post_install', '-at_install')
class TestPlazoBloqueante(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Plazo Bloqueante')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE plazo', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
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
        self._patch(type(self.env['bus.bus']), '_sendone', MagicMock(name='_sendone'))
        self.Doc = self.env['l10n.co.ne.documento']

    def _listo(self, vencido=True):
        """Documento listo; su plazo se fija a mano (ayer = vencido, en 5 días = en plazo) para no depender de la fecha."""
        doc = self._documento(date(2024, 3, 1))
        doc._ne_validar()
        doc.action_generar_xml()
        hoy = fields.Date.context_today(doc)
        doc.fecha_limite = hoy - timedelta(days=1) if vencido else hoy + timedelta(days=5)
        return doc

    def _bloqueo(self, activo=True):
        self.company.l10n_co_ne_bloquear_extemporaneo = activo

    def _usuario(self, admin):
        grupos = [self.env.ref('base.group_user').id, self.env.ref('hr_payroll.group_hr_payroll_user').id]
        if admin:
            grupos.append(self.env.ref('hr_payroll.group_hr_payroll_manager').id)
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario %s' % ('admin' if admin else 'sin admin'), 'login': 'plazo_%s' % int(admin), 'email': 'plazo_%s@example.com' % int(admin),
            'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)], 'groups_id': [(6, 0, grupos)]})

    # ── configuración ────────────────────────────────────────────────
    def test_el_bloqueo_esta_apagado_por_defecto_y_se_edita_en_ajustes(self):
        nueva = self.env['res.company'].create({'name': 'Otra compañía plazo', 'country_id': self.env.ref('base.co').id})
        self.assertFalse(nueva.l10n_co_ne_bloquear_extemporaneo)
        self.assertIn('l10n_co_ne_bloquear_extemporaneo', self.env['res.config.settings']._fields)

    # ── apagado = igual que hoy ──────────────────────────────────────
    def test_apagado_un_documento_vencido_se_encola_sin_pedir_nada(self):
        doc = self._listo(vencido=True)
        doc._ne_encolar()
        self.assertTrue(doc.is_being_sent)
        self.assertNotIn('extemporaneo_confirmado', doc.sending_data)

    # ── activo ───────────────────────────────────────────────────────
    def test_activo_y_vencido_sin_confirmar_no_encola_y_nombra_el_plazo(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        with self.assertRaises(UserError) as exc:
            doc._ne_encolar()
        self.assertIn(str(doc.fecha_limite), str(exc.exception))
        self.assertIn('extemporáneo', str(exc.exception))
        self.assertFalse(doc.is_being_sent)
        self.trigger.assert_not_called()

    def test_activo_y_vencido_con_confirmacion_del_administrador_encola_y_deja_constancia(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        plazo = doc.fecha_limite
        doc._ne_encolar(confirmo_extemporaneo=True)
        self.assertTrue(doc.is_being_sent)
        marca = doc.sending_data['extemporaneo_confirmado']
        self.assertEqual((marca['user_id'], marca['plazo']), (self.env.user.id, str(plazo)))
        nota = doc.message_ids.filtered(lambda m: 'Envío extemporáneo confirmado' in str(m.body))
        self.assertEqual(len(nota), 1)
        self.assertIn(str(plazo), str(nota.body))
        self.assertIn(self.env.user.name, str(nota.body))

    def test_un_usuario_sin_rol_administrador_no_puede_confirmar(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        usuario = self._usuario(admin=False)
        with self.assertRaisesRegex(AccessError, 'administrador de nómina'):
            doc.with_user(usuario)._ne_encolar(confirmo_extemporaneo=True)
        self.assertFalse(doc.is_being_sent)

    def test_un_administrador_si_puede_confirmar(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        doc.with_user(self._usuario(admin=True))._ne_encolar(confirmo_extemporaneo=True)
        self.assertTrue(doc.is_being_sent)

    def test_en_plazo_no_pide_nada_aunque_el_bloqueo_este_activo(self):
        self._bloqueo()
        doc = self._listo(vencido=False)
        doc._ne_encolar()
        self.assertTrue(doc.is_being_sent)
        self.assertNotIn('extemporaneo_confirmado', doc.sending_data)

    def test_confirmar_sin_necesidad_no_deja_marca(self):
        self._bloqueo()
        doc = self._listo(vencido=False)
        doc._ne_encolar(confirmo_extemporaneo=True)
        self.assertNotIn('extemporaneo_confirmado', doc.sending_data)
        self.assertFalse(doc.message_ids.filtered(lambda m: 'extemporáneo' in str(m.body)))

    def test_un_documento_migrado_legacy_no_tiene_plazo_y_no_aplica(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        doc.legacy = True
        self.assertFalse(doc._ne_fuera_de_plazo())
        doc._ne_exigir_plazo()                                   # no lanza

    def test_la_nota_de_ajuste_usa_su_plazo_de_d4(self):
        self._bloqueo()
        nota = self.Doc.create({
            'company_id': self.company.id, 'employee_id': self._listo().employee_id.id, 'period': date(2026, 3, 1),
            'is_adjustment': True, 'adjustment_type': '1', 'adjustment_ref_cune': 'x' * 96,
            'error_conocido_el': date(2026, 3, 20)})
        self.assertEqual(nota.fecha_limite.month, 4)             # mes siguiente al conocimiento del error (D4)
        self.assertTrue(nota._ne_fuera_de_plazo())
        with self.assertRaisesRegex(UserError, str(nota.fecha_limite)):
            nota._ne_exigir_plazo()
        nota._ne_exigir_plazo(confirmado=True)                   # con confirmación pasa

    # ── el cron no se salta el bloqueo ───────────────────────────────
    def test_el_cron_no_envia_un_documento_vencido_encolado_sin_confirmacion(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        self._bloqueo(False)
        doc._ne_encolar()                                        # encolado con el bloqueo apagado
        self._bloqueo(True)                                      # y luego se activa: el cron lo respeta
        self.Doc._cron_enviar_cola()
        self.soap.assert_not_called()
        self.assertFalse(doc.intento_ids)
        self.assertTrue(doc.message_ids.filtered(lambda m: 'No se envió el documento desde la cola' in str(m.body)))

    def test_el_cron_envia_un_documento_vencido_encolado_con_confirmacion(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        doc._ne_encolar(confirmo_extemporaneo=True)
        self.Doc._cron_enviar_cola()
        self.assertEqual(doc.state, 'invoice_accepted')

    def test_el_reintento_conserva_la_confirmacion(self):
        self._bloqueo()
        doc = self._listo(vencido=True)
        doc._ne_encolar(confirmo_extemporaneo=True)
        self.soap.return_value = CONEXION
        self.Doc._cron_enviar_cola()
        self.assertEqual(doc.state, 'invoice_sending_failed')
        self.assertTrue(doc.sending_data['extemporaneo_confirmado'])      # el reintento no vuelve a pedirla

    # ── asistente 8a ─────────────────────────────────────────────────
    def _recibos(self):
        doc = self._documento(date(2024, 3, 1))
        recibos = doc.payslip_ids
        recibos.write({'l10n_co_ne_documento_id': False})
        doc.unlink()
        return recibos

    def _asistente(self, recibos, confirmo_ext=False):
        return self.env['hr.payslip.send'].create({
            'payslip_ids': [(6, 0, recibos.ids)], 'checkbox_send_dian': True, 'checkbox_send_mail': False,
            'confirmo_envio_extemporaneo': confirmo_ext})

    def test_el_asistente_avisa_y_sin_confirmar_prepara_pero_no_encola(self):
        self._bloqueo()
        recibos = self._recibos()
        asistente = self._asistente(recibos)
        self.assertTrue(asistente.hay_extemporaneo)
        self.assertIn('exige confirmar el envío extemporáneo', asistente.resumen)
        accion = asistente.action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertTrue(doc)                                      # preparado
        self.assertFalse(doc.is_being_sent)                       # no encolado
        self.assertIn('requiere confirmar el envío extemporáneo', accion['params']['message'])

    def test_el_asistente_con_la_casilla_encola_y_deja_constancia(self):
        self._bloqueo()
        recibos = self._recibos()
        self._asistente(recibos, confirmo_ext=True).action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertTrue(doc.is_being_sent)
        self.assertTrue(doc.message_ids.filtered(lambda m: 'Envío extemporáneo confirmado' in str(m.body)))

    def test_el_asistente_sin_bloqueo_no_pide_la_casilla(self):
        recibos = self._recibos()
        asistente = self._asistente(recibos)
        self.assertFalse(asistente.hay_extemporaneo)
        asistente.action_send_and_print()
        self.assertTrue(recibos.l10n_co_ne_documento_id.is_being_sent)
