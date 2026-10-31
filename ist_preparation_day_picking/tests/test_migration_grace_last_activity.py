# -*- coding: utf-8 -*-
"""Gracia de un ciclo completo para last_activity (Tech Lead,
2026-10-31) — migrations/18.0.1.2.0/post-migration.py. El nombre de la
carpeta/archivo no es un identificador Python válido (empieza con un
dígito, tiene guiones) — se carga por ruta, mismo patrón ya usado en
l10n_co_nomina_electronica/tests/test_dian_response_parser.py."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    set_active_prep_operator,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_product_claim.request'
)

_MIGRATION_PATH = (
    Path(__file__).parents[1] / 'migrations' / '18.0.1.2.0'
    / 'post-migration.py'
)
_SPEC = importlib.util.spec_from_file_location(
    'ist_preparation_day_picking_post_migration_18_1_2_0', _MIGRATION_PATH,
)
_post_migration = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_post_migration)


@tagged('post_install', '-at_install')
class TestMigrationGraceLastActivity(TestPreparationDay):
    """Hereda setUpClass de TestPreparationDay (producto/partner/
    almacén) para no duplicar el fixture — mismo patrón que
    TestPreparationDayProductClaim."""

    def setUp(self):
        super().setUp()
        self.Claim = self.env['guapante.preparation.day.product.claim']
        self.env.user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'ist_preparation_day_picking.group_preparation_picking_operator'
            ).id)],
        })
        self.operator_a = self.env['hr.employee'].create({
            'name': 'Operario Migración A',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

    def _request_as(self, employee):
        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        return mock_request

    def _load_session_with_product(self, qty=2.0, product=None):
        self._create_confirmed_order(qty=qty, product=product)
        session = self._create_session()
        session.action_load()
        return session

    def test_migration_sets_last_activity_on_in_progress_claim(self):
        """El escenario real del incidente: un claim En progreso
        heredado (asignado ANTES de que existiera last_activity) debe
        salir de la migración con last_activity puesto — mismo ciclo de
        gracia completo que un claim nuevo."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()
        # Simula el estado real pre-despliegue: el campo nuevo todavía
        # en NULL, como quedaría cualquier fila existente al agregar la
        # columna.
        claim.sudo().write({'last_activity': False})
        self.assertEqual(claim.status, 'in_progress')

        _post_migration.migrate(self.env.cr, '18.0.1.2.0')

        claim.invalidate_recordset(['last_activity'])
        self.assertTrue(
            claim.last_activity,
            'la migración debe poner last_activity en todo claim En '
            'progreso que lo tenga en NULL',
        )

    def test_migration_does_not_touch_pending_stopped_or_done_claims(self):
        """Solo le interesa En progreso — los demás estados no usan
        last_activity para nada, no hay motivo para tocarlos."""
        session = self._load_session_with_product()
        pending_claim = session.product_claim_ids
        self.assertEqual(pending_claim.status, 'pending')

        product_b = self.env['product.product'].create({
            'name': 'Producto Migración Detenido', 'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session.action_load()
        stopped_claim = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_b.product_tmpl_id
        )
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            stopped_claim.action_assign()
            stopped_claim.action_stop('sin_stock')
        self.assertEqual(stopped_claim.status, 'stopped')
        # action_stop() limpia assigned_date pero NO last_activity (le
        # queda el valor real que dejó el action_assign() de arriba) —
        # lo que prueba este test es que la MIGRACIÓN no lo toca, no
        # que el campo esté en False (eso ya no es cierto desde antes
        # de llamar a migrate()).
        last_activity_before = stopped_claim.last_activity

        _post_migration.migrate(self.env.cr, '18.0.1.2.0')

        pending_claim.invalidate_recordset(['last_activity'])
        stopped_claim.invalidate_recordset(['last_activity'])
        self.assertFalse(
            pending_claim.last_activity,
            'un claim Pendiente no debe tocarse',
        )
        self.assertEqual(
            stopped_claim.last_activity, last_activity_before,
            'la migración no debe tocar un claim Detenido',
        )
