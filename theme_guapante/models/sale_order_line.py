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

    @api.onchange('product_id')
    def _onchange_product_id_uom_mode(self) -> None:
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        for line in self:
            if not line.product_id:
                continue
            is_weight = (
                weight_categ
                and line.product_id.uom_id.category_id == weight_categ
            )
            # Siempre ajustar al cambiar producto:
            # peso → kg, no-peso → unit
            if is_weight:
                line.uom_mode = 'kg'
            else:
                line.uom_mode = 'unit'

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
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        for line in self:
            if not line.product_id or not line.uom_mode:
                continue
            is_weight = (
                weight_categ
                and line.product_id.uom_id.category_id == weight_categ
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

    @api.depends('product_uom_qty', 'product_id', 'product_packaging_id')
    def _compute_visual_qty(self) -> None:
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        for line in self:
            if not line.product_uom_qty:
                line.visual_qty = 0.0
                continue

            mode = line.uom_mode or 'unit'
            is_weight = (
                weight_categ
                and line.product_id
                and line.product_id.uom_id.category_id == weight_categ
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

        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        for line in self:
            qty = line.visual_qty or 0.0
            mode = line.uom_mode or 'unit'
            is_weight = (
                weight_categ
                and line.product_id
                and line.product_id.uom_id.category_id == weight_categ
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
