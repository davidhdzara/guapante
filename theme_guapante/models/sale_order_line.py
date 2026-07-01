# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    uom_mode = fields.Selection(
        selection=[
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='Unidad (Visual)',
        default='unit',
        help=(
            'Modo de unidad de medida seleccionado por el '
            'usuario (ej. Gramos vs Kg).'
        ),
    )

    visual_qty = fields.Float(
        string='Cantidad (Visual)',
        digits='Product Unit of Measure',
        compute='_compute_visual_qty',
        inverse='_inverse_visual_qty',
        store=True,
        help=(
            'Cantidad digitada por el usuario en base a la '
            'Unidad Visual seleccionada.'
        ),
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
        ``visual_qty`` always equals ``product_uom_qty`` for weight
        items coming from the grid.
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
                if not line.product_packaging_id:
                    line.uom_mode = 'kg'

            # Non-weight product stuck on 'kg'/'g' → switch to 'unit'
            elif not is_weight and mode in ('kg', 'g'):
                line.uom_mode = 'unit'

    # ── ORM overrides ─────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Set correct uom_mode on programmatic creation (e.g. save)."""
        weight_categ = self._guapante_weight_categ()
        for vals in vals_list:
            if 'product_id' not in vals:
                continue
            product = self.env['product.product'].browse(vals['product_id'])
            is_weight = self._guapante_is_weight_product(
                product, weight_categ,
            )
            if 'uom_mode' not in vals or vals.get('uom_mode') == 'unit':
                vals['uom_mode'] = 'kg' if is_weight else 'unit'
        return super().create(vals_list)

    # ── Onchanges ─────────────────────────────────────────────────

    @api.onchange('product_id')
    def _onchange_product_id_uom_mode(self) -> None:
        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_id:
                continue
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )
            # Siempre ajustar al cambiar producto:
            # peso → kg, no-peso → unit
            line.uom_mode = 'kg' if is_weight else 'unit'

    @api.onchange('visual_qty', 'uom_mode')
    def _onchange_visual_qty_uom_mode_sync(self) -> None:
        """Preservación visual: mantiene el número al cambiar modo.

        Al cambiar uom_mode, el inverse toma el visual_qty actual
        y recalcula product_uom_qty para el nuevo modo.
        Ej: 7 en modo 'unit' → puq = 7 × 0.65 = 4.55 kg.
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
                    lambda p: p.sales and p.qty > 0
                )
            )

            if is_weight and line.uom_mode == 'unit' and not has_packaging:
                line.uom_mode = 'kg'
                return {
                    'warning': {
                        'title': 'Modo Restringido',
                        'message': (
                            f'"{line.product_id.name}" no tiene un '
                            f'embalaje (Ej. Caja) configurado. Solo se '
                            f'puede pedir por Kilogramos o Gramos.'
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
                            f'medido por unidades. No se puede pesar.'
                        ),
                    },
                }

    # ── Compute & Inverse ─────────────────────────────────────────

    @api.depends('product_uom_qty', 'product_id', 'product_packaging_id')
    def _compute_visual_qty(self) -> None:
        """Convert internal product_uom_qty → visual_qty for display.

        CRITICAL: calls _guapante_ensure_uom_mode() FIRST to auto-fix
        the uom_mode for lines created by the variant grid, which
        bypasses create() and all onchanges.
        """
        self._guapante_ensure_uom_mode()

        weight_categ = self._guapante_weight_categ()
        for line in self:
            if not line.product_uom_qty:
                line.visual_qty = 0.0
                continue

            mode = line.uom_mode or 'unit'
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )

            if mode == 'g':
                line.visual_qty = line.product_uom_qty * 1000.0
            elif mode == 'kg':
                line.visual_qty = line.product_uom_qty
            else:  # unit
                if is_weight:
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = (
                            line.product_id.packaging_ids.filtered(
                                lambda p: p.sales and p.qty > 0
                            )[:1]
                        )
                    if packaging:
                        line.visual_qty = (
                            line.product_uom_qty / packaging.qty
                        )
                    else:
                        line.visual_qty = line.product_uom_qty
                else:
                    line.visual_qty = line.product_uom_qty

    def _inverse_visual_qty(self) -> None:
        """Convierte visual_qty de vuelta a product_uom_qty.

        PROTECCIÓN: Solo actúa cuando la escritura proviene de una
        interacción de usuario (formulario/onchange). Si el ORM
        dispara el inverse por recomputación interna (ej. tras un
        cambio en stock.move.quantity desde el módulo de Preparación),
        se ignora para evitar que el peso del operario pise la
        cantidad pedida por el cliente.
        """
        # Si estamos en un flujo de inventario/preparación, NO ejecutar
        # el inverse para proteger product_uom_qty del cliente.
        if self.env.context.get('skip_inverse_visual_qty'):
            return

        weight_categ = self._guapante_weight_categ()
        for line in self:
            qty = line.visual_qty or 0.0
            mode = line.uom_mode or 'unit'
            is_weight = self._guapante_is_weight_product(
                line.product_id, weight_categ,
            )

            if mode == 'g':
                line.product_uom_qty = qty / 1000.0
                line.product_packaging_id = False
            elif mode == 'kg':
                line.product_uom_qty = qty
                line.product_packaging_id = False
            else:  # unit
                if is_weight:
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = (
                            line.product_id.packaging_ids.filtered(
                                lambda p: p.sales and p.qty > 0
                            )[:1]
                        )
                    if packaging:
                        line.product_uom_qty = qty * packaging.qty
                        line.product_packaging_id = packaging.id
                    else:
                        line.product_uom_qty = qty
                        line.product_packaging_id = False
                else:
                    line.product_uom_qty = qty
                    line.product_packaging_id = False

    # DEPRECATED: Kept temporarily to prevent crashes with stale views
    display_qty = fields.Char(compute='_compute_legacy_display')
    display_uom_label = fields.Char(compute='_compute_legacy_display')

    def _compute_legacy_display(self) -> None:
        for line in self:
            line.display_qty = str(line.product_uom_qty)
            line.display_uom_label = line.product_uom.name or ''
