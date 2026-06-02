# -*- coding: utf-8 -*-
"""Override Replenishment to generate variant-discriminated PO lines.

Uses PROPORTIONAL DISTRIBUTION:
  1. Odoo calculates the TOTAL PO qty (accounts for stock on hand).
  2. We find pending demand via warehouse picks (internal or outgoing).
  3. Group demand by (variant attributes, measure_type).
  4. Distribute Odoo's total proportionally across groups.

Demand source priority:
  1. Pending internal picks (2-step warehouse: Pick → Ship)
  2. Pending outgoing moves (1-step warehouse: Ship only)
  3. Recent SO lines (last 48 hours) — fallback
  4. No split — leave PO line as Odoo generated it
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import models

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    # ──────────────────────────────────────────────────
    #  PUBLIC: Override the "Orden" button
    # ──────────────────────────────────────────────────
    def action_replenish(self, force_to_max=False):
        """Extend standard replenishment to split PO lines by variant."""
        last_pol = self.env['purchase.order.line'].sudo().search(
            [], order='id desc', limit=1,
        )
        last_pol_id = last_pol.id if last_pol else 0
        product_ids = self.mapped('product_id').ids

        _logger.info(
            '[Guapante] action_replenish: products=%s, last_pol=%s',
            product_ids, last_pol_id,
        )

        result = super().action_replenish(force_to_max=force_to_max)

        if not product_ids:
            return result

        new_po_lines = self.env['purchase.order.line'].sudo().search([
            ('id', '>', last_pol_id),
            ('product_id', 'in', product_ids),
        ])

        _logger.info(
            '[Guapante] New PO lines to split: %s', new_po_lines.ids,
        )

        for pol in new_po_lines:
            try:
                self._split_po_line_by_variant(pol)
            except Exception:
                _logger.exception(
                    '[Guapante] FAILED split PO line %s (%s)',
                    pol.id, pol.product_id.display_name,
                )

        return result

    # ──────────────────────────────────────────────────
    #  PRIVATE: Get demand data (moves or SO lines)
    # ──────────────────────────────────────────────────
    def _get_demand_moves(self, product):
        """Return pending stock.moves linked to SO lines.

        Priority 1: Internal picks (2-step: Pick → Ship)
        Priority 2: Outgoing moves (1-step flow)
        """
        for pick_type in ('internal', 'outgoing'):
            moves = self.env['stock.move'].sudo().search([
                ('product_id', '=', product.id),
                ('picking_id', '!=', False),
                ('picking_id.picking_type_code', '=', pick_type),
                ('state', 'not in', ['done', 'cancel']),
                ('sale_line_id', '!=', False),
            ])
            if moves:
                _logger.info(
                    '[Guapante] %s: %s pending %s moves (%.2f kg)',
                    product.default_code, len(moves), pick_type,
                    sum(moves.mapped('product_uom_qty')),
                )
                return moves

        _logger.info(
            '[Guapante] %s: no pending picks found', product.default_code,
        )
        return self.env['stock.move']

    def _get_fallback_sol(self, product):
        """Fallback: SO lines from the last 48 hours."""
        cutoff = datetime.now() - timedelta(hours=48)
        sol = self.env['sale.order.line'].sudo().search([
            ('product_id', '=', product.id),
            ('state', 'in', ['sale', 'done']),
            ('product_uom_qty', '>', 0),
            ('order_id.date_order', '>=', cutoff),
        ])
        _logger.info(
            '[Guapante] %s: fallback → %s SO lines from last 48h',
            product.default_code, len(sol),
        )
        return sol

    # ──────────────────────────────────────────────────
    #  PRIVATE: Build variant groups from demand data
    # ──────────────────────────────────────────────────
    def _build_variant_groups(self, moves, fallback_sol):
        """Group demand by (attribute_ids, measure_type).

        Returns dict: {key: {demand_kg, attr_names, measure_type}}
        """
        groups = defaultdict(lambda: {
            'demand_kg': 0.0,
            'attr_names': '',
            'measure_type': 'weight',
        })

        if moves:
            for move in moves:
                sol = move.sale_line_id
                self._add_to_group(groups, sol, move.product_uom_qty)
        elif fallback_sol:
            for sol in fallback_sol:
                self._add_to_group(groups, sol, sol.product_uom_qty)

        return dict(groups)

    def _add_to_group(self, groups, sol, qty_kg):
        """Add a SO line's demand to the appropriate group."""
        attr_ids = frozenset(
            sol.product_no_variant_attribute_value_ids.ids
        ) if hasattr(
            sol, 'product_no_variant_attribute_value_ids',
        ) else frozenset()

        uom_mode = getattr(sol, 'uom_mode', None) or 'kg'
        measure_type = 'unit' if uom_mode == 'unit' else 'weight'

        key = (attr_ids, measure_type)
        groups[key]['demand_kg'] += qty_kg
        groups[key]['measure_type'] = measure_type

        if not groups[key]['attr_names']:
            if hasattr(sol, 'product_no_variant_attribute_value_ids'):
                names = sol.product_no_variant_attribute_value_ids.mapped(
                    'product_attribute_value_id.name',
                )
                groups[key]['attr_names'] = (
                    ' / '.join(names) if names else ''
                )

    # ──────────────────────────────────────────────────
    #  PRIVATE: Split a PO line by variant proportionally
    # ──────────────────────────────────────────────────
    def _split_po_line_by_variant(self, po_line):
        """Replace *po_line* with proportionally distributed sub-lines."""
        product = po_line.product_id
        po_total_kg = po_line.product_qty  # Odoo's calculated total

        # ── Packaging weight ────────────────────────────
        packaging = product.packaging_ids.filtered(
            lambda p: p.purchase and p.qty > 0
        )[:1]
        if not packaging:
            packaging = product.packaging_ids.filtered(
                lambda p: p.sales and p.qty > 0
            )[:1]
        pkg_weight = packaging.qty if packaging else 1.0

        _logger.info(
            '[Guapante] Split %s: po_total=%.2f kg, pkg=%.2f kg',
            product.default_code, po_total_kg, pkg_weight,
        )

        # ── Get demand data ─────────────────────────────
        moves = self._get_demand_moves(product)
        fallback_sol = self.env['sale.order.line']
        if not moves:
            fallback_sol = self._get_fallback_sol(product)
            if not fallback_sol:
                _logger.info(
                    '[Guapante] %s: no demand data → keeping original',
                    product.default_code,
                )
                return

        # ── Build variant groups ────────────────────────
        groups = self._build_variant_groups(moves, fallback_sol)
        if not groups:
            return

        total_demand = sum(g['demand_kg'] for g in groups.values())
        if total_demand <= 0:
            return

        _logger.info(
            '[Guapante] %s: %s variant groups, demand=%.2f kg',
            product.default_code, len(groups), total_demand,
        )

        # ── Build description helper ────────────────────
        def _build_desc(attr_name, measure_type, n_units):
            code = product.default_code or ''
            prefix = f'[{code}] ' if code else ''
            name = product.name or product.display_name
            desc = f'{prefix}{name}'
            if attr_name:
                desc += f' — {attr_name}'
            if measure_type == 'unit' and n_units > 0:
                desc += f' ({n_units} {"Ud" if n_units == 1 else "Uds"})'
            return desc

        # ── Distribute PO total proportionally ──────────
        lines_data = []
        allocated_total = 0.0

        sorted_groups = sorted(
            groups.items(),
            key=lambda x: x[1]['demand_kg'],
            reverse=True,
        )

        for i, (key, data) in enumerate(sorted_groups):
            proportion = data['demand_kg'] / total_demand
            mt = data['measure_type']

            # Last group gets remainder (avoids rounding drift)
            if i == len(sorted_groups) - 1:
                allocated_kg = round(po_total_kg - allocated_total, 2)
            else:
                allocated_kg = round(po_total_kg * proportion, 2)
                allocated_total += allocated_kg

            if allocated_kg <= 0:
                continue

            n_units = 0
            if mt == 'unit':
                n_units = max(1, int(round(allocated_kg / pkg_weight)))
                visual = float(n_units)
                qty_kg = round(n_units * pkg_weight, 3)
                uom_mode = 'unit'
            else:
                qty_kg = allocated_kg
                visual = qty_kg
                uom_mode = 'kg'

            desc = _build_desc(data['attr_names'], mt, n_units)

            lines_data.append({
                'desc': desc,
                'product_qty': qty_kg,
                'visual_qty': visual,
                'uom_mode': uom_mode,
            })

            _logger.info(
                '[Guapante]   %s → %.1f%% → %s %s (%.2f kg)',
                data['attr_names'] or 'Sin atributos',
                proportion * 100,
                visual, uom_mode, qty_kg,
            )

        if not lines_data:
            return

        # ── Single group → update existing line ─────────
        if len(lines_data) == 1:
            d = lines_data[0]
            po_line.sudo().write({
                'name': d['desc'],
                'product_qty': d['product_qty'],
                'uom_mode': d['uom_mode'],
            })
            po_line.sudo().write({
                'visual_qty': d['visual_qty'],
                'name': d['desc'],
            })
            _logger.info(
                '[Guapante] Single line %s updated: %s',
                po_line.id, d['desc'],
            )
            return

        # ── Multiple groups → create sub-lines ──────────
        po = po_line.order_id
        POLine = self.env['purchase.order.line'].sudo()
        new_lines = self.env['purchase.order.line']

        for d in lines_data:
            vals = {
                'order_id': po.id,
                'product_id': product.id,
                'name': d['desc'],
                'product_qty': d['product_qty'],
                'uom_mode': d['uom_mode'],
                'price_unit': po_line.price_unit,
                'date_planned': po_line.date_planned,
            }
            if po_line.orderpoint_id:
                vals['orderpoint_id'] = po_line.orderpoint_id.id

            new_line = POLine.create(vals)
            new_line.write({
                'visual_qty': d['visual_qty'],
                'name': d['desc'],
            })
            new_lines |= new_line

        if new_lines:
            _logger.info(
                '[Guapante] Replaced line %s with %s variant lines',
                po_line.id, len(new_lines),
            )
            po_line.sudo().unlink()
