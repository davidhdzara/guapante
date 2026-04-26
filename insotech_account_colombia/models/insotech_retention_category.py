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

    state_id = fields.Many2one('res.country.state', 'Departamento DANE', index=True, ondelete='restrict')
    city_id = fields.Many2one('res.city', 'Municipio DANE', index=True, ondelete='restrict')

    @api.model
    def auto_generate_colombian_dane_categories(self):
        """
        Genera la jerarquía completa de categorías de retención basada en el DANE (res.country.state y res.city).
        Debe ser llamado vía archivo XML data (<function .../>) durante la actualización.
        """
        # Buscar país Colombia
        co_country = self.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            return

        # 1. Crear nodos raíz principales
        cat_nac = self.search([('name', '=', 'Nacionales')], limit=1) or self.create({'name': 'Nacionales'})
        cat_par = self.search([('name', '=', 'Parafiscales')], limit=1) or self.create({'name': 'Parafiscales'})
        cat_dep = self.search([('name', '=', 'Departamentales')], limit=1) or self.create({'name': 'Departamentales'})

        # 2. Generar todos los departamentos y ciudades de Colombia de forma agrupada
        states = self.env['res.country.state'].search([('country_id', '=', co_country.id)])
        cities = self.env['res.city'].search([('country_id', '=', co_country.id)])
        
        # Mapeo de estados
        state_categories = {}
        for state in states:
            cat_state = self.search([('state_id', '=', state.id), ('parent_id', '=', cat_dep.id)], limit=1)
            if not cat_state:
                cat_state = self.create({
                    'name': state.name,
                    'parent_id': cat_dep.id,
                    'state_id': state.id
                })
            state_categories[state.id] = cat_state

        # Batch create cities to avoid thousands of individual ORM calls
        cities_to_create = []
        
        # Index existing cities to avoid duplicates
        existing_city_cats = self.search([('city_id', 'in', cities.ids)])
        existing_city_ids = set(existing_city_cats.mapped('city_id.id'))

        for city in cities:
            if city.id in existing_city_ids:
                continue
                
            parent_cat = state_categories.get(city.state_id.id) if city.state_id else False
            if parent_cat:
                cities_to_create.append({
                    'name': city.name,
                    'parent_id': parent_cat.id,
                    'state_id': city.state_id.id,
                    'city_id': city.id
                })

        if cities_to_create:
            self.create(cities_to_create)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s > %s' % (category.parent_id.complete_name, category.name)
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
