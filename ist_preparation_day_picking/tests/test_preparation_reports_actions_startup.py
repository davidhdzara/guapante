# -*- coding: utf-8 -*-
"""Fix urgente de read_group (Tech Lead, 2026-11-04) — además del fix
puntual (preparation_interval_report.py: el parámetro se llamaba
`fields_list`, el cliente llama por kwargs con `fields=`), test de
ARRANQUE de las 4 acciones del menú Reportes (Tarea 3, Tech Lead/
David, 2026-11-05: se quitó "Productos más solicitados" — quedan
operario + los 3 de tiempo): get_views() de cada
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

    def test_operator_report_graph_groupby_order_is_date_then_employee(self):
        """Tarea 12.0 (Tech Lead/David, 2026-11-05) — BUG: en Odoo 18 el
        gráfico usa el groupBy ACTIVO del buscador cuando hay algún
        search_default_group_* (graph_model.js:_buildMetaData,
        "groupBy.length ? groupBy : this.initialGroupBy") — el orden de
        <field> del arch del gráfico es solo un fallback que nunca se
        usa mientras haya defaults activos. Ese orden activo lo decide
        el orden de las claves search_default_* en el contexto de la
        acción (search_model.js:_extractSearchDefaultsFromGlobalContext
        itera con for..in, que preserva orden de inserción) — por eso
        hace falta fijar 'search_default_group_date_day' ANTES de
        'search_default_group_employee' en el contexto, no solo en el
        arch. Este test lee exactamente eso (contexto + arch del
        buscador), sin levantar navegador."""
        Action = self.env.ref(
            'ist_preparation_day_picking.action_preparation_operator_report'
        )
        context = safe_eval(Action.context or '{}')
        search_defaults = [
            key for key in context
            if key.startswith('search_default_group_')
        ]
        self.assertEqual(
            search_defaults,
            ['search_default_group_date_day', 'search_default_group_employee'],
            f'Orden de claves search_default_group_* en el contexto: '
            f'{search_defaults!r} — debe ser fecha antes de operario '
            f'para que el gráfico abra con eje=fecha, leyenda=operario.',
        )

        search_arch = Action.search_view_id.arch
        root = ET.fromstring(search_arch)
        filter_names = [f.get('name') for f in root.findall('.//filter')]
        self.assertLess(
            filter_names.index('group_date_day'),
            filter_names.index('group_employee'),
            f'Orden de <filter> en el buscador: {filter_names!r} — '
            f'"group_date_day" debe declararse antes que "group_employee" '
            f'(consistencia con el contexto, mismo criterio de orden).',
        )

        graph_views = self.env[Action.res_model].get_views(
            [(False, 'graph')]
        )
        graph_root = ET.fromstring(graph_views['views']['graph']['arch'])
        graph_fields = [f.get('name') for f in graph_root.findall('./field')]
        self.assertEqual(
            graph_fields[:2], ['date', 'employee_id'],
            f'Orden de <field> en el arch del gráfico: {graph_fields!r} — '
            f'fecha antes de operario, para que el fallback (sin ningún '
            f'search_default activo) también quede correcto.',
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
