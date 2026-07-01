# -*- coding: utf-8 -*-
from odoo import fields, models, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    uom_mode = fields.Selection(
        selection=[
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='Unidad (Visual)',
        default='unit',
        help='Modo en el que el proveedor vende este producto.',
    )

    visual_qty = fields.Float(
        string='Cantidad (Visual)',
        digits='Product Unit of Measure',
        compute='_compute_visual_qty',
        inverse='_inverse_visual_qty',
        store=True,
    )

    # ── Helpers ────────────────────────────────────────────────────

    def _guapante_weight_categ(self):
        """Cache-friendly helper to get the weight UoM category."""
        return self.env.ref(
            'uom.product_uom_categ_kgm', raise_if_not_found=False,
        )

    def _guapante_is_weight_product(self, product, weight_categ=None):
        """Return True if *product* belongs to the weight UoM category."""
        if not weight_categ:
            weight_categ = self._guapante_weight_categ()
        return bool(
            weight_categ
            and product
            and product.uom_id.category_id == weight_categ
        )

    # ── ORM overrides ─────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Set correct uom_mode on programmatic creation.

        Only injects uom_mode when the caller did NOT explicitly
        include it in the vals dict.
        """
        weight_categ = self._guapante_weight_categ()
        for vals in vals_list:
            if 'product_id' not in vals:
                continue
            if 'uom_mode' in vals:
                continue
            product = self.env['product.product'].browse(vals['product_id'])
            is_weight = self._guapante_is_weight_product(
                product, weight_categ,
            )
            vals['uom_mode'] = 'kg' if is_weight else 'unit'
        return super().create(vals_list)

    # ── Onchanges ─────────────────────────────────────────────────

    @api.onchange('product_id')
    def _onchange_product_id_uom_mode(self):
        """Set uom_mode when user selects a product manually."""
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            line.uom_mode = 'kg' if is_weight else 'unit'

    @api.onchange('visual_qty')
    def _onchange_visual_qty_sync(self):
        """When user edits visual_qty, recalculate product_qty.

        Also triggers Odoo's native price recalculation so that
        price_unit stays up to date after quantity changes.
        """
        self._inverse_visual_qty()
        # Trigger Odoo's native price recalculation
        if hasattr(super(PurchaseOrderLine, self), '_onchange_quantity'):
            super(PurchaseOrderLine, self)._onchange_quantity()

    @api.onchange('uom_mode')
    def _onchange_uom_mode_handler(self):
        """Handle unit mode switches with validation and conversion.

        Conversion rules:
          kg ↔ g   → CONVERT visual_qty (same physical quantity)
          kg/g ↔ u → PRESERVE visual_qty (recalculate product_qty)
        """
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id or not line.uom_mode:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            mode = line.uom_mode
            has_packaging = bool(
                line.product_id.packaging_ids.filtered(
                    lambda p: p.purchase and p.qty > 0
                )
            )

            # ── Validation ────────────────────────────────
            if is_weight and mode == 'unit' and not has_packaging:
                line.uom_mode = 'kg'
                return {
                    'warning': {
                        'title': 'Modo Restringido',
                        'message': (
                            f'"{line.product_id.name}" no tiene embalaje '
                            f'de compra configurado. Solo se puede pedir '
                            f'por Kilogramos o Gramos a los proveedores.'
                        ),
                    },
                }
            elif not is_weight and mode in ['kg', 'g']:
                line.uom_mode = 'unit'
                return {
                    'warning': {
                        'title': 'Modo Restringido',
                        'message': (
                            f'"{line.product_id.name}" es un producto '
                            f'unitario, no se puede pesar.'
                        ),
                    },
                }

            # ── Conversion / Preservation ─────────────────
            if is_weight and mode in ('kg', 'g'):
                # CONVERT: recalculate visual_qty from product_qty
                # using the new mode.  product_qty stays unchanged.
                # 12 kg → 12000 g,  12000 g → 12 kg
                if mode == 'kg':
                    line.visual_qty = line.product_qty
                else:  # g
                    line.visual_qty = line.product_qty * 1000.0
            else:
                # PRESERVE: keep visual_qty number, recalc product_qty
                # 12 kg → 12 units (product_qty changes)
                line._inverse_visual_qty()

        # Trigger Odoo's native price recalculation
        if hasattr(super(PurchaseOrderLine, self), '_onchange_quantity'):
            super(PurchaseOrderLine, self)._onchange_quantity()

    # ── Compute & Inverse ─────────────────────────────────────────

    @api.depends('product_qty', 'product_id', 'product_packaging_id')
    def _compute_visual_qty(self):
        """Convert internal product_qty → visual_qty for display.

        Auto-corrects uom_mode for lines created by the variant grid
        (product matrix), which bypasses create() and all onchanges.
        Uses 'effective_mode' as a guaranteed fallback.
        """
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_qty:
                line.visual_qty = 0.0
                continue

            mode = line.uom_mode or 'unit'
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )

            # ── Auto-correct uom_mode (grid fix) ─────────
            effective_mode = mode
            if is_weight and mode == 'unit' and not line.product_packaging_id:
                effective_mode = 'kg'
                line.uom_mode = 'kg'
            elif not is_weight and mode in ('kg', 'g'):
                effective_mode = 'unit'
                line.uom_mode = 'unit'

            # ── Calculate visual_qty ──────────────────────
            if effective_mode == 'g':
                line.visual_qty = line.product_qty * 1000.0
            elif effective_mode == 'kg':
                line.visual_qty = line.product_qty
            else:  # unit
                if is_weight:
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = (
                            line.product_id.packaging_ids.filtered(
                                lambda p: p.purchase and p.qty > 0
                            )[:1]
                        )
                    if packaging:
                        line.visual_qty = line.product_qty / packaging.qty
                    else:
                        line.visual_qty = line.product_qty
                else:
                    line.visual_qty = line.product_qty

    def _inverse_visual_qty(self):
        """Convert visual_qty → product_qty for storage."""
        weight_categ = self._guapante_weight_categ()
        for line in self:
            qty = line.visual_qty or 0.0
            mode = line.uom_mode or 'unit'
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )

            if mode == 'g':
                line.product_packaging_qty = 0.0
                line.product_qty = qty / 1000.0
                line.product_packaging_id = False
            elif mode == 'kg':
                line.product_packaging_qty = 0.0
                line.product_qty = qty
                line.product_packaging_id = False
            else:  # unit
                if is_weight:
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = (
                            line.product_id.packaging_ids.filtered(
                                lambda p: p.purchase and p.qty > 0
                            )[:1]
                        )
                    if packaging:
                        line.product_packaging_qty = qty
                        line.product_qty = qty * packaging.qty
                        line.product_packaging_id = packaging.id
                    else:
                        line.product_packaging_qty = 0.0
                        line.product_qty = qty
                        line.product_packaging_id = False
                else:
                    line.product_packaging_qty = 0.0
                    line.product_qty = qty
                    line.product_packaging_id = False
