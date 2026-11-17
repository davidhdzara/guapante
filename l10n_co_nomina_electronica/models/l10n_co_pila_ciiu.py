# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Catálogo de actividades económicas del Sistema General de Riesgos Laborales.

Tabla de clasificación de actividades económicas adoptada por el Decreto 768 de 2022 (anexo
técnico; reemplazó la del Decreto 1607 de 2002), dentro del marco del Decreto 1072 de 2015. Cada
actividad trae su clase de riesgo (I a V).

No existe un modelo nativo de Odoo que represente este catálogo (l10n_co trae el CIIU del
contacto, pero no la clase de riesgo ARL), así que es una tabla propia administrable: mismo
patrón que l10n.co.retefuente.uvt. Las filas se versionan con vigencia (date_start/date_end): un
decreto futuro agrega filas nuevas, no reemplaza las viejas.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nCoPilaCiiu(models.Model):
    _name = 'l10n.co.pila.ciiu'
    _description = 'Actividad económica ARL (Decreto 768 de 2022)'
    _order = 'code, date_start desc'
    # Búsqueda por código O por descripción (pedido de David), en el campo y en los filtros.
    _rec_names_search = ['code', 'name']

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Actividad', required=True, translate=False)
    risk_class = fields.Selection(
        selection=[
            ('1', 'I - Riesgo Mínimo'),
            ('2', 'II - Riesgo Bajo'),
            ('3', 'III - Riesgo Medio'),
            ('4', 'IV - Riesgo Alto'),
            ('5', 'V - Riesgo Máximo'),
        ],
        string='Clase de Riesgo',
        required=True,
    )
    date_start = fields.Date(string='Vigente desde')
    date_end = fields.Date(string='Vigente hasta')

    _sql_constraints = [
        ('code_start_uniq', 'unique(code, date_start)',
         'Ya existe esa actividad con la misma fecha de inicio de vigencia.'),
    ]

    @api.constrains('date_start', 'date_end')
    def _check_vigencia(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_(
                    'La actividad %(codigo)s tiene la vigencia invertida (hasta antes de desde).',
                    codigo=record.code))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '[%s] %s' % (record.code, record.name) if record.code else record.name
