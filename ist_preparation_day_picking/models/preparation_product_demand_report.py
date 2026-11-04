# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools import SQL


class PreparationProductDemandReport(models.Model):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — Reporte 2
    "Productos más solicitados": UNA fila por línea de Picking ya
    Terminada, de TODAS las sesiones, SIN el filtro de
    reports_start_date (única excepción explícita entre los 5
    reportes — ver const_preparation.py) porque la demanda histórica
    de un producto no debe perder datos de antes de esa fecha.

    product_tmpl_id (no la variante): coincide con la unidad de
    trabajo del Nivel 1 (guapante.preparation.day.product.claim),
    nunca la variante — mismo criterio que ya usa ese modelo."""
    _name = 'guapante.preparation.product.demand.report'
    _description = 'Picking — Reporte 2: productos más solicitados'
    _auto = False
    _order = 'product_tmpl_id'

    product_tmpl_id = fields.Many2one('product.template', string='Producto', readonly=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Pedido', readonly=True, aggregator='count_distinct',
        help='Pedidos distintos que solicitaron este producto.',
    )
    wizard_id = fields.Many2one(
        'guapante.preparation.day', string='Sesión', readonly=True,
        aggregator='count_distinct',
        help='Jornadas distintas en que apareció este producto.',
    )
    line_done = fields.Integer(
        string='Líneas despachadas', readonly=True, aggregator='sum',
        help='Líneas Terminadas con kg > 0 (realmente despachadas).',
    )
    line_zero = fields.Integer(
        string='Líneas en 0', readonly=True, aggregator='sum',
        help='Líneas Terminadas sin peso (E7, "sin stock").',
    )
    kg = fields.Float(
        string='Kg', readonly=True, aggregator='sum', digits=(10, 3),
    )

    _depends = {
        'guapante.preparation.day.line': [
            'wizard_id', 'product_id', 'sale_order_id', 'is_done', 'actual_kg',
        ],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL(
            '''
            SELECT
                line.id AS id,
                line.product_id AS product_tmpl_id,
                line.sale_order_id AS sale_order_id,
                line.wizard_id AS wizard_id,
                CASE WHEN line.actual_kg > 0 THEN 1 ELSE 0 END AS line_done,
                CASE WHEN line.actual_kg <= 0 THEN 1 ELSE 0 END AS line_zero,
                line.actual_kg AS kg
            FROM guapante_preparation_day_line line
            WHERE line.is_done IS TRUE
            '''
        )
