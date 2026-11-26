# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 3, D8 (doc 53 §28): el XML lleva la hora de BOGOTÁ (Anexo DIAN: "Considerando zona horaria de Colombia (-5)";
regla DC24: la firma no puede ser posterior a la fecha del sistema). Con un reloj falso a las 01:30 UTC del 3-abr-2026 (=
20:30 del 2-abr en Bogotá), FechaGen, HoraGen y SigningTime deben salir del 2-abr; con la hora UTC "naive" saldrían del 3-abr
(HoraGen 01:30 y una firma 5 h en el futuro). Sin llamar a la DIAN. Documento generado con recibos REALES (fixture de
``test_documento_generar_real``) y firmado con un certificado autofirmado efímero."""

import base64
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytz
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import soap_client, xml_signer

from .test_documento_enviar import ACEPTADA
from .common_dane import ciudad_con_dane

MODULO = 'odoo.addons.l10n_co_nomina_electronica'
_SIGN_XML_REAL = xml_signer.sign_xml      # la función real, antes de que el setUp la parchee
UTC = pytz.UTC
# 2026-04-03 01:30 UTC == 2026-04-02 20:30 en Bogotá (UTC-5, sin horario de verano)
INSTANTE = {'utc': datetime(2026, 4, 3, 1, 30, 0, tzinfo=UTC)}


class _RelojFalso(datetime):
    """``datetime`` con ``now`` fijo. Con zona devuelve el instante convertido; sin zona, la hora UTC "naive" (lo que
    haría un servidor Odoo.sh si el código no convirtiera a Bogotá)."""

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return INSTANTE['utc'].replace(tzinfo=None)
        return INSTANTE['utc'].astimezone(tz)


@tagged('post_install', '-at_install')
class TestHoraBogota(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        pais = env.ref('base.co')
        estado = env['res.country.state'].search([('country_id', '=', pais.id)], limit=1)
        ciudad = ciudad_con_dane(env, estado, 'Ciudad Prueba Hora Bogotá')
        cls.company = env['res.company'].create({
            'name': 'Empresa Hora Bogotá', 'country_id': pais.id, 'vat': '900123456-8',
            'street': 'Calle 1 # 2-3', 'state_id': estado.id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_ne_fuente_fecha_pago': 'recibo', 'l10n_co_ne_payroll_prefix': 'NE'})
        cls.company.partner_id.write({
            'country_id': pais.id, 'state_id': estado.id, 'city_id': ciudad.id, 'street': 'Calle 1 # 2-3'})
        env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-HORA', 'software_pin': 'PIN-HORA', 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.company.l10n_co_ne_sequence_id = env['ir.sequence'].create({
            'name': 'Secuencia NE hora', 'prefix': 'NE', 'padding': 8, 'number_next': 1,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        tipo_id = env.ref('l10n_co.national_citizen_id')   # Cedula: un trabajador no se identifica con NIT (alerta tipo_documento_trabajador)
        tipo = env['hr.payroll.structure.type'].create({'name': 'Tipo Hora Bogotá', 'country_id': pais.id})
        cls.empleado = env['hr.employee'].create({
            'name': 'Juan Perez', 'company_id': cls.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_payment_method': '10', 'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00',
            'address_id': cls.company.partner_id.id})
        if tipo_id:
            cls.empleado.work_contact_id.l10n_latam_identification_type_id = tipo_id
        cls.contrato = env['hr.contract'].create({
            'name': 'Contrato Hora Bogotá', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        estructura = env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.recibos = env['hr.payslip']
        for ini, fin in ((1, 15), (16, 31)):
            recibo = env['hr.payslip'].create({
                'name': 'Q %s-%s' % (ini, fin), 'employee_id': cls.empleado.id, 'contract_id': cls.contrato.id,
                'company_id': cls.company.id, 'struct_id': estructura.id,
                'date_from': date(2026, 3, ini), 'date_to': date(2026, 3, fin)})
            recibo.compute_sheet()
            recibo.write({'state': 'paid', 'paid_date': date(2026, 3, fin)})
            cls.recibos |= recibo
        # certificado autofirmado efímero: SOLO para ejercer la firma real (SigningTime)
        cls.llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Prueba hora Bogota')])
        cls.certificado = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre)
                           .public_key(cls.llave.public_key()).serial_number(1)
                           .not_valid_before(datetime(2026, 1, 1)).not_valid_after(datetime(2030, 1, 1))
                           .sign(cls.llave, hashes.SHA256()))

    def setUp(self):
        super().setUp()
        INSTANTE['utc'] = datetime(2026, 4, 3, 1, 30, 0, tzinfo=UTC)
        for objetivo, atributo, valor in (
                (MODULO + '.models.hr_payslip', 'datetime', _RelojFalso),
                (MODULO + '.models.l10n_co_ne_documento', '_dt', _RelojFalso),
                (MODULO + '.services.xml_signer', 'datetime', _RelojFalso)):
            parche = patch(objetivo + '.' + atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)
        for objetivo, atributo, valor in (
                (type(self.company), '_get_ne_certificate', lambda s: SimpleNamespace(date_end=False)),
                (xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None)),
                (xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)):
            parche = patch.object(objetivo, atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _documento_generado(self):
        doc = self.env['l10n.co.ne.documento']._ne_preparar(self.recibos)['documentos']
        doc.action_generar_xml()
        return doc, base64.b64decode(doc.xml_attachment_id.datas)

    def _firmar_de_verdad(self, xml_bytes):
        """Firma con el ``sign_xml`` REAL (el setUp lo parchea para el resto) y el certificado efímero."""
        return _SIGN_XML_REAL(
            xml_bytes=xml_bytes, private_key=self.llave,
            cert_pem=self.certificado.public_bytes(serialization.Encoding.PEM),
            cert_der=self.certificado.public_bytes(serialization.Encoding.DER), cert_obj=self.certificado)

    # ── el reloj de Bogotá ───────────────────────────────────────────
    def test_fechagen_y_horagen_salen_de_la_hora_de_bogota_no_de_utc(self):
        _doc, xml = self._documento_generado()
        raiz = etree.fromstring(xml)
        general = raiz.find('{*}InformacionGeneral')
        periodo = raiz.find('{*}Periodo')
        self.assertEqual(general.get('FechaGen'), '2026-04-02')        # con UTC naive saldría 2026-04-03
        self.assertEqual(general.get('HoraGen'), '20:30:00-05:00')     # con UTC naive saldría 01:30:00
        self.assertEqual(periodo.get('FechaGen'), '2026-04-02')

    def test_la_firma_xades_no_es_futura_signingtime_es_la_hora_de_bogota(self):
        _doc, xml = self._documento_generado()
        firmado = self._firmar_de_verdad(xml)
        tiempos = etree.fromstring(firmado).xpath('//*[local-name()="SigningTime"]')
        self.assertEqual(len(tiempos), 1)
        # con UTC naive + "-05:00" saldría 2026-04-03T01:30:00-05:00: 5 h DESPUÉS del instante real (rechazo DC24)
        self.assertEqual(tiempos[0].text, '2026-04-02T20:30:00-05:00')
        declarado = datetime.fromisoformat(tiempos[0].text)
        self.assertLessEqual(declarado, INSTANTE['utc'])                # nunca posterior al instante real

    def test_un_documento_generado_el_dia_x_y_enviado_el_dia_x_mas_1_conserva_su_fecha_y_firma(self):
        doc, xml = self._documento_generado()
        INSTANTE['utc'] = datetime(2026, 4, 3, 14, 0, 0, tzinfo=UTC)    # al día siguiente (09:00 en Bogotá)
        soap = MagicMock(return_value=ACEPTADA)
        with patch.object(soap_client, 'send_nomina_sync', soap):
            doc._ne_enviar_uno()
        enviado = soap.call_args.kwargs['xml_bytes']
        self.assertEqual(enviado, xml)                                  # exactamente el mismo XML generado el día X
        self.assertEqual(etree.fromstring(enviado).find('{*}InformacionGeneral').get('FechaGen'), '2026-04-02')
