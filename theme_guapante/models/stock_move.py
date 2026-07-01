# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    customer_qty_display = fields.Char(
        string='Cant. Cliente',
        compute='_compute_customer_uom_display',
        store=False,
    )
    customer_uom_display = fields.Char(
        string='UdM Cliente',
        compute='_compute_customer_uom_display',
        store=False,
    )
    is_weight_confirmed = fields.Boolean(
        string='Pesaje Confirmado',
        default=False,
        help=(
            'Marca para confirmar que el producto ha sido '
            're-pesado en bodega y corroborado.'
        ),
    )
    extra_validation = fields.Boolean(
        string='Validación Extra',
        default=False,
        help='Checkbox informativo para validación secundaria por línea.',
    )

    @api.depends('sale_line_id', 'purchase_line_id')
    def _compute_customer_uom_display(self) -> None:
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )

        for move in self:
            s_line = move.sale_line_id
            p_line = (
                move.purchase_line_id
                if hasattr(move, 'purchase_line_id')
                else False
            )

            if s_line:
                mode = s_line.uom_mode or 'unit'
                qty = s_line.product_uom_qty
                product = s_line.product_id
                pack_filter = lambda p: p.sales and p.qty > 0
            elif p_line:
                mode = p_line.uom_mode or 'unit'
                qty = p_line.product_qty
                product = p_line.product_id
                pack_filter = lambda p: p.purchase and p.qty > 0
            else:
                move.customer_qty_display = ''
                move.customer_uom_display = ''
                continue

            if mode == 'g':
                move.customer_qty_display = str(int(round(qty * 1000)))
                move.customer_uom_display = 'g'
            elif mode == 'kg':
                val = round(qty, 2)
                display = (
                    str(int(val)) if val == int(val) else str(val)
                )
                move.customer_qty_display = display
                move.customer_uom_display = 'kg'
            else:
                is_weight = (
                    weight_categ
                    and product.uom_id.category_id == weight_categ
                )
                if is_weight:
                    Packaging = product.packaging_ids.filtered(
                        pack_filter
                    )[:1]
                    if Packaging:
                        qty_units = round(qty / Packaging.qty)
                    else:
                        qty_units = (
                            int(qty) if qty == int(qty) else qty
                        )
                else:
                    qty_units = (
                        int(qty) if qty == int(qty) else qty
                    )

                move.customer_qty_display = str(int(qty_units))
                move.customer_uom_display = 'Unidades'

    @api.onchange('quantity')
    def _onchange_quantity_tolerance(self) -> None:
        """Alerta suave si operario digita más del 20% del peso esperado."""
        for move in self:
            if move.product_uom_qty > 0 and move.quantity > 0:
                expected_kg = move.product_uom_qty
                registered_kg = move.quantity

                weight_categ = self.env.ref(
                    'uom.product_uom_categ_kgm',
                    raise_if_not_found=False,
                )
                if (
                    not weight_categ
                    or move.product_id.uom_id.category_id != weight_categ
                ):
                    continue

                if registered_kg > (expected_kg * 1.20):
                    return {
                        'warning': {
                            'title': '⚠️ Alerta de Tolerancia de Peso',
                            'message': (
                                f'La cantidad pesada ({registered_kg} kg) '
                                f'excede en más de un 20% lo pedido '
                                f'({expected_kg} kg). Asegúrate de que la '
                                f'báscula y el producto sean correctos.'
                            ),
                        },
                    }

    # ──────────────────────────────────────────────────────────────
    # ESTRATEGIA "CONSULTA AL PICK": Después de que Odoo termina
    # su procesamiento, leemos el peso del PICK (ya en estado
    # 'done' en la BD) y lo pegamos tal cual en el OUT.
    # Sin memoria temporal, sin riesgo de cruce entre usuarios.
    # ──────────────────────────────────────────────────────────────

    def _action_done(self, cancel_backorder=False):
        """Después de que Odoo valida el PICK, leemos el peso
        directamente del PICK (que ya está 'done' en BD) y lo
        copiamos al OUT.
        """
        # Dejar que Odoo haga TODO su procesamiento nativo
        res = super()._action_done(cancel_backorder=cancel_backorder)

        # Ahora los moves del PICK están en 'done' con sus pesos intactos.
        # Consultar cada uno y pegar el peso en el movimiento destino (OUT).
        ctx = {
            'guapante_wizard_intent': True,
            'skip_recolectar_zero_check': True,
            'manual_entry': True,
        }
        MoveLine = self.env['stock.move.line'].sudo()

        for pick_move in self:
            # Solo procesar movimientos con pesaje confirmado
            if not pick_move.is_weight_confirmed:
                continue

            # Leer el peso del PICK (fuente de verdad en la BD)
            weight = pick_move.quantity
            if weight <= 0:
                continue

            _logger.info(
                "GUAPANTE: PICK move %s (%s) done con %.3f kg → propagando a destinos",
                pick_move.id, pick_move.product_id.display_name, weight,
            )

            # Pegar el peso en cada movimiento destino (OUT, PACK, etc.)
            for dest in pick_move.move_dest_ids:
                if dest.state in ('done', 'cancel'):
                    continue

                # 1. Forzar estado a 'assigned' (disponible)
                if dest.state in ('waiting', 'confirmed', 'partially_available'):
                    dest.sudo().with_context(**ctx).write({'state': 'assigned'})

                # 2. Pegar el peso en las líneas de movimiento
                if dest.move_line_ids:
                    dest.move_line_ids[0].sudo().with_context(**ctx).write({
                        'quantity': weight,
                    })
                    # Limpiar líneas extra vacías
                    extra_empty = dest.move_line_ids[1:].filtered(
                        lambda l: l.quantity == 0
                    )
                    if extra_empty:
                        extra_empty.with_context(**ctx).unlink()
                else:
                    # Odoo borró todas las líneas → crear una nueva
                    MoveLine.with_context(**ctx).create({
                        'move_id': dest.id,
                        'product_id': dest.product_id.id,
                        'product_uom_id': dest.product_uom.id,
                        'location_id': dest.location_id.id,
                        'location_dest_id': dest.location_dest_id.id,
                        'picking_id': dest.picking_id.id,
                        'quantity': weight,
                    })

                # 3. Marcar el destino como picked y confirmado
                dest.sudo().with_context(**ctx).write({
                    'picked': True,
                    'is_weight_confirmed': True,
                })

                _logger.info(
                    "GUAPANTE: OUT move %s (%s) → pegado %.3f kg OK",
                    dest.id, dest.product_id.display_name, weight,
                )

        return res

    def _action_assign(self):
        """Después de la reserva nativa, si un movimiento del OUT
        tiene peso confirmado pero fue vaciado, leemos el peso
        del PICK origen (que está 'done') y lo restauramos.
        """
        # Ejecutar reserva nativa
        res = super(StockMove, self)._action_assign()

        ctx = {
            'guapante_wizard_intent': True,
            'skip_recolectar_zero_check': True,
            'manual_entry': True,
        }
        MoveLine = self.env['stock.move.line'].sudo()

        for move in self:
            # Caso 1: Movimientos de Recolectar sin confirmar → forzar a 0
            if (
                not move.is_weight_confirmed
                and move.picking_type_id.name
                and 'recolectar' in move.picking_type_id.name.lower()
                and not self.env.context.get('skip_recolectar_zero_check')
            ):
                move.sudo().move_line_ids.write({'quantity': 0.0})
                move.sudo().write({'picked': False})
                continue

            # Caso 2: Movimientos con peso confirmado que fue vaciado
            if move.is_weight_confirmed and move.quantity <= 0:
                # Consultar el peso del PICK origen (fuente de verdad)
                weight = 0
                for orig in move.move_orig_ids:
                    if orig.state == 'done' and orig.is_weight_confirmed and orig.quantity > 0:
                        weight = orig.quantity
                        break

                if weight <= 0:
                    continue

                _logger.info(
                    "GUAPANTE _action_assign: Restaurando move %s (%s) → %.3f kg desde PICK origen",
                    move.id, move.product_id.display_name, weight,
                )

                # Forzar estado
                if move.state in ('waiting', 'confirmed', 'partially_available'):
                    move.sudo().with_context(**ctx).write({'state': 'assigned'})

                # Pegar peso
                if move.move_line_ids:
                    move.move_line_ids[0].sudo().with_context(**ctx).write({
                        'quantity': weight,
                    })
                else:
                    MoveLine.with_context(**ctx).create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'picking_id': move.picking_id.id,
                        'quantity': weight,
                    })

                move.sudo().with_context(**ctx).write({'picked': True})

        return res


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Forzar cantidad 0.0 en el momento de creación para Recolectar."""
        for vals in vals_list:
            picking_type_id = vals.get('picking_type_id')
            if not picking_type_id and vals.get('move_id'):
                move = self.env['stock.move'].browse(vals['move_id'])
                picking_type_id = move.picking_type_id.id

            if picking_type_id:
                pt = self.env['stock.picking.type'].browse(picking_type_id)
                if pt.name and 'recolectar' in pt.name.lower():
                    vals['quantity'] = 0.0
                    if 'picked' in self._fields:
                        vals['picked'] = False

        return super().create(vals_list)

    def write(self, vals):
        """Protección de líneas de movimiento contra el drenado nativo."""
        # Protección de Recolectar: no auto-llenar
        if (
            'quantity' in vals
            and vals['quantity'] > 0
            and not self.env.context.get('skip_recolectar_zero_check')
            and not self.env.context.get('manual_entry')
        ):
            recolectar_lines = self.filtered(
                lambda ml: (
                    ml.picking_type_id.name
                    and 'recolectar' in ml.picking_type_id.name.lower()
                    and not ml.move_id.picked
                )
            )
            if recolectar_lines:
                vals['quantity'] = 0.0
                if 'picked' in self._fields:
                    vals['picked'] = False

        # Bloqueo de drenaje: no permitir que se baje a 0
        if (
            'quantity' in vals
            and vals['quantity'] == 0.0
            and not self.env.context.get('guapante_wizard_intent')
        ):
            for record in self:
                if (
                    (record.move_id.picked or record.move_id.is_weight_confirmed)
                    and record.quantity > 0
                ):
                    vals = dict(vals)  # Copia para no mutar el original
                    vals.pop('quantity')
                    break

        return super().write(vals)

    def unlink(self):
        """Filtrar silenciosamente líneas con peso confirmado."""
        if not self.env.context.get('guapante_wizard_intent'):
            records_to_unlink = self.filtered(
                lambda r: not r.move_id.is_weight_confirmed and r.quantity == 0
            )
            return super(StockMoveLine, records_to_unlink).unlink()

        return super().unlink()
