# -*- coding: utf-8 -*-
"""Tipo de estructura "Empleado Colombia" (.102, pedido de David):

- El tipo colombiano de este módulo trae por defecto la estructura "Nómina Colombia - General".
- El cambio queda AISLADO a la localización colombiana: ningún tipo de otro país (ni el
  genérico, sin país) apunta a nuestra estructura.
- El script de un solo uso scripts/reasignar_structure_type_contratos_co.py, en modo simulación
  (por defecto), lista los contratos colombianos con tipo genérico y NO escribe nada.
"""

import os

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStructureTypeDefault(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tipo_co = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_type_co')
        cls.struct = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def test_tipo_colombia_apunta_a_estructura_colombia(self):
        self.assertEqual(self.tipo_co.default_struct_id, self.struct)

    def test_aislado_a_colombia(self):
        otros = self.env['hr.payroll.structure.type'].search([
            ('id', '!=', self.tipo_co.id),
            ('default_struct_id', '=', self.struct.id),
        ])
        self.assertFalse(
            otros,
            'Ningún otro tipo de estructura (otro país o genérico) debe apuntar a la '
            'estructura de Colombia: %s' % otros.mapped('display_name'),
        )

    def test_script_reasignacion_simulacion_no_escribe(self):
        generico = self.env['hr.payroll.structure.type'].create({
            'name': 'Genérico de Prueba (.102)', 'country_id': False,
        })
        compania = self.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba Reasignación (.102)'})
        compania.partner_id.country_id = self.env.ref('base.co').id
        empleado = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Reasignación (.102)', 'company_id': compania.id,
            # Método '10' (efectivo): el default '1' (Transferencia) exige cuenta bancaria
            # (constraint _check_bank_account_for_transfer, H-021) y esta prueba no la necesita.
            'l10n_co_ne_payment_method': '10',
        })
        contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Reasignación (.102)',
            'employee_id': empleado.id,
            'company_id': compania.id,
            'structure_type_id': generico.id,
            'wage': 1800000.0,
            'date_start': '2026-01-01',
        })
        ruta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'reasignar_structure_type_contratos_co.py')
        with open(ruta, encoding='utf-8') as f:
            codigo = f.read()
        os.environ.pop('APLICAR', None)
        espacio = {'env': self.env, '__name__': 'script_prueba'}
        exec(compile(codigo, ruta, 'exec'), espacio)  # noqa: S102
        contrato.invalidate_recordset()
        self.assertEqual(contrato.structure_type_id, generico)
