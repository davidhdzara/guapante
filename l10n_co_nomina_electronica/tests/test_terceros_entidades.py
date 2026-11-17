# -*- coding: utf-8 -*-
"""Terceros reales (EPS, AFP, CCF, ARL, SENA, ICBF, DIAN) como contactos.

El codigo PILA vive en el contacto; empleado y compania lo derivan. Nivel de
verificacion: modelo/campos; el asiento contable por tercero se prueba en el
commit siguiente.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTercerosEntidades(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.eps = Partner.create({
            'name': 'EPS Prueba', 'l10n_co_entity_type': 'eps',
            'l10n_co_pila_entity_code': 'EPS999'})
        cls.arl = Partner.create({
            'name': 'ARL Prueba', 'l10n_co_entity_type': 'arl',
            'l10n_co_pila_entity_code': '14-99'})
        cls.empleado = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Terceros'})
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Terceros'})

    def test_empleado_deriva_codigo_del_contacto(self):
        self.empleado.l10n_co_pila_eps_id = self.eps
        self.assertEqual(self.empleado.l10n_co_pila_eps_code, 'EPS999')
        self.eps.l10n_co_pila_entity_code = 'EPS000'
        self.assertEqual(self.empleado.l10n_co_pila_eps_code, 'EPS000')

    def test_empleado_sin_contacto_no_tiene_codigo(self):
        self.assertFalse(self.empleado.l10n_co_pila_afp_code)
        self.assertFalse(self.empleado.l10n_co_pila_ccf_code)

    def test_compania_deriva_codigo_y_nombre_arl(self):
        self.company.l10n_co_pila_arl_id = self.arl
        self.assertEqual(self.company.l10n_co_pila_arl_code, '14-99')
        self.assertEqual(self.company.l10n_co_pila_arl_name, 'ARL Prueba')

    def test_campos_fijos_por_compania(self):
        for campo in ('l10n_co_sena_partner_id', 'l10n_co_icbf_partner_id',
                      'l10n_co_dian_partner_id'):
            self.assertIn(campo, self.company._fields)
            self.assertFalse(self.company[campo])

