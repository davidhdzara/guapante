# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Zona horaria por defecto para operaciones de Guapante.
_DEFAULT_TZ = 'America/Bogota'


def _date_to_utc_range(env, date_val):
    """Convert a naive date into a UTC datetime range respecting
    the user's (or default) timezone.

    Returns (dt_start_utc, dt_end_utc) where:
      - dt_start_utc = midnight of *date_val* in local tz → UTC
      - dt_end_utc   = midnight of *date_val + 1 day* in local tz → UTC

    Example for America/Bogota (UTC-5):
      date_val = 2026-04-04
      → dt_start = 2026-04-04 05:00:00 UTC
      → dt_end   = 2026-04-05 05:00:00 UTC
    """
    tz_name = env.user.tz or _DEFAULT_TZ
    local_tz = pytz.timezone(tz_name)
    naive_start = fields.Datetime.to_datetime(date_val)
    naive_end = fields.Datetime.to_datetime(date_val + timedelta(days=1))
    dt_start = local_tz.localize(naive_start).astimezone(pytz.utc).replace(tzinfo=None)
    dt_end = local_tz.localize(naive_end).astimezone(pytz.utc).replace(tzinfo=None)
    return dt_start, dt_end


class PreparationDayLog(models.Model):
    _name = 'guapante.picking.log'
    _description = 'Log de Rendimiento de Empaque'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users',
        string='Operario',
        default=lambda self: self.env.user,
    )
    product_product_id = fields.Many2one(
        'product.product',
        string='Variante Registrada',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
    )
    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
    )
    actual_kg = fields.Float(
        string='Peso Registrado (kg)',
        digits=(10, 3),
    )
    time_taken_seconds = fields.Integer(
        string='Tiempo tomado (segs)',
        help='Tiempo entre este empaque y el anterior de la sesión.',
    )


class PreparationDayLine(models.Model):
    """One row per sale.order.line that needs preparation."""
    _name = 'guapante.preparation.day.line'
    _description = 'Línea de Preparación del Día'
    _order = 'is_done, product_product_id, order_name'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.template',
        string='Producto',
        readonly=True,
    )
    product_product_id = fields.Many2one(
        'product.product',
        string='Variante',
        readonly=True,
    )
    product_description = fields.Char(
        string='Descripción del Producto',
        readonly=True,
    )
    packaging_name = fields.Char(
        string='Embalaje del cliente',
        readonly=True,
        help=(
            'Nombre del embalaje B2B que eligió el cliente en la '
            'tienda online (ej. Paquete 200g).'
        ),
    )
    daily_sequence = fields.Integer(
        string='# del día',
        readonly=True,
    )
    order_name = fields.Char(string='Orden', readonly=True)
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Línea de pedido',
        readonly=True,
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento',
        readonly=True,
    )
    main_customer_name = fields.Char(
        string='Cliente Principal',
        readonly=True,
    )
    zone_name = fields.Char(string='Zona', readonly=True)

    uom_mode = fields.Selection(
        selection=[
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='UoM cliente',
        readonly=True,
    )
    customer_qty_display = fields.Char(
        string='Pidió',
        readonly=True,
    )
    customer_uom_label = fields.Char(string='En', readonly=True)
    estimated_kg = fields.Float(
        string='Kg estimado',
        digits=(10, 3),
        readonly=True,
    )

    actual_kg = fields.Float(
        string='Peso real (kg)',
        digits=(10, 3),
        help=(
            'Solo editable para productos pedidos en Unidades. '
            'Deja en 0 para usar el kg estimado.'
        ),
    )
    needs_weighing = fields.Boolean(
        string='Requiere repesaje',
        readonly=True,
        help='True cuando el cliente pidió en Unidades y el precio es variable.',
    )

    is_done = fields.Boolean(
        string='Completado',
        default=False,
        readonly=True,
        help='Indica si esta línea ya fue pesada y validada en esta sesión.',
    )

    @api.model
    def _get_display_qty(self, line) -> tuple:
        """Return (qty_str, uom_label) as the customer sees it.

        Args:
            line: sale.order.line recordset.

        Returns:
            Tuple of (quantity_string, unit_label).
        """
        mode = line.uom_mode or 'unit'
        qty = line.product_uom_qty
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        is_weight = (
            weight_categ
            and line.product_id.uom_id.category_id == weight_categ
        )

        if mode == 'g':
            return str(int(round(qty * 1000))), 'g'
        elif mode == 'kg':
            val = round(qty, 2)
            display = str(int(val)) if val == int(val) else str(val)
            return display, 'kg'
        else:
            if is_weight:
                # Usar el embalaje que eligió el cliente, no el primero
                packaging = line.product_packaging_id
                if not packaging:
                    packaging = line.product_id.packaging_ids.filtered(
                        lambda p: p.sales and p.qty > 0
                    )[:1]
                if packaging:
                    units = int(round(qty / packaging.qty))
                else:
                    units = int(qty)
            else:
                units = int(qty) if qty == int(qty) else qty
            return str(units), 'unidades'

    def action_save_line_weight_from_ui(self) -> bool:
        """Botón manual en caso de no usar Enter."""
        for line in self:
            if not line.is_done:
                line.wizard_id.action_save_line_weight(line.id)
        return False

    def write(self, vals):
        """Override para auto-guardar peso al escribir actual_kg.

        Usa flag de contexto 'skip_auto_save' para evitar recursión
        cuando action_save_line_weight() escribe is_done en la misma línea.
        """
        res = super().write(vals)
        if (
            'actual_kg' in vals
            and not self.env.context.get('skip_auto_save')
        ):
            for line in self:
                if line.actual_kg > 0 and not line.is_done:
                    line.wizard_id.action_save_line_weight(line.id)
        return res

    def action_undo_line(self) -> bool:
        """Devuelve una línea de los Hechos a Pendientes para corregirla."""
        for line in self:
            if line.is_done:
                summary = line.wizard_id.summary_ids.filtered(
                    lambda s: s.product_id == line.product_product_id
                )
                if summary:
                    summary.total_done_kg = round(
                        max(0.0, summary.total_done_kg - line.actual_kg),
                        3,
                    )
                # Limpiar la cantidad ejecutada en el picking.
                # sudo(): el operario puede no tener permisos
                # de escritura directa sobre stock.move.line.
                # skip_inverse_visual_qty: misma protección que en save.
                if line.stock_move_id:
                    line.stock_move_id.sudo().with_context(
                        skip_inverse_visual_qty=True,
                    ).move_line_ids.write({'quantity': 0})
                line.with_context(skip_auto_save=True).write(
                    {'is_done': False, 'actual_kg': 0.0}
                )
        return True


class PreparationDay(models.Model):
    """Session: select a date → see products to prepare → enter weights."""
    _name = 'guapante.preparation.day'
    _description = 'Sesión Permanente de Preparación del Día'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default='Nueva Sesión',
    )
    date = fields.Date(
        string='Fecha de entrega a preparar',
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        'guapante.preparation.day.line',
        'wizard_id',
        string='Líneas',
    )
    summary_ids = fields.One2many(
        'guapante.preparation.day.summary',
        'wizard_id',
        string='Resumen por producto',
    )
    summary_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_summary_count',
    )
    state = fields.Selection(
        [
            ('draft', 'Nueva Sesión'),
            ('loaded', 'En Progreso'),
            ('done', 'Finalizada'),
        ],
        default='draft',
    )
    save_note = fields.Char(string='Resultado', readonly=True)

    global_progress_pct = fields.Float(
        string='Progreso General',
        compute='_compute_global_progress',
        digits=(5, 1),
    )
    total_lines = fields.Integer(
        string='Total líneas',
        compute='_compute_global_progress',
    )
    done_lines = fields.Integer(
        string='Completadas',
        compute='_compute_global_progress',
    )
    pending_lines = fields.Integer(
        string='Pendientes',
        compute='_compute_global_progress',
    )

    # ── Conciliación Cajas: Ventas vs Inventario ──
    so_count = fields.Integer(
        string='Órdenes de Venta',
        compute='_compute_box_reconciliation',
        help='Cantidad de órdenes de venta confirmadas para la fecha.',
    )
    pick_count = fields.Integer(
        string='Pickings (Recolectar)',
        compute='_compute_box_reconciliation',
        help='Cantidad de pickings PICK programados para la fecha.',
    )
    box_diff = fields.Integer(
        string='Diferencia',
        compute='_compute_box_reconciliation',
    )
    box_match = fields.Boolean(
        string='Coinciden',
        compute='_compute_box_reconciliation',
    )
    draft_count = fields.Integer(
        string='Cotizaciones pendientes',
        compute='_compute_box_reconciliation',
        help='Cotizaciones (draft/sent) que podrían ser cajas si se confirman.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Sesión') == 'Nueva Sesión':
                date_str = vals.get(
                    'date',
                    fields.Date.context_today(self),
                )
                vals['name'] = f'Preparación: {date_str}'
        return super().create(vals_list)

    @api.depends('summary_ids')
    def _compute_summary_count(self) -> None:
        for session in self:
            session.summary_count = len(session.summary_ids)

    @api.depends('line_ids.is_done')
    def _compute_global_progress(self) -> None:
        """Calcula el progreso global de toda la sesión."""
        for session in self:
            total = len(session.line_ids)
            done = len(session.line_ids.filtered(lambda l: l.is_done))
            session.total_lines = total
            session.done_lines = done
            session.pending_lines = total - done
            session.global_progress_pct = (
                (done / total * 100.0) if total else 0.0
            )

    @api.depends('date', 'line_ids')
    def _compute_box_reconciliation(self) -> None:
        """Conciliación de cajas: confirmadas vs cotizaciones pendientes.

        En Guapante, toda orden confirmada genera un PICK
        inmediatamente, así que so_count == pick_count siempre.
        El valor real de este indicador es mostrar cotizaciones
        draft/sent que podrían convertirse en cajas adicionales.
        """
        for session in self:
            if not session.date:
                session.so_count = 0
                session.pick_count = 0
                session.box_diff = 0
                session.box_match = True
                session.draft_count = 0
                continue

            dt_start, dt_end = _date_to_utc_range(
                self.env, session.date,
            )

            # Pickings PICK (internal) de órdenes activas para la fecha.
            # Excluir pickings cancelados Y órdenes canceladas (S00217).
            Pickings = self.env['stock.picking'].sudo().search([
                ('scheduled_date', '>=', dt_start),
                ('scheduled_date', '<', dt_end),
                ('picking_type_code', '=', 'internal'),
                ('sale_id', '!=', False),
                ('sale_id.state', 'in', ('sale', 'done')),
                ('state', 'not in', ('cancel',)),
            ])
            pick_orders = Pickings.mapped('sale_id')
            session.pick_count = len(pick_orders)
            session.so_count = len(pick_orders)

            session.box_diff = 0
            session.box_match = True

            # Cotizaciones pendientes (draft/sent) que podrían
            # llegar si el cliente confirma.
            # Buscan por expected_date (fecha estimada de entrega
            # calculada por Odoo) o date_order (fecha de creación).
            DraftOrders = self.env['sale.order'].sudo().search([
                ('state', 'in', ('draft', 'sent')),
                '|',
                '&',
                ('expected_date', '>=', dt_start),
                ('expected_date', '<', dt_end),
                '&',
                ('date_order', '>=', dt_start),
                ('date_order', '<', dt_end),
            ])
            session.draft_count = len(DraftOrders)

    def action_view_summaries(self) -> dict:
        """Abre la vista de resumen por producto (Smart Button)."""
        self.ensure_one()
        return {
            'name': 'Productos a preparar',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.summary',
            'view_mode': 'list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {'default_wizard_id': self.id},
            'target': 'current',
        }

    def action_load(self) -> bool:
        """Load confirmed SO lines whose picking is scheduled on self.date."""
        if self.state == 'done':
            self.state = 'loaded'

        # Limpieza: desvincular líneas cuya orden fue cancelada o cuyo
        # movimiento ya fue procesado, para mantener la lista al día.
        LinesToUnlink = self.line_ids.filtered(
            lambda l: not l.is_done and (
                l.sale_order_id.state in ('cancel', 'draft')
                or (
                    l.stock_move_id
                    and l.stock_move_id.state in ('done', 'cancel')
                )
            )
        )
        if LinesToUnlink:
            LinesToUnlink.unlink()

        # Recrear summaries desde cero basándose en las líneas actuales.
        self.summary_ids.unlink()

        # ── Buscar órdenes via stock.picking directo ──
        # IMPORTANTE: No usar dominio sobre sale.order.picking_ids
        # porque Odoo evalúa cada condición en picking_ids como un
        # EXISTS independiente (puede matchear pickings DIFERENTES).
        #
        # Solo buscamos pickings de tipo PICK/Recolectar (internal)
        # porque el Preparation Day es para la etapa de alistamiento,
        # NO para la entrega (OUT). Si el warehouse es 1-step (solo
        # OUT), se usa outgoing como fallback.
        dt_start, dt_end = _date_to_utc_range(self.env, self.date)
        base_domain = [
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('state', 'not in', ('done', 'cancel')),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
        ]
        # Solo pickings internos (Recolectar / PICK step).
        # El Preparation Day prepara lo del PICK; el OUT hereda
        # la información que se registró aquí.
        Pickings = self.env['stock.picking'].sudo().search(
            base_domain + [('picking_type_code', '=', 'internal')]
        )
        Orders = Pickings.mapped('sale_id')
        if not Orders and not self.line_ids:
            raise UserError(
                'No hay pedidos pendientes para la fecha seleccionada.'
            )

        # Secuencia diaria: reinicia desde 1 cada día.
        self.env['sale.order']._assign_daily_sequences(self.date)

        existing_sale_line_ids = self.line_ids.mapped('sale_line_id').ids
        line_vals = []
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )

        for order in Orders:
            # Desglose Cliente Principal y Zona.
            # parent_id en vez de commercial_partner_id porque este
            # último está corrupto para contactos tipo "Cocina"/"Bar".
            partner = order.partner_id
            main_cust_name = (
                partner.parent_id.name
                if partner.parent_id
                else partner.name
            )
            shipping_name = order.partner_shipping_id.name or ''

            ProductLines = order.order_line.filtered(
                lambda l: (
                    l.product_id
                    and not l.display_type
                    # Excluir servicios (delivery, shipping charges)
                    and l.product_id.type != 'service'
                )
            )
            for line in ProductLines:
                if line.id in existing_sale_line_ids:
                    # Actualizar nombre retroactivamente si cambió
                    ExistingPrepLine = self.line_ids.filtered(
                        lambda x: x.sale_line_id.id == line.id
                    )
                    if ExistingPrepLine and (
                        ExistingPrepLine.main_customer_name != main_cust_name
                        or ExistingPrepLine.zone_name != shipping_name
                    ):
                        ExistingPrepLine.write({
                            'main_customer_name': main_cust_name,
                            'zone_name': shipping_name,
                        })
                    continue

                # Buscar stock.move del PICK (internal/Recolectar).
                # En warehouse 2-step cada SO line genera 2 moves:
                # uno para PICK y otro para OUT. Sin este filtro,
                # limit=1 podía agarrar el OUT y el peso nunca
                # llegaba al Recolectar.
                Move = self.env['stock.move'].search([
                    ('sale_line_id', '=', line.id),
                    ('picking_type_id.code', '=', 'internal'),
                    ('state', 'not in', ('done', 'cancel')),
                ], limit=1)
                if not Move:
                    # No hay move pendiente → línea ya procesada
                    # o cancelada. No cargar en la preparación.
                    continue

                mode = line.uom_mode or 'unit'
                is_weight = (
                    weight_categ
                    and line.product_id.uom_id.category_id == weight_categ
                )
                needs_weighing = (mode == 'unit' and is_weight)

                qty_str, uom_label = self.env[
                    'guapante.preparation.day.line'
                ]._get_display_qty(line)

                # Packaging: solo mostrar si el cliente pidió por unidad
                packaging_name = False
                if (
                    line.product_packaging_id
                    and (line.uom_mode or 'unit') == 'unit'
                ):
                    packaging_name = line.product_packaging_id.name

                line_vals.append({
                    'wizard_id': self.id,
                    'product_id': line.product_id.product_tmpl_id.id,
                    'product_product_id': line.product_id.id,
                    'product_description': line.name,
                    'packaging_name': packaging_name,
                    'daily_sequence': order.daily_sequence,
                    'order_name': order.name,
                    'sale_order_id': order.id,
                    'sale_line_id': line.id,
                    'stock_move_id': Move.id if Move else False,
                    'main_customer_name': main_cust_name,
                    'zone_name': shipping_name,
                    'uom_mode': mode,
                    'customer_qty_display': qty_str,
                    'customer_uom_label': uom_label,
                    'estimated_kg': round(line.product_uom_qty, 3),
                    'actual_kg': 0.0,
                    'needs_weighing': needs_weighing,
                    'is_done': False,
                })

        added_count = len(line_vals)
        if added_count > 0:
            self.env['guapante.preparation.day.line'].create(line_vals)

        self._rebuild_summary()
        self.state = 'loaded'

        if added_count == 0:
            self.save_note = (
                '✅ Listado actualizado. No se detectaron productos nuevos.'
            )
        else:
            self.save_note = (
                f'✅ {added_count} líneas nuevas cargadas a la preparación.'
            )

        return False

    def _rebuild_summary(self) -> None:
        """Build per-product summary aggregating all lines.

        Uses an upsert pattern: updates existing summaries where possible
        and creates new ones for products not yet tracked.
        """
        existing_summaries = {
            s.product_id.id: s for s in self.summary_ids
        }
        product_totals = {}

        for line in self.line_ids:
            pid = line.product_product_id.id
            if pid not in product_totals:
                product_totals[pid] = {
                    'total_estimated_kg': 0.0,
                    'total_done_kg': 0.0,
                    'order_count': 0,
                    'available_qty': line.product_product_id.qty_available,
                }
            product_totals[pid]['total_estimated_kg'] += line.estimated_kg
            product_totals[pid]['order_count'] += 1
            if line.is_done:
                product_totals[pid]['total_done_kg'] += line.actual_kg

        # Actualizar existentes y crear nuevos
        seen_pids = set()
        create_vals = []
        for pid, totals in product_totals.items():
            totals['total_estimated_kg'] = round(
                totals['total_estimated_kg'], 3,
            )
            totals['stock_ok'] = (
                totals['available_qty'] >= totals['total_estimated_kg']
            )
            seen_pids.add(pid)

            if pid in existing_summaries:
                existing_summaries[pid].write({
                    'total_estimated_kg': totals['total_estimated_kg'],
                    'total_done_kg': round(totals['total_done_kg'], 3),
                    'order_count': totals['order_count'],
                    'available_qty': totals['available_qty'],
                    'stock_ok': totals['stock_ok'],
                })
            else:
                create_vals.append({
                    'wizard_id': self.id,
                    'product_id': pid,
                    'total_estimated_kg': totals['total_estimated_kg'],
                    'total_done_kg': round(totals['total_done_kg'], 3),
                    'order_count': totals['order_count'],
                    'available_qty': totals['available_qty'],
                    'stock_ok': totals['stock_ok'],
                })

        # Eliminar summaries de productos que ya no están en las líneas
        StaleSummaries = self.summary_ids.filtered(
            lambda s: s.product_id.id not in seen_pids
        )
        if StaleSummaries:
            StaleSummaries.unlink()

        if create_vals:
            self.env['guapante.preparation.day.summary'].create(create_vals)

    def action_save_line_weight(self, line_id: int) -> bool:
        """Called when user sets weight (via JS Enter or manual button).

        Registers the real weight in stock.move.line and marks the
        preparation line as done.
        """
        Line = self.env['guapante.preparation.day.line'].browse(line_id)
        if not Line or Line.is_done or Line.actual_kg <= 0:
            return False

        # Registrar peso real en stock.move.line (cantidad ejecutada).
        # sudo(): el operario de bodega puede no tener permisos de
        # escritura directa sobre stock.move.line del almacén.
        # skip_inverse_visual_qty: evita que el cambio en quantity
        # propague de vuelta a sale.order.line.product_uom_qty
        # a través del campo visual_qty compute/inverse.
        if Line.stock_move_id:
            Move = Line.stock_move_id.sudo().with_context(
                skip_inverse_visual_qty=True,
                skip_recolectar_zero_check=True,
                manual_entry=True, # Contexto para Odoo 18
                guapante_wizard_intent=True, # Permitir correcciones humanas
            )
            
            # Odoo 18 Nativo: Al marcar 'picked' en el movimiento, habilitamos
            # la edición directa de cantidad. Odoo se encargará de crear
            # o actualizar la stock.move.line de forma estable.
            Move.write({
                'picked': True,
                'quantity': Line.actual_kg,
                'is_weight_confirmed': True,
            })
            
            # Sincronización de estado para asegurar persistencia
            if Move.state == 'confirmed':
                Move.write({'state': 'assigned'})
            
            # Asegurar que todas las líneas tengan el flag 'picked' (Odoo 18)
            if Move.move_line_ids:
                Move.move_line_ids.write({'picked': True})

            # PROPAGACIÓN EN CADENA: Inyectar peso en los movimientos siguientes (Empaque, Salida)
            # para que la cantidad llegue hasta la factura final.
            self._propagate_weight_to_chain(Move, Line.actual_kg)

        # Marcar como hecho usando skip_auto_save para evitar que
        # el override de write() vuelva a llamar este método.
        Line.with_context(skip_auto_save=True).write({'is_done': True})

        # Actualizar total_done_kg en el resumen del producto
        Summary = self.summary_ids.filtered(
            lambda s: s.product_id == Line.product_product_id
        )
        if Summary:
            Summary.total_done_kg = round(
                Summary.total_done_kg + Line.actual_kg, 3,
            )

        # Log de rendimiento por operario
        LastLog = self.env['guapante.picking.log'].search([
            ('user_id', '=', self.env.user.id),
            ('wizard_id', '=', self.id),
        ], order='create_date desc', limit=1)

        time_taken = 0
        if LastLog:
            time_diff = fields.Datetime.now() - LastLog.create_date
            time_taken = int(time_diff.total_seconds())

        self.env['guapante.picking.log'].create({
            'product_product_id': Line.product_product_id.id,
            'sale_order_id': Line.sale_order_id.id,
            'wizard_id': self.id,
            'actual_kg': Line.actual_kg,
            'time_taken_seconds': time_taken,
        })

        self.save_note = (
            f'✅ Peso de {Line.order_name} guardado: '
            f'{Line.actual_kg} kg.'
        )

        # Forzar invalidación para actualizar importes de la SO.
        # sudo(): lectura cruzada de totales puede requerir acceso
        # a líneas de facturación protegidas.
        Line.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        # Auto-finish si ya no quedan líneas pendientes
        pending_total = self.env[
            'guapante.preparation.day.line'
        ].search_count([
            ('wizard_id', '=', self.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0:
            self.action_mark_done()
            self.save_note = (
                '🎉 ¡Todos los productos han sido empaquetados '
                'exitosamente! Sesión Finalizada.'
            )

        return True

    def _propagate_weight_to_chain(self, move, weight):
        """Recursivamente inyecta el peso en los movimientos destino."""
        for dest in move.move_dest_ids:
            if dest.state not in ('done', 'cancel'):
                dest.sudo().with_context(
                    skip_recolectar_zero_check=True,
                    manual_entry=True,
                    guapante_wizard_intent=True # Autorizar el peso en toda la cadena
                ).write({
                    'picked': True,
                    'quantity': weight,
                    'is_weight_confirmed': True, # PROTEGER EL PESO EN TODA LA CADENA
                })
                # SEGUIR LA CADENA (Recursivo)
                # Odoo 18: Forzar estado 'assigned' para que acepte el peso manual
                # y no lo borre por estar "esperando otra operación".
                if dest.state in ('waiting', 'confirmed'):
                    dest.sudo().write({'state': 'assigned'})
                
                self._propagate_weight_to_chain(dest, weight)

    def action_mark_done(self) -> bool:
        """Mark session as done."""
        self.state = 'done'
        return False

    def action_reopen(self) -> bool:
        """Reopen a finished session to allow adding new orders."""
        self.state = 'loaded'
        return False

    def action_export_excel(self) -> dict:
        """Retorna una acción de URL para descargar el consolidado en Excel."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/guapante/preparation_day/{self.id}/export_excel',
            'target': 'new',
        }


class PreparationDaySummary(models.Model):
    """Aggregated view: one row per product variant showing totals."""
    _name = 'guapante.preparation.day.summary'
    _description = 'Resumen de Preparación por Producto'
    _order = 'packing_status asc, product_id'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    total_estimated_kg = fields.Float(
        string='Total kg estimado',
        digits=(10, 3),
        readonly=True,
    )
    total_done_kg = fields.Float(
        string='Total kg hecho',
        digits=(10, 3),
    )
    order_count = fields.Integer(string='Órdenes', readonly=True)
    available_qty = fields.Float(
        string='Disponible (kg)',
        digits=(10, 3),
        readonly=True,
    )
    stock_ok = fields.Boolean(string='Stock OK', readonly=True)
    packing_status = fields.Selection(
        selection=[
            ('1_not_started', 'Sin iniciar'),
            ('2_in_progress', 'En progreso'),
            ('3_done', 'Terminado'),
        ],
        string='Estado de empaque',
        compute='_compute_progress_pct',
        store=True,
    )
    progress_pct = fields.Float(
        string='Progreso',
        compute='_compute_progress_pct',
        digits=(5, 1),
        store=True,
    )

    @api.depends(
        'wizard_id.line_ids.is_done',
        'wizard_id.line_ids.product_product_id',
    )
    def _compute_progress_pct(self) -> None:
        for rec in self:
            AllLines = rec.wizard_id.line_ids.filtered(
                lambda l: l.product_product_id == rec.product_id
            )
            DoneLines = AllLines.filtered(lambda l: l.is_done)
            if AllLines:
                rec.progress_pct = (len(DoneLines) / len(AllLines) * 100.0)
                if len(DoneLines) == 0:
                    rec.packing_status = '1_not_started'
                elif len(DoneLines) < len(AllLines):
                    rec.packing_status = '2_in_progress'
                else:
                    rec.packing_status = '3_done'
            else:
                rec.progress_pct = 0.0
                rec.packing_status = '1_not_started'

    def action_select_product(self) -> dict:
        """Abre un wizard transitorio aislado por usuario para empacar."""
        Wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].create({
            'session_id': self.wizard_id.id,
            'product_id': self.product_id.id,
            'available_qty': self.available_qty,
            'total_estimated_kg': self.total_estimated_kg,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.wizard',
            'res_id': Wizard.id,
            'view_mode': 'form',
            'target': 'current',
        }


class PreparationDayProductWizard(models.TransientModel):
    _name = 'guapante.preparation.day.product.wizard'
    _description = 'Wizard de Empaque por Producto (Aislado por Usuario)'

    session_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
    )

    available_qty = fields.Float(
        string='Disponible en stock',
        digits=(10, 3),
        readonly=True,
    )
    total_estimated_kg = fields.Float(
        string='Total kg pedido',
        digits=(10, 3),
        readonly=True,
    )

    progress_percentage = fields.Float(
        string='Progreso de Empaque',
        compute='_compute_lists',
    )

    # Pendientes y Hechos (separados para las vistas XML)
    detail_line_pending_ids = fields.Many2many(
        'guapante.preparation.day.line',
        compute='_compute_lists',
        readonly=False,
    )
    detail_line_done_ids = fields.Many2many(
        'guapante.preparation.day.line',
        compute='_compute_lists',
        readonly=False,
    )

    @api.depends(
        'session_id.line_ids.is_done',
        'session_id.line_ids.actual_kg',
    )
    def _compute_lists(self) -> None:
        for wiz in self:
            AllLines = wiz.session_id.line_ids.filtered(
                lambda l: l.product_product_id == wiz.product_id
            )
            DoneLines = AllLines.filtered(lambda l: l.is_done)
            PendingLines = AllLines - DoneLines
            wiz.detail_line_done_ids = DoneLines.ids
            wiz.detail_line_pending_ids = PendingLines.ids
            if AllLines:
                wiz.progress_percentage = (
                    (len(DoneLines) / len(AllLines)) * 100.0
                )
            else:
                wiz.progress_percentage = 0.0

    def action_back_to_session(self) -> dict:
        """Regresa a la vista principal de la sesión."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day',
            'res_id': self.session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
