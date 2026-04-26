from odoo import api, fields, models
from odoo.osv import expression

class InsotechRetentionCategory(models.Model):
    _name = 'insotech.retention.category'
    _description = 'Categorías de Retención'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Nombre de Categoría', required=True, translate=True)
    parent_id = fields.Many2one('insotech.retention.category', 'Categoría Padre', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('insotech.retention.category', 'parent_id', 'Categorías Hijas')
    
    complete_name = fields.Char(
        'Nombre Completo', compute='_compute_complete_name', recursive=True, store=True
    )
    
    concept_count = fields.Integer(
        '# Conceptos', compute='_compute_concept_count',
        help="Cantidad de conceptos asociados a esta categoría y sus subcategorías"
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    def _compute_concept_count(self):
        for category in self:
            # Incluye la categoría actual y todas sus hijas en la cuenta
            category_ids = self.search([('id', 'child_of', category.id)]).ids
            category.concept_count = self.env['insotech.retention.concept'].search_count([
                ('category_id', 'in', category_ids)
            ])

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            args = expression.AND([args, ['|', ('name', operator, name), ('complete_name', operator, name)]])
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)
