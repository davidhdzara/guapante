# -*- coding: utf-8 -*-
from odoo import api, fields, models


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


    def write(self, vals):
        """Blindaje del Movimiento Principal: Impedir que Odoo 18
        vacíe las cantidades ya pesadas manualmente.
        """
        # PROTECCIÓN DE ATRIBUTOS CLAVE
        # Si el sistema intenta resetear a 0.0 o quitar el flag 'picked'
        # sin que sea una intención manual del asistente de Guapante.
        if not self.env.context.get('guapante_wizard_intent'):
            if 'quantity' in vals and vals['quantity'] == 0.0:
                # Filtrar movimientos que ya tienen peso confirmado
                # para que Odoo no pueda bajarlos a cero.
                for move in self:
                    if move.is_weight_confirmed and move.quantity > 0:
                        vals.pop('quantity')
                        break
            
            if 'picked' in vals and vals['picked'] is False:
                for move in self:
                    if move.is_weight_confirmed and move.picked:
                        vals.pop('picked')
                        break

        return super(StockMove, self).write(vals)

    def _action_assign(self):
        """FUERZA BRUTA: Engañar al motor de Odoo 18.
        Si hay un peso confirmado, le decimos al sistema que el stock 
        está disponible para que no vacíe la cantidad en el OUT.
        """
        # Primero, para los movimientos confirmados, aseguramos que tengan
        # las cantidades preparadas antes de que Odoo intente reservar.
        for move in self:
            if move.is_weight_confirmed and move.quantity > 0:
                # Forzamos picked=True para que Odoo 18 lo trate como manual
                move.sudo().with_context(guapante_wizard_intent=True).write({
                    'picked': True,
                    'state': 'assigned'
                })

        # Ejecutar reserva nativa
        res = super(StockMove, self)._action_assign()
        
        # Post-Reserva: Si Odoo lo vació a pesar de todo, lo restauramos a la fuerza
        for move in self:
            if move.is_weight_confirmed and move.quantity > 0:
                if move.state in ('waiting', 'confirmed') or not move.picked:
                    move.sudo().with_context(guapante_wizard_intent=True).write({
                        'state': 'assigned',
                        'picked': True,
                        'quantity': move.quantity # Mantener el peso
                    })
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
        """Protección adicional para que el auto-llenado de Odoo 18
        no sobrescriba el 0 inicial durante la asignación.
        """
        # Si la escritura viene del sistema y está intentando poner
        # quantity > 0 basándose en la demanda/reserva.
        if (
            'quantity' in vals
            and vals['quantity'] > 0
            and not self.env.context.get('skip_recolectar_zero_check')
            and not self.env.context.get('manual_entry')
        ):
            # Optimización: Solo filtrar si alguno pertenece a Recolectar
            recolectar_lines = self.filtered(
                lambda ml: (
                    ml.picking_type_id.name
                    and 'recolectar' in ml.picking_type_id.name.lower()
                    and not ml.move_id.picked  # Odoo 18: Si ya está picked, no tocamos
                )
            )
            if recolectar_lines:
                # Si matchea Recolectar y no ha sido 'recogido' manualmente,
                # forzamos a quedar en 0.
                vals['quantity'] = 0.0
                if 'picked' in self._fields:
                    vals['picked'] = False

        # BLOQUEO DE DRENAJE: Prevenir que Odoo 18 resetee a 0.0
        # durante la validación si ya tenemos un peso manual.
        if (
            'quantity' in vals
            and vals['quantity'] == 0.0
            and not self.env.context.get('guapante_wizard_intent')
        ):
            # Si el movimiento ya está 'picked' (pesado físicamente),
            # no permitimos que Odoo lo baje a 0.0 por falta de stock en validación.
            for record in self:
                if (record.move_id.picked or record.move_id.is_weight_confirmed) and record.quantity > 0:
                    # Omitimos el cambio a 0.0 para este registro si es automático del sistema
                    vals.pop('quantity')
                    break

        return super().write(vals)

    def unlink(self):
        """Filtrar silenciosamente líneas con peso para que Odoo no las borre."""
        if not self.env.context.get('guapante_wizard_intent'):
            # El escudo de 'Berenjena': solo permitimos el borrado de líneas 
            # que NO tengan peso o que no hayan sido confirmadas por Guapante.
            # Esto evita que Odoo las limpie por falta de stock.
            records_to_unlink = self.filtered(
                lambda r: not r.move_id.is_weight_confirmed and r.quantity == 0
            )
            return super(StockMoveLine, records_to_unlink).unlink()
        
        return super().unlink()
