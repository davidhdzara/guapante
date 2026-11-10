# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import SQL

from odoo.addons.ist_preparation_day.models.const_preparation import (
    REPORTS_START_DATE_DEFAULT,
    REPORTS_START_DATE_PARAM_KEY,
)


class PreparationOperatorReport(models.Model):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — Reporte 1
    "Pickings por operario": UNA fila por línea de Picking ya
    Terminada (is_done, con quién y cuándo la terminó), nunca por
    intervalo — David decidió que "cantidad de pickings" = líneas
    hechas, no tiempo (eso lo cubren los reportes 3/4/5, modelo
    aparte). `_table_query` (no `init()`/CREATE VIEW — patrón moderno
    de Odoo 18, ver account.invoice.report del propio core): la
    consulta corre en vivo en cada lectura, nunca hay que recrearla
    en un -u.

    Filtro de fecha (reports_start_date, en 1/3/4/5 — NUNCA en 2):
    leído DENTRO de la propia consulta vía subselect contra
    ir_config_parameter (ver const_preparation.py) — cero interpolación
    desde Python, un cambio del parámetro en Ajustes se refleja sin
    reinstalar nada.

    employee_id SIN filtro de active (Fase 2, punto 4, David
    2026-11-04): un empleado archivado sigue siendo historia real —
    nunca se excluye de este reporte.

    ESPEJO Inventario→Preparación (David/Tech Lead, 2026-11-05): una
    línea cerrada automáticamente porque su PICK se validó directo
    desde Inventario (sin pasar por el tablet ni por Productos) nunca
    tiene done_by_employee_id (no hubo operario) — el filtro WHERE
    done_by_employee_id IS NOT NULL de abajo ya la excluye de este
    reporte sin necesitar ningún cambio adicional: "Pickings por
    operario" solo cuenta trabajo real de un operario identificado.
    """
    _name = 'guapante.preparation.operator.report'
    _description = 'Picking — Reporte 1: pickings por operario'
    _auto = False
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one(
        'hr.employee', string='Operario', readonly=True,
        # Tarea 7 (Tech Lead/David, 2026-11-05) — regla ya
        # implementada en el write() de guapante.preparation.day.line
        # (done_by_employee_id): es siempre quien efectivamente pesó/
        # cerró la línea, nunca el dueño nominal del claim. Un
        # administrador/ayudante que pesa un producto que no es suyo
        # (E3, cualquier operario con PIN puede) SE LLEVA el crédito de
        # la línea acá — a propósito, ver duration_s en el Reporte 3/4/5
        # para la otra mitad de la regla (tiempo).
        help=(
            'Quien efectivamente pesó/cerró esta línea — no '
            'necesariamente el dueño asignado del producto. Si un '
            'administrador o ayudante pesa una línea que no es suya '
            '(cualquier operario con PIN puede), el crédito de ESTA '
            'línea queda con quien la pesó. Ver el Reporte 3/4/5 '
            '(Tiempo trabajado) para el tiempo: ese pesaje puntual no '
            'suma tiempo a nadie, ni a quien pesó ni al dueño.'
        ),
    )
    wizard_id = fields.Many2one('guapante.preparation.day', string='Sesión', readonly=True)
    date = fields.Date(string='Jornada', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Producto', readonly=True)
    # Tarea 13 (Tech Lead/David, 2026-11-05): categoría ESTÁNDAR del
    # catálogo (product.template.categ_id), nada propio de Guapante —
    # para agrupar/filtrar en el buscador, igual que David ya agrupa/
    # filtra por operario o producto.
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    # Integer 0/1 por fila, aggregator='sum' (default de Integer):
    # suma = conteo de líneas que cumplen la condición — la técnica
    # estándar de los reportes _auto=False de Odoo para un "conteo
    # condicional" sin que el pivote tenga que promediar nada fila a
    # fila (acá no hay ninguna razón, solo conteos y sumas simples,
    # todas agregables sin sesgo).
    line_done = fields.Integer(
        string='Líneas hechas', readonly=True, aggregator='sum',
        help='Líneas Terminadas con kg > 0 (realmente pesadas).',
    )
    line_zero = fields.Integer(
        string='Líneas en 0', readonly=True, aggregator='sum',
        help='Líneas Terminadas sin peso (E7, "sin stock" — Listo con un clic).',
    )
    # Tech Lead (2026-11-04): "cajas distintas (COUNT DISTINCT
    # wizard_id+daily_sequence)" — una caja es la combinación
    # sesión+# del día, NUNCA la línea (un pedido con 2 productos en
    # la misma caja son 2 líneas pero 1 sola caja). box_count es un
    # Char con la clave compuesta "wizard_id/daily_sequence" y
    # aggregator='count_distinct' (genérico, cualquier tipo de campo
    # — ver fields.py) para que el pivote cuente cajas, no líneas.
    box_count = fields.Char(
        string='Cajas', readonly=True, aggregator='count_distinct',
        help='Cajas Terminadas distintas (sesión + # del día; pesadas + en 0).',
    )
    kg = fields.Float(
        string='Kg', readonly=True, aggregator='sum', digits=(10, 3),
    )

    _depends = {
        'guapante.preparation.day.line': [
            'wizard_id', 'product_id', 'done_by_employee_id', 'done_date',
            'actual_kg', 'daily_sequence',
        ],
        'guapante.preparation.day': ['date'],
        'product.template': ['categ_id'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL(
            '''
            SELECT
                line.id AS id,
                line.done_by_employee_id AS employee_id,
                line.wizard_id AS wizard_id,
                pd.date AS date,
                line.product_id AS product_tmpl_id,
                pt.categ_id AS categ_id,
                CASE WHEN line.actual_kg > 0 THEN 1 ELSE 0 END AS line_done,
                CASE WHEN line.actual_kg <= 0 THEN 1 ELSE 0 END AS line_zero,
                (line.wizard_id::text || '/' || line.daily_sequence::text) AS box_count,
                line.actual_kg AS kg
            FROM guapante_preparation_day_line line
            JOIN guapante_preparation_day pd ON pd.id = line.wizard_id
            LEFT JOIN product_template pt ON pt.id = line.product_id
            WHERE line.done_by_employee_id IS NOT NULL
              AND line.done_date >= COALESCE(
                  (SELECT value::timestamp FROM ir_config_parameter
                   WHERE key = %s),
                  %s::timestamp
              )
            ''',
            REPORTS_START_DATE_PARAM_KEY, REPORTS_START_DATE_DEFAULT,
        )
