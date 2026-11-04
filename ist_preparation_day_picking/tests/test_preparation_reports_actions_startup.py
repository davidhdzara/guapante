# -*- coding: utf-8 -*-
"""Fix urgente de read_group (Tech Lead, 2026-11-04) — además del fix
puntual (preparation_interval_report.py: el parámetro se llamaba
`fields_list`, el cliente llama por kwargs con `fields=`), test de
ARRANQUE de las 5 acciones del menú Reportes: get_views() de cada
vista declarada MÁS una llamada de read_group/web_read_group con los
defaults REALES de pivote (arch `type="row"/"col"/"measure"`,
sobreescritos por `pivot_row_groupby`/`pivot_column_groupby`/
`pivot_measures` del contexto de la acción cuando los hay — exactamente
lo que el pivote del cliente usaría al abrir) por el MISMO camino de
kwargs que usa el navegador (`odoo.api.call_kw`, nunca posicional).

El bug real (David, "Tiempo por producto" revienta) solo se veía por
este camino — un test que llama `.read_group(domain, fields, groupby)`
posicional (como ya hacían los tests existentes de los 3 reportes)
nunca lo iba a notar. Esto cubre las 5 acciones, no solo la que David
probó primero — un error de arranque igual en otro reporte no debe
esperar a que alguien lo abra a mano."""
import xml.etree.ElementTree as ET

from odoo.api import call_kw
from odoo.tests.common import tagged
from odoo.tools import safe_eval

from .test_preparation_day_product_claim import TestPreparationDayProductClaim

REPORT_ACTION_XMLIDS = [
    'ist_preparation_day_picking.action_preparation_operator_report',
    'ist_preparation_day_picking.action_preparation_product_demand_report',
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
