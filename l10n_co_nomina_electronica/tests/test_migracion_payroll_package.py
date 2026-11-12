# -*- coding: utf-8 -*-
"""Localización nómina (.99, pedido de David): prueba del script de
migración migrations/18.0.3.0.99/post-backfill_payroll_package.py --
backfill de res.company.l10n_co_ne_payroll_package para compañías
colombianas ya existentes (ej. Guapante), mismo patrón que
test_migracion_identificacion.py (.89/.94).

La carpeta migrations/18.0.3.0.99/ no es un paquete Python importable de
forma normal, así que el script se carga con importlib.util desde su ruta
real -- es la función migrate() real del repo, no una copia reescrita
para la prueba.
"""

import importlib.util
import os

from odoo.tests.common import TransactionCase, tagged


def _cargar_migracion():
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'migrations', '18.0.3.0.99', 'post-backfill_payroll_package.py',
    )
    spec = importlib.util.spec_from_file_location(
        'l10n_co_nomina_electronica_migracion_99', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@tagged('post_install', '-at_install')
class TestMigracionPayrollPackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migracion = _cargar_migracion()

    def test_compania_colombiana_sin_paquete_recibe_colombia(self):
        company = self.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Migración Paquete Sin Paquete',
        })
        company.partner_id.country_id = self.env.ref('base.co').id
        self.assertFalse(company.l10n_co_ne_payroll_package)

        self.migracion.migrate(self.env.cr, '18.0.3.0.99')
        company.invalidate_recordset(['l10n_co_ne_payroll_package'])

        self.assertEqual(company.l10n_co_ne_payroll_package, 'l10n_co_nomina_electronica')

    def test_compania_colombiana_con_paquete_no_se_toca(self):
        """Idempotente: una compañía que YA tiene un paquete elegido (a
        mano, o por una corrida anterior de esta misma migración) nunca
        se sobreescribe."""
        company = self.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Migración Paquete Ya Tiene',
        })
        company.partner_id.country_id = self.env.ref('base.co').id
        company.l10n_co_ne_payroll_package = 'l10n_co_nomina_electronica'

        self.migracion.migrate(self.env.cr, '18.0.3.0.99')
        company.invalidate_recordset(['l10n_co_ne_payroll_package'])

        self.assertEqual(company.l10n_co_ne_payroll_package, 'l10n_co_nomina_electronica')

    def test_compania_no_colombiana_no_se_toca(self):
        company = self.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Migración Paquete No Colombiana',
        })
        company.partner_id.country_id = self.env.ref('base.us').id

        self.migracion.migrate(self.env.cr, '18.0.3.0.99')
        company.invalidate_recordset(['l10n_co_ne_payroll_package'])

        self.assertFalse(company.l10n_co_ne_payroll_package)
