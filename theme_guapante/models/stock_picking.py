# -*- coding: utf-8 -*-
import odoo
from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehículo Asignado")
    driver_id = fields.Many2one('res.partner', string="Conductor")
    daily_sequence = fields.Integer(
        string='Caja #',
        related='sale_id.daily_sequence',
        store=True,
        readonly=True,
    )

    is_recolectar_operation = fields.Boolean(
        string='Es operación Recolectar',
        compute='_compute_is_recolectar',
        store=False,
    )
    sale_parent_id = fields.Many2one(
        'res.partner',
        compute='_compute_sale_parent_id',
        string="Cliente Principal",
        store=False,
    )

    @api.depends('sale_id.partner_id')
    def _compute_sale_parent_id(self) -> None:
        for picking in self:
            partner = picking.sale_id.partner_id
            if partner:
                picking.sale_parent_id = (
                    partner.parent_id if partner.parent_id else partner
                )
            else:
                picking.sale_parent_id = False

    @api.depends('picking_type_id')
    def _compute_is_recolectar(self) -> None:
        for picking in self:
            picking.is_recolectar_operation = (
                picking.picking_type_id.name
                and 'recolectar' in picking.picking_type_id.name.lower()
            )

    def button_validate(self):
        # Desactivar la restricción durante la ejecución de pruebas
        if (
            odoo.tools.config['test_enable']
            or self.env.context.get('install_mode')
        ):
            return super().button_validate()

        for picking in self:
            # Odoo 18: Forzar 'picked' en los movimientos que tengan líneas con cantidad.
            # Esto es vital para que la validación permita sobre-procesar sin stock
            # en cualquier parte de la cadena (Recolectar, Empaque o Salida).
            picking.move_ids_without_package.filtered(
                lambda m: any(ml.quantity > 0 for ml in m.move_line_ids) or m.quantity > 0
            ).write({'picked': True})

            # Solo validar pesaje confirmado en operaciones de RECOLECTAR
            if picking.is_recolectar_operation:
                unconfirmed_moves = picking.move_ids_without_package.filtered(
                    lambda m: (
                        not m.is_weight_confirmed
                        and m.state not in ('cancel', 'done')
                    )
                )
                if unconfirmed_moves:
                    product_names = "\n".join(
                        [
                            f"- {m.product_id.display_name}"
                            for m in unconfirmed_moves
                        ]
                    )
                    raise UserError(
                        "⚠️ Faltan pesajes por confirmar.\n\n"
                        "Para poder validar esta orden de Recolección, "
                        "debes marcar el campo 'Pesaje Confirmado' (Check) "
                        "al final de la línea en los siguientes "
                        f"productos:\n\n{product_names}"
                    )
        # Proceder con la validación nativa inyectando el escudo de protección.
        # manual_entry y skip_recolectar_zero_check le dicen al sistema que
        # respete los pesos digitados aunque no haya stock.
        return super(StockPicking, self.with_context(
            manual_entry=True,
            skip_recolectar_zero_check=True
        )).button_validate()

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self) -> None:
        """Auto-asignar conductor basado en el vehículo."""
        if self.vehicle_id and self.vehicle_id.driver_id:
            self.driver_id = self.vehicle_id.driver_id

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
                'title': 'Reset de Cajas ✅',
                'message': (
                    f'{count} órdenes reseteadas. '
                    'Ejecuta "Ver pedidos" en Preparación '
                    'del Día para reasignar desde #1.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
