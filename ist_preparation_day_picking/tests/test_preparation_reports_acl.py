# -*- coding: utf-8 -*-
"""Fase 2, commit 6/7 (Tech Lead, 2026-11-04) — ACL de los modelos de
Fase 2 que hasta 5/7 solo se usaban por sudo() (sin exponer un solo
menú/ACL propio): guapante.preparation.interval, .operator.report,
.interval.report (.product.demand.report se quitó en la Tarea 3,
Tech Lead/David, 2026-11-05). Regla: el operario de
Picking no tiene acceso a ninguno (no ve tiempo ni reportes desde la
pantalla de Picking — eso es trabajo de Diana/Mauricio, no del
operario); el administrador de Preparación solo lee (nunca crea,
escribe ni borra un intervalo a mano — esos los crea la propia lógica
de Picking, siempre por sudo()).

operacion@donguapante.com (Fase 2, punto 4 citado por Tech Lead): el
usuario compartido real del tablet de Picking en staging_dev — no un
usuario sintético. Confirmado por consulta directa (SQL, solo lectura)
que en la categoría "Preparación" tiene únicamente el grupo "Operario
de Picking", nunca "Administrador" — aunque sí tiene grupos de
administrador de OTRAS apps (Empleados, Nómina, etc., de un perfil de
cuenta de servicio) que no son los que estos ACL verifican."""
import uuid

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationReportsAcl(TestPreparationDayProductClaim):

    def setUp(self):
        super().setUp()
        self.admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.operator_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_picking_operator',
        )
        self.reports_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_reports_pds',
        )
        self.internal_group = self.env.ref('base.group_user')

        # Tema A (2026-11-08): los reportes ya NO los da group_preparation_
        # admin sino «Reportes y PDS» (grupo aparte, sin implied_ids).
        self.prep_reports_user = self.env['res.users'].create({
            'name': 'Reportes y PDS Test (ACL reportes)',
            'login': f'prep.reports.acl.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.reports_group.id, self.internal_group.id,
            ])],
        })
        self.prep_admin_user = self.env['res.users'].create({
            'name': 'Admin Preparación Test (ACL reportes)',
            'login': f'prep.admin.acl.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.admin_group.id, self.internal_group.id,
            ])],
        })
        self.prep_operator_user = self.env['res.users'].create({
            'name': 'Operario Test (ACL reportes)',
            'login': f'prep.operator.acl.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.operator_group.id, self.internal_group.id,
            ])],
        })

        session = self._load_session_with_product()
        self.claim = session.product_claim_ids

    # ── Operario: sin acceso a intervalos ──

    def test_operator_cannot_read_intervals(self):
        self.Interval.sudo().create({
            'wizard_id': self.claim.wizard_id.id,
            'claim_id': self.claim.id,
            'employee_id': self.operator_a.id,
            'kind': 'working',
            'start_dt': '2026-11-04 10:00:00',
            'last_touched_dt': '2026-11-04 10:00:00',
        })
        with self.assertRaises(AccessError):
            self.Interval.with_user(self.prep_operator_user).search([])

    def test_operator_cannot_create_intervals(self):
        with self.assertRaises(AccessError):
            self.Interval.with_user(self.prep_operator_user).create({
                'wizard_id': self.claim.wizard_id.id,
                'claim_id': self.claim.id,
                'employee_id': self.operator_a.id,
                'kind': 'working',
                'start_dt': '2026-11-04 10:00:00',
                'last_touched_dt': '2026-11-04 10:00:00',
            })

    # ── Admin: solo lectura en los 4 modelos ──

    def test_reports_group_user_can_read_the_two_reports(self):
        for model_name in (
            'guapante.preparation.operator.report',
            'guapante.preparation.interval.report',
        ):
            self.env[model_name].with_user(self.prep_reports_user).search_read(
                [], ['id'],
            )  # no debe lanzar AccessError

    def test_admin_without_reports_group_cannot_read_the_two_reports(self):
        """Tema A: Administrador de Preparación (ej. Mauricio) sin el
        permiso «Reportes y PDS» NO ve los reportes."""
        for model_name in (
            'guapante.preparation.operator.report',
            'guapante.preparation.interval.report',
        ):
            with self.assertRaises(AccessError):
                self.env[model_name].with_user(
                    self.prep_admin_user,
                ).search_read([], ['id'])

    def test_operator_cannot_read_the_two_reports(self):
        for model_name in (
            'guapante.preparation.operator.report',
            'guapante.preparation.interval.report',
        ):
            with self.assertRaises(AccessError):
                self.env[model_name].with_user(
                    self.prep_operator_user,
                ).search_read([], ['id'])

    def test_admin_can_read_intervals(self):
        self.Interval.with_user(self.prep_admin_user).search([])  # no debe lanzar

    def test_admin_cannot_create_intervals(self):
        with self.assertRaises(AccessError):
            self.Interval.with_user(self.prep_admin_user).create({
                'wizard_id': self.claim.wizard_id.id,
                'claim_id': self.claim.id,
                'employee_id': self.operator_a.id,
                'kind': 'working',
                'start_dt': '2026-11-04 10:00:00',
                'last_touched_dt': '2026-11-04 10:00:00',
            })

    def test_admin_cannot_write_intervals(self):
        interval = self.Interval.sudo().create({
            'wizard_id': self.claim.wizard_id.id,
            'claim_id': self.claim.id,
            'employee_id': self.operator_a.id,
            'kind': 'working',
            'start_dt': '2026-11-04 10:00:00',
            'last_touched_dt': '2026-11-04 10:00:00',
        })
        with self.assertRaises(AccessError):
            interval.with_user(self.prep_admin_user).write({
                'last_touched_dt': '2026-11-04 10:05:00',
            })

    def test_admin_cannot_unlink_intervals(self):
        interval = self.Interval.sudo().create({
            'wizard_id': self.claim.wizard_id.id,
            'claim_id': self.claim.id,
            'employee_id': self.operator_a.id,
            'kind': 'working',
            'start_dt': '2026-11-04 10:00:00',
            'last_touched_dt': '2026-11-04 10:00:00',
        })
        with self.assertRaises(AccessError):
            interval.with_user(self.prep_admin_user).unlink()

    # ── Usuario compartido real del tablet (operacion@donguapante.com) ──

    def test_shared_tablet_user_get_views_denied_on_reports(self):
        """Tech Lead: get_view()/read_group() deben fallar con
        AccessError para este usuario real — no solo un test user
        sintético. Si el login no existe en esta base (otro entorno),
        el test se salta en vez de fallar por una razón ajena al ACL."""
        shared_user = self.env['res.users'].search(
            [('login', '=', 'operacion@donguapante.com')], limit=1,
        )
        if not shared_user:
            self.skipTest(
                'operacion@donguapante.com no existe en esta base — '
                'nada que verificar acá.'
            )
        self.assertFalse(shared_user.has_group(
            'ist_preparation_day_picking.group_preparation_admin',
        ))
        with self.assertRaises(AccessError):
            self.env['guapante.preparation.operator.report'].with_user(
                shared_user,
            ).get_views([(False, 'list')])
        with self.assertRaises(AccessError):
            self.env['guapante.preparation.operator.report'].with_user(
                shared_user,
            ).read_group([], ['line_done:sum'], [])
