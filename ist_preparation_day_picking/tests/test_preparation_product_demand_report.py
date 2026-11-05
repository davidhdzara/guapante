# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    REPORTS_START_DATE_PARAM_KEY,
)

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationProductDemandReport(TestPreparationDayProductClaim):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — Reporte 2
    "Productos más solicitados": ÚNICO de los 5 reportes SIN filtro
    de reports_start_date (ver preparation_product_demand_report.py).
    Mismo patrón de fixtures por ORM directo que el Reporte 1."""

    def setUp(self):
        super().setUp()
        self.Report = self.env['guapante.preparation.product.demand.report']
        self.Line = self.env['guapante.preparation.day.line']
        self.Day = self.env['guapante.preparation.day']
        self._next_box = 0

    def _far_today(self):
        """Fecha lejana para fixtures de sesión (Tech Lead, endurecimiento
        de tests, 2026-11-04) — NUNCA context_today real, ver el mismo
        helper en test_preparation_interval_report.py (+200 días). +220
        acá — distinto por archivo para que ni los 3 de reportes puedan
        pisarse entre sí."""
        return fields.Date.add(
            fields.Date.context_today(self.env['sale.order']), days=220,
        )

    def _session(self, date):
        return self.Day.create({'date': date})

    def _box(self):
        self._next_box += 1
        return self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id,
            'daily_sequence': self._next_box,
        })

    def _line(self, wizard, product, actual_kg=0.0, is_done=True,
              sale_order=None):
        return self.Line.sudo().create({
            'wizard_id': wizard.id,
            'product_id': product.product_tmpl_id.id,
            'product_product_id': product.id,
            'sale_order_id': sale_order.id if sale_order else self._box().id,
            'actual_kg': actual_kg,
            'is_done': is_done,
        })

    def test_pending_lines_excluded(self):
        """Reporte 2 también se basa en is_done=True — una línea sin
        terminar nunca es "demanda" todavía."""
        today = self._far_today()
        session = self._session(today)
        self._line(session, self.product_weight, actual_kg=0.0, is_done=False)

        # Dominio [] sobre todo el reporte capturaba datos reales de
        # staging_dev (el Reporte 2 no filtra por reports_start_date,
        # a propósito) — se acota a esta sesión de fixture, nunca al
        # reporte completo.
        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['product_tmpl_id'],
        )
        self.assertFalse(rows)

    def test_line_done_and_zero_counted_separately(self):
        today = self._far_today()
        session = self._session(today)
        self._line(session, self.product_weight, actual_kg=4.0)
        self._line(session, self.product_weight, actual_kg=0.0)

        rows = self.Report.sudo().search_read(
            [('product_tmpl_id', '=', self.product_weight.product_tmpl_id.id)],
            ['line_done', 'line_zero', 'kg'],
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(r['line_done'] for r in rows), 1)
        self.assertEqual(sum(r['line_zero'] for r in rows), 1)
        self.assertEqual(sum(r['kg'] for r in rows), 4.0)

    def test_no_reports_start_date_filter_unlike_report_1(self):
        """Diferencia explícita con el Reporte 1: una línea Terminada
        ANTES del parámetro reports_start_date SÍ cuenta aquí — la
        demanda histórica de un producto no se recorta."""
        cutoff = self._far_today()
        self.env['ir.config_parameter'].sudo().set_param(
            REPORTS_START_DATE_PARAM_KEY, str(cutoff),
        )
        old_session = self._session(cutoff - timedelta(days=30))
        self._line(old_session, self.product_weight, actual_kg=1.5)

        rows = self.Report.sudo().search_read(
            [('product_tmpl_id', '=', self.product_weight.product_tmpl_id.id)],
            ['kg'],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kg'], 1.5)

    def test_sale_order_id_count_distinct(self):
        """2 líneas del mismo pedido + 1 línea de otro pedido, mismo
        producto: pedidos distintos = 2, no 3."""
        today = self._far_today()
        session = self._session(today)
        order1 = self._box()
        self._line(session, self.product_weight, actual_kg=1.0, sale_order=order1)
        self._line(session, self.product_weight, actual_kg=1.0, sale_order=order1)
        self._line(session, self.product_weight, actual_kg=1.0)

        groups = self.Report.sudo().read_group(
            [('product_tmpl_id', '=', self.product_weight.product_tmpl_id.id)],
            ['sale_order_id:count_distinct'], [],
        )
        self.assertEqual(groups[0]['sale_order_id'], 2)

    def test_wizard_id_count_distinct_across_sessions(self):
        """El mismo producto aparece en 2 jornadas distintas: jornadas
        distintas = 2."""
        day1 = self._far_today()
        day2 = fields.Date.add(day1, days=1)
        session1 = self._session(day1)
        session2 = self._session(day2)
        self._line(session1, self.product_weight, actual_kg=1.0)
        self._line(session2, self.product_weight, actual_kg=1.0)

        groups = self.Report.sudo().read_group(
            [('product_tmpl_id', '=', self.product_weight.product_tmpl_id.id)],
            ['wizard_id:count_distinct'], [],
        )
        self.assertEqual(groups[0]['wizard_id'], 2)

    def test_product_rank_orders_by_total_line_done_desc(self):
        """Task C (Tech Lead, 2026-11-04): product_rank viene de un
        RANK() sobre el total de líneas despachadas POR PRODUCTO (no
        por línea), calculado sobre TODA la historia (sin filtro de
        reports_start_date, igual que el resto de este reporte) — así
        que no se puede asumir un valor absoluto (staging_dev/la BD
        de test puede tener datos reales de otros productos con más
        demanda). Se verifica el ORDEN RELATIVO entre 3 productos de
        fixture con totales distintos (3, 2, 1): rank(A) < rank(B) <
        rank(C), y que TODAS las líneas de un mismo producto
        comparten el mismo rank."""
        today = self._far_today()
        session = self._session(today)
        product_b = self.env['product.product'].create({
            'name': 'Producto Demanda B', 'type': 'consu',
        })
        product_c = self.env['product.product'].create({
            'name': 'Producto Demanda C', 'type': 'consu',
        })
        for _ in range(3):
            self._line(session, self.product_weight, actual_kg=1.0)
        for _ in range(2):
            self._line(session, product_b, actual_kg=1.0)
        self._line(session, product_c, actual_kg=1.0)

        def _rank_of(product):
            rows = self.Report.sudo().search_read(
                [('product_tmpl_id', '=', product.product_tmpl_id.id)],
                ['product_rank'], limit=1,
            )
            return rows[0]['product_rank']

        rank_weight = _rank_of(self.product_weight)
        rank_b = _rank_of(product_b)
        rank_c = _rank_of(product_c)
        self.assertLess(rank_weight, rank_b)
        self.assertLess(rank_b, rank_c)

        # Todas las líneas del producto con más demanda de los 3
        # comparten exactamente el mismo rank.
        rows = self.Report.sudo().search_read(
            [('product_tmpl_id', '=', self.product_weight.product_tmpl_id.id)],
            ['product_rank'],
        )
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['product_rank'] == rank_weight for r in rows))

    def test_top_n_filter_domain_excludes_lower_ranked_products(self):
        """El mecanismo de los filtros "Top 10"/"Top 20" del buscador
        es este mismo domain sobre product_rank — se prueba acá
        filtrando por el rank real del producto más demandado de 2
        de fixture (sin asumir que sea el #1 global, que puede no
        serlo si hay datos reales de fondo): el domain debe incluir
        SOLO ese producto y excluir el de menor demanda."""
        today = self._far_today()
        session = self._session(today)
        product_b = self.env['product.product'].create({
            'name': 'Producto Demanda B', 'type': 'consu',
        })
        self._line(session, self.product_weight, actual_kg=1.0)
        self._line(session, self.product_weight, actual_kg=1.0)
        self._line(session, product_b, actual_kg=1.0)

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)],
            ['product_tmpl_id', 'product_rank'],
        )
        rank_weight = next(
            r['product_rank'] for r in rows
            if r['product_tmpl_id'][0] == self.product_weight.product_tmpl_id.id
        )

        top = self.Report.sudo().search([
            ('wizard_id', '=', session.id), ('product_rank', '<=', rank_weight),
        ])
        self.assertEqual(
            set(top.mapped('product_tmpl_id.id')),
            {self.product_weight.product_tmpl_id.id},
        )
