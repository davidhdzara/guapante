# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F2-03 (C4; pedido del TL tras aprobar ``_ne_pin_del_software``; decision posterior del TL, 22-nov): el flujo REAL de generar el XML de un recibo con usuarios que NO son superusuario, de punta a punta:
validacion de la configuracion (``_l10n_co_ne_validar_config``: software, PIN y certificado), ``SoftwareSC`` del ``ProveedorXML`` y CUNE. Con el fixture de ``test_documento_generar_real`` (recibos calculados por el
motor, ``_collect_payslip_data``, constructor del XML y CUNE sin parchear) pero SIN parchear ``_get_ne_certificate``: aqui se lee el certificado de la compania con ``certificate.certificate`` de verdad (un registro
con un X.509 AUTOFIRMADO generado con ``cryptography``, en PEM y sin llave privada), y solo se simulan la carga de la llave y la firma (no hay llave real que firme). Las pruebas con ``_get_ne_certificate`` parcheado (p. ej. el flujo de usuario
real) ocultaban el defecto previo: ``certificate.certificate`` solo da permiso de acceso a ``base.group_system`` y el certificado se leia sin ``sudo``.
Por que no un contenido de relleno: desde el commit ``cb27fb63ba`` de la 18.0 (marzo de 2026) el addon ``certificate`` tiene ``_constrains_certificate_loaded``, que lanza ``ValidationError`` al crear un registro con
``content`` que no se puede cargar; un X.509 valido funciona igual con y sin esa restriccion (sin llave privada: no se crea ``certificate.key`` ni corre la compatibilidad certificado-llave).

Decision del TL: (1) ``_get_ne_certificate`` lee con ``sudo`` (como Facturacion, ``certificates_sudo[-1]``) y el sudo NO abre el modelo; (2) generar o transmitir el XML exige al administrador de nomina en TODOS los modos
(acciones del recibo y asistente «Enviar y Procesar»): el OFICIAL recibe un error claro, no un AccessError del certificado; el ADMINISTRADOR de nomina que no es del sistema genera el XML completo; el del SISTEMA igual.
NO ejecutadas."""

import base64
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from lxml import etree

from odoo.addons.l10n_co_nomina_electronica.services import cune as cune_service, xml_signer
from odoo.exceptions import AccessError
from odoo.service.model import get_public_method
from odoo.tests.common import TransactionCase, tagged

from . import test_documento_generar_real as real

NOMBRE_CERTIFICADO = 'Certificado de prueba nomina electronica'


@lru_cache(maxsize=1)
def _certificado_autofirmado_pem():
    """X.509 autofirmado (RSA 2048, SHA-256, 10 anos) en PEM y SIN la llave privada, para que ``certificate.certificate`` lo cargue de verdad. Se genera una vez por proceso."""
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NOMBRE_CERTIFICADO)])
    ahora = datetime.now(timezone.utc)
    certificado = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(llave.public_key())
                   .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1)).not_valid_after(ahora + timedelta(days=3650))
                   .sign(llave, hashes.SHA256()))
    return certificado.public_bytes(Encoding.PEM)


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
            'name': NOMBRE_CERTIFICADO, 'company_id': self.company.id, 'content': base64.b64encode(_certificado_autofirmado_pem())})

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

    def test_el_oficial_de_nomina_recibe_el_error_claro_de_que_solo_el_administrador_transmite_y_no_un_error_del_certificado(self):
        oficial = self._usuario('xml_oficial', 'hr_payroll.group_hr_payroll_user')
        with self.assertRaises(AccessError) as exc:
            self._generar_como(oficial)
        texto = str(exc.exception)
        self.assertIn('administrador de nómina', texto)
        self.assertIn('también en habilitación', texto)
        self.assertNotIn('Certificate', texto, 'El oficial recibe el error claro, no el del certificado')
        recibo = self.recibos[0]
        self.assertEqual(recibo.l10n_co_ne_state, 'draft', 'No se genero nada')
        self.assertFalse(recibo.l10n_co_ne_consecutive, 'No se gasto un consecutivo')

    def test_el_oficial_tampoco_transmite_desde_el_asistente_ni_desde_las_acciones_del_recibo_en_habilitacion(self):
        oficial = self._usuario('xml_oficial_asistente', 'hr_payroll.group_hr_payroll_user')
        recibo = self.recibos[0]
        recibo.write({'state': 'done'})
        Asistente = self.env['hr.payslip.send'].with_user(oficial).with_context(allowed_company_ids=self.company.ids)
        asistente = Asistente.create({'payslip_ids': [(6, 0, recibo.ids)], 'checkbox_send_dian': True, 'checkbox_send_mail': False})
        with self.assertRaises(AccessError) as exc:
            asistente.action_send_and_print()
        self.assertIn('administrador de nómina', str(exc.exception))
        for accion in ('action_generate_ne_xml', 'action_regenerate_ne_xml', 'action_send_ne_dian', 'action_mass_generate_ne_xml', 'action_mass_send_ne_dian', 'action_check_dian_status', 'action_send_test_set'):
            with self.assertRaises(AccessError, msg=accion) as exc:
                getattr(recibo.with_user(oficial).with_context(allowed_company_ids=self.company.ids), accion)()
            self.assertIn('administrador de nómina', str(exc.exception), accion)
        self.assertEqual(recibo.l10n_co_ne_state, 'draft')

    def test_el_oficial_tampoco_genera_el_documento_mensual_ni_inicia_la_habilitacion_ni_consulta_por_cune(self):
        """Regla general del TL: todo metodo publico que llega al certificado exige al administrador de nomina (la prueba ``test_guarda_de_transmision`` las recorre todas; aqui se ejercen las de otros modelos)."""
        oficial = self._usuario('xml_oficial_documento', 'hr_payroll.group_hr_payroll_user')
        documento = self.env['l10n.co.ne.documento'].create({'company_id': self.company.id, 'employee_id': self.empleado.id, 'period': date(2026, 3, 1)})
        con_oficial = {'allowed_company_ids': self.company.ids}
        with self.assertRaises(AccessError) as exc:
            documento.with_user(oficial).with_context(**con_oficial).action_generar_xml()
        self.assertIn('administrador de nómina', str(exc.exception))
        with self.assertRaises(AccessError) as exc:
            self.env['l10n.co.ne.habilitacion'].with_user(oficial).with_context(**con_oficial).start(self.company)
        self.assertIn('administrador de nómina', str(exc.exception))
        with self.assertRaises(AccessError):                                              # el asistente de consulta por CUNE es solo del administrador de nomina (ACL) y su accion tambien lleva la guarda
            self.env['l10n.co.ne.status.cune.wizard'].with_user(oficial).with_context(**con_oficial).create({'cune': 'x' * 96}).action_check_status()
        self.assertFalse(documento.consecutive, 'No se gasto un consecutivo')

    def test_el_administrador_de_nomina_que_no_es_del_sistema_genera_el_xml_de_punta_a_punta(self):
        self._afirmar_xml_completo(self._generar_como(self._usuario('xml_admin_nomina', 'hr_payroll.group_hr_payroll_manager')))

    def test_control_el_administrador_del_sistema_genera_el_xml_de_punta_a_punta(self):
        self._afirmar_xml_completo(self._generar_como(self._usuario('xml_sistema', 'hr_payroll.group_hr_payroll_manager', 'base.group_system')))

    def test_el_sudo_del_certificado_no_abre_el_modelo_a_quien_no_es_del_sistema(self):
        """``_get_ne_certificate`` lee con sudo solo el de la compania; el oficial y el administrador de nomina siguen SIN leer ``certificate.certificate`` ni ``l10n_co_ne_certificate_ids`` directamente, y el metodo
        no se llama por RPC (``get_public_method``, ``odoo/service/model.py:29-45``)."""
        for login, grupo in (('cert_oficial', 'hr_payroll.group_hr_payroll_user'), ('cert_admin_nomina', 'hr_payroll.group_hr_payroll_manager')):
            usuario = self._usuario(login, grupo)
            Certificado = self.env['certificate.certificate'].with_user(usuario).with_context(allowed_company_ids=self.company.ids)
            with self.assertRaises(AccessError, msg='%s no busca certificados' % login):
                Certificado.search([])
            with self.assertRaises(AccessError, msg='%s no lee el certificado' % login):
                Certificado.browse(self.certificado.id).read(['name'])
            compania = self.company.with_user(usuario).with_context(allowed_company_ids=self.company.ids)
            with self.assertRaises(AccessError, msg='%s no lee la lista de certificados de la compania' % login):
                compania.l10n_co_ne_certificate_ids.mapped('name')
            with self.assertRaises(AccessError, msg='%s no llama al metodo por RPC' % login):
                get_public_method(compania, '_get_ne_certificate')
            self.assertEqual(compania._get_ne_certificate(), self.certificado, 'El flujo interno si lo obtiene (sudo, solo el de la compania)')
            self.assertTrue(compania._get_ne_certificate().env.su)
