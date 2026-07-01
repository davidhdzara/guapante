from odoo import models, fields, api
from datetime import date

class GuapanteKardexDaily(models.Model):
    _name = 'guapante.kardex.daily'
    _description = 'Kardex Diario (Snapshot)'
    _order = 'date desc, product_id'

    date = fields.Date(string='Fecha', required=True, index=True, default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Producto', required=True, index=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', required=True, index=True)
    
    qty_start = fields.Float(string='Con cuanto inicie', required=True, default=0.0)
    qty_in = fields.Float(string='Cuanto se compro', default=0.0)
    qty_out = fields.Float(string='Cuanto se vendio', default=0.0)
    qty_scrap = fields.Float(string='Desperdicios', default=0.0)
    
    qty_theoretical = fields.Float(string='Total que debo de tener', compute='_compute_totals', store=True)
    qty_real = fields.Float(string='Total en inventario', compute='_compute_totals', store=True)
    difference = fields.Float(string='Diferencia', compute='_compute_totals', store=True)

    _sql_constraints = [
        ('unique_daily_product_location', 'unique(date, product_id, location_id)',
         'Solo puede haber un snapshot por producto, ubicación y fecha.')
    ]

    # ── helpers ──────────────────────────────────────────────────────────

    @api.model
    def _get_main_stock_location(self):
        """Retorna la ubicacion principal del almacen (WH/Stock)."""
        wh = self.env['stock.warehouse'].search([], limit=1)
        return wh.lot_stock_id if wh else self.env['stock.location']

    @api.model
    def _get_tracked_locations(self):
        """WH/Stock y sub-ubicaciones. Solo se usa para filtrar ajustes de inventario."""
        main = self._get_main_stock_location()
        if not main:
            return self.env['stock.location']
        return self.env['stock.location'].search([
            ('id', 'child_of', main.id),
            ('usage', '=', 'internal'),
        ])

    # ── computed fields ──────────────────────────────────────────────────

    @api.depends('qty_start', 'qty_in', 'qty_out', 'qty_scrap', 'date')
    def _compute_totals(self):
        all_internal = self.env['stock.location'].search([('usage', '=', 'internal')])
        for record in self:
            record.qty_theoretical = (
                record.qty_start + record.qty_in - record.qty_out - record.qty_scrap
            )

            if record.date == fields.Date.context_today(self):
                # Stock real = suma de quants en TODAS las ubicaciones internas
                # Esto incluye WH/Stock, WH/Entrada, WH/Salida y sub-ubicaciones
                # para reflejar el inventario total de la empresa
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', 'in', all_internal.ids),
                ])
                record.qty_real = sum(q.quantity for q in quants)
            else:
                record.qty_real = record.qty_theoretical

            record.difference = record.qty_real - record.qty_theoretical

    # ── cron: snapshot diario ────────────────────────────────────────────

    @api.model
    def take_daily_snapshot(self):
        """
        Cron job (00:01). Crea UN registro por producto con el stock total
        de todas las ubicaciones internas como saldo inicial del dia.
        """
        today = fields.Date.context_today(self)
        main_stock = self._get_main_stock_location()
        if not main_stock:
            return

        all_internal = self.env['stock.location'].search([('usage', '=', 'internal')])
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', all_internal.ids),
        ])

        # Sumar stock por producto (todas las ubicaciones internas)
        product_totals = {}
        for q in quants:
            pid = q.product_id.id
            product_totals[pid] = product_totals.get(pid, 0) + q.quantity

        for pid, total in product_totals.items():
            if total == 0:
                continue
            existing = self.search([
                ('date', '=', today),
                ('product_id', '=', pid),
                ('location_id', '=', main_stock.id),
            ])
            if not existing:
                self.create({
                    'date': today,
                    'product_id': pid,
                    'location_id': main_stock.id,
                    'qty_start': total,
                    'qty_in': 0.0,
                    'qty_out': 0.0,
                    'qty_scrap': 0.0,
                })

    # ── sync desde stock.move ────────────────────────────────────────────

    @api.model
    def _sync_moves(self, moves):
        """
        Llamado desde stock.move._action_done().

        Rastrea movimientos en la FRONTERA de la empresa:
          - COMPRA:      proveedor  →  interno  (recepcion del vendor)
          - VENTA:       interno    →  cliente   (entrega al cliente)
          - DESPERDICIO: interno    →  desecho   (scrap_location=True)
          - AJUSTE:      inv. adj   ↔  WH/Stock  (modifica saldo inicial)

        Todo movimiento interno-interno se IGNORA (picks, storage, transfers).
        """
        today = fields.Date.context_today(self)
        main_stock = self._get_main_stock_location()
        if not main_stock:
            return

        tracked_ids = set(self._get_tracked_locations().ids)

        for move in moves.filtered(lambda m: m.state == 'done'):
            src = move.location_id
            dest = move.location_dest_id

            # COMPRA: proveedor → cualquier ubicacion interna
            if src.usage == 'supplier' and dest.usage == 'internal':
                self._update_kardex_line(
                    today, move.product_id.id, main_stock.id, 'in', move.product_uom_qty)

            # VENTA: cualquier ubicacion interna → cliente
            elif src.usage == 'internal' and dest.usage == 'customer':
                self._update_kardex_line(
                    today, move.product_id.id, main_stock.id, 'out', move.product_uom_qty)

            # DESPERDICIO: cualquier ubicacion interna → desecho
            elif src.usage == 'internal' and dest.scrap_location:
                self._update_kardex_line(
                    today, move.product_id.id, main_stock.id, 'scrap', move.product_uom_qty)

            # AJUSTE POSITIVO: ajuste de inventario → WH/Stock (solo ubicaciones rastreadas)
            elif src.usage == 'inventory' and dest.id in tracked_ids:
                self._adjust_start_balance(
                    today, move.product_id.id, main_stock.id, move.product_uom_qty)

            # AJUSTE NEGATIVO: WH/Stock → ajuste de inventario
            elif dest.usage == 'inventory' and src.id in tracked_ids:
                self._adjust_start_balance(
                    today, move.product_id.id, main_stock.id, -move.product_uom_qty)

    # ── helpers de escritura ─────────────────────────────────────────────

    def _get_or_create_kardex(self, today, product_id, location_id):
        """Obtiene o crea el registro del Kardex para hoy."""
        kardex = self.search([
            ('date', '=', today),
            ('product_id', '=', product_id),
            ('location_id', '=', location_id),
        ], limit=1)

        if not kardex:
            # Calcular stock total actual en todas las ubicaciones internas
            all_internal = self.env['stock.location'].search([('usage', '=', 'internal')])
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product_id),
                ('location_id', 'in', all_internal.ids),
            ])
            total_stock = sum(q.quantity for q in quants)

            kardex = self.create({
                'date': today,
                'product_id': product_id,
                'location_id': location_id,
                'qty_start': total_stock,
            })
        return kardex

    def _adjust_start_balance(self, today, product_id, location_id, qty_delta):
        """Ajuste de inventario: modifica el saldo inicial."""
        kardex = self._get_or_create_kardex(today, product_id, location_id)
        self.env.cr.execute(
            "UPDATE guapante_kardex_daily SET qty_start = qty_start + %s WHERE id = %s",
            (qty_delta, kardex.id)
        )
        kardex.invalidate_recordset(['qty_start'])

    def _update_kardex_line(self, today, product_id, location_id, direction, qty):
        """Actualiza compras/ventas/desperdicios de forma atomica."""
        kardex = self._get_or_create_kardex(today, product_id, location_id)

        # Si es la primera vez, ajustar el start descontando este movimiento
        if kardex.qty_in == 0 and kardex.qty_out == 0 and kardex.qty_scrap == 0:
            # El stock total actual YA incluye este movimiento, hay que deshacer
            if direction == 'in':
                self.env.cr.execute(
                    "UPDATE guapante_kardex_daily SET qty_start = qty_start - %s WHERE id = %s",
                    (qty, kardex.id)
                )
            elif direction in ('out', 'scrap'):
                self.env.cr.execute(
                    "UPDATE guapante_kardex_daily SET qty_start = qty_start + %s WHERE id = %s",
                    (qty, kardex.id)
                )

        field_map = {'in': 'qty_in', 'out': 'qty_out', 'scrap': 'qty_scrap'}
        field_name = field_map[direction]
        self.env.cr.execute(
            f"UPDATE guapante_kardex_daily SET {field_name} = {field_name} + %s WHERE id = %s",
            (qty, kardex.id)
        )
        kardex.invalidate_recordset(['qty_start', field_name])
