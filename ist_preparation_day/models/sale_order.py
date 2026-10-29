# -*- coding: utf-8 -*-
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError

from .preparation_day import (
    _date_to_utc_range,
    _utc_datetime_to_session_date,
)

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Numeración diaria de cajas ("Caja #") para Preparation Day.

    Vive en este módulo (no en theme_guapante) porque nace y se consume acá: se
    asigna en action_load() y se muestra/resetea en Inventario (ver
    models/stock_picking.py de este mismo módulo) — es dominio de Preparation Day,
    nunca se expone en ecommerce/portal (verificado 2026-10-21: cero referencias
    en theme_guapante/views/shop, views/portal, controllers/shop.py,
    controllers/customer_portal.py).
    """
    _inherit = 'sale.order'

    daily_sequence = fields.Integer(
        string='# del día',
        default=0,
        copy=False,
        help=(
            'Daily box number for the order\'s delivery date '
            '(pickings scheduled date).'
        ),
    )

    @api.model
    def _guapante_daily_sequence_code(
        self, company_id: int, delivery_date
    ) -> str:
        """Stable ir.sequence code: one counter per company and day."""
        d = fields.Date.to_date(delivery_date)
        cid = int(company_id) if company_id else 0
        return 'guapante.daily.%s.%s' % (cid, d.strftime('%Y%m%d'))

    @api.model
    def _guapante_max_daily_sequence_on_date(
        self, company_id: int, delivery_date
    ) -> int:
        """Max existing daily_sequence for orders on this delivery date.

        Includes ALL states (even cancelled) to prevent box number
        reuse after order cancellation.
        """
        dt_start, dt_end = _date_to_utc_range(self.env, delivery_date)
        cid = company_id if company_id else None
        domain_company = (
            [('company_id', '=', cid)]
            if cid
            else [('company_id', '=', False)]
        )
        # Solo pickings PICK (internal/Recolectar).
        PickDomain = [
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('sale_id', '!=', False),
            ('sale_id.daily_sequence', '>', 0),
        ]
        if cid:
            PickDomain.append(('company_id', '=', cid))

        Pickings = self.env['stock.picking'].sudo().search(PickDomain)
        Candidates = Pickings.mapped('sale_id')
        if not Candidates:
            return 0
        return max(Candidates.mapped('daily_sequence'))

    @api.model
    def _guapante_get_or_create_daily_ir_sequence(
        self, company_id: int, delivery_date
    ):
        """Return ir.sequence for (company, day); create if missing.

        SIEMPRE sincroniza number_next con el máximo real de la BD
        para evitar duplicados tras cancelaciones o ediciones manuales.
        """
        # sudo(): ir.sequence creation requiere permisos de admin
        # ya que el usuario de preparación normalmente no tiene
        # acceso a la configuración de secuencias.
        Sequence = self.env['ir.sequence'].sudo()
        code = self._guapante_daily_sequence_code(
            company_id, delivery_date,
        )
        seq = Sequence.search([('code', '=', code)], limit=1)

        max_existing = self._guapante_max_daily_sequence_on_date(
            company_id, delivery_date,
        )
        safe_next = max_existing + 1 if max_existing >= 0 else 1

        if seq:
            # CORRECCIÓN: Siempre sincronizar number_next con el max
            # real de la BD. Si alguien canceló órdenes, editó
            # manualmente, o la secuencia quedó desincronizada,
            # esto garantiza que el próximo número sea max + 1.
            if seq.number_next_actual != safe_next:
                seq.sudo().write({'number_next': safe_next})
                _logger.info(
                    'Guapante: synced ir.sequence %s number_next '
                    'to %d (was %d)',
                    code, safe_next, seq.number_next_actual,
                )
            return seq

        d = fields.Date.to_date(delivery_date)
        vals = {
            'name': 'Guapante delivery day %s (%s)' % (
                d.isoformat(), code,
            ),
            'code': code,
            'implementation': 'standard',
            'company_id': company_id if company_id else False,
            'active': True,
            'prefix': '',
            'suffix': '',
            'padding': 1,
            'number_increment': 1,
            'number_next': safe_next,
        }
        try:
            with self.env.cr.savepoint():
                seq = Sequence.create(vals)
        except IntegrityError:
            seq = Sequence.browse()
        if not seq:
            seq = Sequence.search([('code', '=', code)], limit=1)
        if not seq:
            _logger.error(
                'Guapante: failed to get ir.sequence for code %s',
                code,
            )
            raise UserError(
                'Could not initialize the daily order sequence. '
                'Please retry or contact support.'
            )
        return seq

    @api.model
    def _assign_daily_sequences(self, delivery_date) -> None:
        """Assign daily_sequence to confirmed orders for a delivery date.

        Called from PreparationDay.action_load so the sequence is always
        scoped to the actual delivery date, not the order creation date.
        Orders that already have a sequence keep it; new orders receive
        the next number from an ir.sequence (concurrency-safe).
        """
        # Buscar solo pickings PICK (internal/Recolectar) PENDIENTES.
        # Excluir done/cancel: órdenes ya entregadas no deben recibir
        # un nuevo número de caja (bug S00204/S00220).
        dt_start, dt_end = _date_to_utc_range(self.env, delivery_date)
        Pickings = self.env['stock.picking'].sudo().search([
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('state', 'not in', ('done', 'cancel')),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
        ])
        OrdersForDate = Pickings.mapped('sale_id').sorted('id')
        seq_by_company = {}
        Touched = self.env['sale.order']
        for order in OrdersForDate:
            if order.daily_sequence:
                continue
            cid = order.company_id.id if order.company_id else False
            if cid not in seq_by_company:
                seq_by_company[cid] = (
                    self.env['sale.order']
                    .sudo()
                    ._guapante_get_or_create_daily_ir_sequence(
                        cid, delivery_date,
                    )
                )
            seq = seq_by_company[cid]
            next_str = seq.next_by_id()
            try:
                order.daily_sequence = int(next_str)
            except (TypeError, ValueError) as err:
                _logger.error(
                    'Guapante: invalid sequence value %r from %s: %s',
                    next_str, seq.display_name, err,
                )
                raise
            Touched |= order
        if Touched:
            Touched.flush_recordset(['daily_sequence'])

    def action_confirm(self):
        """Al confirmar, asegura la sesión de Preparación del Día de
        CADA fecha en la que caiga alguno de los pickings internos
        resultantes — hoy o futura (Regla de la jornada, David
        2026-10-29; antes solo se auto-creaba si la fecha era "hoy").
        """
        res = super().action_confirm()
        Pickings = self.mapped('picking_ids').filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.scheduled_date
                and p.state not in ('done', 'cancel')
            )
        )
        session_dates = {
            _utc_datetime_to_session_date(self.env, p.scheduled_date)
            for p in Pickings
        }
        Session = self.env['guapante.preparation.day']
        for date_val in session_dates:
            Session._ensure_session_for_date(date_val)
        return res
