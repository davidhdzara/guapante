# -*- coding: utf-8 -*-
import logging
import math
from datetime import timedelta

import pytz

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

    @api.depends('state', 'order_line.invoice_status')
    def _compute_invoice_status(self):
        super()._compute_invoice_status()
        for order in self:
            if order.state == 'sale' and order.invoice_ids.filtered(lambda i: i.state != 'cancel'):
                order.invoice_status = 'invoiced'

    def _prepare_invoice(self):
        """Ensure invoice is always created for the commercial partner (parent).

        eCommerce users authenticate with a child contact (type=delivery),
        so the SO's partner_id is the child.  The child does NOT carry fiscal
        data (NIT, fiscal responsibilities, regime) required by DIAN
        electronic invoicing.  By forcing the invoice partner to the
        commercial partner we guarantee:
          - Correct NIT and fiscal information on the invoice
          - partner_shipping_id (delivery address) remains untouched
          - No manual replication of fiscal data to child contacts
        """
        invoice_vals = super()._prepare_invoice()
        commercial = self.partner_id.commercial_partner_id
        if self.partner_id.id != commercial.id:
            invoice_vals['partner_id'] = commercial.id
            _logger.info(
                'Guapante: invoice partner switched from child [%s] %s '
                'to commercial [%s] %s for %s',
                self.partner_id.id, self.partner_id.name,
                commercial.id, commercial.name,
                self.name,
            )
        return invoice_vals

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
        from .preparation_day import _date_to_utc_range
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
        from .preparation_day import _date_to_utc_range
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

    # ── Daily Price Update ────────────────────────────────────────

    def action_update_daily_prices(self):
        """Recalculate prices on all open SOs using their pricelists.

        Triggered by a server action button.  Updates:
          - Quotations (draft/sent)
          - Confirmed orders (sale) without any posted invoice
          - Confirmed orders with only draft invoices (not sent to DIAN)

        Respects each order's pricelist, so both fixed-price and
        cost+margin rules are correctly applied.
        """
        SaleOrder = self.env['sale.order'].sudo()

        # 1. All quotations (draft/sent)
        quotations = SaleOrder.search([
            ('state', 'in', ('draft', 'sent')),
        ])

        # 2. Confirmed orders — filter out those with posted invoices
        confirmed = SaleOrder.search([
            ('state', '=', 'sale'),
        ])
        eligible_confirmed = confirmed.filtered(
            lambda so: not so.invoice_ids.filtered(
                lambda inv: inv.state == 'posted'
            )
        )

        all_orders = quotations | eligible_confirmed
        if not all_orders:
            _logger.info(
                'Guapante Daily Prices: no qualifying orders found.'
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Actualización de Precios',
                    'message': 'No hay pedidos pendientes para actualizar.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        updated_lines = 0
        updated_orders = 0

        for order in all_orders:
            pricelist = order.pricelist_id
            if not pricelist:
                continue

            order_changed = False
            for line in order.order_line:
                if line.display_type:
                    # Skip section/note lines
                    continue
                if not line.product_id:
                    continue

                product = line.product_id.with_context(
                    partner=order.partner_id.id,
                    quantity=line.product_uom_qty,
                    date=fields.Date.today(),
                    pricelist=pricelist.id,
                    uom=line.product_uom.id,
                )
                new_price = pricelist._get_product_price(
                    product,
                    line.product_uom_qty,
                    currency=order.currency_id,
                    date=fields.Date.today(),
                )

                if (
                    new_price
                    and round(new_price, 2) != round(line.price_unit, 2)
                ):
                    old_price = line.price_unit
                    line.price_unit = new_price
                    updated_lines += 1
                    order_changed = True
                    _logger.info(
                        'Guapante Prices: %s | %s | $%.2f → $%.2f',
                        order.name,
                        line.product_id.name,
                        old_price,
                        new_price,
                    )

            if order_changed:
                updated_orders += 1

        msg = (
            'Precios actualizados: %d líneas en %d pedidos.'
            % (updated_lines, updated_orders)
        )
        _logger.info('Guapante Daily Prices: %s', msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Actualización de Precios ✅',
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }
