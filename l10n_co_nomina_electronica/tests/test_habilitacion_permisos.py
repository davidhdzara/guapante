# -*- coding: utf-8 -*-
"""H-022: ``l10n.co.ne.habilitacion.start`` exige rol y compañía antes de escribir nada."""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_ENGINE = 'odoo.addons.l10n_co_nomina_electronica.models.l10n_co_ne_habilitacion.L10nCoNeHabilitacion'


@tagged('post_install', '-at_install')
class TestHabilitacionPermisos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba Permisos Habilitación'})
        cls.otra = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Ajena Permisos Habilitación'})
        cls.company.l10n_co_ne_hab_state = 'idle'

    def _usuario(self, login, grupos, companies=None):
        companies = companies or self.company
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'company_id': companies[0].id, 'company_ids': [(6, 0, companies.ids)],
            'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])],
        })

    def _start(self, user, company=None):
        company = company or self.company
        with patch(_ENGINE + '._schedule') as schedule:
            try:
                self.env['l10n.co.ne.habilitacion'].with_user(user).start(
                    company.with_user(user))
            finally:
                self.schedule_llamado = schedule.called

    def _assert_sin_efectos(self):
        self.assertEqual(self.company.l10n_co_ne_hab_state, 'idle')
        self.assertFalse(self.schedule_llamado)

    def test_usuario_interno_sin_rol_no_puede(self):
        user = self._usuario('hab_sin_rol', ['base.group_user'])
        with self.assertRaisesRegex(AccessError, 'rol'):
            self._start(user)
        self._assert_sin_efectos()

    def test_mensaje_nombra_el_rol_sin_nombre_tecnico(self):
        user = self._usuario('hab_msg', ['base.group_user'])
        with self.assertRaises(AccessError) as ctx:
            self._start(user)
        self.assertNotIn('group_hr_payroll_manager', str(ctx.exception))
        self.assertIn(
            self.env.ref('hr_payroll.group_hr_payroll_manager').full_name, str(ctx.exception))

    def test_administrador_de_nomina_pasa_el_chequeo(self):
        user = self._usuario('hab_nomina', ['hr_payroll.group_hr_payroll_manager'])
        # Con sus permisos no debe fallar por AccessError; la validación de configuración
        # (sin certificado, etc.) devuelve un aviso, no excepción.
        self._start(user)

    def test_administrador_del_sistema_pasa_el_chequeo(self):
        user = self._usuario('hab_sistema', ['base.group_system'])
        self._start(user)

    def test_compania_ajena_no_puede(self):
        user = self._usuario('hab_ajena', ['hr_payroll.group_hr_payroll_manager'])
        with self.assertRaisesRegex(AccessError, 'acceso'):
            self._start(user, company=self.otra)
        self._assert_sin_efectos()
