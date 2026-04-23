from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    insotech_retention_concept_ids = fields.Many2many(
        'insotech.retention.concept',
        'partner_retention_concept_rel',
        'partner_id',
        'concept_id',
        string='Conceptos de Retención por Defecto',
        help='Retenciones que se aplican automáticamente al calcular '
             'en facturas de proveedor de este contacto.',
    )
