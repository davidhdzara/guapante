# -*- coding: utf-8 -*-
from odoo import fields, models


class PreparationDayLine(models.Model):
    _inherit = 'guapante.preparation.day.line'

    # Punto de montaje del widget de identificación por PIN en cada card
    # del kanban de Picking — el valor no se usa (operatorState es un
    # singleton compartido en JS), solo existe para que el widget se
    # monte. Mismo patrón que operator_identification en el wizard y
    # live_refresh_anchor en guapante.preparation.day.
    picking_operator_anchor = fields.Char(
        compute='_compute_picking_operator_anchor',
    )

    def _compute_picking_operator_anchor(self) -> None:
        for line in self:
            line.picking_operator_anchor = ''
