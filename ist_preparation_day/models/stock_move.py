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

    def _action_cancel(self):
        """Extensión del espejo (Tech Lead/David, 2026-11-06): un PICK
        que se cancela (ej. "sin stock", declinar backorder) nunca
        pasa por _action_done — sin este hook simétrico, needs_
        inventory_mirror nunca se prende y la línea queda Pendiente
        para siempre (hueco encontrado por Tech Lead en producción,
        sesión 226, 2026-11-06).

        Verificado en el fuente real de Odoo 18 (stock/models/
        stock_move.py _action_cancel, stock_picking.py action_cancel,
        sale_stock/models/sale_order.py _action_cancel) antes de
        escribir esto: _action_cancel() es el ÚNICO lugar que escribe
        el state de stock.move a 'cancel' (moves_to_cancel.state =
        'cancel' en el fuente) — sin bypass por write() directo que
        hiciera falta cubrir aparte. stock.picking.action_cancel()
        siempre delega en self.move_ids._action_cancel(). La
        cascada de sale.order real (sale_stock, que sobreescribe a
        sale base) cancela PRIMERO los pickings/moves y SOLO DESPUÉS
        pone el pedido en 'cancel' (_action_cancel: picking_ids.
        action_cancel() antes de super()._action_cancel()) — pero
        como el reflejo real lo hace el cron 2 minutos después, en
        una transacción separada que lee ya con todo comprometido,
        esto no abre ninguna ventana de carrera real para el guard
        de preparation_day.py (sale_order_id.state == 'cancel').
        """
        res = super()._action_cancel()

        Line = self.env['guapante.preparation.day.line'].sudo().search([
            ('stock_move_id', 'in', self.ids),
            ('needs_inventory_mirror', '=', False),
        ])
        if Line:
            Line.write({'needs_inventory_mirror': True})

        return res
