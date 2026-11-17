# -*- coding: utf-8 -*-
"""Migracion .173: borra el parametro obsoleto l10n_co_max_renta_exenta_uvt (240 UVT/mes) y
conserva el nuevo (790 UVT/anio). Idempotente."""

import importlib.util
import os

from odoo.tests.common import TransactionCase, tagged


def _cargar_migracion():
    ruta = os.path.join(
        os.path.dirname(__file__), '..', 'migrations', '18.0.3.0.173',
        'post-remove_max_renta_exenta_uvt_mensual.py')
    spec = importlib.util.spec_from_file_location('migracion_172', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@tagged('post_install', '-at_install')
class TestMigracionMaxRentaExenta(TransactionCase):
    def _viejo(self):
        param = self.env['hr.rule.parameter'].create({
            'name': 'Obsoleto', 'code': 'l10n_co_max_renta_exenta_uvt',
            'country_id': self.env.ref('base.co').id})
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': param.id, 'parameter_value': '240.0',
            'date_from': '2024-01-01'})
        return param

    def test_borra_el_parametro_viejo_con_sus_valores_y_conserva_el_nuevo(self):
        migracion = _cargar_migracion()
        param = self._viejo()
        valores = param.parameter_version_ids
        self.assertTrue(valores)
        self.assertEqual(migracion.borrar_parametro_viejo(self.env), 1)
        self.assertFalse(self.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_max_renta_exenta_uvt')]))
        self.assertFalse(valores.exists())
        self.assertTrue(self.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_max_renta_exenta_uvt_anual')]))

    def test_es_idempotente(self):
        migracion = _cargar_migracion()
        self.assertEqual(migracion.borrar_parametro_viejo(self.env), 0)
