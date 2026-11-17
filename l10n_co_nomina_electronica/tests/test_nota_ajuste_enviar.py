# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 6c (doc 53 §23.16): envío de la nota de ajuste y eliminación del padre al quedar aceptada una nota
Eliminar (envío, Modo Demo y reconsulta). Todo con *mock*: nada llama a la DIAN."""

import copy
from datetime import date, datetime
from unittest.mock import MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, PENDIENTE, RECHAZO
from .test_documento_generar import FECHA, HORA, PIN, _quincena_con_prima
from .test_documento_merge import _recibo
from .test_nota_ajuste import XML_NOTA, XML_PADRE


@tagged('post_install', '-at_install')
class TestNotaAjusteEnviar(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Nota Enviar')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE nota enviar', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        cls.company.l10n_co_ne_sequence_id = cls.secuencia
        cls.env['ir.sequence'].search([
            ('code', '=', 'l10n_co_nomina.ajuste'), ('company_id', '=', cls.company.id)], limit=1).write(
            {'prefix': 'NA', 'padding': 8, 'number_next': 7, 'implementation': 'no_gap'})

    def setUp(self):
        super().setUp()

        def fabrica(slip):
            datos = copy.deepcopy(_quincena_con_prima() if slip.date_to.day > 15 else _recibo())
            datos['informacion_general'] = dict(datos['informacion_general'], FechaGen=FECHA, HoraGen=HORA)
            datos['lugar_generacion'] = {'Pais': 'CO', 'DepartamentoEstado': '11', 'MunicipioCiudad': '11001',
                                         'Idioma': 'es'}
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
        self._patch(nomina_xml_builder, 'build_nomina_individual_v2', lambda datos: XML_PADRE)
        self._patch(nomina_xml_builder, 'build_nota_ajuste_v2', MagicMock(return_value=XML_NOTA))
        self.soap = MagicMock(name='send_nomina_sync')
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.consulta = MagicMock(name='get_status_zip')
        self._patch(soap_client, 'get_status_zip', self.consulta)
        self.padre = self._documento(date(2024, 3, 1))
        self.padre._ne_validar()
        self.padre.action_generar_xml()
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.padre.id, 'state': 'invoice_accepted', 'identifier': self.padre.cune,
            'numero': self.padre.consecutive, 'datetime': datetime(2026, 4, 2)})

    def _nota_lista(self, tipo):
        nota = self.padre.action_crear_ajuste(tipo)
        nota._ne_validar()
        nota.action_generar_xml()
        return nota

    def test_reemplazar_aceptada_deja_al_padre_intacto(self):
        nota = self._nota_lista('1')
        self.soap.return_value = ACEPTADA
        nota._ne_enviar_uno()
        self.assertEqual(nota.state, 'invoice_accepted')
        self.assertFalse(self.padre.eliminado)
        self.assertEqual(self.padre.state, 'invoice_accepted')

    def test_eliminar_aceptada_elimina_al_padre(self):
        nota = self._nota_lista('2')
        self.soap.return_value = ACEPTADA
        nota._ne_enviar_uno()
        self.assertTrue(self.padre.eliminado)
        self.assertEqual(self.padre.eliminado_por_id, nota)

    def test_eliminar_en_modo_demo_elimina_al_padre(self):
        nota = self._nota_lista('2')
        self.company.l10n_co_ne_demo_mode = True
        nota._ne_enviar_uno()
        self.soap.assert_not_called()
        self.assertTrue(self.padre.eliminado)

    def test_eliminar_pendiente_y_rechazada_no_cambian_al_padre(self):
        nota = self._nota_lista('2')
        self.soap.return_value = PENDIENTE
        nota._ne_enviar_uno()
        self.assertFalse(self.padre.eliminado)
        nota.intento_ids.write({'state': 'invoice_rejected'})
        self.assertFalse(self.padre.eliminado)

    def test_eliminar_pendiente_pasa_a_aceptada_por_reconsulta(self):
        nota = self._nota_lista('2')
        self.soap.return_value = PENDIENTE
        nota._ne_enviar_uno()
        self.consulta.return_value = dict(ACEPTADA, ZipKey='abc', XmlDocumentKey=nota.cune)
        nota._ne_reconsultar()
        self.assertEqual(nota.state, 'invoice_accepted')
        self.assertTrue(self.padre.eliminado)
        self.assertEqual(self.padre.eliminado_por_id, nota)

    def test_nota_rechazada_se_regenera_con_consecutivo_de_ajuste_nuevo(self):
        nota = self._nota_lista('1')
        primero = nota.consecutive
        self.soap.return_value = RECHAZO
        nota._ne_enviar_uno()
        self.assertEqual(nota.state, 'invoice_rejected')
        nota.action_generar_xml()
        self.assertNotEqual(nota.consecutive, primero)
        self.assertTrue(nota.consecutive.startswith('NA'))

    def test_no_se_envia_si_el_padre_dejo_de_ser_el_ultimo_aceptado(self):
        nota = self._nota_lista('1')
        self.padre.eliminado = True
        with self.assertRaises(UserError):
            nota._ne_enviar_uno()
        self.soap.assert_not_called()
        self.assertFalse(nota.intento_ids)

    def test_el_original_aceptado_sigue_sin_poder_reenviarse(self):
        with self.assertRaisesRegex(UserError, 'ya fue enviado'):
            self.padre._ne_enviar_uno()
