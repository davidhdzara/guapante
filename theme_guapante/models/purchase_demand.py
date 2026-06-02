# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseDemand(models.Model):
    """Session to analyze pending purchase demand from confirmed SOs.

    Follows the same pattern as guapante.preparation.day: a session
    with a 'Refresh' button that loads data from sale.order.lines.
    """
    _name = 'guapante.purchase.demand'
    _description = 'Sesión de Demanda de Compra'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default='Nueva Sesión',
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('loaded', 'Cargada'),
        ],
        default='draft',
    )
    line_ids = fields.One2many(
        'guapante.purchase.demand.line',
        'session_id',
        string='Líneas de Demanda',
    )

    # ── Smart Buttons / Header Info ──
    total_products = fields.Integer(
        string='Productos Únicos',
        compute='_compute_totals',
    )
    total_demand_kg = fields.Float(
        string='Demanda Total (kg)',
        compute='_compute_totals',
        digits=(10, 2),
    )
    total_lines = fields.Integer(
        string='Líneas de Demanda',
        compute='_compute_totals',
    )
    deficit_product_count = fields.Integer(
        string='Productos con Déficit',
        compute='_compute_totals',
    )
    save_note = fields.Char(string='Resultado', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Sesión') == 'Nueva Sesión':
                vals['name'] = 'Demanda de Compra: %s' % (
                    fields.Date.context_today(self),
                )
        return super().create(vals_list)

    @api.depends(
        'line_ids',
        'line_ids.pending_kg',
        'line_ids.product_deficit',
    )
    def _compute_totals(self) -> None:
        for session in self:
            lines = session.line_ids
            session.total_lines = len(lines)
            session.total_products = len(
                lines.mapped('product_id')
            )
            session.total_demand_kg = round(
                sum(lines.mapped('pending_kg')), 2,
            )
            # Count unique products with deficit
            deficit_products = lines.filtered(
                lambda l: l.product_deficit > 0
            ).mapped('product_id')
            session.deficit_product_count = len(deficit_products)

    # ─────────────────────────────────────────────────
    #  action_refresh: Load demand from confirmed SOs
    # ─────────────────────────────────────────────────
    def action_refresh(self) -> bool:
        """Rebuild demand lines from all confirmed SO lines pending delivery.

        Groups by product_id + attribute combination (no_variant values).
        Calculates deficit at the PRODUCT level (shared stock) and
        distributes it correctly across attribute combos.
        """
        self.line_ids.unlink()

        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )

        # ── Fetch all confirmed SO lines with pending delivery ──
        SaleLines = self.env['sale.order.line'].sudo().search([
            ('order_id.state', 'in', ('sale', 'done')),
            ('product_uom_qty', '>', 0),
            ('display_type', '=', False),
            ('product_id', '!=', False),
        ])

        # Filter to only lines with pending quantity
        PendingLines = SaleLines.filtered(
            lambda l: l.product_uom_qty > l.qty_delivered
        )

        if not PendingLines:
            raise UserError(
                'No hay demanda pendiente de entrega en las '
                'órdenes confirmadas.'
            )

        # ── Build demand dictionary ──
        # Key = (product_id, frozenset of attribute_value_ids, uom_mode)
        # uom_mode is included so unit orders and kg orders of same
        # product + attribute are tracked separately.
        demand = {}
        for line in PendingLines:
            product = line.product_id
            pid = product.id

            # Get no_variant attribute values
            attr_ids = frozenset()
            if hasattr(line, 'product_no_variant_attribute_value_ids'):
                attr_ids = frozenset(
                    line.product_no_variant_attribute_value_ids.ids
                )

            # Use the ACTUAL uom_mode from the SO line, not the
            # product's base UoM. In Guapante, all products have
            # kg as base UoM but customers order by 'unit' or 'kg'.
            line_uom_mode = getattr(line, 'uom_mode', None) or 'unit'
            
            # Group 'kg' and 'g' together as 'kg' to consolidate weight orders
            is_weight = weight_categ and product.uom_id.category_id == weight_categ
            group_uom_mode = 'kg' if is_weight and line_uom_mode in ('kg', 'g') else line_uom_mode

            key = (pid, attr_ids, group_uom_mode)
            pending_product_qty = (
                line.product_uom_qty - line.qty_delivered
            )

            if key not in demand:
                demand[key] = {
                    'product_id': pid,
                    'attr_value_ids': list(attr_ids),
                    'uom_mode': group_uom_mode,
                    'pending_product_qty': 0.0,
                    'order_ids': set(),
                    'order_names': [],
                    'packaging_ids': [],
                }

            demand[key]['pending_product_qty'] += pending_product_qty
            demand[key]['order_ids'].add(line.order_id.id)
            demand[key]['order_names'].append(line.order_id.name)
            if line.product_packaging_id:
                demand[key]['packaging_ids'].append(
                    line.product_packaging_id.id
                )

        # ── Phase 1: Build per-line data (without deficit) ──
        raw_lines = []
        for key, data in demand.items():
            product = self.env['product.product'].browse(
                data['product_id']
            )

            # Build attribute combination string
            attr_combination = ''
            if data['attr_value_ids']:
                AttrValues = self.env[
                    'product.template.attribute.value'
                ].browse(data['attr_value_ids'])
                sorted_vals = AttrValues.sorted(
                    key=lambda v: (
                        v.attribute_id.sequence,
                        v.product_attribute_value_id.sequence,
                    )
                )
                attr_combination = ' / '.join(
                    v.product_attribute_value_id.name
                    for v in sorted_vals
                )

            # Use the uom_mode from the SO lines (already stored
            # in the grouping key — NOT from the product's UoM).
            uom_mode = data['uom_mode']

            # pending_kg is ALWAYS the internal Odoo qty (kg).
            # product_uom_qty is stored in the product's UoM (kg)
            # regardless of how the customer ordered.
            pending_kg = round(data['pending_product_qty'], 3)

            # pending_qty: what the customer sees
            # - kg mode: same as pending_kg
            # - unit mode: convert kg → visual units via packaging
            # - g mode: kg × 1000
            if uom_mode == 'unit':
                pkg = product.packaging_ids.filtered(
                    lambda p: p.purchase and p.qty > 0
                )[:1]
                if pkg and pkg.qty > 0:
                    pending_qty = round(
                        pending_kg / pkg.qty, 2,
                    )
                else:
                    pending_qty = pending_kg
            elif uom_mode == 'g':
                pending_qty = round(pending_kg * 1000, 0)
            else:  # kg
                pending_qty = pending_kg

            # Packaging name (most common among the lines)
            packaging_name = ''
            if data['packaging_ids']:
                pkg_id = max(
                    set(data['packaging_ids']),
                    key=data['packaging_ids'].count,
                )
                pkg = self.env['product.packaging'].browse(pkg_id)
                packaging_name = pkg.name or ''

            # Supplier info
            supplier_info = product.seller_ids[:1]
            supplier_id = (
                supplier_info.partner_id.id
                if supplier_info
                else False
            )
            supplier_price = (
                supplier_info.price if supplier_info else 0.0
            )

            unique_names = sorted(set(data['order_names']))

            raw_lines.append({
                'product_id': product.id,
                'attribute_combination': (
                    attr_combination or 'Sin atributos'
                ),
                'attr_value_ids': data['attr_value_ids'],
                'uom_mode': uom_mode,
                'pending_qty': pending_qty,
                'pending_kg': pending_kg,
                'packaging_name': packaging_name,
                'order_count': len(data['order_ids']),
                'sale_order_names': ', '.join(unique_names[:10]),
                'supplier_id': supplier_id,
                'supplier_price': supplier_price,
            })

        # ── Phase 2: Calculate PRODUCT-LEVEL stock & deficit ──
        # The deficit must be at the product level because no_variant
        # attributes share the same stock pool.
        product_totals = defaultdict(lambda: {
            'total_demand_kg': 0.0,
            'available_qty': 0.0,
        })
        for rline in raw_lines:
            pid = rline['product_id']
            product_totals[pid]['total_demand_kg'] += rline['pending_kg']

        # Fetch stock once per product
        # Use virtual_available = on_hand + incoming - outgoing
        # so confirmed POs are accounted for (avoids double ordering).
        for pid in product_totals:
            product = self.env['product.product'].browse(pid)
            product_totals[pid]['available_qty'] = (
                product.virtual_available
            )

        # Calculate product-level deficit
        for pid, totals in product_totals.items():
            totals['deficit'] = round(max(
                0,
                totals['total_demand_kg'] - totals['available_qty'],
            ), 3)

        # ── Phase 3: Create demand lines with correct values ──
        line_vals = []
        for rline in raw_lines:
            pid = rline['product_id']
            pt = product_totals[pid]

            line_vals.append({
                'session_id': self.id,
                'product_id': pid,
                'attribute_combination': rline['attribute_combination'],
                'attribute_value_ids': [
                    (6, 0, rline['attr_value_ids'])
                ],
                'uom_mode': rline['uom_mode'],
                'pending_qty': rline['pending_qty'],
                'pending_kg': rline['pending_kg'],
                'packaging_name': rline['packaging_name'],
                'order_count': rline['order_count'],
                'sale_order_names': rline['sale_order_names'],
                'product_stock': pt['available_qty'],
                'product_total_demand': pt['total_demand_kg'],
                'product_deficit': pt['deficit'],
                'supplier_id': rline['supplier_id'],
                'supplier_price': rline['supplier_price'],
                # Auto-select lines for products with deficit
                'selected': pt['deficit'] > 0,
            })

        if line_vals:
            self.env['guapante.purchase.demand.line'].create(line_vals)

        self.state = 'loaded'
        deficit_products = len([
            pid for pid, pt in product_totals.items()
            if pt['deficit'] > 0
        ])
        self.save_note = (
            '✅ %d combinaciones producto-atributo cargadas '
            'desde %d líneas de venta. %d producto%s con déficit.'
            % (
                len(line_vals),
                len(PendingLines),
                deficit_products,
                's' if deficit_products != 1 else '',
            )
        )
        return False

    # ─────────────────────────────────────────────────
    #  action_generate_purchase_orders
    # ─────────────────────────────────────────────────
    def action_generate_purchase_orders(self) -> dict:
        """Generate Purchase Orders from selected demand lines.

        Groups lines by supplier (vendor) and creates one PO per vendor.
        Each PO line includes the attribute breakdown in the description.
        """
        self.ensure_one()

        selected = self.line_ids.filtered(lambda l: l.selected)
        if not selected:
            raise UserError(
                'Selecciona al menos una línea de demanda para '
                'generar la orden de compra.'
            )

        # Validate all selected lines have a supplier
        no_supplier = selected.filtered(lambda l: not l.supplier_id)
        if no_supplier:
            product_names = ', '.join(
                no_supplier.mapped('product_id.name')
            )
            raise UserError(
                'Los siguientes productos no tienen proveedor '
                'configurado: %s\n\n'
                'Configura un proveedor en la pestaña "Compra" '
                'de cada producto antes de generar la PO.'
                % product_names
            )

        # Group by supplier
        suppliers = {}
        for line in selected:
            sid = line.supplier_id.id
            if sid not in suppliers:
                suppliers[sid] = []
            suppliers[sid].append(line)

        created_orders = self.env['purchase.order']
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )

        for supplier_id, demand_lines in suppliers.items():
            # Create the PO header
            po_vals = {
                'partner_id': supplier_id,
                'origin': 'Demanda Guapante: %s' % self.name,
            }
            po = self.env['purchase.order'].create(po_vals)

            for dline in demand_lines:
                product = dline.product_id

                # Description: clean — just product + variant
                desc_parts = [product.display_name]
                if (
                    dline.attribute_combination
                    and dline.attribute_combination
                    != 'Sin atributos'
                ):
                    desc_parts.append(
                        '— %s' % dline.attribute_combination
                    )
                description = ' '.join(desc_parts)

                # Determine packaging for the PO line
                packaging = False
                if dline.uom_mode == 'unit':
                    packaging = product.packaging_ids.filtered(
                        lambda p: p.purchase and p.qty > 0
                    )[:1]

                # Get supplier info for price
                supplier_info = product.seller_ids.filtered(
                    lambda s: s.partner_id.id == supplier_id
                )[:1]

                # PO line: product_qty in kg (Odoo internal).
                # Do NOT set visual_qty manually — the POL compute
                # (_compute_visual_qty) will derive it correctly
                # from product_qty + uom_mode + packaging.
                # Setting it manually causes double-conversion.
                po_line_vals = {
                    'order_id': po.id,
                    'product_id': product.id,
                    'name': description,
                    'product_qty': dline.pending_kg,
                    'product_uom': (
                        product.uom_po_id.id
                        or product.uom_id.id
                    ),
                    'price_unit': (
                        supplier_info.price
                        if supplier_info
                        else product.standard_price
                    ),
                    'uom_mode': dline.uom_mode,
                }

                if packaging:
                    po_line_vals['product_packaging_id'] = packaging.id

                po_line = self.env['purchase.order.line'].create(po_line_vals)
                # Odoo's compute method for name overwrites it upon creation. 
                # We force the name again to preserve the variant description.
                po_line.write({'name': description})

            created_orders |= po

        count = len(created_orders)
        self.save_note = (
            '🛒 %d orden%s de compra generada%s exitosamente.'
            % (
                count,
                'es' if count > 1 else '',
                's' if count > 1 else '',
            )
        )

        # Return action to view the created POs
        if len(created_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': created_orders.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_orders.ids)],
            'target': 'current',
            'name': 'Órdenes de Compra Generadas',
        }

    def action_select_all(self) -> bool:
        """Select all demand lines."""
        self.line_ids.write({'selected': True})
        return False

    def action_select_deficit(self) -> bool:
        """Select only lines whose PRODUCT has a deficit."""
        self.line_ids.write({'selected': False})
        deficit_lines = self.line_ids.filtered(
            lambda l: l.product_deficit > 0
        )
        if deficit_lines:
            deficit_lines.write({'selected': True})
        return False

    def action_deselect_all(self) -> bool:
        """Deselect all demand lines."""
        self.line_ids.write({'selected': False})
        return False


class PurchaseDemandLine(models.Model):
    """One row per product + attribute combination.

    IMPORTANT on stock and deficit:
    Since no_variant attributes share the same stock pool, the
    fields product_stock, product_total_demand and product_deficit
    are PRODUCT-LEVEL values, not per-line. All attribute combos
    of the same product show identical stock/deficit values.
    """
    _name = 'guapante.purchase.demand.line'
    _description = 'Línea de Demanda de Compra'
    _order = 'product_deficit desc, product_id, attribute_combination'

    session_id = fields.Many2one(
        'guapante.purchase.demand',
        string='Sesión',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    attribute_combination = fields.Char(
        string='Atributos',
        readonly=True,
        help=(
            'Combinación de atributos no-variante del producto '
            '(ej. Pintón / Grande).'
        ),
    )
    attribute_value_ids = fields.Many2many(
        'product.template.attribute.value',
        relation='guapante_demand_line_attr_val_rel',
        column1='demand_line_id',
        column2='attr_value_id',
        string='Valores de Atributo',
        readonly=True,
    )

    uom_mode = fields.Selection(
        [
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='UdM',
        readonly=True,
    )
    pending_qty = fields.Float(
        string='Demanda',
        digits='Product Unit of Measure',
        readonly=True,
        help=(
            'Cantidad total pendiente de ESTA combinación de '
            'atributos: en kg para productos de peso, en '
            'unidades para productos unitarios.'
        ),
    )
    pending_kg = fields.Float(
        string='Demanda (kg)',
        digits=(10, 3),
        readonly=True,
        help='Total en kg (para unitarios: qty × peso embalaje).',
    )
    packaging_name = fields.Char(
        string='Embalaje',
        readonly=True,
    )

    order_count = fields.Integer(
        string='# Órdenes',
        readonly=True,
    )
    sale_order_names = fields.Char(
        string='Órdenes',
        readonly=True,
    )

    # ── PRODUCT-LEVEL stock & deficit ──
    # These fields are IDENTICAL for all lines of the same product
    # because no_variant attributes share a single stock pool.
    product_stock = fields.Float(
        string='Stock Producto (kg)',
        digits=(10, 3),
        readonly=True,
        help=(
            'Stock virtual del PRODUCTO: stock en mano + '
            'POs confirmadas en tránsito - demanda saliente. '
            'Compartido entre todas las combinaciones de atributos.'
        ),
    )
    product_total_demand = fields.Float(
        string='Demanda Total Producto (kg)',
        digits=(10, 3),
        readonly=True,
        help=(
            'Demanda TOTAL del producto sumando TODAS las '
            'combinaciones de atributos.'
        ),
    )
    product_deficit = fields.Float(
        string='Déficit Producto (kg)',
        digits=(10, 3),
        readonly=True,
        help=(
            'Faltante a nivel de PRODUCTO: '
            'demanda_total_producto - stock_disponible. '
            'Todas las combinaciones del mismo producto '
            'comparten este valor.'
        ),
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        readonly=True,
    )
    supplier_price = fields.Float(
        string='Precio Proveedor',
        digits='Product Price',
        readonly=True,
    )
    estimated_cost = fields.Float(
        string='Costo Estimado',
        compute='_compute_estimated_cost',
        digits='Product Price',
    )

    selected = fields.Boolean(
        string='Seleccionar',
        default=False,
        help='Marca las líneas que deseas incluir en la PO.',
    )

    @api.depends('pending_kg', 'supplier_price')
    def _compute_estimated_cost(self) -> None:
        for line in self:
            line.estimated_cost = round(
                line.pending_kg * line.supplier_price, 2,
            )
