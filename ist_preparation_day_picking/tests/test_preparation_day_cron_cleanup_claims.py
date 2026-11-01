# -*- coding: utf-8 -*-
"""#4 (David/Tech Lead, 2026-10-31): el cron de limpieza de sesiones
vacías (ist_preparation_day._cron_repair_missing_orders) nunca borra
una sesión que tenga un claim de Nivel 1 de Picking — vive en este
módulo (no en ist_preparation_day) porque guapante.preparation.day.
product.claim solo existe acá."""
from datetime import timedelta
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

CURRENT_SESSION_DATE_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '._current_session_date'
)


@tagged('post_install', '-at_install')
class TestPreparationDayCronCleanupClaims(TestPreparationDay):

    def _run_cron_as_of(self, fake_today):
        with patch(CURRENT_SESSION_DATE_TARGET, return_value=fake_today):
            self.env['guapante.preparation.day']._cron_repair_missing_orders()

    def test_cron_never_deletes_session_with_stopped_claim_without_owner(self):
        fake_today = self.delivery_date
        far_day = fake_today + timedelta(days=30)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', far_day)], limit=1,
        ) or self.env['guapante.preparation.day'].create({'date': far_day})
        self.assertFalse(Session.line_ids)

        self.env['guapante.preparation.day.product.claim'].create({
            'wizard_id': Session.id,
            'product_tmpl_id': self.product_weight.product_tmpl_id.id,
            'stop_reason': 'sin_stock',
        })
        session_id = Session.id

        self._run_cron_as_of(fake_today)

        self.assertTrue(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'un claim detenido sin dueño activo sigue siendo trabajo '
            'hecho — la sesión no se borra aunque hoy no tenga líneas',
        )
