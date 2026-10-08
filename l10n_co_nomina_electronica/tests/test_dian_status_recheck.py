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
from datetime import date, datetime, timedelta
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

    _NEUTRAL_RESPONSE = {'StatusCode': '', 'DianResponses': []}

    def _patch_get_status_zip(self, responses=None):
        """responses: {zip_key: respuesta}. Cualquier OTRA ZipKey recibe una respuesta neutra
        (sin resultado identificable, no cambia nada) en vez de una fija para todos.

        AUD-DIAN-34 (2026-10-05): la corrida real en staging mostró que este mock devolvía
        el MISMO resultado a toda ZipKey, incluidas las de documentos reales de OTRAS
        compañías que ya existen en esa base (copia de producción) -- `assert_not_called()`
        fallaba porque esas otras compañías sí se consultan (correctamente: el cron no las
        conoce ni debe ignorarlas). Ahora solo se responde con un resultado real a las
        ZipKeys de ESTA prueba; todo lo demás es neutro, y las aserciones verifican que las
        ZipKeys de la prueba no se llamaron, no que nadie se llamó.
        """
        responses = responses or {}

        def fake_get_status_zip(track_id=None, **kwargs):
            return responses.get(track_id, self._NEUTRAL_RESPONSE)

        return patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'soap_client.get_status_zip',
            side_effect=fake_get_status_zip,
        )

    @staticmethod
    def _called_zip_keys(mocked):
        return {call.kwargs.get('track_id') for call in mocked.call_args_list}

    def test_recheck_accepts_a_sent_document_the_dian_already_resolved(self):
        """Caso NE58-62: la DIAN ya aceptó, el cron debe pasar el documento a 'accepted' solo."""
        payslip = self._make_sent_payslip('Aceptable', 'ZIPKEY-OK', 'CUNE-OK')
        response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-OK'}],
        }
        with self._patch_get_status_zip({'ZIPKEY-OK': response}):
            self.env['hr.payslip']._cron_recheck_sent_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'accepted')

    def test_recheck_leaves_still_pending_document_as_sent(self):
        """Si la DIAN sigue 'en proceso' (sin resultado identificable) el documento queda 'sent'."""
        payslip = self._make_sent_payslip('Pendiente', 'ZIPKEY-PEND', 'CUNE-PEND')
        with self._patch_get_status_zip({}):
            self.env['hr.payslip']._cron_recheck_sent_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'sent')

    def test_recheck_never_touches_accepted_generated_or_rejected(self):
        """El cron solo debe considerar 'sent' -- nunca reconsulta un estado ya resuelto."""
        accepted = self._make_sent_payslip('YaAceptada', 'ZIPKEY-A', 'CUNE-A')
        accepted.l10n_co_ne_state = 'accepted'
        generated = self._make_payslip('Generada', state='generated', zip_key=False)
        rejected = self._make_sent_payslip('Rechazada', 'ZIPKEY-R', 'CUNE-R')
        rejected.l10n_co_ne_state = 'rejected'

        with self._patch_get_status_zip({}) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()

        called = self._called_zip_keys(mocked)
        self.assertNotIn('ZIPKEY-A', called)
        self.assertNotIn('ZIPKEY-R', called)
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
        with self._patch_get_status_zip({'ZIPKEY-HAB': response}) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()
        self.assertNotIn('ZIPKEY-HAB', self._called_zip_keys(mocked))
        self.assertEqual(payslip.l10n_co_ne_state, 'sent')

    def test_error_in_one_zip_key_group_does_not_block_the_next(self):
        """Un ZipKey que falla al consultarse no debe impedir que se procese el siguiente."""
        broken = self._make_sent_payslip('ConError', 'ZIPKEY-ERR', 'CUNE-ERR')
        healthy = self._make_sent_payslip('Sana', 'ZIPKEY-SANA', 'CUNE-SANA')
        healthy_response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-SANA'}],
        }

        def fake_get_status_zip(track_id=None, **kwargs):
            if track_id == 'ZIPKEY-ERR':
                raise RuntimeError('fallo simulado consultando esta ZipKey')
            return {'ZIPKEY-SANA': healthy_response}.get(track_id, self._NEUTRAL_RESPONSE)

        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'soap_client.get_status_zip',
            side_effect=fake_get_status_zip,
        ):
            self.env['hr.payslip']._cron_recheck_sent_status()

        self.assertEqual(broken.l10n_co_ne_state, 'sent')
        self.assertEqual(healthy.l10n_co_ne_state, 'accepted')

    def _backdate_write_date(self, record, hours):
        """Retrocede write_date por SQL directo -- write() siempre lo pone en "ahora", no
        hay otra forma de simular "este documento lleva N horas esperando" en una prueba."""
        self.env.cr.execute(
            'UPDATE hr_payslip SET write_date = %s WHERE id = %s',
            (datetime.now() - timedelta(hours=hours), record.id),
        )
        record.invalidate_recordset(['write_date'])

    def test_recheck_expired_document_leaves_the_cron_and_is_marked_uncertain(self):
        """(c) H-012 (2026-10-06): pasado el plazo configurado (ir.config_parameter
        l10n_co_nomina_electronica.recheck_max_hours), el documento deja de entrar al cron
        y queda 'uncertain' -- nunca se reconsulta para siempre."""
        stuck = self._make_sent_payslip('Atascada', 'ZIPKEY-STUCK', 'CUNE-STUCK')
        self.env['ir.config_parameter'].sudo().set_param(
            'l10n_co_nomina_electronica.recheck_max_hours', '1')
        self._backdate_write_date(stuck, hours=2)

        with self._patch_get_status_zip({}) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()

        self.assertNotIn('ZIPKEY-STUCK', self._called_zip_keys(mocked))
        self.assertEqual(stuck.l10n_co_ne_state, 'uncertain')

    def test_recheck_document_within_limit_still_enters_the_cron(self):
        """Control: dentro del plazo configurado, el documento se sigue reconsultando
        como siempre -- sin este control, el límite rompería el caso normal."""
        fresh = self._make_sent_payslip('Fresca', 'ZIPKEY-FRESH', 'CUNE-FRESH')
        self.env['ir.config_parameter'].sudo().set_param(
            'l10n_co_nomina_electronica.recheck_max_hours', '1')

        with self._patch_get_status_zip({}) as mocked:
            self.env['hr.payslip']._cron_recheck_sent_status()

        self.assertIn('ZIPKEY-FRESH', self._called_zip_keys(mocked))
        self.assertEqual(fresh.l10n_co_ne_state, 'sent')

    def test_recheck_batch_queries_zip_keys_in_write_date_ascending_order(self):
        """(e) El lote se consulta en orden de write_date ascendente -- el que más
        tiempo lleva esperando entra primero."""
        older = self._make_sent_payslip('MasAntigua', 'ZIPKEY-OLD', 'CUNE-OLD')
        newer = self._make_sent_payslip('MasReciente', 'ZIPKEY-NEW', 'CUNE-NEW')
        self._backdate_write_date(older, hours=5)

        call_order = []

        def fake_get_status_zip(track_id=None, **kwargs):
            call_order.append(track_id)
            return self._NEUTRAL_RESPONSE

        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.'
            'soap_client.get_status_zip',
            side_effect=fake_get_status_zip,
        ):
            self.env['hr.payslip']._cron_recheck_sent_status()

        self.assertEqual(call_order, ['ZIPKEY-OLD', 'ZIPKEY-NEW'])
        self.assertEqual(older.l10n_co_ne_state, 'sent')
        self.assertEqual(newer.l10n_co_ne_state, 'sent')

    def test_identical_response_does_not_rewrite_the_document(self):
        """(d) H-012 (2026-10-06): si la respuesta de la DIAN es exactamente la misma que
        la última vez, no se reescribe el documento (write_date no se mueve) -- antes cada
        pasada del cron reescribía aunque nada hubiera cambiado.

        Corrección tras la corrida real en staging (.71): comparar write_date contra el
        valor leído INMEDIATAMENTE después de la primera llamada no prueba nada -- en Odoo
        write_date toma el timestamp de la transacción (cr.now()), así que dos escrituras
        en la misma prueba (misma transacción) caen en el mismo valor aunque SÍ se
        reescriba. Se usa la misma técnica que la prueba de orden del lote: retroceder
        write_date por SQL a un valor que NO puede coincidir con "ahora", y comprobar que
        se mantiene así -- si el código reescribiera de verdad, write_date saltaría a la
        hora real de la prueba, distinta de la retrocedida."""
        payslip = self._make_sent_payslip('SinCambios', 'ZIPKEY-NOCHANGE', 'CUNE-NOCHANGE')
        with self._patch_get_status_zip({}):
            payslip.action_check_dian_status()
        self._backdate_write_date(payslip, hours=1)
        backdated_write_date = payslip.write_date

        with self._patch_get_status_zip({}):
            payslip.action_check_dian_status()

        self.assertEqual(payslip.write_date, backdated_write_date)

    def test_different_response_does_rewrite_the_document(self):
        """Control: si la respuesta SÍ cambia, el resumen visible (y write_date) se
        actualiza -- confirma que (d) no rompe el caso normal. Misma técnica de
        retroceder write_date por SQL que la prueba hermana, por el mismo motivo
        (dos escrituras en la misma transacción comparten timestamp)."""
        payslip = self._make_sent_payslip('ConCambios', 'ZIPKEY-CHANGE', 'CUNE-CHANGE')
        with self._patch_get_status_zip({}):
            payslip.action_check_dian_status()
        self._backdate_write_date(payslip, hours=1)
        backdated_write_date = payslip.write_date

        response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-CHANGE'}],
            'RawResponse': b'<otra-respuesta-distinta/>',
        }
        with self._patch_get_status_zip({'ZIPKEY-CHANGE': response}):
            payslip.action_check_dian_status()

        self.assertNotEqual(payslip.write_date, backdated_write_date)
        self.assertEqual(payslip.l10n_co_ne_state, 'accepted')


class TestSetLevelStatusResponse(TestDianStatusRecheckCron):
    """H-012 (2026-10-06): evidencia real (NA0000000049, payslip 944, ZipKey 98e2fdc3) --
    GetStatusZip respondió StatusCode=2, IsValid=false, StatusDescription hablando del "set
    de prueba", sin XmlDocumentKey ni ApplicationResponse. David confirmó con el portal DIAN:
    ese software/set de pruebas ya está "Habilitado" y no procesa más documentos -- no es un
    estado transitorio que una reconsulta futura vaya a resolver, el documento nunca se va a
    resolver bajo ese set."""

    _SET_LEVEL_RESPONSE = {
        'StatusCode': '2',
        'IsValid': 'false',
        'StatusDescription': (
            'Set de prueba con identificador e07c1748-0000-0000-0000-000000000000 '
            'se encuentra Aceptado.'
        ),
        'DianResponses': [{
            'IsValid': 'false', 'StatusCode': '2',
            'StatusDescription': (
                'Set de prueba con identificador e07c1748-0000-0000-0000-000000000000 '
                'se encuentra Aceptado.'
            ),
            'ErrorMessages': [],
        }],
    }

    def test_set_level_response_is_detected(self):
        self.assertTrue(
            self.env['hr.payslip']._ne_is_set_level_status(self._SET_LEVEL_RESPONSE))

    def test_normal_accepted_document_response_is_not_set_level(self):
        normal = {'StatusCode': '00', 'IsValid': 'true', 'XmlDocumentKey': 'CUNE-X'}
        self.assertFalse(self.env['hr.payslip']._ne_is_set_level_status(normal))

    def test_rejection_response_is_not_set_level(self):
        rejection = {'StatusCode': '99', 'IsValid': 'false', 'ErrorMessages': ['x']}
        self.assertFalse(self.env['hr.payslip']._ne_is_set_level_status(rejection))

    def test_set_level_response_marks_uncertain_not_accepted_or_rejected(self):
        """(b) nunca accepted/rejected con esta respuesta -- y, confirmada la causa real,
        se marca 'uncertain' de inmediato en vez de reconsultar para siempre."""
        payslip = self._make_sent_payslip('SetLevel', 'ZIPKEY-SET', 'CUNE-SET')
        with self._patch_get_status_zip({'ZIPKEY-SET': self._SET_LEVEL_RESPONSE}):
            payslip.action_check_dian_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'uncertain')

    def test_set_level_response_message_distinguishes_set_from_document(self):
        """(a) el mensaje al usuario debe decir que la respuesta es del SET, no del
        documento, y que ya no se va a resolver."""
        payslip = self._make_sent_payslip('SetLevelMsg', 'ZIPKEY-SETMSG', 'CUNE-SETMSG')
        with self._patch_get_status_zip({'ZIPKEY-SETMSG': self._SET_LEVEL_RESPONSE}):
            notification = payslip.action_check_dian_status()
        message = notification['params']['message']
        self.assertIn('SET', message)
        self.assertIn('Habilitado', message)

    def test_set_level_response_never_degrades_an_already_accepted_document(self):
        """Un documento ya 'accepted' nunca se toca, aunque llegue una respuesta de set
        para el mismo ZipKey -- se preserva el invariante existente de nunca degradar."""
        payslip = self._make_sent_payslip('YaAceptadaSet', 'ZIPKEY-SETACC', 'CUNE-SETACC')
        payslip.l10n_co_ne_state = 'accepted'
        with self._patch_get_status_zip({'ZIPKEY-SETACC': self._SET_LEVEL_RESPONSE}):
            payslip.action_check_dian_status()
        self.assertEqual(payslip.l10n_co_ne_state, 'accepted')

    def test_normal_accepted_and_rejected_responses_are_unaffected(self):
        """Regresión: un documento normal aceptado o rechazado sigue igual -- esta
        corrección solo distingue la respuesta de SET, no toca esas ramas."""
        accepted = self._make_sent_payslip(
            'AceptadaNormal', 'ZIPKEY-OKNORMAL', 'CUNE-OKNORMAL')
        rejected = self._make_sent_payslip(
            'RechazadaNormal', 'ZIPKEY-RECHNORMAL', 'CUNE-RECHNORMAL')
        accepted_response = {
            'StatusCode': '00',
            'DianResponses': [{'IsValid': 'true', 'XmlDocumentKey': 'CUNE-OKNORMAL'}],
        }
        rejected_response = {
            'StatusCode': '99',
            'DianResponses': [{
                'IsValid': 'false', 'StatusCode': '99',
                'XmlDocumentKey': 'CUNE-RECHNORMAL', 'ErrorMessages': ['error x'],
            }],
        }
        with self._patch_get_status_zip({
            'ZIPKEY-OKNORMAL': accepted_response,
            'ZIPKEY-RECHNORMAL': rejected_response,
        }):
            accepted.action_check_dian_status()
            rejected.action_check_dian_status()
        self.assertEqual(accepted.l10n_co_ne_state, 'accepted')
        self.assertEqual(rejected.l10n_co_ne_state, 'rejected')
