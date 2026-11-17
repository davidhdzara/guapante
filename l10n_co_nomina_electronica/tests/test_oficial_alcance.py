# -*- coding: utf-8 -*-
"""Frente 6, P6-3 (doc 59 4.4, F6-ROL): la visibilidad del documento mensual, sus intentos, el IBC mensual y el
reparto por tercero no excede la del recibo. El oficial de nomina solo ve lo de los empleados cuyo recibo ve
(empleado propio, sin departamento o de un departamento que el gerencia); el administrador ve todo; un usuario
interno sin rol de nomina no ve nada. Usuarios REALES con correo."""

from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture

CUNE = 'c' * 96


@tagged('post_install', '-at_install')
class TestOficialAlcance(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Alcance Oficial')
        grupo_base = cls.env.ref('base.group_user').id

        def usuario(clave, grupo=None):
            grupos = [grupo_base] + ([cls.env.ref(grupo).id] if grupo else [])
            return cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'Alcance %s' % clave, 'login': 'alcance_%s' % clave,
                'email': 'alcance_%s@example.com' % clave, 'company_id': cls.company.id,
                'company_ids': [(6, 0, cls.company.ids)], 'groups_id': [(6, 0, grupos)]})

        cls.oficial = usuario('oficial', 'hr_payroll.group_hr_payroll_user')
        cls.administrador = usuario('administrador', 'hr_payroll.group_hr_payroll_manager')
        cls.interno = usuario('interno')
        cls.gerente_ajeno = usuario('gerente_ajeno')
        depto_ajeno = cls.env['hr.department'].create({
            'name': 'Departamento ajeno alcance', 'company_id': cls.company.id,
            'manager_id': cls.env['hr.employee'].create({
                'name': 'Gerente ajeno', 'company_id': cls.company.id, 'user_id': cls.gerente_ajeno.id,
                'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'}).id})
        depto_propio = cls.env['hr.department'].create({
            'name': 'Departamento propio alcance', 'company_id': cls.company.id,
            'manager_id': cls.env['hr.employee'].create({
                'name': 'Gerente oficial', 'company_id': cls.company.id, 'user_id': cls.oficial.id,
                'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'}).id})
        cls.docs = {}
        for clave, depto in (('sin_departamento', False), ('del_oficial', depto_propio), ('ajeno', depto_ajeno)):
            doc = DocumentoFixture._documento(cls, date(2024, 3, 1))
            doc.employee_id.department_id = depto.id if depto else False
            cls.docs[clave] = doc
            cls.env['l10n.co.ne.documento.intento'].create({
                'documento_id': doc.id, 'state': 'invoice_pending', 'identifier': CUNE, 'numero': 'NE15',
                'datetime': '2026-04-05 10:00:00'})
            cls.env['l10n.co.ibc.mensual'].create({
                'company_id': cls.company.id, 'employee_id': doc.employee_id.id, 'period': date(2026, 3, 1)})
            cls.env['l10n.co.payslip.tercero'].create({
                'slip_id': doc.payslip_ids[:1].id, 'rule_code': 'ALCANCE_%s' % clave})

    def _ver(self, usuario, modelo):
        return self.env[modelo].with_user(usuario).with_context(allowed_company_ids=self.company.ids)

    def _claves_visibles(self, usuario):
        """Claves de los 3 empleados cuyo documento, intento, IBC y tercero ve el usuario (deben coincidir)."""
        visibles = {}
        visibles['documento'] = {
            k for k, d in self.docs.items() if self._ver(usuario, 'l10n.co.ne.documento').search([('id', '=', d.id)])}
        visibles['intento'] = {
            k for k, d in self.docs.items() if self._ver(usuario, 'l10n.co.ne.documento.intento').search(
                [('documento_id', '=', d.id)])}
        visibles['ibc'] = {
            k for k, d in self.docs.items() if self._ver(usuario, 'l10n.co.ibc.mensual').search(
                [('employee_id', '=', d.employee_id.id)])}
        visibles['tercero'] = {
            k for k, d in self.docs.items() if self._ver(usuario, 'l10n.co.payslip.tercero').search(
                [('slip_id', 'in', d.payslip_ids.ids)])}
        for modelo, valor in visibles.items():
            self.assertEqual(valor, visibles['documento'], '%s debe ver lo mismo que el documento' % modelo)
        return visibles['documento']

    def test_administrador_ve_todo(self):
        self.assertEqual(self._claves_visibles(self.administrador), {'sin_departamento', 'del_oficial', 'ajeno'})

    def test_oficial_ve_sin_departamento_y_el_de_su_departamento_pero_no_el_ajeno(self):
        self.assertEqual(self._claves_visibles(self.oficial), {'sin_departamento', 'del_oficial'})

    def test_oficial_con_empleado_propio_ve_su_documento(self):
        # Un usuario por empleado y compania (hr_employee_user_uniq): se desliga el empleado gerente que ya tenia.
        self.env['hr.employee'].with_context(active_test=False).search([
            ('user_id', '=', self.oficial.id), ('company_id', '=', self.company.id)]).write({'user_id': False})
        self.env.flush_all()   # el ORM aplaza las escrituras: sin volcarlas, ambos UPDATE chocan juntos en la restriccion unica
        propio = self.docs['ajeno'].employee_id
        propio.user_id = self.oficial
        self.assertIn('ajeno', self._claves_visibles(self.oficial))

    def test_oficial_no_lee_el_documento_ajeno_con_error_claro(self):
        doc = self.docs['ajeno'].with_user(self.oficial).with_context(allowed_company_ids=self.company.ids)
        with self.assertRaises(AccessError):
            doc.read(['period'])

    def test_usuario_interno_sin_rol_no_ve_nada(self):
        for modelo in ('l10n.co.ne.documento', 'l10n.co.ne.documento.intento', 'l10n.co.ibc.mensual',
                       'l10n.co.payslip.tercero'):
            with self.assertRaises(AccessError, msg=modelo):
                self.env[modelo].with_user(self.interno).search([])

    def test_adjuntos_del_documento_ajeno_no_se_leen_pero_los_propios_si(self):
        """F6-EMP-001 / B3: el adjunto sigue el acceso al registro padre (ir.attachment.check)."""
        adjuntos = {}
        for clave in ('ajeno', 'sin_departamento'):
            adjuntos[clave] = self.env['ir.attachment'].create({
                'name': 'adjunto_%s.xml' % clave, 'raw': b'<x/>', 'res_model': 'l10n.co.ne.documento',
                'res_id': self.docs[clave].id})
        ver = lambda usuario, adjunto: adjunto.with_user(usuario).with_context(  # noqa: E731
            allowed_company_ids=self.company.ids).read(['name'])
        with self.assertRaises(AccessError):
            ver(self.oficial, adjuntos['ajeno'])
        with self.assertRaises(AccessError):
            ver(self.interno, adjuntos['sin_departamento'])
        self.assertTrue(ver(self.oficial, adjuntos['sin_departamento']))
        self.assertTrue(ver(self.administrador, adjuntos['ajeno']))
