# -*- coding: utf-8 -*-
"""Pruebas del motor de habilitación DIAN automática (``l10n.co.ne.habilitacion``).

Sin red ni certificado: se reemplazan con dobles el envío/consulta a la DIAN y la generación
del XML; lo que se prueba es la lógica de decisión (una etapa por tick): un ZIP por documento,
detención ante rechazo, reanudación, orden individual -> ajuste, y aislamiento entre sets.
"""

import base64
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

_PAYSLIP = 'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.HrPayslip'
_ENGINE = 'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_habilitacion.L10nCoNeHabilitacion'


class TestHabilitacionEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (nunca modificar self.env.company: la build de
        # Odoo.sh corre sobre una copia de la BD real).
        cls.company = cls.env['res.company'].create({'name': 'Compañía de Prueba Habilitación NE'})
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1) or cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Habilitación', 'country_id': co_country.id})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Habilitación', 'type_id': cls.structure_type.id})

    def setUp(self):
        super().setUp()
        self.company.write({
            'l10n_co_ne_certification_process': True,
            'l10n_co_ne_environment': '2',
            'l10n_co_ne_num_nomina_certificar': 2,
            'l10n_co_ne_num_ajuste_certificar': 2,
            'l10n_co_ne_hab_state': 'running',
        })
        self.env['l10n.co.ne.operation_mode'].create({
            'company_id': self.company.id,
            'software_id': 'SOFTWARE-TEST-ID',
            'software_pin': 'PIN-TEST',
            'test_set_id': 'SET-ACTUAL',
        })
        # Odoo prohíbe cr.commit() dentro de un test: el motor lo aísla en _commit().
        commit_patcher = patch(_ENGINE + '._commit')
        commit_patcher.start()
        self.addCleanup(commit_patcher.stop)
        self.engine = self.env['l10n.co.ne.habilitacion'].with_company(self.company)

    def _slip(self, name, state, adjustment=False, set_id='SET-ACTUAL'):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '30' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
        })
        vals = {
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'l10n_co_ne_is_adjustment': adjustment, 'l10n_co_ne_hab_set_id': set_id,
        }
        if adjustment:
            vals['l10n_co_ne_adjustment_ref_cune'] = 'CUNE-ORIGINAL-%s' % name
        slip = self.env['hr.payslip'].create(vals)
        slip.l10n_co_ne_state = state
        if state == 'generated':
            # XML mínimo con el SoftwareID vigente: el motor lo revisa antes de enviar.
            slip.l10n_co_ne_xml_attachment_id = self.env['ir.attachment'].create({
                'name': '%s.xml' % name,
                'datas': base64.b64encode(b'<NominaIndividual>SOFTWARE-TEST-ID</NominaIndividual>'),
            })
        return slip

    # ── un ZIP por documento ────────────────────────────────────────────────

    def test_cada_documento_se_envia_en_su_propio_zip(self):
        slips = self._slip('A', 'generated') | self._slip('B', 'generated')
        sizes = []

        def fake_send(records):
            sizes.append(len(records))
            records.write({'l10n_co_ne_state': 'sent', 'l10n_co_ne_zip_key': 'ZIP-%d' % records.id})

        with patch(_PAYSLIP + '.action_send_test_set', autospec=True, side_effect=fake_send), \
                patch(_PAYSLIP + '._validate_company_ne_config'):
            finished = self.engine._step(self.company)
        self.assertFalse(finished)
        self.assertEqual(sizes, [1, 1], 'cada documento debe viajar en su propio ZIP')
        self.assertEqual(set(slips.mapped('l10n_co_ne_state')), {'sent'})
        self.assertEqual(len(set(slips.mapped('l10n_co_ne_zip_key'))), 2)

    def test_send_test_set_con_varios_registros_los_separa_por_zip(self):
        """action_send_test_set sobre un recordset llama una vez por documento."""
        slips = self._slip('A', 'generated') | self._slip('B', 'generated')
        calls = []
        real = type(slips).action_send_test_set

        def spy(records):
            calls.append(len(records))
            if len(records) == 1:
                records.write({'l10n_co_ne_state': 'sent'})
                return {}
            return real(records)

        with patch(_PAYSLIP + '.action_send_test_set', autospec=True, side_effect=spy):
            slips.action_send_test_set()
        self.assertEqual(calls, [2, 1, 1])

    # ── detención y reanudación ─────────────────────────────────────────────

    def test_un_rechazo_detiene_el_proceso_y_muestra_el_motivo(self):
        self._slip('A', 'accepted')
        rejected = self._slip('B', 'rejected')
        rejected.l10n_co_ne_consecutive = 'NE0000000099'
        with patch(_ENGINE + '._rejection_reasons', return_value='Regla: NIAE999, algo falló'):
            finished = self.engine._step(self.company)
        self.assertTrue(finished)
        self.assertEqual(self.company.l10n_co_ne_hab_state, 'error')
        self.assertIn('NE0000000099', self.company.l10n_co_ne_hab_message)
        self.assertIn('NIAE999', self.company.l10n_co_ne_hab_message)

    def test_al_reintentar_se_regeneran_solo_los_rechazados(self):
        ok = self._slip('A', 'accepted')
        bad = self._slip('B', 'rejected')

        def fake_regen(records):
            records.write({'l10n_co_ne_state': 'generated'})

        with patch(_PAYSLIP + '.action_regenerate_ne_xml', autospec=True, side_effect=fake_regen) as regen:
            replaced = self.engine._replace_failed(self.company)
        self.assertEqual(replaced, 1)
        self.assertEqual(regen.call_args[0][0], bad)
        self.assertEqual(ok.l10n_co_ne_state, 'accepted')
        self.assertEqual(bad.l10n_co_ne_state, 'generated')

    # ── orden: individuales primero, luego ajustes ──────────────────────────

    def test_no_prepara_ajustes_mientras_hay_individuales_sin_resolver(self):
        self._slip('A', 'accepted')
        self._slip('B', 'sent')
        with patch(_PAYSLIP + '.action_check_dian_status', return_value=True), \
                patch(_ENGINE + '._prepare') as prepare:
            finished = self.engine._step(self.company)
        self.assertFalse(finished)
        prepare.assert_not_called()

    def test_prepara_ajustes_cuando_todas_las_individuales_estan_aceptadas(self):
        self._slip('A', 'accepted')
        self._slip('B', 'accepted')
        with patch(_ENGINE + '._prepare', return_value=None) as prepare:
            finished = self.engine._step(self.company)
        self.assertFalse(finished)
        prepare.assert_called_once_with(self.company, individual=False)

    def test_prepara_individuales_si_el_set_no_tiene_documentos(self):
        with patch(_ENGINE + '._prepare', return_value=None) as prepare:
            finished = self.engine._step(self.company)
        self.assertFalse(finished)
        prepare.assert_called_once_with(self.company, individual=True)

    def test_error_al_preparar_detiene_el_proceso(self):
        with patch(_ENGINE + '._prepare', return_value='Falta el contrato de un empleado'):
            finished = self.engine._step(self.company)
        self.assertTrue(finished)
        self.assertEqual(self.company.l10n_co_ne_hab_state, 'error')
        self.assertIn('contrato', self.company.l10n_co_ne_hab_message)

    # ── fin y avance ────────────────────────────────────────────────────────

    def test_termina_cuando_se_alcanzan_las_dos_metas(self):
        for name in ('A', 'B'):
            self._slip('I' + name, 'accepted')
            self._slip('J' + name, 'accepted', adjustment=True)
        finished = self.engine._step(self.company)
        self.assertTrue(finished)
        self.assertEqual(self.company.l10n_co_ne_hab_state, 'done')

    def test_progreso_cuenta_aceptadas_y_rechazadas_del_set(self):
        self._slip('A', 'accepted')
        self._slip('B', 'rejected')
        self._slip('C', 'accepted', adjustment=True)
        progress = self.engine.progress(self.company)
        self.assertEqual(progress['ind'], (1, 1, 2))
        self.assertEqual(progress['aj'], (1, 0, 2))
        self.assertEqual(progress['percent'], 50.0)

    # ── aislamiento entre sets ──────────────────────────────────────────────

    def test_un_set_nuevo_ignora_los_documentos_del_set_anterior(self):
        self._slip('Viejo', 'rejected', set_id='SET-ANTERIOR')
        self._slip('Viejo2', 'accepted', set_id=False)
        self.assertEqual(self.engine.progress(self.company)['ind'], (0, 0, 2))
        with patch(_ENGINE + '._prepare', return_value=None) as prepare:
            finished = self.engine._step(self.company)
        self.assertFalse(finished, 'el rechazo de un set anterior no debe detener el set actual')
        prepare.assert_called_once_with(self.company, individual=True)

    # ── configuración ───────────────────────────────────────────────────────

    def test_no_inicia_fuera_de_ambiente_de_pruebas(self):
        self.company.l10n_co_ne_environment = '1'
        with self.assertRaises(UserError):
            self.engine._validate_config(self.company)

    def test_no_inicia_con_metas_mayores_a_los_empleados_de_prueba(self):
        self.company.l10n_co_ne_num_nomina_certificar = 99
        with patch(_PAYSLIP + '._validate_company_ne_config'), self.assertRaises(UserError):
            self.engine._validate_config(self.company)
