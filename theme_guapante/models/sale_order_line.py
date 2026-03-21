# -*- coding: utf-8 -*-
from odoo import fields, models, api


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
        help='Modo de unidad de medida seleccionado por el usuario (ej. Gramos vs Kg).',
    )

    visual_qty = fields.Float(
        string='Cantidad (Visual)',
        digits='Product Unit of Measure',
        compute='_compute_visual_qty',
        inverse='_inverse_visual_qty',
        store=True,
        help='Cantidad digitada por el usuario en base a la Unidad Visual seleccionada.',
    )

    @api.onchange('product_id')
    def _onchange_product_id_uom_mode(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            if not line.product_id:
                continue
            is_weight = weight_categ and line.product_id.uom_id.category_id == weight_categ
            if is_weight:
                has_packaging = bool(line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0))
                if not has_packaging:
                    line.uom_mode = 'kg'
            else:
                line.uom_mode = 'unit'

    @api.onchange('uom_mode')
    def _onchange_uom_mode_warning(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            if not line.product_id or not line.uom_mode:
                continue
            is_weight = weight_categ and line.product_id.uom_id.category_id == weight_categ
            has_packaging = bool(line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0))
            
            if is_weight and line.uom_mode == 'unit' and not has_packaging:
                line.uom_mode = 'kg'
                return {'warning': {'title': 'Modo Restringido', 'message': f'"{line.product_id.name}" no tiene un embalaje (Ej. Caja) configurado. Solo se puede pedir por Kilogramos o Gramos.'}}
            elif not is_weight and line.uom_mode in ['kg', 'g']:
                line.uom_mode = 'unit'
                return {'warning': {'title': 'Modo Restringido', 'message': f'"{line.product_id.name}" es un producto medido por unidades. No se puede pesar.'}}

    @api.depends('product_uom_qty', 'uom_mode', 'product_id', 'product_packaging_id')
    def _compute_visual_qty(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            if not line.product_uom_qty:
                line.visual_qty = 0.0
                continue
                
            mode = line.uom_mode or 'unit'
            is_weight = weight_categ and line.product_id and line.product_id.uom_id.category_id == weight_categ
            
            if mode == 'g':
                line.visual_qty = line.product_uom_qty * 1000.0
            elif mode == 'kg':
                line.visual_qty = line.product_uom_qty
            else: # unit
                if is_weight:
                    # FIX: Use existing product_packaging_id instead of forcing the first one blindly
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
                    
                    if packaging:
                        line.visual_qty = line.product_uom_qty / packaging.qty
                    else:
                        line.visual_qty = line.product_uom_qty
                else:
                    line.visual_qty = line.product_uom_qty

    def _inverse_visual_qty(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            qty = line.visual_qty or 0.0
            mode = line.uom_mode or 'unit'
            is_weight = weight_categ and line.product_id and line.product_id.uom_id.category_id == weight_categ
            
            if mode == 'g':
                line.product_uom_qty = qty / 1000.0
                line.product_packaging_id = False
            elif mode == 'kg':
                line.product_uom_qty = qty
                line.product_packaging_id = False
            else: # unit
                if is_weight:
                    # FIX: Use existing product_packaging_id instead of forcing the first one blindly
                    packaging = line.product_packaging_id
                    if not packaging:
                        packaging = line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
                        
                    if packaging:
                        line.product_uom_qty = qty * packaging.qty
                        line.product_packaging_id = packaging.id
                    else:
                        line.product_uom_qty = qty
                        line.product_packaging_id = False
                else:
                    line.product_uom_qty = qty
                    line.product_packaging_id = False


    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.visual_qty and self.uom_mode:
            mode_label = dict(self._fields['uom_mode'].selection).get(self.uom_mode) or self.uom_mode
            qty_fmt = int(self.visual_qty) if self.visual_qty == int(self.visual_qty) else self.visual_qty
            visual_desc = f"\nSolicitado: {qty_fmt} {mode_label}"
            
            if self.qty_delivered > 0 and self.uom_mode == 'unit':
                 visual_desc += f" (Peso facturado: {self.qty_delivered} {self.product_uom.name})"
                 
            if 'name' in res:
                res['name'] += visual_desc
        return res

    # DEPRECATED: Kept temporarily to prevent crashes with stale views
    display_qty = fields.Char(compute='_compute_legacy_display')
    display_uom_label = fields.Char(compute='_compute_legacy_display')

    def _compute_legacy_display(self):
        for line in self:
            line.display_qty = str(line.product_uom_qty)
            line.display_uom_label = line.product_uom.name or ''
