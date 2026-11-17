# -*- coding: utf-8 -*-
"""M2 (doc 51): la configuracion de retencion es compartida por anio (company_id vacio) y la propia
de la compania es la excepcion; nunca se usa la de OTRA compania. Migracion: los registros del
modulo pasan a compartidos y los que creo una compania se quedan."""

import importlib.util
import os
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _migracion():
    ruta = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.3.0.176',
                        'post-retefuente_config_compartida.py')
    spec = importlib.util.spec_from_file_location('migracion_176', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@tagged('post_install', '-at_install')
class TestRetefuenteConfigCompartida(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        datos = {'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
                 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.a = Company.create({'name': 'Empresa A Retencion', **datos})
        cls.b = Company.create({'name': 'Empresa B Retencion', **datos})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Retencion Compartida', 'country_id': cls.env.ref('base.co').id})
        cls.est = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.Config = cls.env['l10n.co.retefuente.uvt']

    def _recibo(self, company, anio=2027):
        empleado = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Emp %s' % company.name, 'company_id': company.id})
        contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'C', 'employee_id': empleado.id, 'company_id': company.id,
            'structure_type_id': self.tipo.id, 'wage': 3000000.0,
            'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Prima', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': company.id, 'struct_id': self.est.id,
            'date_from': date(anio, 7, 1), 'date_to': date(anio, 12, 31)})

    def test_no_usa_la_configuracion_de_otra_compania(self):
        propia_de_a = self.Config.create({'year': '2027', 'company_id': self.a.id, 'procedure': '1'})
        self.assertEqual(self._recibo(self.a)._ne_retefuente_config(), propia_de_a)
        with self.assertRaises(UserError) as exc:
            self._recibo(self.b)._ne_retefuente_config()
        self.assertIn('2027', str(exc.exception))
        self.assertIn('Empresa B Retencion', str(exc.exception))

    def test_la_compartida_sirve_a_toda_compania_sin_propia(self):
        compartida = self.Config.create({'year': '2027', 'company_id': False, 'procedure': '1'})
        self.assertEqual(self._recibo(self.a)._ne_retefuente_config(), compartida)
        self.assertEqual(self._recibo(self.b)._ne_retefuente_config(), compartida)

    def test_la_propia_tiene_prioridad_sobre_la_compartida(self):
        self.Config.create({'year': '2027', 'company_id': False, 'procedure': '1'})
        propia = self.Config.create({'year': '2027', 'company_id': self.a.id, 'procedure': '2'})
        self.assertEqual(self._recibo(self.a)._ne_retefuente_config(), propia)
        self.assertEqual(
            self.Config.get_uvt_for_year('2027', self.a), propia)
        self.assertFalse(self.Config.get_uvt_for_year('2027', self.b).company_id)

    def test_migracion_pasa_los_del_modulo_a_compartidos_y_respeta_los_propios(self):
        migracion = _migracion()
        r2026 = self.env.ref('l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2026')
        r2026.company_id = self.a
        creada = self.Config.create({'year': '2031', 'company_id': self.a.id, 'procedure': '1'})
        migracion.compartir_registros_del_modulo(self.env)
        self.assertFalse(r2026.company_id)
        self.assertEqual(creada.company_id, self.a)
        self.assertEqual(migracion.compartir_registros_del_modulo(self.env), 0)  # idempotente
