# -*- coding: utf-8 -*-
"""Corrección (b), Tech Lead 2026-10-31: bloquear mover un PICK hacia
una sesión de Preparación que ya está 'done' — nunca por la sesión de
ORIGEN (ver StockPicking.write() en ist_preparation_day/models/
stock_picking.py).

Setup mínimo copiado de TestPreparationDayRelocation (misma ventana
lejana libre de colisión con datos reales de staging_dev) en vez de
heredar esa clase, para no re-correr sus ~15 tests de reubicación bajo
un nombre nuevo.
"""
from datetime import datetime, time
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)


@tagged('post_install', '-at_install')
class TestStockPickingBlockDoneDestination(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Block Done',
                'code': 'TWBD',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Block Done',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Product Block Done Test',
            'type': 'consu',
            'list_price': 1000.0,
        })
        # Ventana lejana para no chocar con otros tests/datos reales.
        cls.day_a = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']), days=50,
        )
        cls.day_b = fields.Date.add(cls.day_a, days=3)

    def _create_confirmed_order(self, day):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, day)
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.scheduled_date = dt_start
        return order, pick

    def _load_session(self, day):
        Session = self.env['guapante.preparation.day'].sudo().search(
            [('date', '=', day)], limit=1,
        )
        if not Session:
            Session = self.env['guapante.preparation.day'].create(
                {'date': day},
            )
        Session.action_load()
        return Session

    def test_moving_to_done_destination_session_blocks_with_user_error(self):
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        SessionB = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.day_b)
        SessionB.action_mark_done()

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        original_scheduled_date = pick.scheduled_date

        with self.assertRaises(UserError):
            pick.scheduled_date = dt_start_b

        pick.invalidate_recordset(['scheduled_date'])
        self.assertEqual(
            pick.scheduled_date, original_scheduled_date,
            'si el destino está cerrado, el picking conserva su fecha',
        )

    def test_moving_to_reopened_destination_session_allowed(self):
        """E5 (David/Tech Lead, 2026-11-02): el bloqueo mira state==
        'done' en vivo — tras action_reopen() el destino ya no está
        'done', así que el mismo write() que antes rechazaba ahora
        debe pasar sin tocar nada más (sin cambio de código acá, solo
        confirma que action_reopen() lo desbloquea solo)."""
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        SessionB = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.day_b)
        SessionB.action_mark_done()

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with self.assertRaises(UserError):
            pick.scheduled_date = dt_start_b
        pick.invalidate_recordset(['scheduled_date'])

        # action_reopen() exige group_preparation_admin cuando Picking
        # está instalado (override en ese módulo) — este test corre
        # como TransactionCase simple, sin ese grupo por defecto.
        admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
            raise_if_not_found=False,
        )
        if admin_group:
            self.env.user.sudo().write({'groups_id': [(4, admin_group.id)]})
        SessionB.action_reopen()

        pick.scheduled_date = dt_start_b  # ya no debe lanzar UserError

        pick.invalidate_recordset(['scheduled_date'])
        self.assertEqual(pick.scheduled_date, dt_start_b)

    def test_moving_from_done_origin_without_lines_to_open_destination_allowed(self):
        """Condición 2 de Tech Lead: origen 'done' pero SIN líneas
        (la orden entró después del cierre, e2 solo dejó nota) → debe
        poder moverse al destino abierto — bloquearla la dejaría
        atrapada en una jornada cerrada.

        Confirma con fixed_now en day_a (patrón de
        test_moving_picking_from_a_closed_session_creates_draft_destination
        en test_preparation_day_relocation.py) en vez de
        _create_confirmed_order + reasignar scheduled_date: así el
        PICK nace YA en day_a, sin pasar por un write() de cambio de
        día que el bloqueo nuevo (correctamente) también rechazaría al
        confirmarse."""
        SessionA = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.day_a)
        SessionA.action_mark_done()

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        bogota_tz = pytz.timezone('America/Bogota')
        fixed_now = bogota_tz.localize(
            datetime.combine(self.day_a, time(0, 10)),
        ).astimezone(pytz.utc).replace(tzinfo=None)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            order.action_confirm()
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        # NOTA: no se afirma aquí que SessionA quede sin líneas — lo
        # que importa para esta corrección es que el bloqueo nunca
        # mira la sesión de ORIGEN, con o sin líneas; el escenario de
        # Tech Lead (orden entra después del cierre, sin líneas) es
        # el camino normal de _guapante_add_confirmed_order cuando
        # Day.state == 'done' (ver preparation_day.py), no algo que
        # dependa de esta prueba.

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b  # no debe lanzar UserError

        pick.invalidate_recordset(['scheduled_date'])
        self.assertEqual(pick.scheduled_date, dt_start_b)

    def test_moving_to_destination_without_any_session_allowed(self):
        """Destino SIN ninguna sesión todavía (el caso normal: la
        búsqueda de sesión destino da vacío, nunca 'done') → se puede
        mover, igual que antes de la corrección (b) — la sesión de
        day_b se crea sola después, vía _guapante_relocate_picking."""
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        self.assertFalse(
            self.env['guapante.preparation.day'].search(
                [('date', '=', self.day_b)], limit=1,
            ),
            'precondición: destino sin sesión todavía',
        )

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b  # no debe lanzar UserError

        pick.invalidate_recordset(['scheduled_date'])
        self.assertEqual(pick.scheduled_date, dt_start_b)

    def test_write_without_day_change_is_not_affected_by_done_destination_block(self):
        """Un write que NO cambia el día calendario (p. ej. solo ajusta
        la hora) nunca debe mirar el bloqueo nuevo, aunque el destino
        "natural" del mismo día esté done — ni siquiera entra a
        DayChanging."""
        order, pick = self._create_confirmed_order(self.day_a)
        SessionA = self._load_session(self.day_a)
        SessionA.action_mark_done()

        same_day_later_hour = fields.Datetime.add(
            pick.scheduled_date, hours=3,
        )
        pick.scheduled_date = same_day_later_hour  # no debe lanzar nada

        pick.invalidate_recordset(['scheduled_date'])
        self.assertEqual(pick.scheduled_date, same_day_later_hour)
