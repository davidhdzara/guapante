# -*- coding: utf-8 -*-
"""Fase 2, commits 7/7 y 8/7 (Tech Lead, 2026-11-04) — guard de
hr.employee.unlink() sobre done_by_employee_id (guapante.preparation.
day.line), guapante.picking.log.employee_id y guapante.preparation.
day.responsible_employee_id. El guard sobre guapante.preparation.
interval.employee_id vive en su propio test en
ist_preparation_day_picking (ese modelo solo existe ahí) — este
archivo cubre únicamente lo que define este módulo."""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_preparation_day import TestPreparationDay


@tagged('post_install', '-at_install')
class TestHrEmployeeUnlinkGuard(TestPreparationDay):

    def test_employee_with_done_line_cannot_be_deleted(self):
        session = self._create_session()
        employee = self.env['hr.employee'].create({
            'name': 'Operario a borrar',
            # l10n_co_nomina_electronica exige cuenta bancaria cuando el
            # método de pago es transferencia (default) — sin relación
            # con este guard, pero rompe la creación si se omite.
            'l10n_co_ne_payment_method': '10',
        })
        self.env['guapante.preparation.day.line'].sudo().create({
            'wizard_id': session.id,
            'product_id': self.product_weight.product_tmpl_id.id,
            'product_product_id': self.product_weight.id,
            'is_done': True,
            'actual_kg': 1.5,
            'done_by_employee_id': employee.id,
        })

        with self.assertRaises(UserError):
            employee.unlink()
        self.assertTrue(employee.exists())

    def test_employee_without_done_line_can_be_deleted(self):
        employee = self.env['hr.employee'].create({
            'name': 'Operario sin historial',
            'l10n_co_ne_payment_method': '10',
        })
        employee.unlink()
        self.assertFalse(employee.exists())

    def test_employee_with_picking_log_cannot_be_deleted(self):
        employee = self.env['hr.employee'].create({
            'name': 'Operario en log a borrar',
            'l10n_co_ne_payment_method': '10',
        })
        self.env['guapante.picking.log'].sudo().create({
            'employee_id': employee.id,
        })

        with self.assertRaises(UserError):
            employee.unlink()
        self.assertTrue(employee.exists())

    def test_employee_responsible_of_session_cannot_be_deleted(self):
        session = self._create_session()
        employee = self.env['hr.employee'].create({
            'name': 'Responsable a borrar',
            'l10n_co_ne_payment_method': '10',
        })
        session.sudo().write({'responsible_employee_id': employee.id})

        with self.assertRaises(UserError):
            employee.unlink()
        self.assertTrue(employee.exists())
