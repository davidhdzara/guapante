# -*- coding: utf-8 -*-
"""Nomina > Configuracion > Ajustes con SOLO una compania mexicana activa abre sin error de acceso
(.187): los diarios de las estructuras colombianas solo se leen/escriben para companias colombianas.
Usuario NO superusuario (la regla nativa por pais oculta las estructuras colombianas)."""

from odoo.tests.common import TransactionCase, tagged

CAMPOS_DIARIO = ('l10n_co_ne_journal_nomina_id', 'l10n_co_ne_journal_prima_id',
                 'l10n_co_ne_journal_liquidacion_id', 'l10n_co_ne_journal_bonificacion_id')


@tagged('post_install', '-at_install')
class TestAjustesCompaniaMexicana(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        datos = {'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
                 'l10n_co_ne_redondeo_dias': 'DOWN',
                 'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U'}
        cls.co = cls.env['res.company'].create({
            'name': 'Empresa CO Ajustes', 'country_id': cls.env.ref('base.co').id, **datos})
        cls.mx = cls.env['res.company'].create({
            'name': 'Empresa MX Ajustes', 'country_id': cls.env.ref('base.mx').id})
        grupos = [cls.env.ref('base.group_user').id, cls.env.ref('base.group_system').id,
                  cls.env.ref('hr_payroll.group_hr_payroll_manager').id]
        cls.user_mx = cls.env['res.users'].create({
            'name': 'ajustes_mx', 'login': 'ajustes_mx', 'company_id': cls.mx.id,
            'company_ids': [(6, 0, cls.mx.ids)], 'groups_id': [(6, 0, grupos)]})

    def _valores(self, user, company):
        ajustes = self.env['res.config.settings'].with_user(user).with_context(
            allowed_company_ids=[company.id])
        return ajustes.with_company(company).get_values()

    def test_ajustes_con_solo_la_compania_mexicana_no_dan_error_de_acceso(self):
        res = self._valores(self.user_mx, self.mx)
        for campo in CAMPOS_DIARIO:
            self.assertFalse(res.get(campo), campo)

    def test_con_compania_colombiana_activa_se_leen_los_diarios_de_las_estructuras(self):
        user = self.env['res.users'].create({
            'name': 'ajustes_co', 'login': 'ajustes_co', 'company_id': self.co.id,
            'company_ids': [(6, 0, (self.co | self.mx).ids)],
            'groups_id': [(6, 0, self.user_mx.groups_id.ids)]})
        res = self._valores(user, self.co)
        for campo in CAMPOS_DIARIO:
            self.assertIn(campo, res)
