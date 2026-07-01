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

    def _guapante_ensure_uom_mode(self):
        """Auto-correct uom_mode for weight products stuck on default.

        The variant grid (product matrix) creates virtual NewId records
        via ``@api.onchange('grid')``.  During that onchange the ORM
        never calls ``create()`` and never triggers individual
        ``@api.onchange('product_id')`` callbacks on each line.
        This means ``uom_mode`` stays at its field default ``'unit'``
        even for products whose native UoM is kg.

        This helper detects that inconsistency and silently flips
        ``uom_mode`` to ``'kg'`` **before** the compute runs, so
        ``visual_qty`` always equals ``product_qty`` for weight items
        coming from the grid.
        """
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            mode = line.uom_mode or 'unit'

            # Weight product stuck on 'unit' → switch to 'kg'
            if is_weight and mode == 'unit':
                # Only auto-correct if the user hasn't explicitly chosen
                # 'unit' by having a packaging already set.
                if not line.product_packaging_id:
                    line.uom_mode = 'kg'

            # Non-weight product stuck on 'kg'/'g' → switch to 'unit'
            elif not is_weight and mode in ('kg', 'g'):
                line.uom_mode = 'unit'

    # ── ORM overrides ─────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Set correct uom_mode on programmatic creation (e.g. save).

        Only injects uom_mode when the caller did NOT explicitly
        include it in the vals dict (pure programmatic creation,
        e.g. from an API or a wizard).  When the form UI saves,
        uom_mode IS always present because the field is on the view,
        so we respect the user's choice.
        """
        weight_categ = self._guapante_weight_categ()
        for vals in vals_list:
            if 'product_id' not in vals:
                continue
            if 'uom_mode' in vals:
                continue  # User/UI set it explicitly — respect it
            product = self.env['product.product'].browse(vals['product_id'])
            is_weight = self._guapante_is_weight_product(
                product, weight_categ,
            )
            vals['uom_mode'] = 'kg' if is_weight else 'unit'
        return super().create(vals_list)

    # ── Onchanges ─────────────────────────────────────────────────

    @api.onchange('product_id')
    def _onchange_product_id_uom_mode(self):
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            line.uom_mode = 'kg' if is_weight else 'unit'

    @api.onchange('visual_qty', 'uom_mode')
    def _onchange_visual_qty_uom_mode_sync(self):
        """Preserve the visual number when switching units.

        Forces the inverse to recalculate product_qty based on the
        current visual_qty and the (possibly new) uom_mode.
        """
        self._inverse_visual_qty()

    @api.onchange('uom_mode')
    def _onchange_uom_mode_warning(self):
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id or not line.uom_mode:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            has_packaging = bool(
                line.product_id.packaging_ids.filtered(
                    lambda p: p.purchase and p.qty > 0
                )
            )

            if is_weight and line.uom_mode == 'unit' and not has_packaging:
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
            elif not is_weight and line.uom_mode in ['kg', 'g']:
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

    # ── Compute & Inverse ─────────────────────────────────────────

    @api.depends('product_qty', 'product_id', 'product_packaging_id')
    def _compute_visual_qty(self):
        """Convert internal product_qty → visual_qty for display.

        CRITICAL: calls _guapante_ensure_uom_mode() FIRST to auto-fix
        the uom_mode for lines created by the variant grid, which
        bypasses create() and all onchanges.
        """
        self._guapante_ensure_uom_mode()

        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_qty:
                line.visual_qty = 0.0
                continue

            mode = line.uom_mode or 'unit'
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )

            if mode == 'g':
                line.visual_qty = line.product_qty * 1000.0
            elif mode == 'kg':
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
