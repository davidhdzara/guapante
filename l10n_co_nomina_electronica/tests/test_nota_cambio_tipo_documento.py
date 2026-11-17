# -*- coding: utf-8 -*-
"""Cambio del tipo de documento desde la ficha del empleado (doc 59 §18.8, decision de TL 2026-11-14: B con constancia).

El campo UX-02 escribe el tipo en el contacto de trabajo (con sudo, como hr nativo). El cambio NO se bloquea (el contacto del
empleado recibe asientos publicados desde la primera nomina y el dato correcto del trabajador manda para la nomina
electronica), pero NO es silencioso (principio «sin defaults silenciosos» de David): el contacto recibe una nota en su chatter
con el tipo anterior y el nuevo, la ficha del empleado y el usuario, y dice si el contacto tiene asientos publicados."""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNotaCambioTipoDocumento(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Nota Tipo Documento'})
        cls.usuario = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Responsable Nota Tipo', 'login': 'responsable_nota_tipo', 'email': 'responsable_nota_tipo@example.com',
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('hr_payroll.group_hr_payroll_manager').id])]})
        cls.cedula = cls.env.ref('l10n_co.national_citizen_id')
        cls.pasaporte = cls.env.ref('l10n_latam_base.it_pass')

    def _empleado(self):
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Nota Tipo', 'company_id': self.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        self.assertEqual(empleado.work_contact_id.l10n_latam_identification_type_id, self.cedula)
        return empleado

    def _notas(self, contacto):
        return contacto.message_ids.filtered(lambda m: 'Tipo de documento cambiado' in (m.body or ''))

    def _cambiar(self, empleado, tipo):
        empleado.with_user(self.usuario).with_context(allowed_company_ids=self.company.ids).write(
            {'l10n_co_ne_identification_type_id': tipo.id})

    def test_el_cambio_deja_una_nota_en_el_contacto_con_antes_despues_ficha_y_usuario(self):
        empleado = self._empleado()
        self._cambiar(empleado, self.pasaporte)
        contacto = empleado.work_contact_id
        self.assertEqual(contacto.l10n_latam_identification_type_id, self.pasaporte)    # el cambio NO se bloquea
        notas = self._notas(contacto)
        self.assertEqual(len(notas), 1)
        texto = notas.body
        for esperado in (self.cedula.name, self.pasaporte.name, empleado.name, self.usuario.name):
            self.assertIn(esperado, texto)
        self.assertNotIn('asientos publicados', texto)

    def test_con_asientos_publicados_la_nota_lo_dice_explicitamente(self):
        empleado = self._empleado()
        with patch.object(type(self.env['hr.employee']), '_ne_asientos_publicados_del_contacto', lambda s, c: 3):
            self._cambiar(empleado, self.pasaporte)
        notas = self._notas(empleado.work_contact_id)
        self.assertEqual(len(notas), 1)
        self.assertIn('3 asientos publicados', notas.body)

    def test_sin_cambio_real_no_hay_nota(self):
        empleado = self._empleado()
        self._cambiar(empleado, self.cedula)       # el mismo tipo
        self.assertFalse(self._notas(empleado.work_contact_id))
