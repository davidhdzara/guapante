# -*- coding: utf-8 -*-
"""Fix urgente de read_group (Tech Lead, 2026-11-04) — además del fix
puntual (preparation_interval_report.py: el parámetro se llamaba
`fields_list`, el cliente llama por kwargs con `fields=`), test de
ARRANQUE de las acciones del menú Reportes (Tarea 3, Tech Lead/David,
2026-11-05: se quitó "Productos más solicitados" — quedaban 4;
Tarea 12, 2026-11-05: se agregó "Tiempo por operario" — son 5):
get_views() de cada
vista declarada MÁS una llamada de read_group/web_read_group con los
defaults REALES de pivote (arch `type="row"/"col"/"measure"`,
sobreescritos por `pivot_row_groupby`/`pivot_column_groupby`/
`pivot_measures` del contexto de la acción cuando los hay — exactamente
lo que el pivote del cliente usaría al abrir) por el MISMO camino de
kwargs que usa el navegador (`odoo.api.call_kw`, nunca posicional).

El bug real (David, "Tiempo por producto" revienta) solo se veía por
este camino — un test que llama `.read_group(domain, fields, groupby)`
posicional (como ya hacían los tests existentes de los 3 reportes)
nunca lo iba a notar. Esto cubre las 4 acciones, no solo la que David
probó primero — un error de arranque igual en otro reporte no debe
esperar a que alguien lo abra a mano."""
import xml.etree.ElementTree as ET

from odoo.api import call_kw
from odoo.tests.common import tagged
from odoo.tools.safe_eval import safe_eval

from .test_preparation_day_product_claim import TestPreparationDayProductClaim

REPORT_ACTION_XMLIDS = [
    'ist_preparation_day_picking.action_preparation_operator_report',
    'ist_preparation_day_picking.action_preparation_interval_report_2',
    'ist_preparation_day_picking.action_preparation_interval_report_3',
    'ist_preparation_day_picking.action_preparation_interval_report_4',
    'ist_preparation_day_picking.action_preparation_interval_report_5',
]


@tagged('post_install', '-at_install')
class TestPreparationReportsActionsStartup(TestPreparationDayProductClaim):

    def _pivot_defaults(self, res_model, pivot_arch, context):
        """(groupby, measure_specs) a partir del arch del pivote
        (type="row"/"col"/"measure"), sobreescritos por el contexto de
        la acción cuando trae pivot_row_groupby/pivot_column_groupby/
        pivot_measures — mismo criterio de prioridad que usa el
        pivote real del cliente (contexto gana sobre el arch).
        measure_specs ya trae el sufijo ':aggregator' que el CAMPO
        declara en Python (nunca el arch, que no lo dice) — igual que
        arma orm.readGroup en el cliente."""
        root = ET.fromstring(pivot_arch)
        row = [f.get('name') for f in root.findall(".//field[@type='row']")]
        col = [f.get('name') for f in root.findall(".//field[@type='col']")]
        measures = [
            f.get('name') for f in root.findall(".//field[@type='measure']")
        ]
        row = context.get('pivot_row_groupby', row)
        col = context.get('pivot_column_groupby', col)
        measures = context.get('pivot_measures', measures)
        Model = self.env[res_model]
        measure_specs = [
            f'{name}:{Model._fields[name].aggregator or "sum"}'
            for name in measures
        ]
        groupby = list(row) + [g for g in col if g not in row]
        return groupby, measure_specs

    def test_get_views_and_pivot_defaults_do_not_crash(self):
        for action_xmlid in REPORT_ACTION_XMLIDS:
            with self.subTest(action=action_xmlid):
                Action = self.env.ref(action_xmlid)
                res_model = Action.res_model
                context = safe_eval(Action.context or '{}')
                domain = safe_eval(Action.domain or '[]')
                Model = self.env[res_model].sudo()

                views = Model.get_views([
                    (False, 'list'), (False, 'pivot'),
                    (False, 'graph'), (False, 'search'),
                ])
                self.assertIn('pivot', views['views'])
                self.assertIn('graph', views['views'])
                pivot_arch = views['views']['pivot']['arch']

                groupby, measure_specs = self._pivot_defaults(
                    res_model, pivot_arch, context,
                )
                self.assertTrue(
                    measure_specs,
                    f'{action_xmlid}: el pivote no declaró ninguna '
                    'medida — revisar el arch/contexto.',
                )

                # Mismo camino de kwargs que el pivote real del
                # cliente (orm.readGroup → call_kw(model, 'read_group',
                # [], {domain, fields, groupby, lazy})).
                call_kw(
                    Model, 'read_group', [],
                    {
                        'domain': domain, 'fields': measure_specs,
                        'groupby': groupby, 'lazy': False,
                    },
                )
                # Y el camino de lista agrupada con fila de total
                # (orm.webReadGroup → web_read_group).
                call_kw(
                    Model, 'web_read_group', [],
                    {
                        'domain': domain, 'fields': measure_specs,
                        'groupby': groupby[:1], 'lazy': False,
                    },
                )

    def test_graph_is_the_default_view_on_all_report_actions(self):
        """Tarea 3 (Tech Lead/David, 2026-11-05): vista gráfica por
        defecto en los 4 reportes — view_mode debe empezar por
        'graph', no 'pivot'/'list'."""
        for action_xmlid in REPORT_ACTION_XMLIDS:
            with self.subTest(action=action_xmlid):
                Action = self.env.ref(action_xmlid)
                self.assertTrue(
                    Action.view_mode.startswith('graph'),
                    f'{action_xmlid}: view_mode={Action.view_mode!r}',
                )

    def _action_view_id(self, action, view_mode):
        """El view_id REAL que el cliente usaría para este modo —
        resuelto desde action.views (ir.actions.act_window._compute_
        views, que federa view_ids/view_mode/view_id), NUNCA
        adivinado con get_views([(False, view_mode)]) directo sobre el
        modelo: eso ignora cualquier ir.actions.act_window.view
        explícito y siempre cae al default del MODELO (el de menor
        id), que es justo el bug que estos tests deben detectar si
        reaparece."""
        for view_id, mode in action.views:
            if mode == view_mode:
                return view_id
        return False

    def test_each_action_resolves_its_own_graph_view_explicitly(self):
        """Tarea 12 (Tech Lead/David, 2026-11-05): desde que existe el
        gráfico propio del Reporte 2 ("Tiempo por operario", línea por
        jornada/operario), el modelo guapante.preparation.interval.
        report tiene varias vistas gráfico — sin un view_id explícito
        por acción (ir.actions.act_window.view, agregado en este mismo
        commit para las acciones del modelo), get_views() podría
        resolver cualquiera por un criterio implícito. Este test
        confirma que cada acción abre EXACTAMENTE la que le
        corresponde, no la de otro reporte por accidente.

        Tarea 14 (Tech Lead/David, 2026-11-05): Reportes 4 y 5 suman
        su PROPIA vista gráfico cada uno (antes compartían la bar/
        product_tmpl_id del Reporte 3) — ordenadas DESC por la razón
        (ver view_preparation_interval_report_kg_graph/_box_graph)."""
        expectations = {
            'ist_preparation_day_picking.action_preparation_interval_report_2': (
                'line', ['date', 'employee_id'],
            ),
            'ist_preparation_day_picking.action_preparation_interval_report_3': (
                'bar', ['product_tmpl_id'],
            ),
            'ist_preparation_day_picking.action_preparation_interval_report_4': (
                'bar', ['product_tmpl_id'],
            ),
            'ist_preparation_day_picking.action_preparation_interval_report_5': (
                'bar', ['product_tmpl_id'],
            ),
        }
        for action_xmlid, (expected_type, expected_groupby) in expectations.items():
            with self.subTest(action=action_xmlid):
                Action = self.env.ref(action_xmlid)
                graph_view_id = self._action_view_id(Action, 'graph')
                views = self.env[Action.res_model].get_views(
                    [(graph_view_id, 'graph')]
                )
                root = ET.fromstring(views['views']['graph']['arch'])
                self.assertEqual(root.get('type'), expected_type)
                group_fields = [
                    f.get('name') for f in root.findall('field')
                    if f.get('type') != 'measure'
                ]
                self.assertEqual(group_fields, expected_groupby)

    def _assert_graph_groupby_order_is_date_then_employee(self, action_xmlid):
        """Tarea 12.0 (Tech Lead/David, 2026-11-05) — BUG: en Odoo 18 el
        gráfico usa el groupBy ACTIVO del buscador cuando hay algún
        search_default_group_* (graph_model.js:_buildMetaData,
        "groupBy.length ? groupBy : this.initialGroupBy") — el orden de
        <field> del arch del gráfico es solo un fallback que nunca se
        usa mientras haya defaults activos.

        El orden real de ese groupBy activo lo decide el defaultRank de
        cada filtro (search_arch_parser.js: defaultRank = el VALOR del
        search_default_* si es number, si no 100), ordenado en
        search_model.js:_activateDefaultSearchItems con Array.sort
        (estable desde ES2019) — NO el orden de las claves del
        contexto ni, por sí solo, el orden de los <filter> del arch
        (eso solo desempata entre rangos IGUALES, que es justo lo que
        había ANTES de este fix: 1 y 1 para el Reporte 1). Por eso el
        fix real es dar rangos EXPLÍCITOS y distintos: date_day=1,
        employee=2 — así no depende de ningún desempate implícito.
        Esta verifica los valores (rangos), no el orden de inserción
        de las claves, sin levantar navegador."""
        Action = self.env.ref(action_xmlid)
        context = safe_eval(Action.context or '{}')
        self.assertLess(
            context['search_default_group_date_day'],
            context['search_default_group_employee'],
            f'{action_xmlid}: rango (defaultRank) de '
            f'search_default_group_date_day '
            f'({context["search_default_group_date_day"]!r}) debe ser '
            f'MENOR que el de search_default_group_employee '
            f'({context["search_default_group_employee"]!r}) — Odoo '
            f'activa los filtros default ordenados por ese valor '
            f'(Array.sort estable), no por el orden de las claves.',
        )

        graph_view_id = self._action_view_id(Action, 'graph')
        graph_views = self.env[Action.res_model].get_views(
            [(graph_view_id, 'graph')]
        )
        graph_root = ET.fromstring(graph_views['views']['graph']['arch'])
        graph_fields = [f.get('name') for f in graph_root.findall('./field')]
        self.assertEqual(
            graph_fields[:2], ['date', 'employee_id'],
            f'{action_xmlid}: orden de <field> en el arch del gráfico: '
            f'{graph_fields!r} — fecha antes de operario, para que el '
            f'fallback (sin ningún search_default activo) también '
            f'quede correcto.',
        )

    def test_operator_report_graph_groupby_order_is_date_then_employee(self):
        self._assert_graph_groupby_order_is_date_then_employee(
            'ist_preparation_day_picking.action_preparation_operator_report'
        )

    def test_interval_report_2_graph_groupby_order_is_date_then_employee(self):
        self._assert_graph_groupby_order_is_date_then_employee(
            'ist_preparation_day_picking.action_preparation_interval_report_2'
        )

    def test_product_demand_report_was_fully_removed(self):
        """Tarea 3 (Tech Lead/David, 2026-11-05): "Productos más
        solicitados" se quitó completo — modelo, acción y menú no
        deben existir. Guarda de regresión contra un revert parcial
        (ej. manifest/ACL quitados pero el modelo Python olvidado)."""
        self.assertNotIn(
            'guapante.preparation.product.demand.report', self.env.registry,
        )
        self.assertFalse(self.env.ref(
            'ist_preparation_day_picking.action_preparation_product_demand_report',
            raise_if_not_found=False,
        ))
        self.assertFalse(self.env.ref(
            'ist_preparation_day_picking.menu_preparation_product_demand_report',
            raise_if_not_found=False,
        ))
