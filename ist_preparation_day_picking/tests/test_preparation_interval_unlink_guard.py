# -*- coding: utf-8 -*-
"""Fase 2, commit 7/7 (Tech Lead, 2026-11-04) — guard de hr.employee.
unlink() sobre guapante.preparation.interval.employee_id. El guard
sobre done_by_employee_id (guapante.preparation.day.line) vive en su
propio test en ist_preparation_day (ese campo es de ese módulo) —
este archivo cubre únicamente lo que agrega Picking."""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationIntervalUnlinkGuard(TestPreparationDayProductClaim):

    def test_employee_with_interval_cannot_be_deleted(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        employee = self.env['hr.employee'].create({
            'name': 'Operario con intervalo a borrar',
            'l10n_co_ne_payment_method': '10',
        })
        self._create_interval(
            claim, 'working', employee=employee,
            start_dt='2026-11-04 10:00:00',
            end_dt='2026-11-04 10:10:00', duration_s=600,
        )

        with self.assertRaises(UserError):
            employee.unlink()
        self.assertTrue(employee.exists())

    def test_employee_without_interval_can_be_deleted(self):
        employee = self.env['hr.employee'].create({
            'name': 'Operario sin intervalos',
            'l10n_co_ne_payment_method': '10',
        })
        employee.unlink()
        self.assertFalse(employee.exists())
