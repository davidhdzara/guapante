# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    # Espejo de is_done con labels legibles — el kanban de Picking agrupa
    # por este campo en vez de por is_done directo, porque Odoo no deja
    # poner labels custom a un group_by de un Boolean (sale "No"/"Sí"
    # crudo). store=True porque el group_by de kanban necesita un campo
    # en la base de datos, no uno puramente en memoria.
    picking_status = fields.Selection(
        selection=[('pending', 'Pendiente'), ('done', 'Terminado')],
        compute='_compute_picking_status',
        store=True,
    )

    def _compute_picking_operator_anchor(self) -> None:
        for line in self:
            line.picking_operator_anchor = ''

    @api.depends('is_done')
    def _compute_picking_status(self) -> None:
        for line in self:
            line.picking_status = 'done' if line.is_done else 'pending'
