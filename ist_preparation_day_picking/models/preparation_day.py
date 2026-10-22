# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError


class PreparationDay(models.Model):
    _inherit = 'guapante.preparation.day'

    def action_view_picking_kanban(self) -> dict:
        """Abre Picking: kanban a pantalla completa de las líneas
        pendientes de esta sesión — báscula + PIN, sin paso de
        selección de producto (eso ya lo resuelve el Summary kanban +
        wizard existentes).

        Chequeo de grupo explícito en Python: el botón ya se oculta por
        grupo en la vista, pero esto devuelve un dict dinámico (no un
        ir.actions.act_window con id propio), así que un groups_id en
        un registro XML no alcanzaría a protegerlo solo — hace falta
        esta verificación para que el acceso quede cerrado también si
        alguien llama al método directamente, no solo por UI.
        """
        self.ensure_one()
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError(
                'No tienes acceso a la pantalla de Picking.'
            )
        return {
            'name': 'Picking',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.line',
            'view_mode': 'kanban',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'fullscreen',
        }
