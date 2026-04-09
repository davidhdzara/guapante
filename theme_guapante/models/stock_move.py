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

                # Revisa si es un producto por peso
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
    # ESTRATEGIA "SAVE & RESTORE": Dejar que Odoo haga lo que
    # quiera y luego restaurar los pesos confirmados.
    # ──────────────────────────────────────────────────────────────

    def _action_done(self, cancel_backorder=False):
        """Override principal: Salvar pesos de movimientos destino (OUT)
        ANTES de que Odoo los limpie, y restaurarlos DESPUÉS.
        
        Flujo:
        1. PICK se valida → Odoo llama _action_done en moves del PICK
        2. Dentro de _action_done, Odoo llama _action_assign en moves del OUT
        3. _action_assign ve que no hay stock y vacía las cantidades del OUT
        4. Nosotros restauramos las cantidades después de que Odoo terminó
        """
        # ── FASE 1: GUARDAR pesos de movimientos destino ──
        weights_backup = {}
        for move in self:
            for dest in move.move_dest_ids:
                if (
                    dest.is_weight_confirmed
                    and dest.state not in ('done', 'cancel')
                ):
                    # Leer el peso actual (puede venir del move o de sus lines)
                    weight = dest.quantity
                    if weight <= 0 and dest.move_line_ids:
                        weight = sum(dest.move_line_ids.mapped('quantity'))
                    
                    if weight > 0:
                        weights_backup[dest.id] = {
                            'weight': weight,
                            'product_id': dest.product_id.id,
                            'product_uom_id': dest.product_uom.id,
                            'location_id': dest.location_id.id,
                            'location_dest_id': dest.location_dest_id.id,
                            'picking_id': dest.picking_id.id,
                        }
                        _logger.info(
                            "GUAPANTE SAVE: move %s (%s) → destino %s = %.3f kg",
                            move.id, move.product_id.display_name,
                            dest.id, weight,
                        )

        # ── FASE 2: EJECUTAR Odoo nativo ──
        # Aquí Odoo valida el PICK, marca como 'done', y dispara
        # _action_assign en los moves del OUT (que limpia las cantidades).
        res = super()._action_done(cancel_backorder=cancel_backorder)

        # ── FASE 3: RESTAURAR pesos ──
        if weights_backup:
            ctx = {
                'guapante_wizard_intent': True,
                'skip_recolectar_zero_check': True,
                'manual_entry': True,
            }
            Move = self.env['stock.move'].sudo()
            MoveLine = self.env['stock.move.line'].sudo()

            for move_id, data in weights_backup.items():
                dest = Move.browse(move_id)
                if not dest.exists() or dest.state == 'done':
                    continue

                weight = data['weight']

                _logger.info(
                    "GUAPANTE RESTORE: move %s (%s) → %.3f kg (estado actual: %s, qty actual: %.3f)",
                    dest.id, dest.product_id.display_name,
                    weight, dest.state, dest.quantity,
                )

                # 1. Forzar estado a 'assigned' (disponible)
                if dest.state in ('waiting', 'confirmed', 'partially_available'):
                    dest.with_context(**ctx).write({'state': 'assigned'})

                # 2. Restaurar peso en las líneas de movimiento
                if dest.move_line_ids:
                    # Usar la primera línea para el peso
                    dest.move_line_ids[0].with_context(**ctx).write({
                        'quantity': weight,
                    })
                    # Limpiar líneas extra vacías que Odoo haya creado
                    extra_empty = dest.move_line_ids[1:].filtered(
                        lambda l: l.quantity == 0
                    )
                    if extra_empty:
                        extra_empty.with_context(**ctx).unlink()
                else:
                    # Odoo borró todas las líneas → crear una nueva
                    MoveLine.with_context(**ctx).create({
                        'move_id': dest.id,
                        'product_id': data['product_id'],
                        'product_uom_id': data['product_uom_id'],
                        'location_id': data['location_id'],
                        'location_dest_id': data['location_dest_id'],
                        'picking_id': data['picking_id'],
                        'quantity': weight,
                    })

                # 3. Marcar el movimiento como picked
                dest.with_context(**ctx).write({'picked': True})

                _logger.info(
                    "GUAPANTE RESTORE OK: move %s → qty final: %.3f, state: %s",
                    dest.id, dest.quantity, dest.state,
                )

        return res

    def _action_assign(self):
        """Interceptor de reserva: Salvar y restaurar pesos confirmados.
        
        Cuando Odoo ejecuta _action_assign (sea desde _action_done del PICK
        o desde cualquier otro trigger), salvamos los pesos antes y los
        restauramos después.
        """
        # Salvar pesos confirmados de los movimientos en self
        confirmed_weights = {}
        for move in self:
            if move.is_weight_confirmed and move.quantity > 0:
                confirmed_weights[move.id] = {
                    'weight': move.quantity,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'picking_id': move.picking_id.id,
                }

        # Ejecutar reserva nativa
        res = super(StockMove, self)._action_assign()

        # Restaurar pesos que Odoo pudo haber limpiado
        if confirmed_weights:
            ctx = {
                'guapante_wizard_intent': True,
                'skip_recolectar_zero_check': True,
                'manual_entry': True,
            }
            Move = self.env['stock.move'].sudo()
            MoveLine = self.env['stock.move.line'].sudo()

            for move_id, data in confirmed_weights.items():
                move = Move.browse(move_id)
                if not move.exists() or move.state == 'done':
                    continue

                weight = data['weight']

                # Forzar estado a assigned
                if move.state in ('waiting', 'confirmed', 'partially_available'):
                    move.with_context(**ctx).write({'state': 'assigned'})

                # Restaurar peso en líneas
                if move.move_line_ids:
                    move.move_line_ids[0].with_context(**ctx).write({
                        'quantity': weight,
                    })
                else:
                    MoveLine.with_context(**ctx).create({
                        'move_id': move.id,
                        'product_id': data['product_id'],
                        'product_uom_id': data['product_uom_id'],
                        'location_id': data['location_id'],
                        'location_dest_id': data['location_dest_id'],
                        'picking_id': data['picking_id'],
                        'quantity': weight,
                    })

                move.with_context(**ctx).write({'picked': True})

        # Recolectar: asegurar que líneas nuevas empiecen en 0
        for move in self:
            if (
                not move.is_weight_confirmed
                and move.picking_type_id.name
                and 'recolectar' in move.picking_type_id.name.lower()
                and not self.env.context.get('skip_recolectar_zero_check')
            ):
                move.sudo().move_line_ids.write({'quantity': 0.0})
                move.sudo().write({'picked': False})

        return res


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Forzar cantidad 0.0 en el momento de creación para Recolectar.

        Odoo 18 puede pre-llenar la cantidad basado en la reserva
        o el tipo de picking. Para Guapante, el operario debe
        pesar obligatoriamente, por lo que empezamos en 0.
        """
        for vals in vals_list:
            picking_type_id = vals.get('picking_type_id')
            if not picking_type_id and vals.get('move_id'):
                move = self.env['stock.move'].browse(vals['move_id'])
                picking_type_id = move.picking_type_id.id

            if picking_type_id:
                pt = self.env['stock.picking.type'].browse(picking_type_id)
                if pt.name and 'recolectar' in pt.name.lower():
                    # Forzar cantidad a 0 y asegurar que NO esté marcado
                    # como 'picked' (Odoo 18 logica nativa).
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
