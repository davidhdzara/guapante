# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_seasonal = fields.Boolean(
        string='De Temporada',
        default=False,
        help='Marcar este producto para que aparezca en la sección "Cosecha en temporada" del home'
    )

    # ── VIP B2B: Exclusividad a nivel producto ──
    is_b2b_exclusive = fields.Boolean(
        string='Producto Exclusivo B2B',
        default=False,
        help='Si se marca, este producto SOLO será visible en la tienda online '
             'para los clientes listados abajo. Para el público general o clientes '
             'no autorizados, el producto no aparecerá en el catálogo ni será '
             'accesible por URL directa.',
    )

    b2b_exclusive_customer_ids = fields.Many2many(
        'res.partner',
        'product_tmpl_b2b_partner_rel',
        'product_tmpl_id',
        'partner_id',
        string='Clientes B2B Permitidos',
        domain=[('is_company', '=', True)],
        help='Clientes (empresas) que pueden ver y comprar este producto exclusivo '
             'en la tienda online. Se verifica usando el contacto comercial (padre) '
             'del usuario logueado.',
    )

    b2b_replaces_product_ids = fields.Many2many(
        'product.template',
        'product_tmpl_b2b_replaces_rel',
        'exclusive_product_id',
        'replaced_product_id',
        string='Reemplaza Productos',
        help='Productos generales que se OCULTAN para los clientes VIP de este '
             'producto. Ejemplo: "Perejil crespo x250g" (VIP) reemplaza a '
             '"Perejil crespo" (general) → el cliente VIP solo ve la versión '
             'exclusiva. Si se deja vacío, el producto VIP convive con los generales.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'is_seasonal' in vals:
            # Invalidate only the affected product records so the website
            # picks up the new is_seasonal value without nuking the entire
            # ORM registry cache (which would cause performance spikes).
            self.invalidate_recordset(['is_seasonal'])
        return res
