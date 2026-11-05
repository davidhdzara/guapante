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
    vía _sync_weight_to_stock. Así que este hook SIEMPRE se dispara
    desde Inventario (o cualquier flujo ajeno a Preparación), nunca
    desde el propio guardado de Preparación.

    CORRECCIÓN (encontrada por test, 2026-11-05): el filtro de este
    search NO debe excluir is_done=True. Decisión (c) — "gana quien
    llegó primero" — exige que el cron SIEMPRE evalúe la línea
    cuando el PICK se valida desde Inventario, incluso si Preparación
    ya la había cerrado antes (para dejar la nota de diferencia de
    peso en el chatter); filtrar por is_done=False acá mataba esa
    comparación antes de que el cron pudiera verla.

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
            ('needs_inventory_mirror', '=', False),
        ])
        if Line:
            Line.write({'needs_inventory_mirror': True})

        return res
