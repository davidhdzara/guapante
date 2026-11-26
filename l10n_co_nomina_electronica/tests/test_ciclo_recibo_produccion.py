# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 3, D3 (doc 53 §27.1; D-5h/D-26c): en una compañía en PRODUCCIÓN el ciclo por recibo no transmite: se reporta por
documento mensual. En habilitación (ambiente 2, o ambiente 1 con proceso de certificación) el ciclo por recibo sigue
igual (clientes nuevos y port a v19). D-R1: consultar un recibo LEGACY pendiente se permite (solo consulta). Sin DIAN."""

from datetime import date

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

from .common_documento import DocumentoFixture

METODOS = ('action_generate_ne_xml', 'action_send_ne_dian', 'action_regenerate_ne_xml', 'action_send_test_set',
           'action_create_adjustment', 'action_create_elimination')


@tagged('post_install', '-at_install')
class TestCicloReciboProduccion(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Ciclo Recibo Producción')

    def setUp(self):
        super().setUp()
        doc = self._documento(date(2024, 3, 1))
        self.slip = doc.payslip_ids[:1]
        self.slip.write({'l10n_co_ne_documento_id': False})     # un recibo SIN documento: ciclo por recibo
        self.company.write({'l10n_co_ne_environment': '1', 'l10n_co_ne_certification_process': False})

    def _legacy(self):
        """Documento legacy del recibo: ya transmitido por RECIBO (envío real)."""
        self.slip.write({'l10n_co_ne_state': 'accepted', 'l10n_co_ne_cune': 'cc' * 48,
                         'l10n_co_ne_consecutive': 'NE1'})
        self.env['l10n.co.ne.exchange'].create_exchange(
            self.company, 'send_sync', 'https://dian.test/ws', {'RawRequest': b'<r/>'}, self.slip)
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(self.slip)
        self.assertTrue(self.slip.l10n_co_ne_documento_id.legacy)

    # ── compañía ─────────────────────────────────────────────────────
    def test_la_compania_distingue_produccion_de_habilitacion(self):
        self.assertTrue(self.company._ne_en_produccion())
        self.company.l10n_co_ne_certification_process = True          # ambiente 1 pero certificando: habilitación
        self.assertFalse(self.company._ne_en_produccion())
        self.company.write({'l10n_co_ne_certification_process': False, 'l10n_co_ne_environment': '2'})
        self.assertFalse(self.company._ne_en_produccion())

    def test_el_campo_del_recibo_sigue_a_la_compania(self):
        self.assertTrue(self.slip.l10n_co_ne_en_produccion)
        self.company.l10n_co_ne_environment = '2'
        self.assertFalse(self.slip.l10n_co_ne_en_produccion)

    # ── bloqueo por ambiente ─────────────────────────────────────────
    def test_en_produccion_se_bloquea_todo_envio_y_regeneracion_por_recibo(self):
        for metodo in METODOS:
            with self.subTest(metodo=metodo):
                with self.assertRaises(UserError) as exc:
                    getattr(self.slip, metodo)()
                mensaje = str(exc.exception)
                self.assertIn(self.company.name, mensaje)              # nombra la compañía
                self.assertIn('documento mensual', mensaje)            # remite al documento
                self.assertIn('Producción', mensaje)

    def test_en_produccion_se_bloquea_tambien_la_consulta_de_un_recibo_sin_documento(self):
        with self.assertRaisesRegex(UserError, 'Producción'):
            self.slip.action_check_dian_status()

    def test_en_habilitacion_el_ciclo_por_recibo_no_se_bloquea(self):
        for ambiente, certificando in (('2', False), ('1', True)):
            self.company.write({'l10n_co_ne_environment': ambiente, 'l10n_co_ne_certification_process': certificando})
            with self.subTest(ambiente=ambiente, certificando=certificando):
                self.assertIsNone(self.slip._ne_bloquear_si_va_en_documento())
                self.assertIsNone(self.slip._ne_bloquear_si_va_en_documento(consulta=True))

    # ── D-R1: la consulta de un recibo legacy pendiente se permite ───
    def test_d_r1_un_recibo_legacy_se_puede_consultar_pero_no_transmitir_en_produccion(self):
        self._legacy()
        self.assertIsNone(self.slip._ne_bloquear_si_va_en_documento(consulta=True))
        with self.assertRaises(UserError) as exc:
            self.slip.action_check_dian_status()                      # llega a su propia validación, no al bloqueo
        self.assertNotIn('Producción', str(exc.exception))
        for metodo in METODOS:
            with self.subTest(metodo=metodo):
                with self.assertRaisesRegex(UserError, 'Producción'):
                    getattr(self.slip, metodo)()

    # ── vistas ───────────────────────────────────────────────────────
    def _condicion(self, arch, texto):
        return arch.xpath("//header/button[@string='%s']" % texto)[0].get('invisible')

    def _oculto(self, condicion, produccion, documento, estado_ne, estado='done'):
        return bool(safe_eval(condicion, {
            'country_code': 'CO', 'state': estado, 'l10n_co_ne_is_adjustment': False,
            'l10n_co_ne_documento_id': documento, 'l10n_co_ne_state': estado_ne,
            'l10n_co_ne_en_produccion': produccion}))

    def test_los_botones_del_recibo_se_ocultan_en_produccion_salvo_consultar_de_un_legacy(self):
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        botones = (('Generar XML', 'draft'), ('Regenerar XML', 'generated'), ('Enviar a DIAN', 'generated'),
                   ('Nota de Ajuste', 'accepted'), ('Eliminar Documento', 'accepted'))
        for texto, estado in botones:
            condicion = self._condicion(arch, texto)
            self.assertFalse(self._oculto(condicion, False, False, estado), '%s: habilitación lo ve' % texto)
            self.assertTrue(self._oculto(condicion, True, False, estado), '%s: producción lo oculta' % texto)
        consultar = self._condicion(arch, 'Consultar Estado')
        self.assertFalse(self._oculto(consultar, False, False, 'sent'))
        self.assertTrue(self._oculto(consultar, True, False, 'sent'))          # producción, sin documento: oculto
        self.assertFalse(self._oculto(consultar, True, 1, 'sent'))             # producción, legacy pendiente: visible

    def test_el_boton_enviar_y_procesar_sigue_visible_en_produccion(self):
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        condicion = self._condicion(arch, 'Enviar y Procesar')
        self.assertFalse(self._oculto(condicion, True, 1, 'draft'))             # abre el asistente de documentos

    def test_la_columna_del_ciclo_por_recibo_queda_opcional_y_oculta_por_defecto(self):
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='list')['arch'].encode())
        columna = arch.xpath("//field[@string='Estado NE (por recibo)']")
        self.assertEqual(len(columna), 1)
        self.assertEqual(columna[0].get('optional'), 'hide')

    def test_el_cron_del_recibo_no_se_toca(self):
        cron = self.env.ref('l10n_co_nomina_electronica.ir_cron_ne_dian_status_recheck')
        self.assertEqual(cron.code, 'model._cron_recheck_sent_status()')
        self.assertTrue(cron.active)
