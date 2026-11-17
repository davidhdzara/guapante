# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 3, D9: flujo completo con usuarios REALES (no superusuario). Nuestras pruebas corren como superusuario y
ocultan fallos de permisos (p. ej. el defecto de ``ir.cron`` sin sudo de 7b/8a, que un administrador de nómina habría
sufrido). Aquí un usuario del grupo ``hr_payroll.group_hr_payroll_manager`` SIN permisos de sistema recorre el asistente
8a: preparar → generar XML → encolar; el cron (que corre como superusuario, como en producción) lo envía con la DIAN
simulada; y el usuario reconsulta. Otro usuario del grupo ``group_hr_payroll_user`` afirma qué SÍ puede (leer documentos) y qué
NO (preparar, encolar, enviar). Sin llamar a la DIAN. Si algo falla por permisos, es un defecto de código: no se maquilla."""

import copy
from datetime import date
from unittest.mock import MagicMock

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, PENDIENTE
from .test_documento_generar import FECHA, HORA, PIN, XML_STUB, _quincena_con_prima
from .test_documento_merge import _recibo


@tagged('post_install', '-at_install')
class TestFlujoUsuarioReal(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Flujo Usuario Real')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE flujo', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        cls.company.l10n_co_ne_sequence_id = cls.secuencia
        cls.manager = cls._usuario('flujo_manager', 'hr_payroll.group_hr_payroll_manager')
        cls.usuario = cls._usuario('flujo_usuario', 'hr_payroll.group_hr_payroll_user')

    @classmethod
    def _usuario(cls, login, grupo):
        usuario = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario %s' % login, 'login': login, 'email': '%s@example.com' % login,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref(grupo).id])]})
        return usuario

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
        self.soap = MagicMock(name='send_nomina_sync', return_value=dict(PENDIENTE))
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.consulta = MagicMock(name='get_status_zip')
        self._patch(soap_client, 'get_status_zip', self.consulta)
        self._patch(type(self.env['ir.cron']), '_trigger', MagicMock(name='_trigger'))
        self._patch(type(self.env['bus.bus']), '_sendone', MagicMock(name='_sendone'))
        self.Doc = self.env['l10n.co.ne.documento']

    def _recibos(self):
        doc = self._documento(date(2024, 3, 1))
        recibos = doc.payslip_ids
        recibos.write({'l10n_co_ne_documento_id': False})
        doc.unlink()
        return recibos

    def _wizard(self, usuario, recibos, enviar=True):
        return self.env['hr.payslip.send'].with_user(usuario).create({
            'payslip_ids': [(6, 0, recibos.ids)], 'checkbox_send_dian': enviar, 'checkbox_send_mail': False})

    # ── administrador de nómina, SIN permisos de sistema ─────────────
    def test_el_usuario_de_prueba_es_administrador_de_nomina_sin_permisos_de_sistema(self):
        self.assertTrue(self.manager.has_group('hr_payroll.group_hr_payroll_manager'))
        self.assertFalse(self.manager.has_group('base.group_system'))
        self.assertFalse(self.env(user=self.manager.id).is_superuser())

    def test_flujo_completo_del_administrador_de_nomina(self):
        recibos = self._recibos()
        # 1. Asistente 8a: preparar → generar XML → encolar
        accion = self._wizard(self.manager, recibos).action_send_and_print()
        doc = recibos.l10n_co_ne_documento_id
        self.assertTrue(doc, 'el administrador no pudo preparar el documento: %s' % accion['params']['message'])
        self.assertIn('1 encolados', accion['params']['message'], accion['params']['message'])
        self.assertTrue(doc.is_being_sent)
        self.assertTrue(doc.cune and doc.xml_attachment_id)
        # 2. El cron (como superusuario, igual que en producción) lo envía: respuesta "en proceso" con ZipKey
        self.Doc._cron_enviar_cola()
        self.assertEqual(doc.state, 'invoice_pending')
        self.assertTrue(doc.intento_ids.zip_key)
        # 3. El administrador reconsulta (get_status_zip simulado) y queda aceptado
        self.consulta.return_value = dict(ACEPTADA, ZipKey=doc.intento_ids.zip_key, XmlDocumentKey=doc.cune)
        doc.with_user(self.manager)._ne_reconsultar()
        self.assertEqual(doc.state, 'invoice_accepted')

    # ── usuario del grupo de nómina (no administrador) ───────────────
    def test_el_usuario_de_nomina_puede_leer_documentos_pero_no_preparar_ni_enviar(self):
        recibos = self._recibos()
        self._wizard(self.manager, recibos, enviar=False).action_send_and_print()    # el admin prepara
        doc = recibos.l10n_co_ne_documento_id
        doc.action_generar_xml()
        como_usuario = doc.with_user(self.usuario)
        # SÍ puede leer
        self.assertEqual(como_usuario.read(['name', 'etapa', 'state'])[0]['id'], doc.id)
        self.assertTrue(como_usuario.payslip_ids)
        # NO puede escribir ni encolar
        with self.assertRaises(AccessError):
            como_usuario.write({'etapa': 'draft'})
        with self.assertRaises(AccessError):
            como_usuario._ne_encolar()
        self.assertFalse(doc.is_being_sent)
        self.soap.assert_not_called()
        # NO puede preparar desde el asistente (el error sale del ``has_group`` del botón)
        with self.assertRaisesRegex(AccessError, 'administrador de nómina'):
            self._wizard(self.usuario, self._recibos()).action_send_and_print()
