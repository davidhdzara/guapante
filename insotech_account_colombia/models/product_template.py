from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    insotech_parafiscal_concept_id = fields.Many2one(
        'insotech.retention.concept',
        string='Parafiscal Aplicable',
        domain=[('type', '=', 'parafiscal'), ('active', '=', True)],
        help='Concepto parafiscal que se aplica al comprar este producto '
             '(Ej. Asohofrucol, Fedepapa, Cereales, Leguminosas, Soya).',
    )
