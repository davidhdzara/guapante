# -*- coding: utf-8 -*-
import logging
import math
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
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

    guapante_product_line_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_guapante_product_line_count',
    )

    @api.depends('order_line', 'order_line.display_type')
    def _compute_guapante_product_line_count(self) -> None:
        for order in self:
            order.guapante_product_line_count = len(
                order.order_line.filtered(lambda l: not l.display_type)
            )

    def action_confirm(self):
        return super().action_confirm()

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
        dt_start = fields.Datetime.to_datetime(delivery_date)
        dt_end = fields.Datetime.to_datetime(
            delivery_date + timedelta(days=1)
        )
        cid = company_id if company_id else None
        domain_company = (
            [('company_id', '=', cid)]
            if cid
            else [('company_id', '=', False)]
        )
        # sudo(): necesitamos leer TODAS las órdenes de la compañía
        # para determinar el máximo secuencial, independientemente
        # de los permisos del usuario actual.
        # NO filtramos por state: una caja asignada a una orden
        # cancelada sigue siendo "usada" y no debe reasignarse.
        Candidates = self.env['sale.order'].sudo().search(
            domain_company + [
                ('picking_ids.scheduled_date', '>=', dt_start),
                ('picking_ids.scheduled_date', '<', dt_end),
                ('daily_sequence', '>', 0),
            ],
        )
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
            if seq.number_next_actual < safe_next:
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

    def _assign_daily_sequences(self, delivery_date) -> None:
        """Assign daily_sequence to confirmed orders for a delivery date.

        Called from PreparationDay.action_load so the sequence is always
        scoped to the actual delivery date, not the order creation date.
        Orders that already have a sequence keep it; new orders receive
        the next number from an ir.sequence (concurrency-safe).
        """
        # sudo(): necesitamos acceso a TODAS las órdenes de la fecha
        # para asignar secuencias, sin importar el usuario actual.
        OrdersForDate = self.env['sale.order'].sudo().search(
            [
                (
                    'picking_ids.scheduled_date',
                    '>=',
                    fields.Datetime.to_datetime(delivery_date),
                ),
                (
                    'picking_ids.scheduled_date',
                    '<',
                    fields.Datetime.to_datetime(
                        delivery_date + timedelta(days=1)
                    ),
                ),
                ('state', 'in', ('sale', 'done')),
            ],
            order='id asc',
        )
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

    @api.depends('order_line.product_uom_qty', 'order_line.product_id')
    def _compute_cart_info(self) -> None:
        """Override to use ceil() instead of int().

        Odoo 18 uses int(sum(qty)) for cart_quantity. For fractional
        quantities like 0.2 kg, int(0.2) = 0 which triggers
        cart_update_json → sale_reset() → deletes the entire order.
        Using ceil() ensures any non-zero quantity counts as at least 1.
        """
        for order in self:
            raw_qty = sum(
                order.mapped('website_order_line.product_uom_qty')
            )
            order.cart_quantity = (
                math.ceil(raw_qty) if raw_qty > 0 else 0
            )
            order.only_services = all(
                sol.product_id.type == 'service'
                for sol in order.website_order_line
            )

    guapante_delivery_status = fields.Selection(
        [
            ('received', 'Recibido'),
            ('preparing', 'Preparando'),
            ('shipping', 'En Camino'),
            ('delivered', 'Entregado'),
        ],
        string="Estado de Entrega (Guapante)",
        compute='_compute_guapante_delivery_status',
        store=True,
    )

    @api.depends('state', 'picking_ids.state')
    def _compute_guapante_delivery_status(self) -> None:
        for order in self:
            status = 'received'

            Pickings = order.picking_ids.filtered(
                lambda p: p.state != 'cancel'
            )
            if not Pickings:
                order.guapante_delivery_status = status
                continue

            # Identificar Recolectar (Internal/Pick) vs Entregas (Out)
            PickPickings = Pickings.filtered(
                lambda p: p.picking_type_id.code == 'internal'
            )
            OutPickings = Pickings.filtered(
                lambda p: p.picking_type_id.code == 'outgoing'
            )

            # Fallback 1-step: outgoing es el step principal
            if not PickPickings and OutPickings:
                PickPickings = OutPickings

            # 4. Entregado: todas las entregas están hechas
            if OutPickings and all(
                p.state == 'done' for p in OutPickings
            ):
                status = 'delivered'

            # 3. En Camino: entrega asignada o recolección completada
            elif (
                (
                    OutPickings
                    and any(
                        p.state in ['assigned', 'in_progress']
                        for p in OutPickings
                    )
                )
                or (
                    PickPickings
                    and all(p.state == 'done' for p in PickPickings)
                    and OutPickings
                )
            ):
                status = 'shipping'

            # 2. Preparando: recolección abierta con pesaje iniciado
            elif PickPickings and any(
                p.state not in ['done', 'cancel']
                for p in PickPickings
            ):
                ActivePicks = PickPickings.filtered(
                    lambda p: p.state not in ['done', 'cancel']
                )
                has_picked_field = (
                    'picked' in self.env['stock.move.line']._fields
                )
                has_qty = False
                for p in ActivePicks:
                    if p.move_line_ids:
                        if has_picked_field and any(
                            ml.picked for ml in p.move_line_ids
                        ):
                            has_qty = True
                            break
                        elif not has_picked_field and any(
                            ml.quantity > 0 for ml in p.move_line_ids
                        ):
                            has_qty = True
                            break
                if has_qty:
                    status = 'preparing'

            order.guapante_delivery_status = status

    def _cart_update(
        self,
        product_id,
        line_id=None,
        add_qty=0,
        set_qty=0,
        **kwargs,
    ):
        """Override to support fractional quantities (e.g. 500g = 0.5 kg).

        Odoo 18's native _cart_update truncates quantities with int(),
        so 0.5 kg becomes 0 and the line gets deleted. We ceil() to
        keep the line alive, then write the exact float value.
        """
        float_add = float(add_qty or 0)
        float_set = float(set_qty or 0)
        is_fractional = (
            (float_add and float_add != int(float_add))
            or (float_set and float_set != int(float_set))
        )

        if not is_fractional:
            return super()._cart_update(
                product_id,
                line_id=line_id,
                add_qty=add_qty,
                set_qty=set_qty,
                **kwargs,
            )

        # Para fraccional, buscar la línea existente primero
        ExistingLine = self._cart_find_product_line(
            product_id, line_id, **kwargs
        )[:1]

        if float_set:
            desired_qty = float_set
        else:
            current_qty = (
                ExistingLine.product_uom_qty if ExistingLine else 0
            )
            desired_qty = current_qty + float_add

        if desired_qty <= 0:
            return super()._cart_update(
                product_id,
                line_id=line_id,
                add_qty=0,
                set_qty=0,
                **kwargs,
            )

        ceil_qty = max(1, math.ceil(desired_qty))
        found_line_id = ExistingLine.id if ExistingLine else line_id
        result = super()._cart_update(
            product_id,
            line_id=found_line_id,
            set_qty=ceil_qty,
            **kwargs,
        )

        if result and result.get('line_id'):
            # sudo(): necesitamos escribir la qty exacta fraccionaria
            # después de que Odoo la truncó internamente.
            Line = self.env['sale.order.line'].sudo().browse(
                result['line_id']
            )
            if Line.exists() and Line.product_uom_qty != desired_qty:
                Line.product_uom_qty = desired_qty
                result['quantity'] = desired_qty
                _logger.info(
                    "Guapante _cart_update: wrote exact fractional "
                    "qty=%.4f on line %s",
                    desired_qty,
                    Line.id,
                )

        return result

    def _cart_find_product_line(
        self, product_id, line_id=None, **kwargs
    ):
        """Override to:
        1. Fix attribute ID order sensitivity in Odoo 18.
        2. Ensure different packagings get SEPARATE cart lines.

        Rule: Only separate by packaging when a specific non-zero
        packaging_id is explicitly requested.
        """
        self.ensure_one()

        # 1. Let Odoo's native logic run first
        Lines = super()._cart_find_product_line(
            product_id, line_id, **kwargs
        )

        # 2. Separar líneas por packaging cuando se pide explícitamente.
        # El JS envía un packaging_id real (>0) solo cuando el usuario
        # seleccionó un botón específico (ej. 'Paquete 200g').
        target_pkg_id = kwargs.get('product_packaging_id')
        if target_pkg_id and int(target_pkg_id) > 0:
            Lines = Lines.filtered(
                lambda l: l.product_packaging_id.id == int(target_pkg_id)
            )

        if Lines:
            return Lines

        # 3. Fallback: reintento con comparación de atributos por set
        no_var_ids = kwargs.get('no_variant_attribute_value_ids') or []
        if not no_var_ids:
            return Lines  # Empty, nothing else we can try

        target_set = set(no_var_ids)
        Matched = self.env['sale.order.line']
        for line in self.order_line:
            if line.product_id.id != product_id:
                continue
            if line_id and line.id != line_id:
                continue
            if hasattr(line, 'product_no_variant_attribute_value_ids'):
                line_set = set(
                    line.product_no_variant_attribute_value_ids.ids
                )
                if line_set == target_set:
                    Matched |= line

        return Matched
