# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    REPORTS_START_DATE_PARAM_KEY,
)

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationOperatorReport(TestPreparationDayProductClaim):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — Reporte 1
    "Pickings por operario". Las líneas se crean por ORM directo
    (create(), no write() sobre una línea real pesada) porque el
    reporte es de solo lectura sobre datos ya Terminados — no hace
    falta reproducir el flujo completo de pesaje para probar la
    AGREGACIÓN. Hereda operator_a/operator_b/product_weight de
    TestPreparationDayProductClaim."""

    def setUp(self):
        super().setUp()
        self.Report = self.env['guapante.preparation.operator.report']
        self.Line = self.env['guapante.preparation.day.line']
        self.Day = self.env['guapante.preparation.day']
        self._next_box = 0

    def _far_today(self):
        """Fecha lejana para fixtures de sesión (Tech Lead, endurecimiento
        de tests, 2026-11-04) — NUNCA context_today real, ver el mismo
        helper en test_preparation_interval_report.py (+200 días). +210
        acá — distinto por archivo para que ni los 3 de reportes puedan
        pisarse entre sí."""
        return fields.Date.add(
            fields.Date.context_today(self.env['sale.order']), days=210,
        )

    def _session(self, date):
        return self.Day.create({'date': date})

    def _box(self):
        """daily_sequence en la línea es related+store de solo lectura
        sobre sale_order_id.daily_sequence (sin inverse) — para fijar
        una caja distinta en el fixture hace falta una sale.order real
        con su propio daily_sequence, nunca escribir el campo de la
        línea directo."""
        self._next_box += 1
        return self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id,
            'daily_sequence': self._next_box,
        })

    def _line(self, wizard, product, employee=None, actual_kg=0.0,
              done_date=None, is_done=True, sale_order=None):
        return self.Line.sudo().create({
            'wizard_id': wizard.id,
            'product_id': product.product_tmpl_id.id,
            'product_product_id': product.id,
            'sale_order_id': sale_order.id if sale_order else self._box().id,
            'actual_kg': actual_kg,
            'is_done': is_done,
            'done_by_employee_id': employee.id if employee else False,
            'done_date': done_date,
        })

    def test_line_done_and_zero_counted_separately(self):
        """Dos cajas Terminadas del mismo operario/jornada: una pesada
        (kg > 0) y una en 0 (E7, sin stock) — line_done y line_zero
        deben contarse por separado, nunca mezcladas."""
        today = self._far_today()
        session = self._session(today)
        self._line(
            session, self.product_weight, self.operator_a,
            actual_kg=3.5, done_date=fields.Datetime.now(),
        )
        self._line(
            session, self.product_weight, self.operator_a,
            actual_kg=0.0, done_date=fields.Datetime.now(),
        )

        rows = self.Report.sudo().search_read(
            [('employee_id', '=', self.operator_a.id)],
            ['line_done', 'line_zero', 'kg'],
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(r['line_done'] for r in rows), 1)
        self.assertEqual(sum(r['line_zero'] for r in rows), 1)
        self.assertEqual(sum(r['kg'] for r in rows), 3.5)

    def test_box_count_is_distinct_boxes_not_distinct_lines(self):
        """Tech Lead (2026-11-04): "cajas distintas (COUNT DISTINCT
        wizard_id+daily_sequence)" — dos productos TERMINADOS dentro de
        LA MISMA caja (mismo sale_order_id) cuentan como 1 caja, no 2;
        una tercera línea en otra caja sí suma una caja más."""
        today = self._far_today()
        session = self._session(today)
        box1 = self._box()
        self._line(
            session, self.product_weight, self.operator_a, actual_kg=1.0,
            done_date=fields.Datetime.now(), sale_order=box1,
        )
        self._line(
            session, self.product_unit, self.operator_a, actual_kg=2.0,
            done_date=fields.Datetime.now(), sale_order=box1,
        )
        self._line(
            session, self.product_weight, self.operator_a, actual_kg=1.0,
            done_date=fields.Datetime.now(),
        )

        groups = self.Report.sudo().read_group(
            [('employee_id', '=', self.operator_a.id)],
            ['box_count:count_distinct'], [],
        )
        self.assertEqual(groups[0]['box_count'], 2)

    def test_pending_line_without_employee_excluded(self):
        """Una línea sin terminar (done_by_employee_id vacío) no es un
        picking de nadie todavía — nunca debe aparecer en el reporte
        de operario."""
        today = self._far_today()
        session = self._session(today)
        self._line(
            session, self.product_weight, employee=None,
            actual_kg=0.0, done_date=None, is_done=False,
        )

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['employee_id'],
        )
        self.assertFalse(rows)

    def test_archived_employee_still_included(self):
        """Fase 2, punto 4 (David, 2026-11-04): un empleado archivado
        sigue siendo historia real — nunca se excluye de este
        reporte, aunque ya no pueda operar Picking hoy."""
        today = self._far_today()
        session = self._session(today)
        self._line(
            session, self.product_weight, self.operator_a,
            actual_kg=2.0, done_date=fields.Datetime.now(),
        )
        self.operator_a.active = False

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['employee_id', 'line_done'],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['employee_id'][0], self.operator_a.id)
        self.assertEqual(rows[0]['line_done'], 1)

    def test_reports_start_date_excludes_lines_before_param(self):
        """Fase 2, commit 5/7 (Tech Lead): reports_start_date filtra
        por done_date — una línea Terminada antes del parámetro queda
        fuera, una terminada después queda dentro, sin excepción."""
        cutoff = self._far_today()
        self.env['ir.config_parameter'].sudo().set_param(
            REPORTS_START_DATE_PARAM_KEY, str(cutoff),
        )
        session = self._session(cutoff)
        self._line(
            session, self.product_weight, self.operator_a, actual_kg=1.0,
            done_date=fields.Datetime.to_datetime(cutoff) - timedelta(days=1),
        )
        self._line(
            session, self.product_weight, self.operator_a, actual_kg=2.0,
            done_date=fields.Datetime.to_datetime(cutoff) + timedelta(hours=1),
        )

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['kg'],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kg'], 2.0)

    def test_groupby_employee_and_jornada_day(self):
        """Agrupación por operario y jornada (día) — base de la vista
        pivot por defecto del Reporte 1. Dos jornadas distintas, dos
        operarios: cada combinación suma solo lo suyo."""
        day1 = self._far_today()
        day2 = fields.Date.add(day1, days=1)
        session1 = self._session(day1)
        session2 = self._session(day2)
        self._line(
            session1, self.product_weight, self.operator_a, actual_kg=1.0,
            done_date=fields.Datetime.now(),
        )
        self._line(
            session1, self.product_weight, self.operator_a, actual_kg=1.0,
            done_date=fields.Datetime.now(),
        )
        self._line(
            session2, self.product_weight, self.operator_b, actual_kg=5.0,
            done_date=fields.Datetime.now(),
        )

        groups = self.Report.sudo().read_group(
            [], ['line_done:sum', 'kg:sum'], ['employee_id', 'date:day'],
        )
        by_employee = {g['employee_id'][0]: g for g in groups}
        self.assertEqual(by_employee[self.operator_a.id]['line_done'], 2)
        self.assertEqual(by_employee[self.operator_a.id]['kg'], 2.0)
        self.assertEqual(by_employee[self.operator_b.id]['line_done'], 1)
        self.assertEqual(by_employee[self.operator_b.id]['kg'], 5.0)
