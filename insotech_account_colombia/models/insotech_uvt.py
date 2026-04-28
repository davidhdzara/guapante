from odoo import models, fields, api

class InsotechUvt(models.Model):
    _name = 'insotech.uvt'
    _description = 'Histórico de UVT Colombia'
    _order = 'year desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year)
    value = fields.Monetary(string='Valor UVT', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('year_unique', 'unique(year)', 'Ya existe un valor de UVT registrado para este año. Modifica el existente en lugar de crear uno nuevo.')
    ]

    @api.depends('year')
    def _compute_name(self):
        for record in self:
            record.name = f"UVT {record.year}"
