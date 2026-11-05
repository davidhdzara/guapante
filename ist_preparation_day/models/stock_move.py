# -*- coding: utf-8 -*-
from odoo import models


class StockMove(models.Model):
    """ESPEJO Inventario→Preparación (David/Tech Lead, 2026-11-05):
    cuando el PICK de una línea de Preparación se valida (llega a
    'done') SIN que Preparación la haya cerrado antes (is_done=False
    todavía — ej. alguien validó el traslado Recolectar directo desde
    Inventario, con o sin peso), esta línea queda huérfana para
    siempre si nadie la refleja: el PICK ya está Hecho pero
    Preparación sigue mostrándola Pendiente.

    Preparación NUNCA llama button_validate/_action_done por su
    cuenta (ver nota de dominio en ist_preparation_day/models/
    stock_picking.py) — solo escribe quantity/picked/state='assigned'
    vía _sync_weight_to_stock. Así que este hook se dispara para
    TODA validación de un PICK, tanto si vino del tablet (ya
    is_done=True, no hay nada que reflejar) como si no (is_done=False,
    caso real) — el filtro `not Line.is_done` ya distingue los dos
    casos sin necesitar ninguna marca de contexto.

    Hook deliberadamente LIVIANO (Tech Lead, 2026-11-03): solo pone la
    bandera needs_inventory_mirror=True y retorna — nunca toca
    actual_kg/is_done acá mismo, para no poder tumbar ni demorar la
    validación del usuario de Inventario con un error de Preparación.
    El reflejo real lo hace _cron_mirror_inventory_to_preparation
    (PreparationDayLine), en su propia transacción.
    """
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)

        Line = self.env['guapante.preparation.day.line'].sudo().search([
            ('stock_move_id', 'in', self.ids),
            ('is_done', '=', False),
            ('needs_inventory_mirror', '=', False),
        ])
        if Line:
            Line.write({'needs_inventory_mirror': True})

        return res
