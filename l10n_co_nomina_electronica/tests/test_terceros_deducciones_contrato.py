# -*- coding: utf-8 -*-
"""Deducciones del contrato con tercero obligatorio (commit 2 de terceros).

Nivel de verificacion: validacion sobre lineas de nomina sinteticas; el
asiento por tercero se prueba en el commit de asientos.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTercerosDeduccionesContrato(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La compania activa debe ser colombiana: la logica del modulo solo corre para Colombia.
        cls.env.company.partner_id.country_id = cls.env.ref('base.co')
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Deducciones'})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Deducciones', 'employee_id': cls.employee.id,
            'wage': 3000000, 'date_start': '2026-01-01', 'state': 'draft',
        })
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Nomina Deducciones', 'employee_id': cls.employee.id,
            'contract_id': cls.contract.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
        })
        cls.regla = cls.env.ref('l10n_co_nomina_electronica.hr_salary_rule_co_sindicato')

    def _linea(self, total):
        self.env['hr.payslip.line'].create({
            'slip_id': self.slip.id, 'salary_rule_id': self.regla.id,
            'code': 'CO_SINDICATO', 'name': 'Cuota Sindical',
            'category_id': self.regla.category_id.id,
            'employee_id': self.employee.id, 'contract_id': self.contract.id,
            'total': total, 'amount': total, 'quantity': 1, 'rate': 100,
        })

    def test_deduccion_sin_tercero_da_error_claro(self):
        self._linea(-50000.0)
        with self.assertRaises(UserError) as e:
            self.slip._ne_validar_terceros_deducciones()
        self.assertIn('Sindicato', str(e.exception))
        self.assertIn(self.contract.display_name, str(e.exception))

    def test_deduccion_con_tercero_pasa(self):
        self.contract.l10n_co_ne_sindicato_partner_id = self.env['res.partner'].create({
            'name': 'Sindicato Prueba', 'l10n_co_entity_type': 'other'})
        self._linea(-50000.0)
        self.slip._ne_validar_terceros_deducciones()

    def test_deduccion_en_cero_no_exige_tercero(self):
        self._linea(0.0)
        self.slip._ne_validar_terceros_deducciones()
