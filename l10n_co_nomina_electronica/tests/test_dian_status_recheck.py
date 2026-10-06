# -*- coding: utf-8 -*-
"""Pruebas del cron de reconsulta automática de documentos 'sent' (Ronda 1 DIAN, 2026-10-05):
5 nóminas (NE58-62) se enviaron, la DIAN las aceptó en segundos, pero Odoo las dejó en
'sent' durante 15 min porque nadie volvió a hacer clic en "Consultar Estado". El motor de
habilitación sí reconsulta lo suyo (su propio cron); el envío normal no tenía nada equivalente.

No se testea contra la DIAN real ni se abre conexión de red: soap_client.get_status_zip() y el
certificado se reemplazan con dobles de prueba. Compañía dedicada y descartable para todo el
aislamiento (ver AUD-DIAN-34 en test_dian_matching.py: la build de Odoo.sh corre los tests sobre
una COPIA de la BD real, nunca sobre self.env.company).
"""

import base64
import hashlib
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class _FakeCertificate:
    """Doble mínimo: solo necesita ser verdadero y no estar vencido."""
    date_end = False

    def __bool__(self):
        return True


class TestDianStatusRecheckCron(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Reconsulta DIAN',
        })
        cls.company.write({
            'l10n_co_ne_certification_process': True,
            'l10n_co_ne_environment': '2',
        })
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id,
            'software_id': 'SOFTWARE-TEST-ID',
            'software_pin': 'PIN-TEST',
            'test_set_id': 'TESTSET-TEST-ID',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Reconsulta',
            'country_id': co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Reconsulta',
            'type_id': cls.structure_type.id,
        })

    def setUp(self):
        super().setUp()
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

        # Odoo prohíbe cr.commit() en un test; se aísla también rollback() para poder
        # ejercer esa rama de _cron_recheck_sent_status() sin tocar la transacción de la prueba.
        self.commit_patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'HrPayslip._cron_recheck_commit',
        )
        self.commit_patcher.start()
        self.addCleanup(self.commit_patcher.stop)

        self.rollback_patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'HrPayslip._cron_recheck_rollback',
        )
        self.rollback_patcher.start()
        self.addCleanup(self.rollback_patcher.stop)

    def _make_payslip(self, name, state='sent', zip_key='ZIPKEY-1'):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '30' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # l10n_co_ne_payment_method default es '1' (Transferencia Bancaria), que exige
            # l10n_co_ne_bank_account -- sin interés aquí, 'Efectivo' evita datos bancarios falsos.
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
        payslip.l10n_co_ne_state = state
        payslip.l10n_co_ne_zip_key = zip_key
        return payslip

    def _attach_xml(self, payslip, xml_bytes):
        attachment = self.env['ir.attachment'].create({
            'name': 'test.xml',
            'datas': base64.b64encode(xml_bytes),
            'res_model': 'hr.payslip',
            'res_id': payslip.id,
        })
        payslip.l10n_co_ne_xml_attachment_id = attachment.id

    def _make_sent_payslip(self, name, zip_key, cune):
        """Nómina 'sent' con manifiesto propio -- lo que action_check_dian_status() necesita
        para emparejar el resultado de GetStatusZip (ver _ne_match_dian_results, por CUNE)."""
        payslip = self._make_payslip(name, state='sent', zip_key=zip_key)
        xml = ('<xml>%s</xml>' % name).encode()
        self._attach_xml(payslip, xml)
        payslip.l10n_co_ne_cune = cune
        exchange = self.env['l10n.co.ne.exchange'].create({
            'company_id': self.company.id,
            'operation': 'send_test_set',
            'endpoint': 'https://example.test/habilitacion',
            'zip_key': zip_key,
        })
        self.env['l10n.co.ne.exchange.document'].create({
            'exchange_id': exchange.id,
            'payslip_id': payslip.id,
            'cune': cune,
            'file_name': 'test.xml',
            'sha256': hashlib.sha256(xml).hexdigest(),
            'signed_xml': base64.b64encode(xml),
        })
        return payslip

    def _patch_get_status_zip(self, response=None, side_effect=None):
        kwargs = {'side_effect': side_effect} if side_effect else {'return_value': response}
        return patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'soap_client.get_status_zip',
            **kwargs,
        )

    def test_recheck_accepts_a_sent_document_the_dian_already_resolved(self):
        """Caso NE58-62: la DIAN ya aceptó, el cron debe pasar el documento a 'accepted' solo."""
        payslip = self._make_sent_payslip('Aceptable', 'ZIPKEY-OK', 'CUNE-OK')
        response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-OK'}],
        }
        with self._patch_get_status_zip(response):
            self.env['hr.payslip']._cron_recheck_sent_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'accepted')

    def test_recheck_leaves_still_pending_document_as_sent(self):
        """Si la DIAN sigue 'en proceso' (sin resultado identificable) el documento queda 'sent'."""
        payslip = self._make_sent_payslip('Pendiente', 'ZIPKEY-PEND', 'CUNE-PEND')
        response = {'StatusCode': '', 'DianResponses': []}
        with self._patch_get_status_zip(response):
            self.env['hr.payslip']._cron_recheck_sent_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'sent')

    def test_recheck_never_touches_accepted_generated_or_rejected(self):
        """El cron solo debe considerar 'sent' -- nunca reconsulta un estado ya resuelto."""
        accepted = self._make_sent_payslip('YaAceptada', 'ZIPKEY-A', 'CUNE-A')
        accepted.l10n_co_ne_state = 'accepted'
        generated = self._make_payslip('Generada', state='generated', zip_key=False)
        rejected = self._make_sent_payslip('Rechazada', 'ZIPKEY-R', 'CUNE-R')
        rejected.l10n_co_ne_state = 'rejected'

        with self._patch_get_status_zip({'StatusCode': '99'}) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()

        mocked.assert_not_called()
        self.assertEqual(accepted.l10n_co_ne_state, 'accepted')
        self.assertEqual(generated.l10n_co_ne_state, 'generated')
        self.assertEqual(rejected.l10n_co_ne_state, 'rejected')

    def test_recheck_skips_company_while_habilitacion_engine_is_running(self):
        """El motor de habilitación ya reconsulta sus propios 'sent' -- este cron no debe
        duplicar la consulta sobre el mismo ZipKey mientras esté corriendo."""
        payslip = self._make_sent_payslip('EnHabilitacion', 'ZIPKEY-HAB', 'CUNE-HAB')
        self.company.l10n_co_ne_hab_state = 'running'
        response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-HAB'}],
        }
        with self._patch_get_status_zip(response) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()
        mocked.assert_not_called()
        self.assertEqual(payslip.l10n_co_ne_state, 'sent')

    def test_error_in_one_zip_key_group_does_not_block_the_next(self):
        """Un ZipKey que falla al consultarse no debe impedir que se procese el siguiente."""
        broken = self._make_sent_payslip('ConError', 'ZIPKEY-ERR', 'CUNE-ERR')
        healthy = self._make_sent_payslip('Sana', 'ZIPKEY-SANA', 'CUNE-SANA')

        def fake_get_status_zip(track_id=None, **kwargs):
            if track_id == 'ZIPKEY-ERR':
                raise RuntimeError('fallo simulado consultando esta ZipKey')
            return {
                'StatusCode': '00',
                'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-SANA'}],
            }

        with self._patch_get_status_zip(side_effect=fake_get_status_zip):
            self.env['hr.payslip']._cron_recheck_sent_status()

        self.assertEqual(broken.l10n_co_ne_state, 'sent')
        self.assertEqual(healthy.l10n_co_ne_state, 'accepted')
