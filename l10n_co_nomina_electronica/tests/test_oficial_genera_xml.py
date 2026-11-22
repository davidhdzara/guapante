# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F2-03 (C4; pedido del TL tras aprobar ``_ne_pin_del_software``): el flujo REAL de generar el XML de un recibo con un usuario que NO es superusuario, de punta a punta: validacion de la configuracion
(``_l10n_co_ne_validar_config``: software, PIN y certificado), ``SoftwareSC`` del ``ProveedorXML`` y CUNE. Con el fixture de ``test_documento_generar_real`` (recibos calculados por el motor, ``_collect_payslip_data``,
constructor del XML y CUNE sin parchear) pero SIN parchear ``_get_ne_certificate``: aqui se lee el certificado de la compania con ``certificate.certificate`` de verdad (un registro con contenido de relleno: la
carga del PEM no falla), y solo se simulan la carga de la llave y la firma (no hay certificado de prueba).

Tres usuarios: el OFICIAL de nomina (el caso del TL: el PIN con ``groups`` ya no lo lee directo), el ADMINISTRADOR de nomina SIN ser del sistema (el unico grupo con el boton «Generar XML» en la vista) y un
administrador del SISTEMA (control: el unico con permiso sobre ``certificate.certificate`` en la rama publica 18.0, ``addons/certificate/security/ir.model.access.csv``). NO ejecutada: si la generacion falla por el
certificado para el oficial o el administrador de nomina, la causa es previa a H-F2-03 (``res_company._get_ne_certificate`` lee ``l10n_co_ne_certificate_ids`` sin ``sudo`` y el PIN se lee antes que el certificado)."""

import base64
from unittest.mock import patch

from lxml import etree

from odoo.addons.l10n_co_nomina_electronica.services import cune as cune_service, xml_signer
from odoo.tests.common import TransactionCase, tagged

from . import test_documento_generar_real as real


@tagged('post_install', '-at_install')
class TestOficialGeneraXml(real.TestDocumentoGenerarReal):
    """Hereda la fixture (compania, empleado, contrato y dos recibos reales) pero no vuelve a correr las pruebas del padre."""

    def setUp(self):
        TransactionCase.setUp(self)                         # SIN los parches de ``_get_ne_certificate`` de la clase base: aqui se lee el certificado de verdad
        for objetivo, atributo, valor in (
                (xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None)),
                (xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)):
            parche = patch.object(objetivo, atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.certificado = self.env['certificate.certificate'].sudo().create({
            'name': 'Certificado de relleno', 'company_id': self.company.id, 'content': base64.b64encode(b'no es un certificado: solo ocupa el lugar')})

    def _usuario(self, login, *grupos):
        refs = ('base.group_user',) + grupos
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref(g).id for g in refs])]})

    def _generar_como(self, usuario):
        """Genera el XML del primer recibo (confirmado, estado DIAN borrador, compañia en habilitacion: el ciclo por recibo) con ``usuario``."""
        recibo = self.recibos[0]
        recibo.write({'state': 'done'})
        self.assertEqual(recibo.l10n_co_ne_state, 'draft')
        self.assertEqual(self.company.l10n_co_ne_environment, '2', 'Premisa: la compañia esta en habilitacion (ciclo por recibo)')
        recibo.with_user(usuario).with_context(allowed_company_ids=self.company.ids).action_generate_ne_xml()
        return recibo

    def _afirmar_xml_completo(self, recibo):
        self.assertEqual(recibo.l10n_co_ne_state, 'generated')
        self.assertTrue(recibo.l10n_co_ne_consecutive.startswith('NE'))
        self.assertRegex(recibo.l10n_co_ne_cune, r'^[0-9a-f]{96}$')
        raiz = etree.fromstring(base64.b64decode(recibo.l10n_co_ne_xml_attachment_id.datas))
        self.assertEqual(raiz.find('.//{*}InformacionGeneral').get('CUNE'), recibo.l10n_co_ne_cune, 'El CUNE del XML es el del recibo')
        esperado = cune_service.compute_software_security_code('SOFT-REAL', 'PIN-REAL', recibo.l10n_co_ne_consecutive)
        self.assertEqual(raiz.find('.//{*}ProveedorXML').get('SoftwareSC'), esperado, 'SoftwareSC sale del PIN real')

    def test_el_oficial_de_nomina_genera_el_xml_de_un_recibo_de_su_compania_de_punta_a_punta(self):
        self._afirmar_xml_completo(self._generar_como(self._usuario('xml_oficial', 'hr_payroll.group_hr_payroll_user')))

    def test_el_administrador_de_nomina_que_no_es_del_sistema_genera_el_xml_de_punta_a_punta(self):
        self._afirmar_xml_completo(self._generar_como(self._usuario('xml_admin_nomina', 'hr_payroll.group_hr_payroll_manager')))

    def test_control_el_administrador_del_sistema_genera_el_xml_de_punta_a_punta(self):
        self._afirmar_xml_completo(self._generar_como(self._usuario('xml_sistema', 'hr_payroll.group_hr_payroll_manager', 'base.group_system')))
