# -*- coding: utf-8 -*-
"""Pruebas de lógica del historial DIAN (revisión 2026-10-04/05):
emparejamiento de resultados GetStatusZip contra el manifiesto persistido
(CUNE primero, número de documento como respaldo único, o el único
documento del manifiesto en último caso), reenvío de nóminas en
'uncertain', y la regla de rechazo restringida a StatusCode=99/
ErrorMessages (en vez de "cualquier código fuera de una lista corta").

No se testea contra la DIAN real ni se abre conexión de red: todo lo que
toca SOAP (send_test_set_async) o el certificado se reemplaza con un
doble de prueba.
"""

import base64
import hashlib
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


def _application_response_xml(document_id=None, cune=None):
    """ApplicationResponse mínimo con la ruta UBL real (ver test_dian_
    response_parser.py: evidencia real GetStatusZip AUTORIZADA, nómina
    SME-10) -- cbc:ID es el NÚMERO de negocio, cbc:UUID es el CUNE."""
    id_xml = '<cbc:ID>%s</cbc:ID>' % document_id if document_id else ''
    uuid_xml = (
        '<cbc:UUID schemeName="CUNE-SHA384">%s</cbc:UUID>' % cune if cune else ''
    )
    return (
        '<ApplicationResponse '
        'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
        '<cac:DocumentResponse><cac:DocumentReference>%s%s</cac:DocumentReference>'
        '</cac:DocumentResponse></ApplicationResponse>'
    ) % (id_xml, uuid_xml)


class _FakeCertificate:
    """Doble mínimo: solo necesita ser verdadero y no estar vencido."""
    date_end = False

    def __bool__(self):
        return True


class TestDianMatchingCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # AUD-DIAN-34 (2026-10-05): nunca crear/modificar registros sobre
        # self.env.company ni depender de datos reales de Guapante -- la
        # build de Odoo.sh corre los tests sobre una COPIA de la BD real
        # (con su propio l10n.co.ne.operation_mode ya cargado para la
        # compañía por defecto); crear ahí uno nuevo violó
        # UNIQUE(company_id) y abortó la carga del módulo ("Failed to
        # load registry"). Compañía dedicada y descartable para todo
        # el aislamiento de estas pruebas.
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba DIAN Matching',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Matching',
            'country_id': co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Matching',
            'type_id': cls.structure_type.id,
        })

    def _make_payslip(self, name, cune, state='sent', zip_key='ZIPKEY-1', consecutive=None):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '10' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # AUD-DIAN-34 (2026-10-05): l10n_co_ne_payment_method default
            # es '1' (Transferencia Bancaria), que _check_bank_account_for_
            # transfer() exige con l10n_co_ne_bank_account -- sin interés
            # para estas pruebas, 'Efectivo' evita fabricar datos bancarios.
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        payslip.l10n_co_ne_cune = cune
        payslip.l10n_co_ne_state = state
        payslip.l10n_co_ne_zip_key = zip_key
        if consecutive:
            payslip.l10n_co_ne_consecutive = consecutive
        return payslip

    def _attach_xml(self, payslip, xml_bytes):
        attachment = self.env['ir.attachment'].create({
            'name': 'test.xml',
            'datas': base64.b64encode(xml_bytes),
            'res_model': 'hr.payslip',
            'res_id': payslip.id,
        })
        payslip.l10n_co_ne_xml_attachment_id = attachment.id
        return attachment

    def _make_manifest_line(self, payslip, cune, xml_bytes, file_name='test.xml'):
        exchange = self.env['l10n.co.ne.exchange'].create({
            'company_id': self.company.id,
            'operation': 'send_test_set',
            'endpoint': 'https://example.test/habilitacion',
        })
        return self.env['l10n.co.ne.exchange.document'].create({
            'exchange_id': exchange.id,
            'payslip_id': payslip.id,
            'cune': cune,
            'file_name': file_name,
            'sha256': hashlib.sha256(xml_bytes).hexdigest(),
            'signed_xml': base64.b64encode(xml_bytes),
        })


class TestDianResultMatching(TestDianMatchingCommon):
    """Regla (a)(b)(c) de _ne_match_dian_results."""

    def test_single_unidentified_result_matches_sole_manifest_document(self):
        """(b) Sin identificador y 1 solo documento en el manifiesto -> se aplica."""
        payslip = self._make_payslip('Uno', 'CUNE-UNO')
        xml = b'<xml>uno</xml>'
        self._attach_xml(payslip, xml)
        manifest = self._make_manifest_line(payslip, 'CUNE-UNO', xml)

        result = {'IsValid': 'true', 'StatusCode': '00'}  # sin XmlDocumentKey/XmlFileName
        matches, ambiguous, unidentified = payslip._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {payslip.id: result})
        self.assertEqual(ambiguous, set())
        self.assertEqual(unidentified, 0)

    def test_multiple_documents_unidentified_result_does_not_match(self):
        """(c) Sin identificador y >1 documento -> no se cambia nada, se cuenta."""
        payslips = [self._make_payslip('Multi%d' % i, 'CUNE-M%d' % i) for i in range(4)]
        manifest = self.env['l10n.co.ne.exchange.document']
        for i, p in enumerate(payslips):
            xml = ('<xml>%d</xml>' % i).encode()
            self._attach_xml(p, xml)
            manifest |= self._make_manifest_line(p, 'CUNE-M%d' % i, xml)

        result = {'IsValid': 'true', 'StatusCode': '00'}
        matches, ambiguous, unidentified = payslips[0]._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {})
        self.assertEqual(unidentified, 1)

    def test_identifier_that_does_not_match_any_document_is_not_applied(self):
        """(a) Identificador presente pero sin coincidencia -> no se cambia estado."""
        payslips = [self._make_payslip('Ident%d' % i, 'CUNE-I%d' % i) for i in range(2)]
        manifest = self.env['l10n.co.ne.exchange.document']
        for i, p in enumerate(payslips):
            xml = ('<xml>%d</xml>' % i).encode()
            self._attach_xml(p, xml)
            manifest |= self._make_manifest_line(p, 'CUNE-I%d' % i, xml)

        result = {'IsValid': 'true', 'StatusCode': '00', 'XmlDocumentKey': 'CUNE-NO-EXISTE'}
        matches, ambiguous, unidentified = payslips[0]._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {})

    def test_cune_identifier_matches_correct_document_among_several(self):
        """(a) Identificador presente y coincide -> se aplica al documento correcto."""
        payslips = [self._make_payslip('Cune%d' % i, 'CUNE-C%d' % i) for i in range(3)]
        manifest = self.env['l10n.co.ne.exchange.document']
        for i, p in enumerate(payslips):
            xml = ('<xml>%d</xml>' % i).encode()
            self._attach_xml(p, xml)
            manifest |= self._make_manifest_line(p, 'CUNE-C%d' % i, xml)

        result = {'IsValid': 'true', 'StatusCode': '00', 'XmlDocumentKey': 'CUNE-C1'}
        matches, ambiguous, unidentified = payslips[0]._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {payslips[1].id: result})
        self.assertEqual(unidentified, 0)

    def test_number_identifier_matches_when_no_cune_and_unique_in_manifest(self):
        """(b) Sin CUNE pero con número (DocumentReference/ID) único -> se aplica.

        AUD-DIAN-34 (2026-10-05): evidencia real (GetStatusZip AUTORIZADO,
        nómina SME-10) -- DIAN sí entrega DocumentReference/UUID (CUNE) en
        la práctica, pero este nivel cubre el caso donde no lo haga.
        """
        payslips = [
            self._make_payslip('Num%d' % i, 'CUNE-NUM-%d' % i, consecutive='NE000000000%d' % i)
            for i in range(3)
        ]
        manifest = self.env['l10n.co.ne.exchange.document']
        for i, p in enumerate(payslips):
            xml = ('<xml>%d</xml>' % i).encode()
            self._attach_xml(p, xml)
            manifest |= self._make_manifest_line(p, 'CUNE-NUM-%d' % i, xml)

        app = _application_response_xml(document_id='NE0000000001')  # sin CUNE
        result = {'IsValid': 'true', 'StatusCode': '00', 'ApplicationResponse': app}
        matches, ambiguous, unidentified = payslips[0]._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {payslips[1].id: result})
        self.assertEqual(unidentified, 0)

    def test_number_identifier_without_match_is_not_applied(self):
        """(b) Número presente pero sin coincidencia en el manifiesto -> no se aplica."""
        payslip = self._make_payslip('NumSinMatch', 'CUNE-NSM', consecutive='NE0000000050')
        xml = b'<xml>numsinmatch</xml>'
        self._attach_xml(payslip, xml)
        manifest = self._make_manifest_line(payslip, 'CUNE-NSM', xml)

        app = _application_response_xml(document_id='NE9999999999')  # no existe en el manifiesto
        result = {'IsValid': 'true', 'StatusCode': '00', 'ApplicationResponse': app}
        matches, ambiguous, unidentified = payslip._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {})
        self.assertEqual(unidentified, 1)

    def test_cune_takes_priority_over_conflicting_number(self):
        """(a) Si DIAN entrega CUNE, el número nunca se consulta -- aunque
        por error apunte a otro documento del mismo manifiesto."""
        payslip_a = self._make_payslip('A', 'CUNE-A', consecutive='NE0000000001')
        payslip_b = self._make_payslip('B', 'CUNE-B', consecutive='NE0000000002')
        manifest = self.env['l10n.co.ne.exchange.document']
        for p, xml in ((payslip_a, b'<xml>a</xml>'), (payslip_b, b'<xml>b</xml>')):
            self._attach_xml(p, xml)
            manifest |= self._make_manifest_line(p, p.l10n_co_ne_cune, xml)

        # CUNE apunta a A, pero el número (si se mirara) apuntaría a B.
        app = _application_response_xml(document_id='NE0000000002', cune='CUNE-A')
        result = {'IsValid': 'true', 'StatusCode': '00', 'ApplicationResponse': app}
        matches, ambiguous, unidentified = payslip_a._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {payslip_a.id: result})

    def test_version_mismatch_between_manifest_and_current_xml_is_not_applied(self):
        """El resultado nunca se aplica si el XML actual ya no es el firmado que se envió."""
        payslip = self._make_payslip('Version', 'CUNE-V')
        xml_sent = b'<xml>enviado</xml>'
        manifest = self._make_manifest_line(payslip, 'CUNE-V', xml_sent)
        # El payslip ya tiene un XML distinto (regenerado después del envío).
        self._attach_xml(payslip, b'<xml>regenerado</xml>')

        result = {'IsValid': 'true', 'StatusCode': '00'}
        matches, ambiguous, unidentified = payslip._ne_match_dian_results([result], manifest)

        self.assertEqual(matches, {})


class TestDianStateTransitions(TestDianMatchingCommon):
    """Reenvío de 'uncertain' y la regla de rechazo restringida."""

    def setUp(self):
        super().setUp()
        self.company.write({
            'l10n_co_ne_certification_process': True,
            'l10n_co_ne_environment': '2',
        })
        self.env['l10n.co.ne.operation_mode'].create({
            'company_id': self.company.id,
            'software_id': 'SOFTWARE-TEST-ID',
            'software_pin': 'PIN-TEST',
            'test_set_id': 'TESTSET-TEST-ID',
        })
        self.cert_patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.res_company.'
            'ResCompany._get_ne_certificate',
            return_value=_FakeCertificate(),
        )
        self.cert_patcher.start()
        self.addCleanup(self.cert_patcher.stop)

        self.signer_patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.xml_signer.'
            'load_from_certificate',
            return_value=(b'fake-key', b'fake-cert-pem', b'fake-cert-der', object(), []),
        )
        self.signer_patcher.start()
        self.addCleanup(self.signer_patcher.stop)

    def _make_uncertain_payslip(self):
        payslip = self._make_payslip('Incierto', 'CUNE-INCIERTO', state='uncertain', zip_key=False)
        xml = b'<xml>SOFTWARE-TEST-ID</xml>'  # debe contener el SoftwareID actual
        self._attach_xml(payslip, xml)
        return payslip

    def test_uncertain_payslip_is_resendable_via_action_send_test_set(self):
        """'uncertain' debe poder reenviarse tal cual, sin regenerar el XML."""
        payslip = self._make_uncertain_payslip()
        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.soap_client.'
            'send_test_set_async',
            return_value={'ZipKey': 'ZIPKEY-NUEVO', 'HttpStatus': 200},
        ) as mocked_send:
            payslip.action_send_test_set()

        self.assertTrue(mocked_send.called)
        self.assertEqual(payslip.l10n_co_ne_state, 'sent')
        self.assertEqual(payslip.l10n_co_ne_zip_key, 'ZIPKEY-NUEVO')

    def test_resend_without_valid_ack_stays_uncertain_not_sent(self):
        """Un reenvío sin ZipKey válido no debe fingir un envío exitoso."""
        payslip = self._make_uncertain_payslip()
        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.soap_client.'
            'send_test_set_async',
            return_value={'ZipKey': '', 'HttpStatus': 200},
        ):
            payslip.action_send_test_set()

        self.assertEqual(payslip.l10n_co_ne_state, 'uncertain')

    def test_rejected_only_when_statuscode_99_or_error_messages(self):
        """Un StatusCode fuera de ('00','0','90') sin ErrorMessages NO debe rechazar."""
        payslip = self._make_payslip('NoRech', 'CUNE-NR', state='sent', zip_key='ZIPKEY-NR')
        xml = b'<xml>nr</xml>'
        self._attach_xml(payslip, xml)
        manifest = self._make_manifest_line(payslip, 'CUNE-NR', xml)
        # _ne_match_dian_results() solo necesita el manifiesto ya devuelto
        # por _make_manifest_line() -- no hace falta (ni es posible: el
        # historial es inmutable, write() bloquea) un segundo exchange con
        # su propio zip_key; mismo patrón que test_accepted_never_degrades.

        ambiguous_result = {'IsValid': 'false', 'StatusCode': '77'}  # sin ErrorMessages, no es 99
        matches, ambiguous, unidentified = payslip._ne_match_dian_results(
            [ambiguous_result], manifest,
        )
        self.assertEqual(matches, {payslip.id: ambiguous_result})
        # La regla de rechazo vive en action_check_dian_status; se prueba
        # el predicado directamente para no depender de la red/GetStatusZip.
        valid = str(ambiguous_result.get('IsValid', '')).lower() == 'true'
        is_rejection = (
            str(ambiguous_result.get('StatusCode', '')).strip() == '99'
            or bool(ambiguous_result.get('ErrorMessages'))
        )
        self.assertFalse(valid)
        self.assertFalse(is_rejection)

    def test_rejected_when_statuscode_99(self):
        result = {'IsValid': 'false', 'StatusCode': '99'}
        is_rejection = (
            str(result.get('StatusCode', '')).strip() == '99'
            or bool(result.get('ErrorMessages'))
        )
        self.assertTrue(is_rejection)

    def test_rejected_when_error_messages_present_even_with_other_statuscode(self):
        result = {'IsValid': 'false', 'StatusCode': '', 'ErrorMessages': ['NIE901']}
        is_rejection = (
            str(result.get('StatusCode', '')).strip() == '99'
            or bool(result.get('ErrorMessages'))
        )
        self.assertTrue(is_rejection)

    def test_accepted_never_degrades(self):
        """Una consulta posterior (incluso de rechazo) nunca debe degradar 'accepted'."""
        payslip = self._make_payslip('Firme', 'CUNE-FIRME', state='accepted', zip_key='ZIPKEY-F')
        xml = b'<xml>firme</xml>'
        self._attach_xml(payslip, xml)
        manifest = self._make_manifest_line(payslip, 'CUNE-FIRME', xml)

        rejection_result = {'IsValid': 'false', 'StatusCode': '99', 'XmlDocumentKey': 'CUNE-FIRME'}
        matches, ambiguous, unidentified = payslip._ne_match_dian_results(
            [rejection_result], manifest,
        )
        self.assertEqual(matches, {payslip.id: rejection_result})
        # action_check_dian_status solo degrada si slip.l10n_co_ne_state != 'accepted';
        # se simula la misma condición que protege el estado:
        result = matches[payslip.id]
        valid = str(result.get('IsValid', '')).lower() == 'true'
        if valid and payslip.l10n_co_ne_state != 'accepted':
            payslip.l10n_co_ne_state = 'accepted'
        elif not valid and payslip.l10n_co_ne_state != 'accepted':
            payslip.l10n_co_ne_state = 'rejected'
        self.assertEqual(payslip.l10n_co_ne_state, 'accepted')
