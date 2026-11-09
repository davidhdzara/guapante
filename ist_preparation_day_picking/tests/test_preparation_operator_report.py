# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.addons.ist_preparation_day.models.box_number import (
    CTX_ORIGIN,
    ORIGIN_ALTA,
    box_origin,
)
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
        # Lote 4 (candado de cajas): el número solo se fija con un origen
        # del sistema.
        return self.env['sale.order'].sudo().with_context(
            **{CTX_ORIGIN: box_origin(ORIGIN_ALTA)}
        ).create({
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

    def test_graph_view_is_line_chart_by_days_with_operator_series(self):
        """Tarea 3 (Tech Lead/David, 2026-11-05): "Pickings por
        operario" pasó de barras a líneas en el tiempo — eje días
        (date, interval day), una línea por operario (employee_id como
        segunda dimensión). Guarda de regresión barata contra un
        revert accidental a type="bar" o a un solo campo de grupo."""
        import xml.etree.ElementTree as ET

        Action = self.env.ref(
            'ist_preparation_day_picking.action_preparation_operator_report',
        )
        self.assertTrue(
            Action.view_mode.startswith('graph'),
            'el gráfico debe ser la vista por defecto (Tarea 3)',
        )
        views = self.Report.sudo().get_views([(False, 'graph')])
        graph_arch = views['views']['graph']['arch']
        root = ET.fromstring(graph_arch)
        self.assertEqual(root.get('type'), 'line')
        group_fields = [
            f.get('name') for f in root.findall('field')
            if f.get('type') != 'measure'
        ]
        self.assertEqual(group_fields, ['date', 'employee_id'])
        date_field = root.find("field[@name='date']")
        self.assertEqual(date_field.get('interval'), 'day')

    def test_graph_measure_is_switchable_lines_boxes_kg_with_lines_default(self):
        """Tarea 12 (Tech Lead/David, 2026-11-05): medida del gráfico
        switchable entre Líneas hechas/Cajas/Kg. En Odoo 18
        (computeReportMeasures, web/static/src/views/utils.js,
        verificado en el fuente real) el selector de medida del
        gráfico solo ofrece automáticamente integer/float/monetary con
        aggregator — "Cajas" (box_count) es Char y quedaría afuera del
        selector aunque declare aggregator='count_distinct', salvo que
        ya venga como medida activa en el arch (bypassa el filtro de
        tipo). Por eso las 3 deben estar declaradas como type="measure"
        en el arch, y 'line_done' debe ser la ÚLTIMA (el cliente usa
        el último <field type="measure"> como medida por defecto)."""
        import xml.etree.ElementTree as ET

        views = self.Report.sudo().get_views([(False, 'graph')])
        root = ET.fromstring(views['views']['graph']['arch'])
        measure_fields = [
            f.get('name') for f in root.findall('field')
            if f.get('type') == 'measure'
        ]
        self.assertEqual(
            set(measure_fields), {'line_done', 'box_count', 'kg'},
            'las 3 medidas (Líneas hechas/Cajas/Kg) deben estar '
            'declaradas como type="measure" en el arch del gráfico.',
        )
        self.assertEqual(
            measure_fields[-1], 'line_done',
            '"Líneas hechas" debe ser la última declarada, para '
            'seguir siendo la medida por defecto al abrir.',
        )
        # box_count es Char — confirma que el campo real sigue siendo
        # agregable (count_distinct) aunque no sea numérico; si algún
        # día deja de tener aggregator, el gráfico lo mostraría vacío.
        self.assertEqual(self.Report._fields['box_count'].type, 'char')
        self.assertTrue(self.Report._fields['box_count'].aggregator)

    def _filter_domain(self, view_xmlid, filter_name):
        import xml.etree.ElementTree as ET

        view = self.env.ref(view_xmlid)
        root = ET.fromstring(view.arch)
        node = root.find(f".//filter[@name='{filter_name}']")
        self.assertIsNotNone(node, f'filtro {filter_name!r} no existe en el arch.')
        return node.get('domain')

    def test_date_filters_are_identical_to_interval_report_search(self):
        """Tarea 13 (Tech Lead/David, 2026-11-05): mismo texto/fórmula
        en los dos buscadores (operario vs. interval report) —
        duplicado a propósito (dos modelos distintos, ver el
        comentario largo en el buscador compartido de 2/3/4/5), pero
        NUNCA debe divergir en el string. Guarda de regresión contra
        un copy-paste que se desalinee con el tiempo; la corrección
        matemática de cada fórmula ya se prueba a fondo en
        test_preparation_interval_report.py, acá solo se verifica que
        este buscador use EXACTAMENTE el mismo texto."""
        for filter_name in (
            'filter_yesterday', 'filter_today', 'filter_last_7_days',
            'filter_this_month', 'filter_last_month',
        ):
            with self.subTest(filter=filter_name):
                self.assertEqual(
                    self._filter_domain(
                        'ist_preparation_day_picking.view_preparation_operator_report_search',
                        filter_name,
                    ),
                    self._filter_domain(
                        'ist_preparation_day_picking.view_preparation_interval_report_search',
                        filter_name,
                    ),
                )

    def test_report_1_defaults_to_last_7_days(self):
        from odoo.tools.safe_eval import safe_eval

        action = self.env.ref(
            'ist_preparation_day_picking.action_preparation_operator_report'
        )
        context = safe_eval(action.context or '{}')
        self.assertEqual(context.get('search_default_filter_last_7_days'), 1)

    def test_categ_id_groups_lines_by_category(self):
        """Tarea 13: mismo criterio que en test_preparation_interval_
        report.py, pero contra el _table_query propio de este modelo
        (LEFT JOIN product_template distinto, línea en vez de
        intervalo) — se prueba acá también en vez de asumir que
        "ya se probó en el otro modelo" cubre este join."""
        categ_a = self.env['product.category'].create({'name': 'Categoría A (test op)'})
        categ_b = self.env['product.category'].create({'name': 'Categoría B (test op)'})
        self.product_weight.product_tmpl_id.categ_id = categ_a.id
        self.product_unit.product_tmpl_id.categ_id = categ_b.id

        today = self._far_today()
        session = self._session(today)
        self._line(
            session, self.product_weight, self.operator_a,
            actual_kg=3.5, done_date=fields.Datetime.now(),
        )
        self._line(
            session, self.product_unit, self.operator_a,
            actual_kg=1.0, done_date=fields.Datetime.now(),
        )

        rows = self.Report.sudo().read_group(
            [('wizard_id', '=', session.id)], ['kg:sum'],
            ['categ_id'],
        )
        by_categ = {r['categ_id'][0]: r['kg'] for r in rows}
        self.assertAlmostEqual(by_categ[categ_a.id], 3.5)
        self.assertAlmostEqual(by_categ[categ_b.id], 1.0)

    def test_product_search_matches_by_name_or_internal_reference(self):
        """Mismo filter_domain declarado en el arch de este buscador
        (relativo a guapante.preparation.operator.report, no a
        product.template directo) — probado contra filas reales del
        reporte, no contra product.template suelto."""
        self.product_weight.product_tmpl_id.default_code = 'REF-TEST-13-OP'
        today = self._far_today()
        session = self._session(today)
        self._line(
            session, self.product_weight, self.operator_a,
            actual_kg=3.5, done_date=fields.Datetime.now(),
        )
        self._line(
            session, self.product_unit, self.operator_a,
            actual_kg=1.0, done_date=fields.Datetime.now(),
        )

        def search_by(term):
            return self.Report.sudo().search([
                '|',
                ('product_tmpl_id.name', 'ilike', term),
                ('product_tmpl_id.default_code', 'ilike', term),
            ])

        by_name = search_by(self.product_weight.product_tmpl_id.name)
        self.assertTrue(
            all(r.product_tmpl_id == self.product_weight.product_tmpl_id
                for r in by_name)
        )
        self.assertTrue(by_name)

        by_ref = search_by('REF-TEST-13-OP')
        self.assertTrue(by_ref)
        self.assertTrue(
            all(r.product_tmpl_id == self.product_weight.product_tmpl_id
                for r in by_ref)
        )
