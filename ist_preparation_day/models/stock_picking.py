# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    """Numeración diaria de cajas ("Caja #") sobre stock.picking.

    Separado de theme_guapante/models/stock_picking.py (que sigue dueño de
    Recolectar/logística de entrega: vehicle_id, driver_id, is_recolectar_operation,
    button_validate) — ver nota de dominio en models/sale_order.py de este módulo.
    """
    _inherit = 'stock.picking'

    daily_sequence = fields.Integer(
        string='Caja #',
        related='sale_id.daily_sequence',
        store=True,
        readonly=True,
    )

    def action_reset_daily_sequence(self) -> dict:
        """Resetea la numeración de cajas para los pickings seleccionados.

        Pone daily_sequence = 0 en las sale.order vinculadas,
        reinicia la ir.sequence del día correspondiente y limpia
        las líneas de preparación del día asociadas.
        """
        Orders = self.mapped('sale_id').filtered(
            lambda o: o.daily_sequence > 0
        )
        if not Orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Reset de Cajas',
                    'message': (
                        'No se encontraron órdenes con número '
                        'de caja asignado en los pickings seleccionados.'
                    ),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        count = len(Orders)
        Orders.write({'daily_sequence': 0})

        # Resetear ir.sequence por cada (company, date) involucrada.
        dates_by_company = {}
        for picking in self.filtered(lambda p: p.sale_id in Orders):
            cid = picking.company_id.id or False
            sdate = (picking.scheduled_date or fields.Datetime.now()).date()
            dates_by_company.setdefault(cid, set()).add(sdate)

        Sequence = self.env['ir.sequence'].sudo()
        for cid, dates in dates_by_company.items():
            for d in dates:
                code = 'guapante.daily.%s.%s' % (
                    cid, d.strftime('%Y%m%d'),
                )
                seq = Sequence.search([('code', '=', code)], limit=1)
                if seq:
                    seq.write({'number_next': 1})

        # Limpiar líneas de preparación del día vinculadas.
        PrepLines = self.env['guapante.preparation.day.line'].search([
            ('sale_order_id', 'in', Orders.ids),
            ('daily_sequence', '>', 0),
        ])
        if PrepLines:
            PrepLines.write({'daily_sequence': 0})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reset de Cajas',
                'message': (
                    f'{count} órdenes reseteadas. '
                    'Ejecuta "Ver pedidos" en Preparación '
                    'del Día para reasignar desde #1.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
