# -*- coding: utf-8 -*-
"""Frente 6, P6-1 (doc 59 §3 B1, §6 F6-AIS): el aislamiento multiempresa se DESCUBRE, no se lista a mano.

Todo modelo definido por este modulo con `company_id` debe tener una `ir.rule` por compania, y todo modelo
persistente propio debe tener al menos un permiso de acceso. Un modelo futuro sin regla hace fallar la prueba y
el mensaje lo nombra. Ademas, dos companias colombianas y usuarios reales con correo: ningun registro visible
para el usuario de A pertenece a B (y viceversa), en cada modelo descubierto.
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

MODULO = 'l10n_co_nomina_electronica'


def _modelos_propios(env):
    """Modelos que ESTE modulo define (no los que solo hereda), persistentes, con su clase del registro."""
    return sorted(
        nombre for nombre, clase in env.registry.items()
        if getattr(clase, '_original_module', None) == MODULO
        and not clase._abstract and not clase._transient)


@tagged('post_install', '-at_install')
class TestMultiempresaDescubrimiento(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        co = cls.env.ref('base.co')
        cls.a = cls.env['res.company'].create({'name': 'Descubrimiento A', 'country_id': co.id})
        cls.b = cls.env['res.company'].create({'name': 'Descubrimiento B', 'country_id': co.id})
        grupos = [cls.env.ref('base.group_user').id, cls.env.ref('hr_payroll.group_hr_payroll_manager').id]

        def usuario(clave, compania):
            return cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'Descubrimiento %s' % clave, 'login': 'descubrimiento_%s' % clave,
                'email': 'descubrimiento_%s@example.com' % clave, 'company_id': compania.id,
                'company_ids': [(6, 0, compania.ids)], 'groups_id': [(6, 0, grupos)]})

        cls.user_a = usuario('a', cls.a)
        cls.user_b = usuario('b', cls.b)

    def test_se_descubren_modelos_propios(self):
        """Si el descubrimiento no encuentra nada, las demas pruebas pasarian en vacio."""
        modelos = _modelos_propios(self.env)
        for esperado in ('l10n.co.ne.documento', 'l10n.co.ibc.mensual', 'l10n.co.pila.planilla'):
            self.assertIn(esperado, modelos)

    def test_todo_modelo_propio_con_compania_tiene_regla_por_compania(self):
        sin_regla = []
        for modelo in _modelos_propios(self.env):
            if 'company_id' not in self.env[modelo]._fields:
                continue
            reglas = self.env['ir.rule'].sudo().search([('model_id.model', '=', modelo)])
            if not any('company_id' in (r.domain_force or '') for r in reglas):
                sin_regla.append(modelo)
        self.assertFalse(
            sin_regla, 'Modelos propios con company_id SIN ir.rule por compania (agregarla en security/): %s'
            % ', '.join(sin_regla))

    def test_todo_modelo_propio_persistente_tiene_permiso_de_acceso(self):
        sin_acl = [
            modelo for modelo in _modelos_propios(self.env)
            if not self.env['ir.model.access'].sudo().search_count([('model_id.model', '=', modelo)])]
        self.assertFalse(
            sin_acl, 'Modelos propios SIN permiso de acceso (agregar a security/ir.model.access.csv): %s'
            % ', '.join(sin_acl))

    def test_ningun_registro_visible_pertenece_a_la_otra_compania(self):
        """F6-AIS-001: con los datos que haya, lo que ve el usuario de A nunca es de B ni al reves."""
        for modelo in _modelos_propios(self.env):
            if 'company_id' not in self.env[modelo]._fields:
                continue
            for usuario, ajena in ((self.user_a, self.b), (self.user_b, self.a)):
                visibles = self.env[modelo].with_user(usuario).with_context(
                    allowed_company_ids=usuario.company_ids.ids).search([])
                self.assertFalse(
                    visibles.filtered(lambda r: r.sudo().company_id == ajena),
                    '%s: %s ve registros de %s' % (modelo, usuario.login, ajena.name))

    def test_refrescar_el_ibc_de_a_con_sudo_no_toca_el_de_b(self):
        """F6-SUD-001: `l10n.co.ibc.mensual._refrescar` usa sudo para recalcular; solo debe tocar la compania,
        el empleado y el mes que recibe (sin recibos elimina SU consolidado, nunca el de otra compania)."""
        periodo = date(2026, 3, 1)
        Ibc = self.env['l10n.co.ibc.mensual']
        filas = {}
        for clave, compania in (('a', self.a), ('b', self.b)):
            empleado = self.env['hr.employee'].create({
                'name': 'Empleado IBC %s' % clave, 'company_id': compania.id,
                'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'})
            filas[clave] = Ibc.create({'company_id': compania.id, 'employee_id': empleado.id, 'period': periodo})
        Ibc.with_user(self.user_a).with_context(allowed_company_ids=self.a.ids)._refrescar(
            self.a, filas['a'].employee_id, periodo)
        self.assertFalse(filas['a'].exists(), 'Sin recibos, el consolidado de A se elimina')
        self.assertTrue(filas['b'].exists(), 'El consolidado de B no se toca')
