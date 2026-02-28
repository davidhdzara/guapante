# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PreparationDayLine(models.TransientModel):
    """One row per sale.order.line that needs preparation on the selected date."""
    _name = 'guapante.preparation.day.line'
    _description = 'Línea de Preparación del Día'
    _order = 'product_product_id, order_name'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.template', string='Producto', readonly=True)
    product_product_id = fields.Many2one('product.product', string='Variante', readonly=True)
    order_name = fields.Char(string='Orden', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Pedido', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', string='Línea de pedido', readonly=True)
    stock_move_id = fields.Many2one('stock.move', string='Movimiento', readonly=True)
    customer_name = fields.Char(string='Cliente', readonly=True)

    uom_mode = fields.Selection(
        selection=[('unit', 'Unidades'), ('kg', 'Kilogramos'), ('g', 'Gramos')],
        string='UoM cliente',
        readonly=True,
    )
    customer_qty_display = fields.Char(string='Pidió', readonly=True)
    customer_uom_label = fields.Char(string='En', readonly=True)
    estimated_kg = fields.Float(string='Kg estimado', digits=(10, 3), readonly=True)

    actual_kg = fields.Float(
        string='Peso real (kg)',
        digits=(10, 3),
        help='Solo editable para productos pedidos en Unidades. '
             'Deja en 0 para usar el kg estimado.',
    )
    needs_weighing = fields.Boolean(
        string='Requiere repesaje',
        readonly=True,
        help='True cuando el cliente pidió en Unidades y el precio es variable.',
    )

    def _get_display_qty(self, line):
        """Return (qty_str, uom_label) as the customer sees it."""
        mode = line.uom_mode or 'unit'
        qty = line.product_uom_qty
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        is_weight = (
            weight_categ
            and line.product_id.uom_id.category_id == weight_categ
        )

        if mode == 'g':
            return str(int(round(qty * 1000))), 'g'
        elif mode == 'kg':
            val = round(qty, 2)
            return (str(int(val)) if val == int(val) else str(val)), 'kg'
        else:
            if is_weight:
                packaging = line.product_id.packaging_ids.filtered(
                    lambda p: p.sales and p.qty > 0
                )[:1]
                if packaging:
                    units = int(round(qty / packaging.qty))
                else:
                    units = int(qty) if qty == int(qty) else qty
            else:
                units = int(qty) if qty == int(qty) else qty
            return str(units), 'unidades'


class PreparationDay(models.TransientModel):
    """Wizard: select a date → see all products to prepare → enter real weights."""
    _name = 'guapante.preparation.day'
    _description = 'Preparación del Día'

    date = fields.Date(
        string='Fecha de entrega',
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        'guapante.preparation.day.line',
        'wizard_id',
        string='Líneas',
    )
    summary_ids = fields.One2many(
        'guapante.preparation.day.summary',
        'wizard_id',
        string='Resumen por producto',
    )
    state = fields.Selection(
        [('draft', 'Seleccionar fecha'), ('loaded', 'Preparando')],
        default='draft',
    )
    save_note = fields.Char(string='Resultado', readonly=True)
    selected_product_id = fields.Many2one(
        'product.product',
        string='Producto seleccionado',
        readonly=True,
    )

    def action_load(self):
        """Load all confirmed sale order lines whose picking is scheduled on self.date."""
        self.line_ids.unlink()
        self.summary_ids.unlink()

        domain = [
            ('state', 'in', ('sale', 'done')),
            ('picking_ids.scheduled_date', '>=', fields.Datetime.to_datetime(self.date)),
            ('picking_ids.scheduled_date', '<', fields.Datetime.to_datetime(
                fields.Date.add(self.date, days=1)
            )),
            ('picking_ids.state', 'not in', ('done', 'cancel')),
        ]
        orders = self.env['sale.order'].search(domain)
        if not orders:
            raise UserError('No hay pedidos pendientes para la fecha seleccionada.')

        line_vals = []
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)

        for order in orders:
            for line in order.order_line.filtered(lambda l: l.product_id and not l.display_type):
                # Find the related stock.move
                move = self.env['stock.move'].search([
                    ('sale_line_id', '=', line.id),
                    ('state', 'not in', ('done', 'cancel')),
                ], limit=1)

                mode = line.uom_mode or 'unit'
                is_weight = (
                    weight_categ
                    and line.product_id.uom_id.category_id == weight_categ
                )
                needs_weighing = (mode == 'unit' and is_weight)

                dummy = self.env['guapante.preparation.day.line'].new({'wizard_id': self.id})
                qty_str, uom_label = dummy._get_display_qty(line)

                line_vals.append({
                    'wizard_id': self.id,
                    'product_id': line.product_id.product_tmpl_id.id,
                    'product_product_id': line.product_id.id,
                    'order_name': order.name,
                    'sale_order_id': order.id,
                    'sale_line_id': line.id,
                    'stock_move_id': move.id if move else False,
                    'customer_name': order.partner_id.name,
                    'uom_mode': mode,
                    'customer_qty_display': qty_str,
                    'customer_uom_label': uom_label,
                    'estimated_kg': round(line.product_uom_qty, 3),
                    'actual_kg': round(line.product_uom_qty, 3) if not needs_weighing else 0.0,
                    'needs_weighing': needs_weighing,
                })

        self.env['guapante.preparation.day.line'].create(line_vals)
        self._compute_summary()
        self.state = 'loaded'
        self.save_note = False
        return False

    def _compute_summary(self):
        """Build per-product summary aggregating all lines."""
        self.summary_ids.unlink()
        product_totals = {}
        for line in self.line_ids:
            pid = line.product_product_id.id
            if pid not in product_totals:
                product_totals[pid] = {
                    'product_id': pid,
                    'total_estimated_kg': 0.0,
                    'order_count': 0,
                    'wizard_id': self.id,
                }
            product_totals[pid]['total_estimated_kg'] += line.estimated_kg
            product_totals[pid]['order_count'] += 1

        for vals in product_totals.values():
            vals['total_estimated_kg'] = round(vals['total_estimated_kg'], 3)

        self.env['guapante.preparation.day.summary'].create(list(product_totals.values()))

    def action_save_weights(self):
        """Propagate actual_kg to stock.move and sale.order.line, then recompute totals."""
        # Re-fetch lines from DB to get the latest committed values
        lines = self.env['guapante.preparation.day.line'].search(
            [('wizard_id', '=', self.id)]
        )

        _logger.info('=== Preparación del Día: guardando pesos (wizard=%s) ===', self.id)
        for line in lines:
            _logger.info(
                '  Línea %s | product=%s | needs_weighing=%s | actual_kg=%.4f',
                line.id, line.product_id.name, line.needs_weighing, line.actual_kg,
            )

        updated_orders = self.env['sale.order']
        updated_count = 0

        for line in lines:
            if not line.needs_weighing:
                continue
            actual = line.actual_kg
            if actual <= 0:
                continue

            # Update the done quantity on the stock move ("Cantidad"), NOT the demand
            if line.stock_move_id:
                line.stock_move_id.sudo().write({'quantity': actual})

            # Update the sale order line quantity so the invoice reflects the real weight
            if line.sale_line_id:
                sale_line = line.sale_line_id.sudo()
                sale_line.write({'product_uom_qty': actual})
                updated_orders |= sale_line.order_id
                updated_count += 1

        if updated_orders:
            updated_orders.sudo().invalidate_recordset(
                ['amount_untaxed', 'amount_tax', 'amount_total']
            )

        self.save_note = (
            f'✅ {updated_count} línea(s) actualizada(s) en {len(updated_orders)} pedido(s).'
            if updated_count
            else '⚠️ No se encontraron pesos reales > 0. Ingresa el valor, haz clic fuera de la celda y luego guarda.'
        )
        # Return False so Odoo refreshes the current record in place
        # (returning act_window stacks a new breadcrumb entry)
        return False

    def action_clear_product_filter(self):
        """Clear the product filter — show all lines in the detail tab."""
        self.selected_product_id = False
        return False


class PreparationDaySummary(models.TransientModel):
    """Aggregated view: one row per product variant showing totals."""
    _name = 'guapante.preparation.day.summary'
    _description = 'Resumen de Preparación por Producto'
    _order = 'product_id'

    wizard_id = fields.Many2one('guapante.preparation.day', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    total_estimated_kg = fields.Float(string='Total kg estimado', digits=(10, 3), readonly=True)
    order_count = fields.Integer(string='Órdenes', readonly=True)

    def action_select_product(self):
        """Set this product variant as the active filter in the wizard detail tab."""
        self.wizard_id.write({'selected_product_id': self.product_id.id})
        return False
