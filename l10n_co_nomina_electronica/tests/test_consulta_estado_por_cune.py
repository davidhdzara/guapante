# -*- coding: utf-8 -*-
"""H-006: el asistente "Consultar estado DIAN por CUNE" resuelve el CUNE a la nómina que lo
generó con el historial de envíos (l10n.co.ne.exchange.document) y reutiliza
action_check_dian_status(). No toca la DIAN: la consulta real se simula con un doble.

Nivel de verificación (doc 38): resolución CUNE -> nómina y errores; NO cubre la respuesta real
de la DIAN (esa lógica es la ya verificada de action_check_dian_status)."""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestConsultaEstadoPorCune(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        co = cls.env.ref('base.co')
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Consulta CUNE'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura CUNE', 'country_id': co.id})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba CUNE', 'type_id': cls.structure_type.id})

    def _payslip(self, name='Consulta CUNE'):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})

    def _envio(self, payslip, cune, zip_key='ZIP-PRUEBA-1'):
        intercambio = self.env['l10n.co.ne.exchange'].sudo().create({
            'company_id': self.company.id, 'operation': 'send_test_set',
            'endpoint': 'https://prueba.invalid', 'zip_key': zip_key})
        self.env['l10n.co.ne.exchange.document'].sudo().create({
            'exchange_id': intercambio.id, 'payslip_id': payslip.id, 'cune': cune,
            'file_name': 'doc.xml', 'sha256': 'x'})
        return intercambio

    def test_cune_conocido_resuelve_la_nomina_y_consulta(self):
        payslip = self._payslip()
        self._envio(payslip, 'CUNE-CONOCIDO', zip_key='ZIP-AAA')
        wizard = self.env['l10n.co.ne.status.cune.wizard'].create({'cune': ' CUNE-CONOCIDO '})
        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento_mixin.'
            'L10nCoNeDocumentoMixin.'
            'action_check_dian_status', autospec=True, return_value=True,
        ) as consulta:
            wizard.action_check_status()
        self.assertEqual(consulta.call_args[0][0], payslip)
        self.assertEqual(payslip.l10n_co_ne_zip_key, 'ZIP-AAA')

    def test_cune_desconocido_levanta_usererror_claro(self):
        wizard = self.env['l10n.co.ne.status.cune.wizard'].create({'cune': 'CUNE-INEXISTENTE'})
        with self.assertRaises(UserError) as exc:
            wizard.action_check_status()
        self.assertIn('no encontrado', str(exc.exception))

    def _usuario(self, login, companias):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'company_id': companias[0].id,
            'company_ids': [(6, 0, companias.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr_payroll.group_hr_payroll_manager').id])]})

    def _otra_compania(self):
        return self.env['res.company'].create({
            'name': 'Otra Compania CUNE', 'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})

    def test_cune_de_otra_compania_no_se_resuelve(self):
        """Un usuario cuyas companias permitidas son solo 'otra' no encuentra el CUNE de la
        compania A: la regla multiempresa del historial de envios lo oculta (no es un filtro del
        asistente por la compania activa)."""
        otra = self._otra_compania()
        payslip = self._payslip('CiaA')
        self._envio(payslip, 'CUNE-CIA-A')
        usuario = self._usuario('cune_solo_otra', otra)
        wizard = self.env['l10n.co.ne.status.cune.wizard'].with_user(usuario).with_context(
            allowed_company_ids=[otra.id]).create({'cune': 'CUNE-CIA-A'})
        with self.assertRaises(UserError) as exc:
            wizard.action_check_status()
        self.assertIn('no encontrado', str(exc.exception))

    def test_usuario_con_ambas_companias_resuelve_el_cune_hasta_la_consulta(self):
        otra = self._otra_compania()
        payslip = self._payslip('CiaA2')
        self._envio(payslip, 'CUNE-CIA-A2', zip_key='ZIP-BBB')
        usuario = self._usuario('cune_ambas', self.company | otra)
        wizard = self.env['l10n.co.ne.status.cune.wizard'].with_user(usuario).with_context(
            allowed_company_ids=[otra.id, self.company.id]).create({'cune': 'CUNE-CIA-A2'})
        with patch(
            'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_documento_mixin.'
            'L10nCoNeDocumentoMixin.'
            'action_check_dian_status', autospec=True, return_value=True,
        ) as consulta:
            wizard.action_check_status()
        self.assertEqual(consulta.call_args[0][0], payslip)
