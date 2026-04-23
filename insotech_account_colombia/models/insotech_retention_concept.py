from odoo import models, fields


class InsotechRetentionConcept(models.Model):
    _name = 'insotech.retention.concept'
    _description = 'Conceptos de Retención Inteligentes'
    _order = 'type, name'

    name = fields.Char(
        string='Nombre del Concepto',
        required=True,
        help='Ej. Retención Compras Agrícolas',
    )
    type = fields.Selection(
        selection=[
            ('retefuente', 'Retención en la Fuente'),
            ('reteica', 'ReteICA'),
            ('reteiva', 'ReteIVA'),
            ('parafiscal', 'Parafiscal'),
        ],
        string='Tipo de Retención',
        required=True,
    )
    direction = fields.Selection(
        selection=[
            ('sale', 'Ventas (nos retienen)'),
            ('purchase', 'Compras (retenemos)'),
            ('both', 'Ambos'),
        ],
        string='Dirección',
        default='sale',
        required=True,
    )
    city_name = fields.Char(
        string='Municipio (ICA)',
        help='Opcional: Si es ReteICA, especifica la ciudad',
    )

    base_uvt = fields.Float(
        string='Base Mínima (UVT)',
        required=True,
        default=0.0,
        help='Tope mínimo en UVT para que aplique la retención',
    )
    percentage = fields.Float(
        string='Porcentaje (%)',
        required=True,
        digits=(5, 3),
        help='Ej. 1.5 para 1.5%%',
    )

    account_id = fields.Many2one(
        'account.account',
        string='Cuenta PUC (Ventas)',
        required=True,
        domain=[('deprecated', '=', False)],
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Venta',
        domain=[('type_tax_use', '=', 'sale')],
        help='Impuesto negativo de venta equivalente',
    )
    purchase_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Compra (a inyectar)',
        domain=[('type_tax_use', '=', 'purchase')],
        help='Impuesto negativo que se inyecta en facturas de proveedor',
    )

    active = fields.Boolean(default=True)
