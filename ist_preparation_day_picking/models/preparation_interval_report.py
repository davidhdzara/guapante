# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import SQL

from odoo.addons.ist_preparation_day.models.const_preparation import (
    REPORTS_START_DATE_DEFAULT,
    REPORTS_START_DATE_PARAM_KEY,
)

# Campos que read_group() fuerza a sumar para poder recalcular una
# razón ponderada (ver el método, abajo) — nombre del campo en el
# modelo -> nombre del campo cuya suma hace de denominador.
_RATIO_MEASURES = {
    'time_per_kg_s': 'kg_done',
    'time_per_box_s': 'lines_done',
}


class PreparationIntervalReport(models.Model):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — modelo compartido
    por los Reportes 3 ("Tiempo por producto"), 4 ("Tiempo por kilo")
    y 5 ("Tiempo por caja") — UNA fila por guapante.preparation.interval
    YA CERRADO (end_dt IS NOT NULL — nunca uno abierto: ver la
    definición de "reportes" acordada en el commit 3b/7, los reportes
    solo cuentan tiempo que ya terminó de medirse). Cada reporte es su
    propia acción (ir.actions.act_window, este mismo commit) con
    domain/contexto de agrupación distintos sobre ESTE modelo — los 3
    menús comparten modelo y vista, no comparten default.

    `_table_query` (patrón moderno de Odoo 18, no `init()`/CREATE VIEW
    — ver account.invoice.report del propio core): la consulta corre
    en vivo en cada lectura.

    Filtro de fecha reports_start_date dentro de la propia consulta
    (ver preparation_operator_report.py para el mismo patrón con
    subselect contra ir_config_parameter, cero interpolación)."""
    _name = 'guapante.preparation.interval.report'
    _description = 'Picking — Reportes 3/4/5: tiempo por intervalo'
    _auto = False
    _order = 'date desc, product_tmpl_id'

    employee_id = fields.Many2one('hr.employee', string='Operario', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Producto', readonly=True)
    wizard_id = fields.Many2one('guapante.preparation.day', string='Sesión', readonly=True)
    date = fields.Date(string='Jornada', readonly=True)
    kind = fields.Selection(
        selection=[('working', 'Trabajando'), ('stopped', 'Detenido')],
        string='Tipo', readonly=True,
    )
    # Reporte 3 ("tiempo en proceso"/"tiempo detenido"): UNA sola
    # medida summable — pivoteada con columnas=kind (default de la
    # acción del reporte 3) da los dos totales lado a lado, nunca dos
    # campos separados para lo mismo.
    duration_s = fields.Integer(string='Tiempo (s)', readonly=True, aggregator='sum')
    # Mismo dato que arriba, expuesto aparte con aggregator='avg'
    # ("tiempo medio por visita") — un Float/Integer tiene UN solo
    # aggregator fijo por campo en Odoo, así que la única forma nativa
    # de ofrecer sum Y avg de la MISMA columna como medidas distintas
    # es declarar dos campos. A diferencia de time_per_kg_s/
    # time_per_box_s (abajo), promediar duración entre visitas es
    # estadísticamente válido sin ponderar (es un promedio de la MISMA
    # unidad, no una razón de dos sumas distintas) — no hace falta
    # read_group() acá.
    duration_avg_s = fields.Integer(string='Tiempo medio (s)', readonly=True, aggregator='avg')
    kg_done = fields.Float(string='Kg', readonly=True, aggregator='sum', digits=(10, 3))
    lines_done = fields.Integer(string='Líneas', readonly=True, aggregator='sum')
    # NULL cuando no aplica (kind='stopped', o 'working' sin ningún
    # pesaje) — AVG de Postgres ignora NULL automáticamente, así que
    # "solo working con primer pesaje" (Tech Lead) sale solo, sin
    # ningún filtro adicional en la vista.
    time_to_first_weigh_s = fields.Integer(
        string='Tiempo hasta 1er pesaje (s)', readonly=True, aggregator='avg',
    )
    # "tiempo sin líneas" (Reporte 3): tiempo de visitas 'working' que
    # no terminaron NINGUNA línea (lines_done=0) — tiempo gastado sin
    # producción real, que las razones de 4/5 excluyen aparte (ver
    # _RATIO_MEASURES y el domain de esos reportes, en la acción).
    time_without_lines_s = fields.Integer(
        string='Tiempo sin líneas (s)', readonly=True, aggregator='sum',
    )
    # RAZONES (segundos ÷ kg o ÷ líneas) — NUNCA sumar ni promediar
    # fila a fila (sesga a favor de las visitas cortas, Tech Lead
    # 2026-11-04): el valor por fila de acá abajo es solo lo que
    # vería un AVG nativo sin el override; read_group() (abajo) lo
    # intercepta y lo reemplaza por SUM(duration_s)/SUM(denominador)
    # ya agregados, en CUALQUIER agrupación del pivote. NULL cuando
    # no aplica (kind='stopped', o denominador en 0) — el domain de
    # las acciones de 4/5 ya filtra a 'working' con lines_done>0 (y
    # kg_done>0 para 4), así que en la práctica esto nunca pivotea
    # sobre filas NULL, pero queda defendido de todas formas.
    time_per_kg_s = fields.Float(
        string='Seg/kg', readonly=True, aggregator='avg', digits=(10, 3),
    )
    time_per_box_s = fields.Float(
        string='Seg/caja', readonly=True, aggregator='avg', digits=(10, 3),
    )

    _depends = {
        'guapante.preparation.interval': [
            'employee_id', 'product_tmpl_id', 'wizard_id', 'kind', 'end_dt',
            'start_dt', 'duration_s', 'kg_done', 'lines_done', 'first_weigh_dt',
        ],
        'guapante.preparation.day': ['date'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL(
            '''
            SELECT
                pi.id AS id,
                pi.employee_id AS employee_id,
                pi.product_tmpl_id AS product_tmpl_id,
                pi.wizard_id AS wizard_id,
                pd.date AS date,
                pi.kind AS kind,
                pi.duration_s AS duration_s,
                pi.duration_s AS duration_avg_s,
                pi.kg_done AS kg_done,
                pi.lines_done AS lines_done,
                CASE
                    WHEN pi.kind = 'working' AND pi.first_weigh_dt IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (pi.first_weigh_dt - pi.start_dt))::int
                    ELSE NULL
                END AS time_to_first_weigh_s,
                CASE
                    WHEN pi.kind = 'working' AND pi.lines_done = 0
                    THEN pi.duration_s ELSE 0
                END AS time_without_lines_s,
                CASE
                    WHEN pi.kind = 'working' AND pi.kg_done > 0
                    THEN pi.duration_s / pi.kg_done ELSE NULL
                END AS time_per_kg_s,
                CASE
                    WHEN pi.kind = 'working' AND pi.lines_done > 0
                    THEN pi.duration_s::float / pi.lines_done ELSE NULL
                END AS time_per_box_s
            FROM guapante_preparation_interval pi
            JOIN guapante_preparation_day pd ON pd.id = pi.wizard_id
            WHERE pi.end_dt IS NOT NULL
              AND pi.start_dt >= COALESCE(
                  (SELECT value::timestamp FROM ir_config_parameter
                   WHERE key = %s),
                  %s::timestamp
              )
            ''',
            REPORTS_START_DATE_PARAM_KEY, REPORTS_START_DATE_DEFAULT,
        )

    @api.model
    def read_group(self, domain, fields_list, groupby, offset=0, limit=None,
                   orderby=False, lazy=True):
        """Razón ponderada correcta para time_per_kg_s/time_per_box_s
        (Tech Lead, 2026-11-04) — mismo patrón que price_average en
        account.invoice.report (Odoo core, verificado leyendo su
        read_group() en el host): cuando el cliente pide
        '<medida>:avg', se fuerza también 'duration_s:sum' y el
        denominador correspondiente (':sum'), se llama a
        super().read_group() para obtener las SUMAS reales de cada
        grupo, y se reemplaza el valor de la razón por
        SUM(duration_s)/SUM(denominador) ya agregados — NUNCA el
        promedio de razones por fila (eso sesga a favor de las
        visitas cortas/con poco volumen). Los campos que esto agregó
        por su cuenta se sacan del resultado si el cliente no los
        había pedido como medida propia (condición explícita de Tech
        Lead).

        Cubre pivot (orm.readGroup → read_group) Y listas agrupadas
        con su fila de total (orm.webReadGroup → web_read_group →
        _web_read_group → read_group — _web_read_group es un simple
        passthrough a read_group en este Odoo, verificado leyendo
        addons/web/models/models.py del propio core: NO hace falta
        una segunda sobreescritura para el camino de listas/gráficos,
        una sola cubre los dos). El groupby vacío (fila de total
        general) pasa por el mismo código sin ningún caso especial —
        read_group con groupby=[] ya devuelve un solo grupo agregado
        por diseño del método base."""
        requested = {
            name: denom for name, denom in _RATIO_MEASURES.items()
            if f'{name}:avg' in fields_list
        }
        if not requested:
            return super().read_group(
                domain, fields_list, groupby, offset, limit, orderby, lazy,
            )

        forced_fields = list(fields_list)
        forced_names = set()
        for denom in {'duration_s', *requested.values()}:
            spec = f'{denom}:sum'
            if spec not in forced_fields:
                forced_fields.append(spec)
                forced_names.add(denom)

        res = super().read_group(
            domain, forced_fields, groupby, offset, limit, orderby, lazy,
        )
        for data in res:
            for name, denom in requested.items():
                denom_value = data.get(denom) or 0
                data[name] = (
                    data.get('duration_s', 0) / denom_value if denom_value else 0.0
                )
            for forced_name in forced_names:
                data.pop(forced_name, None)
        return res
