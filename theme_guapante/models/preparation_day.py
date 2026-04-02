# Este archivo reemplazará a preparation_day.py
# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PreparationDayLog(models.Model):
    _name = 'guapante.picking.log'
    _description = 'Log de Rendimiento de Empaque'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='Operario', default=lambda self: self.env.user)
    product_product_id = fields.Many2one('product.product', string='Variante Registrada')
    sale_order_id = fields.Many2one('sale.order', string='Pedido')
    wizard_id = fields.Many2one('guapante.preparation.day', string='Sesión')
    actual_kg = fields.Float(string='Peso Registrado (kg)', digits=(10, 3))
    time_taken_seconds = fields.Integer(string='Tiempo tomado (segs)', help='Tiempo entre este empaque y el anterior de la sesión.')


class PreparationDayLine(models.Model):
    """One row per sale.order.line that needs preparation on the selected date."""
    _name = 'guapante.preparation.day.line'
    _description = 'Línea de Preparación del Día'
    _order = 'is_done, product_product_id, order_name'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.template', string='Producto', readonly=True)
    product_product_id = fields.Many2one('product.product', string='Variante', readonly=True)
    product_description = fields.Char(string='Descripción del Producto', readonly=True)
    packaging_name = fields.Char(
        string='Embalaje del cliente',
        readonly=True,
        help='Nombre del embalaje B2B que eligió el cliente en la tienda online (ej. Paquete 200g).'
    )
    daily_sequence = fields.Integer(string='# del día', readonly=True)
    order_name = fields.Char(string='Orden', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Pedido', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', string='Línea de pedido', readonly=True)
    stock_move_id = fields.Many2one('stock.move', string='Movimiento', readonly=True)
    main_customer_name = fields.Char(string='Cliente Principal', readonly=True)
    zone_name = fields.Char(string='Zona', readonly=True)

    uom_mode = fields.Selection(
        selection=[('unit', 'Unidades'), ('kg', 'Kilogramos'), ('g', 'Gramos')],
        string='UoM cliente',
        readonly=True,
    )
    customer_qty_display = fields.Char(string='Pidió', readonly=True)
    customer_uom_label = fields.Char(string='En', readonly=True)
    estimated_kg = fields.Float(string='Kg estimado', digits=(10, 3), readonly=True)

    actual_kg = fields.Float(
        string='Peso real (kg)',
        digits=(10, 3),
        help='Solo editable para productos pedidos en Unidades. '
             'Deja en 0 para usar el kg estimado.',
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
        help='Indica si esta línea ya fue pesada y validada en esta sesión.'
    )

    def _get_display_qty(self, line):
        """Return (qty_str, uom_label) as the customer sees it."""
        mode = line.uom_mode or 'unit'
        qty = line.product_uom_qty
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        is_weight = (
            weight_categ
            and line.product_id.uom_id.category_id == weight_categ
        )

        if mode == 'g':
            return str(int(round(qty * 1000))), 'g'
        elif mode == 'kg':
            val = round(qty, 2)
            return (str(int(val)) if val == int(val) else str(val)), 'kg'
        else:
            if is_weight:
                # FIX: Use the packaging the customer chose, not always the first one
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

    def action_save_line_weight_from_ui(self):
        """Boton manual en caso de no usar Enter."""
        for line in self:
            if not line.is_done:
                line.wizard_id.action_save_line_weight(line.id)
        return False

    def write(self, vals):
        res = super().write(vals)
        if 'actual_kg' in vals:
            for line in self:
                if line.actual_kg > 0 and not line.is_done:
                    line.wizard_id.action_save_line_weight(line.id)
        return res

    def action_undo_line(self):
        """Devuelve una línea de los Hechos a los Pendientes para ser corregida."""
        for line in self:
            if line.is_done:
                summary = line.wizard_id.summary_ids.filtered(
                    lambda s: s.product_id == line.product_product_id
                )
                if summary:
                    summary.total_done_kg = round(
                        max(0.0, summary.total_done_kg - line.actual_kg), 3
                    )
                # Limpiar la cantidad ejecutada en el picking
                if line.stock_move_id:
                    line.stock_move_id.sudo().move_line_ids.write({'quantity': 0})
                line.write({'is_done': False, 'actual_kg': 0.0})
        return True


class PreparationDay(models.Model):
    """Session Model: select a date → see all products to prepare → enter real weights."""
    _name = 'guapante.preparation.day'
    _description = 'Sesión Permanente de Preparación del Día'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default='Nueva Sesión')
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
        [('draft', 'Nueva Sesión'), ('loaded', 'En Progreso'), ('done', 'Finalizada')],
        default='draft',
    )
    save_note = fields.Char(string='Resultado', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Sesión') == 'Nueva Sesión':
                date_str = vals.get('date', fields.Date.context_today(self))
                vals['name'] = f'Preparación: {date_str}'
        return super().create(vals_list)

    @api.depends('summary_ids')
    def _compute_summary_count(self):
        for session in self:
            session.summary_count = len(session.summary_ids)

    def action_view_summaries(self):
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

    def action_load(self):
        """Load all confirmed sale order lines whose picking is scheduled on self.date."""
        if self.state == 'done':
            raise UserError('La sesión ya fue marcada como finalizada.')
            
        # Clean up existing pending lines if their associated order or move got cancelled
        lines_to_unlink = self.line_ids.filtered(
            lambda l: not l.is_done and (
                l.sale_order_id.state in ('cancel', 'draft') or 
                (l.stock_move_id and l.stock_move_id.state in ('done', 'cancel'))
            )
        )
        if lines_to_unlink:
            lines_to_unlink.unlink()

        # We will NOT unlink self.line_ids entirely to preserve is_done = True and in-progress tasks.
        # But we MUST recreate summaries from scratch based on the updated lines.
        self.summary_ids.unlink()

        domain = [
            ('state', 'in', ('sale', 'done')),
            ('picking_ids.scheduled_date', '>=', fields.Datetime.to_datetime(self.date)),
            ('picking_ids.scheduled_date', '<', fields.Datetime.to_datetime(
                fields.Date.add(self.date, days=1)
            )),
            ('picking_ids.state', 'not in', ('done', 'cancel')),
        ]
        orders = self.env['sale.order'].search(domain)
        if not orders and not self.line_ids:
            raise UserError('No hay pedidos pendientes para la fecha seleccionada.')

        # Assign daily_sequence scoped to this delivery date (restarts from 1 each day).
        self.env['sale.order']._assign_daily_sequences(self.date)

        existing_sale_line_ids = self.line_ids.mapped('sale_line_id').ids
        line_vals = []
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)

        for order in orders:
            # Desglose de Cliente Principal y Zona (Dirección de Entrega)
            # Usamos parent_id en vez de commercial_partner_id porque este último
            # está corrupto/desactualizado para muchos contactos tipo "Cocina"/"Bar".
            partner = order.partner_id
            main_cust_name = partner.parent_id.name if partner.parent_id else partner.name
            shipping_name = order.partner_shipping_id.name or ''
            
            # We assume order has daily_sequence field from staging_dev
            for line in order.order_line.filtered(lambda l: l.product_id and not l.display_type):
                if line.id in existing_sale_line_ids:
                    # Actualizar retroactivamente el nombre en las sesiones ya cargadas
                    existing_prep_line = self.line_ids.filtered(lambda x: x.sale_line_id.id == line.id)
                    if existing_prep_line and (existing_prep_line.main_customer_name != main_cust_name or existing_prep_line.zone_name != shipping_name):
                        existing_prep_line.write({
                            'main_customer_name': main_cust_name,
                            'zone_name': shipping_name,
                        })
                    continue  # We already loaded this line in the session.
                    
                # Find the related stock.move
                move = self.env['stock.move'].search([
                    ('sale_line_id', '=', line.id),
                    ('state', 'not in', ('done', 'cancel')),
                ], limit=1)

                mode = line.uom_mode or 'unit'
                is_weight = (
                    weight_categ
                    and line.product_id.uom_id.category_id == weight_categ
                )
                needs_weighing = (mode == 'unit' and is_weight)

                qty_str, uom_label = self.env['guapante.preparation.day.line']._get_display_qty(line)

                line_vals.append({
                    'wizard_id': self.id,
                    'product_id': line.product_id.product_tmpl_id.id,
                    'product_product_id': line.product_id.id,
                    'product_description': line.name,
                    # Solo mostrar el embalaje B2B si el cliente pidió por "unidad de embalaje".
                    # Si pidió por kg o g, no mostrar aunque Odoo asigne un packaging internamente.
                    'packaging_name': (
                        line.product_packaging_id.name
                        if line.product_packaging_id and (line.uom_mode or 'unit') == 'unit'
                        else False
                    ),
                    'daily_sequence': order.daily_sequence,
                    'order_name': order.name,
                    'sale_order_id': order.id,
                    'sale_line_id': line.id,
                    'stock_move_id': move.id if move else False,
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

        self._compute_summary()
        self.state = 'loaded'
        
        if added_count == 0:
            self.save_note = '✅ Listado actualizado. No se detectaron productos nuevos.'
        else:
            self.save_note = f'✅ {added_count} líneas nuevas cargadas a la preparación.'
            
        return False

    def _compute_summary(self):
        """Build per-product summary aggregating all lines."""
        self.summary_ids.unlink()
        product_totals = {}
        for line in self.line_ids:
            # Si el producto ya se empaquetó, también lo contamos para el reporte global
            pid = line.product_product_id.id
            if pid not in product_totals:
                product_totals[pid] = {
                    'product_id': pid,
                    'total_estimated_kg': 0.0,
                    'total_done_kg': 0.0,
                    'order_count': 0,
                    'wizard_id': self.id,
                    'available_qty': line.product_product_id.qty_available,
                }
            product_totals[pid]['total_estimated_kg'] += line.estimated_kg
            product_totals[pid]['order_count'] += 1
            if line.is_done:
                product_totals[pid]['total_done_kg'] += line.actual_kg

        for vals in product_totals.values():
            vals['total_estimated_kg'] = round(vals['total_estimated_kg'], 3)
            vals['stock_ok'] = vals['available_qty'] >= vals['total_estimated_kg']

        self.env['guapante.preparation.day.summary'].create(list(product_totals.values()))

    def action_save_line_weight(self, line_id):
        """Called automatically (via JS or single action) when user sets weight."""
        line = self.env['guapante.preparation.day.line'].browse(line_id)
        if not line or line.is_done or line.actual_kg <= 0:
            return False

        # Registrar el peso real en stock.move.line (cantidad ejecutada visible en el picking).
        # Limpiamos todas las move_lines existentes para evitar acumulación por operaciones
        # previas de guardar/deshacer, luego dejamos exactamente una con el peso correcto.
        if line.stock_move_id:
            move = line.stock_move_id.sudo()
            if move.move_line_ids:
                move.move_line_ids.write({'quantity': 0})
                move.move_line_ids[0].quantity = line.actual_kg
            else:
                move.write({
                    'move_line_ids': [(0, 0, {
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'quantity': line.actual_kg,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'picking_id': move.picking_id.id,
                    })]
                })
            
        # Marcar como hecho en esta sesión persistente
        line.is_done = True

        # Actualizar total_done_kg en el resumen del producto
        summary = self.summary_ids.filtered(lambda s: s.product_id == line.product_product_id)
        if summary:
            summary.total_done_kg = round(summary.total_done_kg + line.actual_kg, 3)
        
        # Calcular tiempo para el Log de rendimiento
        last_log = self.env['guapante.picking.log'].search([
            ('user_id', '=', self.env.user.id),
            ('wizard_id', '=', self.id)
        ], order='create_date desc', limit=1)
        
        time_taken = 0
        if last_log:
            time_diff = fields.Datetime.now() - last_log.create_date
            time_taken = int(time_diff.total_seconds())

        self.env['guapante.picking.log'].create({
            'product_product_id': line.product_product_id.id,
            'sale_order_id': line.sale_order_id.id,
            'wizard_id': self.id,
            'actual_kg': line.actual_kg,
            'time_taken_seconds': time_taken
        })
        
        self.save_note = f'✅ Peso de {line.order_name} guardado: {line.actual_kg} kg.'
        
        # Force invalidation to update sales amounts
        line.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )
        
        # Auto-finish si ya no quedan lineas pendientes de ninguno de los productos
        pending_total = self.env['guapante.preparation.day.line'].search_count([
            ('wizard_id', '=', self.id),
            ('is_done', '=', False)
        ])
        if pending_total == 0:
            self.action_mark_done()
            self.save_note = '🎉 ¡Todos los productos han sido empaquetados exitosamente! Sesión Finalizada.'
            
        return True

    def action_mark_done(self):
        """Mark session as done."""
        self.state = 'done'
        return False


class PreparationDaySummary(models.Model):
    """Aggregated view: one row per product variant showing totals."""
    _name = 'guapante.preparation.day.summary'
    _description = 'Resumen de Preparación por Producto'
    _order = 'product_id'

    wizard_id = fields.Many2one('guapante.preparation.day', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    total_estimated_kg = fields.Float(string='Total kg estimado', digits=(10, 3), readonly=True)
    total_done_kg = fields.Float(string='Total kg hecho', digits=(10, 3), readonly=True)
    order_count = fields.Integer(string='Órdenes', readonly=True)
    available_qty = fields.Float(string='Disponible (kg)', digits=(10, 3), readonly=True)
    stock_ok = fields.Boolean(string='Stock OK', readonly=True)
    progress_pct = fields.Float(
        string='Progreso',
        compute='_compute_progress_pct',
        digits=(5, 1),
    )

    @api.depends('wizard_id.line_ids.is_done', 'wizard_id.line_ids.product_product_id')
    def _compute_progress_pct(self):
        for rec in self:
            all_lines = rec.wizard_id.line_ids.filtered(
                lambda l: l.product_product_id == rec.product_id
            )
            done = all_lines.filtered(lambda l: l.is_done)
            rec.progress_pct = (len(done) / len(all_lines) * 100.0) if all_lines else 0.0

    def action_select_product(self):
        """Abre un wizard Transitorio para empacar este producto, sin interferir con otros usuarios."""
        wizard = self.env['guapante.preparation.day.product.wizard'].create({
            'session_id': self.wizard_id.id,
            'product_id': self.product_id.id,
            'available_qty': self.available_qty,
            'total_estimated_kg': self.total_estimated_kg,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'current',
        }

class PreparationDayProductWizard(models.TransientModel):
    _name = 'guapante.preparation.day.product.wizard'
    _description = 'Wizard de Empaque por Producto (Aislado por Usuario)'

    session_id = fields.Many2one('guapante.preparation.day', string='Sesión', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    
    available_qty = fields.Float(string='Disponible en stock', digits=(10, 3), readonly=True)
    total_estimated_kg = fields.Float(string='Total kg pedido', digits=(10, 3), readonly=True)
    
    progress_percentage = fields.Float(string='Progreso de Empaque', compute='_compute_lists')
    
    # Pendientes y Hechos (separados lógicamente para las vistas XML)
    detail_line_pending_ids = fields.Many2many('guapante.preparation.day.line', compute='_compute_lists', readonly=False)
    detail_line_done_ids = fields.Many2many('guapante.preparation.day.line', compute='_compute_lists', readonly=False)

    @api.depends('session_id.line_ids.is_done', 'session_id.line_ids.actual_kg')
    def _compute_lists(self):
        for wiz in self:
            all_lines = wiz.session_id.line_ids.filtered(lambda l: l.product_product_id == wiz.product_id)
            done = all_lines.filtered(lambda l: l.is_done)
            pending = all_lines - done
            wiz.detail_line_done_ids = done.ids
            wiz.detail_line_pending_ids = pending.ids
            if all_lines:
                wiz.progress_percentage = (len(done) / len(all_lines)) * 100.0
            else:
                wiz.progress_percentage = 0.0

    def action_back_to_session(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day',
            'res_id': self.session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
