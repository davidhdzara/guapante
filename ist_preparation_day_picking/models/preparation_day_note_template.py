# -*- coding: utf-8 -*-
from odoo import fields, models


class PreparationDayNoteTemplate(models.Model):
    """Fase D — modelo propio que replica pos.note (nombre + secuencia):
    frases fijas que el engrane de Nivel 2 ofrece como chips al agregar
    una nota, configurables en Preparación › Modelos de notas.
    """
    _name = 'guapante.preparation.day.note.template'
    _description = 'Modelo de nota de Picking'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(default=10)
