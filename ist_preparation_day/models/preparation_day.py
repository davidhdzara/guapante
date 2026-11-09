# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

import pytz
from psycopg2 import errors as pg_errors

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from .const_preparation import get_active_prep_operator_id

_logger = logging.getLogger(__name__)

# Errores transitorios de Postgres que Odoo reintenta a nivel de petición
# completa (ver PG_CONCURRENCY_EXCEPTIONS_TO_RETRY en
# odoo/service/model.py — mismo criterio, no inventado). Nunca deben
# quedar atrapados por un `except Exception` propio: si lo hacen, el
# reintento de Odoo nunca pasa y el lock de más abajo (FOR UPDATE) pierde
# su efecto — justo el caso de concurrencia que debía resolver.
_PG_CONCURRENCY_ERRORS = (
    pg_errors.LockNotAvailable,
    pg_errors.SerializationFailure,
    pg_errors.DeadlockDetected,
)

# Zona horaria por defecto para operaciones de Guapante.
_DEFAULT_TZ = 'America/Bogota'

# Hora de corte para decidir a qué día se programa una orden NUEVA al
# confirmarse (parámetro de sistema, no hardcodeada, para poder
# cambiarla sin tocar código ni redesplegar — Ajustes > Técnico >
# Parámetros del Sistema). NO define el rango de una jornada ya creada
# — Regla de la jornada (David, 2026-10-29): la jornada de la fecha D
# es el día calendario D completo en hora Bogotá, sin corte; lo que
# manda es scheduled_date del PICK, sin importar la hora. Por eso
# _get_cutoff_time ya no la usan _date_to_utc_range ni
# _utc_datetime_to_session_date — queda disponible para conectarla
# más adelante en theme_guapante.action_confirm (que hoy decide el día
# de una orden nueva con un 00:30 fijo, independiente de este
# parámetro), en un cambio aparte y chico que Tech Lead dejó pendiente.
_CUTOFF_PARAM_KEY = 'ist_preparation_day.cutoff_time'
_CUTOFF_DEFAULT_TIME = '00:30'


def _get_cutoff_time(env) -> tuple:
    """Hora de corte configurable (hour, minute) para decidir a qué
    día se programa una orden nueva al confirmarse — ver
    _CUTOFF_PARAM_KEY. No define la ventana de una jornada."""
    raw = env['ir.config_parameter'].sudo().get_param(
        _CUTOFF_PARAM_KEY, default=_CUTOFF_DEFAULT_TIME,
    )
    try:
        hour_str, minute_str = raw.split(':')
        return int(hour_str), int(minute_str)
    except (ValueError, AttributeError):
        _logger.warning(
            'Guapante: parámetro %s inválido (%r), usando default %s',
            _CUTOFF_PARAM_KEY, raw, _CUTOFF_DEFAULT_TIME,
        )
        hour_str, minute_str = _CUTOFF_DEFAULT_TIME.split(':')
        return int(hour_str), int(minute_str)


# Cotas configurables (parámetro de sistema) de cuántas sesiones y
# órdenes puede tocar el cron de respaldo en una sola corrida — plan de
# carga automática, paso e4 (2026-10-30). Para que nunca monopolice el
# worker aunque haya mucho atrasado; si hay más, queda para la próxima
# corrida (cada 10 min, ver data/ir_cron_repair_sessions.xml).
_CRON_MAX_SESSIONS_PARAM_KEY = 'ist_preparation_day.cron_repair_max_sessions'
_CRON_MAX_SESSIONS_DEFAULT = 20
_CRON_MAX_ORDERS_PARAM_KEY = 'ist_preparation_day.cron_repair_max_orders'
_CRON_MAX_ORDERS_DEFAULT = 200


def _get_cron_repair_limits(env) -> tuple:
    """(max_sesiones, max_órdenes) por corrida del cron de respaldo —
    ver las constantes _CRON_MAX_*_PARAM_KEY arriba."""
    IrConfigParameter = env['ir.config_parameter'].sudo()

    def _parse(key, default):
        raw = IrConfigParameter.get_param(key, default=str(default))
        try:
            return int(raw)
        except (TypeError, ValueError):
            _logger.warning(
                'Guapante: parámetro %s inválido (%r), usando '
                'default %s', key, raw, default,
            )
            return default

    return (
        _parse(_CRON_MAX_SESSIONS_PARAM_KEY, _CRON_MAX_SESSIONS_DEFAULT),
        _parse(_CRON_MAX_ORDERS_PARAM_KEY, _CRON_MAX_ORDERS_DEFAULT),
    )


# Cuántos días hacia adelante (desde hoy) el cron de respaldo revisa
# para crear la sesión que falte, si ya hay pedidos elegibles — Tech
# Lead, 2026-10-31, condición 1 de la corrección (a): configurable
# como las demás cotas, nunca hacia el pasado (el rango siempre
# arranca en _current_session_date, nunca en date.today()).
_CRON_REPAIR_CREATE_DAYS_AHEAD_PARAM_KEY = (
    'ist_preparation_day.cron_repair_create_days_ahead'
)
_CRON_REPAIR_CREATE_DAYS_AHEAD_DEFAULT = 7


def _get_cron_repair_create_days_ahead(env) -> int:
    """Días hacia adelante (desde hoy) que cubre la creación
    automática de sesiones faltantes del cron de respaldo — ver
    _CRON_REPAIR_CREATE_DAYS_AHEAD_PARAM_KEY."""
    raw = env['ir.config_parameter'].sudo().get_param(
        _CRON_REPAIR_CREATE_DAYS_AHEAD_PARAM_KEY,
        default=str(_CRON_REPAIR_CREATE_DAYS_AHEAD_DEFAULT),
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        _logger.warning(
            'Guapante: parámetro %s inválido (%r), usando default %s',
            _CRON_REPAIR_CREATE_DAYS_AHEAD_PARAM_KEY, raw,
            _CRON_REPAIR_CREATE_DAYS_AHEAD_DEFAULT,
        )
        return _CRON_REPAIR_CREATE_DAYS_AHEAD_DEFAULT


# Hora de corte configurable (hora Bogotá) desde la que el TABLET de
# Picking resuelve "mañana" en vez de "hoy" — corrección #12. Vivía en
# ist_preparation_day_picking (único usuario original,
# _picking_session_date), pero se movió acá (corrección del ajuste #4,
# Tech Lead/David 2026-11-01) porque la limpieza de sesiones vacías del
# cron de respaldo (más abajo, en ESTE módulo, que NO depende de
# ist_preparation_day_picking) también necesita saber si ya se pasó esa
# hora para no borrar la sesión de mañana mientras el tablet puede
# estar entrando ahí. ist_preparation_day_picking importa estas
# constantes y esta función desde acá — nunca al revés, porque
# depende de ist_preparation_day, no lo contrario. Solo afecta a dónde
# entra el tablet y a esta limpieza; NUNCA a _current_session_date del
# cron de respaldo ni al corte 00:30 de action_confirm — esos siguen
# intactos.
_PICKING_SWITCH_HOUR_PARAM_KEY = (
    'ist_preparation_day_picking.picking_switch_hour'
)
_PICKING_SWITCH_HOUR_DEFAULT = '21:00'


def _get_picking_switch_hour(env) -> tuple:
    """(hour, minute) de corte configurable para _picking_session_date
    y para la limpieza de sesiones vacías — ver
    _PICKING_SWITCH_HOUR_PARAM_KEY."""
    raw = env['ir.config_parameter'].sudo().get_param(
        _PICKING_SWITCH_HOUR_PARAM_KEY, default=_PICKING_SWITCH_HOUR_DEFAULT,
    )
    try:
        hour_str, minute_str = raw.split(':')
        hour, minute = int(hour_str), int(minute_str)
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError(f'hora/minuto fuera de rango: {raw!r}')
        return hour, minute
    except (ValueError, AttributeError):
        _logger.warning(
            'Guapante: parámetro %s inválido (%r), usando default %s',
            _PICKING_SWITCH_HOUR_PARAM_KEY, raw, _PICKING_SWITCH_HOUR_DEFAULT,
        )
        hour_str, minute_str = _PICKING_SWITCH_HOUR_DEFAULT.split(':')
        return int(hour_str), int(minute_str)


def _is_past_picking_switch_hour(env) -> bool:
    """True si la hora local (Bogotá) de 'ahora' ya pasó la hora de
    corte del tablet (_get_picking_switch_hour)."""
    tz_name = env.user.tz or _DEFAULT_TZ
    local_tz = pytz.timezone(tz_name)
    local_dt = pytz.utc.localize(fields.Datetime.now()).astimezone(local_tz)
    switch_hour, switch_minute = _get_picking_switch_hour(env)
    return (local_dt.hour, local_dt.minute) >= (switch_hour, switch_minute)


def _date_to_utc_range(env, date_val):
    """Convert a naive date into a UTC datetime range for the full
    calendar day *date_val* in the user's (or default) timezone.

    Returns (dt_start_utc, dt_end_utc) where:
      - dt_start_utc = medianoche de *date_val* en tz local → UTC
      - dt_end_utc   = medianoche de *date_val + 1 día* en tz local → UTC

    Example for America/Bogota (UTC-5):
      date_val = 2026-04-04
      → dt_start = 2026-04-04 05:00:00 UTC
      → dt_end   = 2026-04-05 05:00:00 UTC

    Mismo criterio que theme_guapante._date_to_utc_range en producción
    — Regla de la jornada (David, 2026-10-29): la jornada de la fecha
    D es el día calendario D completo, sin corte.
    """
    tz_name = env.user.tz or _DEFAULT_TZ
    local_tz = pytz.timezone(tz_name)
    naive_start = datetime.combine(date_val, time(0, 0))
    naive_end = datetime.combine(date_val + timedelta(days=1), time(0, 0))
    dt_start = local_tz.localize(naive_start).astimezone(pytz.utc).replace(tzinfo=None)
    dt_end = local_tz.localize(naive_end).astimezone(pytz.utc).replace(tzinfo=None)
    return dt_start, dt_end


def _utc_datetime_to_session_date(env, utc_dt):
    """Inversa de _date_to_utc_range: dado un datetime naive en UTC,
    determina a qué día calendario (hora local) pertenece — esa es su
    jornada, sin corte (Regla de la jornada, David 2026-10-29)."""
    tz_name = env.user.tz or _DEFAULT_TZ
    local_tz = pytz.timezone(tz_name)
    local_dt = pytz.utc.localize(utc_dt).astimezone(local_tz)
    return local_dt.date()


def _current_session_date(env):
    """Día calendario (hora local) al que pertenece 'ahora mismo'."""
    return _utc_datetime_to_session_date(env, fields.Datetime.now())


class PreparationDayLog(models.Model):
    _name = 'guapante.picking.log'
    _description = 'Log de Rendimiento de Empaque'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users',
        string='Operario',
        default=lambda self: self.env.user,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Operario identificado (PIN)',
        help=(
            'Operario físico que se identificó con su PIN en el paso de '
            'pesaje — distinto de user_id, que siempre es la cuenta '
            'compartida operacion@donguapante.com.'
        ),
        # Fase 2, punto 8 (Tech Lead, 2026-11-04): este log es historia
        # real de rendimiento, igual que done_by_employee_id — el
        # default 'set null' perdería en silencio quién fue. El mensaje
        # claro vive en hr_employee.py (ist_preparation_day).
        ondelete='restrict',
    )
    product_product_id = fields.Many2one(
        'product.product',
        string='Variante Registrada',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
    )
    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
    )
    actual_kg = fields.Float(
        string='Peso Registrado (kg)',
        digits=(10, 3),
    )
    time_taken_seconds = fields.Integer(
        string='Tiempo tomado (segs)',
        help='Tiempo entre este empaque y el anterior de la sesión.',
    )


class PreparationDayLine(models.Model):
    """One row per sale.order.line that needs preparation."""
    _name = 'guapante.preparation.day.line'
    _description = 'Línea de Preparación del Día'
    _order = 'is_done, product_product_id, order_name'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
        # Fase 2 (Tech Lead, 2026-11-04): Seq Scan confirmado en 127k-128k
        # filas (sin índice hasta hoy) — tanto el buscador de la sesión
        # como los reportes e intervalos nuevos filtran por wizard_id en
        # cada lectura. `-u` crea el índice solo, sin backfill.
        index=True,
    )
    product_id = fields.Many2one(
        'product.template',
        string='Producto',
        readonly=True,
    )
    product_product_id = fields.Many2one(
        'product.product',
        string='Variante',
        readonly=True,
    )
    product_description = fields.Char(
        string='Descripción del Producto',
        readonly=True,
    )
    packaging_name = fields.Char(
        string='Embalaje del cliente',
        readonly=True,
        help=(
            'Nombre del embalaje B2B que eligió el cliente en la '
            'tienda online (ej. Paquete 200g).'
        ),
    )
    order_name = fields.Char(string='Orden', readonly=True)
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        readonly=True,
    )
    daily_sequence = fields.Integer(
        string='# del día',
        related='sale_order_id.daily_sequence',
        store=True,
        readonly=True,
        help=(
            'Sigue en vivo el de la orden — antes era una copia fija '
            'tomada al crear la línea, y se quedaba en 0 si la orden '
            'recibía su número después de que la línea ya existiera '
            '(incidente Caja #0, 2026-10-28).'
        ),
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Línea de pedido',
        readonly=True,
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento',
        readonly=True,
    )
    main_customer_name = fields.Char(
        string='Cliente Principal',
        readonly=True,
    )
    zone_name = fields.Char(string='Zona', readonly=True)

    uom_mode = fields.Selection(
        selection=[
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='UoM cliente',
        readonly=True,
    )
    customer_qty_display = fields.Char(
        string='Pidió',
        readonly=True,
    )
    customer_uom_label = fields.Char(string='En', readonly=True)
    estimated_kg = fields.Float(
        string='Kg estimado',
        digits=(10, 3),
        readonly=True,
    )

    actual_kg = fields.Float(
        string='Peso real (kg)',
        digits=(10, 3),
        help=(
            'Solo editable para productos pedidos en Unidades. '
            'Deja en 0 para usar el kg estimado.'
        ),
    )
    needs_weighing = fields.Boolean(
        string='Requiere repesaje',
        readonly=True,
        help='True cuando el cliente pidió en Unidades y el precio es variable.',
    )

    is_done = fields.Boolean(
        string='Completado',
        default=False,
        readonly=True,
        help='Indica si esta línea ya fue pesada y validada en esta sesión.',
    )

    # Insumo de Fase 2 (Tech Lead, 2026-11-02): quién/cuándo completó
    # esta línea — se estampa en los dos únicos sitios que ponen
    # is_done=True (action_save_line_weight y
    # _register_weight_from_productos_tab, más abajo), NUNCA se pisa en
    # una corrección post-cierre (_register_weight_correction no los
    # toca), y se limpia en action_undo_line junto con is_done/
    # actual_kg. Líneas ya Terminadas antes de este cambio quedan con
    # estos campos vacíos — sin migración de relleno (David, vía Tech
    # Lead): no hay cómo reconstruir con fiabilidad quién pesó cada una
    # de las ~127k líneas históricas.
    done_by_employee_id = fields.Many2one(
        'hr.employee',
        string='Completado por',
        readonly=True,
        copy=False,
        # Fase 2, punto 4 (David, 2026-11-04): un empleado que se retira
        # es historia, nunca se borra — se archiva. ondelete='restrict'
        # (el default de un Many2one opcional es 'set null', que
        # borraría en silencio quién pesó cada línea) obliga a archivar
        # en vez de eliminar; el mensaje claro para quien lo intente
        # vive en hr_employee.py (ist_preparation_day_picking), que
        # también cubre guapante.preparation.interval.
        ondelete='restrict',
    )
    done_date = fields.Datetime(
        string='Completado el',
        readonly=True,
        copy=False,
    )

    # ESPEJO Inventario→Preparación (David/Tech Lead, 2026-11-05): el
    # hook liviano en stock.move (_action_done, ver models/stock_move.py)
    # marca esta bandera para TODA validación de un PICK con línea de
    # Preparación asociada — no evalúa ningún flag de contexto (ej.
    # 'guapante_wizard_intent'); confía en que Preparación NUNCA llama
    # button_validate/_action_done por su cuenta (ver nota de dominio
    # en models/stock_picking.py), así que este hook solo se dispara
    # de verdad cuando algo ajeno a Preparación (Inventario) validó el
    # traslado — nunca hace el reflejo en la misma transacción. El cron propio
    # (_cron_mirror_inventory_to_preparation) es quien la procesa y la
    # limpia, con su propia transacción y su propio FOR UPDATE —
    # "liviano" significa que el hook nunca puede tumbar ni demorar la
    # validación del usuario de Inventario.
    needs_inventory_mirror = fields.Boolean(
        string='Pendiente de espejo (Inventario)',
        default=False,
        copy=False,
        help=(
            'Interno: el PICK de esta línea se completó por fuera de '
            'Preparación (ej. validado directo desde Inventario) y '
            'está pendiente de que el cron la refleje aquí.'
        ),
    )

    dispatch_note = fields.Char(
        string='Nota',
        compute='_compute_dispatch_note',
        help=(
            'E7 (David/Tech Lead, 2026-11-02): el cliente pidió un '
            'producto que no hay — la línea se Termina en 0 y queda '
            'marcada así, para que el administrador la revise después.'
        ),
    )

    @api.depends('is_done', 'actual_kg')
    def _compute_dispatch_note(self):
        for line in self:
            line.dispatch_note = (
                'Sin stock — producto no disponible para despacho'
                if line.is_done and line.actual_kg == 0
                else False
            )

    @api.model
    def _get_display_qty(self, line) -> tuple:
        """Return (qty_str, uom_label) as the customer sees it.

        Args:
            line: sale.order.line recordset.

        Returns:
            Tuple of (quantity_string, unit_label).
        """
        mode = line.uom_mode or 'unit'
        qty = line.product_uom_qty
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )
        is_weight = (
            weight_categ
            and line.product_id.uom_id.category_id == weight_categ
        )

        if mode == 'g':
            return str(int(round(qty * 1000))), 'g'
        elif mode == 'kg':
            val = round(qty, 2)
            display = str(int(val)) if val == int(val) else str(val)
            return display, 'kg'
        else:
            if is_weight:
                # Usar el embalaje que eligió el cliente, no el primero
                packaging = line.product_packaging_id
                if not packaging:
                    packaging = line.product_id.packaging_ids.filtered(
                        lambda p: p.sales and p.qty > 0
                    )[:1]
                if packaging:
                    units = int(round(qty / packaging.qty))
                else:
                    units = int(qty)
            else:
                units = int(qty) if qty == int(qty) else qty
            return str(units), 'unidades'

    def action_save_line_weight_from_ui(self) -> bool:
        """Botón manual en caso de no usar Enter."""
        for line in self:
            if not line.is_done:
                line.wizard_id.action_save_line_weight(line.id)
        return False

    def write(self, vals):
        """Override para auto-guardar peso al escribir actual_kg.

        Dos orígenes posibles para una edición de actual_kg:
        - Picking (tablet compartido, widget de báscula): requiere operario
          identificado por PIN, pasa por action_save_line_weight() tal cual.
        - Pestaña Productos del formulario (edición inline en backend): el
          usuario de Odoo logueado ya identifica quién hizo el cambio, no
          exige PIN.

        El origen se distingue por el flag de contexto 'guapante_picking_flow'
        — lo inyecta la acción de Picking (ist_preparation_day_picking), no
        la presencia de un operario de PIN en la sesión. Antes de este
        cambio (Fase A, hallazgo de Tech Lead) se usaba esa presencia como
        señal de origen; con el cierre por inactividad de Picking, un
        operario cuya sesión expiró mientras pesaba dejaba de tener PIN en
        request.session y el pesaje caía silenciosamente en la rama de
        Productos — se guardaba a nombre del usuario compartido, sin
        operario y sin error, justo lo que el timeout busca evitar. Con el
        flag de contexto como señal de origen, un pesaje que sale de Picking
        sin operario activo (expiró) lanza UserError en vez de colarse por
        la otra rama.

        Edición inline de admin en la lista de líneas (Tech Lead/David,
        2026-11-02): al poner en 0 el peso de una línea ya Terminada se
        reusa action_undo_line() entero (nota + guard de sesión cerrada
        incluidos) — Python resuelve el override de Picking automáticamente
        si ese módulo está instalado. Un peso negativo se rechaza acá para
        los tres orígenes por igual (ningún flujo legítimo escribe
        negativos: ni el tablet, ni "Por Hacer", ni esta edición).

        Usa flag de contexto 'skip_auto_save' para evitar recursión
        cuando estos mismos métodos vuelven a escribir en la línea — la
        escritura interna de action_undo_line() usa ese flag, así que
        nunca reentra a este dispatch.

        Concurrencia barata (David/Tech Lead, 2026-11-02 — sin
        ownership, dos operarios pueden pesar el mismo producto a la
        vez de verdad): bloquea la(s) fila(s) con SELECT ... FOR UPDATE
        antes de leer su estado, para no decidir con un snapshot
        obsoleto. Si otro ya la pesó mientras esta escritura esperaba
        el lock, acá se ve YA hecha y se trata como corrección (con su
        nota), nunca como un segundo primer guardado. No se apoya solo
        en el reintento por error de serialización de Postgres — el
        lock explícito es lo que garantiza el orden, no una suposición
        sobre el nivel de aislamiento.

        Despacho en 0 (E7, David/Tech Lead, 2026-11-02): el cliente
        pidió un producto que no hay en bodega — el operario lo
        despacha en 0 desde el tablet y la línea queda Terminada
        igual (antes era imposible: "mayor que cero" bloqueaba el
        pesaje y 0 sobre una Terminada la devolvía a Pendiente). El 0
        completa una línea SOLO cuando viene del flujo explícito del
        tablet (contexto 'guapante_picking_flow') con un operario con
        PIN vigente — así ninguna escritura incidental de
        actual_kg=0 (reset, reubicación, reintento, código) completa
        una línea por accidente; auditado por grep contra todos los
        orígenes de escritura de actual_kg en el módulo. Una vez
        Terminada, 0 se corrige igual que cualquier otro valor
        (_register_weight_correction, nunca action_undo_line). La
        casilla "Terminado" de admin (E4) también acepta 0 directo.
        Cada línea en 0 queda marcada con 'dispatch_note' (compute,
        ver su campo) para la leyenda en la lista, y con una nota de
        chatter propia (_maybe_post_dispatch_zero_note).

        Casilla "Terminado" editable para admin (E4, David/Tech Lead,
        2026-11-02): SOLO cuando 'is_done' viene SOLO (sin 'actual_kg'
        en el mismo vals) — si vienen los dos juntos en la misma fila
        (marcar la casilla Y cambiar el peso a la vez), se trata como
        pesar/corregir: el camino de abajo (track_kg) ya decide todo
        solo con el peso, e is_done termina en el valor correcto de
        todas formas sin que haga falta este bloque. Desmarcar
        (True→False) reusa action_undo_line() entero (nota + guard de
        sesión cerrada, igual que poner el peso en 0). Marcar
        (False→True) sin tocar el peso exige actual_kg>0 YA puesto —
        nunca Terminado de un peso que no existe — y reusa
        _register_weight_from_productos_tab() entero (mismo efecto
        que lo que ya hace guardar un peso>0 sobre una Pendiente). Si
        vals trae alguna OTRA clave además de is_done (hoy no pasa
        desde la vista, pero la vía RPC/Python no lo impide), esa
        parte igual se escribe antes de retornar — is_done no absorbe
        todo el write().
        """
        track_done = (
            'is_done' in vals
            and 'actual_kg' not in vals
            and not self.env.context.get('skip_auto_save')
            and bool(self)
        )
        if track_done:
            target = bool(vals['is_done'])
            ToMarkDone = self.filtered(lambda l: target and not l.is_done)
            ToUndo = self.filtered(lambda l: not target and l.is_done)
            for line in ToMarkDone:
                # E7 (David/Tech Lead, 2026-11-02): 0 es válido acá —
                # "despacho en 0" (sin stock) también se puede marcar
                # desde la casilla de admin, igual que desde el
                # tablet. Solo un peso negativo se rechaza.
                if line.actual_kg < 0:
                    raise UserError(
                        f'{line.product_description} '
                        f'(Caja #{line.daily_sequence}): el peso no '
                        'puede ser negativo.'
                    )
            for line in ToMarkDone:
                # _register_weight_from_productos_tab() ya posta la
                # nota de "sin stock" si actual_kg quedó en 0 — no
                # duplicar la llamada acá.
                line._register_weight_from_productos_tab()
            if ToUndo:
                ToUndo.action_undo_line()
            # Tech Lead, 2026-11-02: is_done no es la única clave posible
            # en vals (un admin podría editar otro campo en la misma
            # fila/llamada) — sin esto, el resto se perdía en silencio
            # al retornar antes de llegar a super().write(vals).
            rest = {k: v for k, v in vals.items() if k != 'is_done'}
            if rest:
                super().write(rest)
            return True

        track_kg = (
            'actual_kg' in vals
            and not self.env.context.get('skip_auto_save')
            and bool(self)
        )
        old_snapshot = {}
        if track_kg:
            if vals['actual_kg'] < 0:
                raise UserError('El peso no puede ser negativo.')
            self.flush_recordset()
            self.env.cr.execute(
                'SELECT id FROM guapante_preparation_day_line '
                'WHERE id IN %s FOR UPDATE',
                (tuple(self.ids),),
            )
            self.invalidate_recordset(['actual_kg', 'is_done'])
            old_snapshot = {
                line.id: (line.actual_kg, line.is_done) for line in self
            }

        res = super().write(vals)

        if track_kg:
            is_picking_flow = bool(self.env.context.get('guapante_picking_flow'))
            operator_employee_id = (
                get_active_prep_operator_id(self.env, request.session, refresh=True)
                if request else False
            )
            if is_picking_flow and not operator_employee_id:
                raise UserError(
                    'Tu sesión de operario expiró por inactividad. '
                    'Ingresa tu NIP de nuevo.'
                )
            for line in self:
                old_kg, was_done = old_snapshot.get(line.id, (0.0, False))
                new_kg = line.actual_kg

                if was_done:
                    # E7 (David/Tech Lead, 2026-11-02): poner el peso
                    # en 0 sobre una línea ya Terminada ya NO la
                    # devuelve a Pendiente (se quitó la rama que
                    # llamaba action_undo_line() en new_kg==0) — 0 es
                    # un valor de despacho válido ("sin stock"), no un
                    # "deshacer". Cualquier cambio de valor (incluido
                    # hacia o desde 0) se trata como corrección.
                    if new_kg != old_kg:
                        # Guard de sesión cerrada para el operario
                        # (David/Tech Lead, 2026-11-02): desde Picking
                        # ya no corrige si la operación cerró — solo un
                        # administrador, desde Preparación o
                        # reabriendo la sesión. Backend (sin
                        # guapante_picking_flow) sigue permitido tal
                        # cual (1).
                        if is_picking_flow and line.wizard_id.state == 'done':
                            raise UserError(
                                'La operación está cerrada. Reabre la '
                                'sesión (botón «Reabrir Sesión») para '
                                'poder corregir esta línea.'
                            )
                        line._register_weight_correction(
                            old_kg, operator_employee_id,
                        )
                elif new_kg > 0 or (
                    new_kg == 0 and is_picking_flow and operator_employee_id
                ):
                    # E7: 0 también marca Terminado ("despacho en 0" —
                    # sin stock), pero SOLO desde el flujo explícito
                    # del tablet con un operario con PIN vigente — así
                    # ninguna escritura incidental de actual_kg=0 fuera
                    # de ese flujo completa una línea por accidente
                    # (ver auditoría de grep en el diseño aprobado).
                    if is_picking_flow:
                        line.wizard_id.action_save_line_weight(line.id)
                    else:
                        line._register_weight_from_productos_tab()
        return res

    def _sync_weight_to_stock(self, weight: float) -> None:
        """Escribe el peso real en stock.move.line y lo propaga a la cadena.

        Compartido por los flujos de edición inline (primer guardado y
        corrección) desde la pestaña Productos — action_save_line_weight()
        no se toca y mantiene su propia copia de esta lógica.
        """
        self.ensure_one()
        if not self.stock_move_id:
            return
        if self.stock_move_id.state in ('done', 'cancel'):
            estado = (
                'cancelado' if self.stock_move_id.state == 'cancel'
                else 'ya procesado'
            )
            raise UserError(
                f'No se puede actualizar el peso: el movimiento de stock '
                f'de esta línea está {estado} y ya no admite cambios. '
                f'Contacta a Inventario si el dato necesita corregirse.'
            )
        Move = self.stock_move_id.sudo().with_context(
            skip_inverse_visual_qty=True,
            skip_recolectar_zero_check=True,
            manual_entry=True,
            guapante_wizard_intent=True,
        )
        Move.write({
            'picked': True,
            'quantity': weight,
            'is_weight_confirmed': True,
        })
        if Move.state == 'confirmed':
            Move.write({'state': 'assigned'})
        if Move.move_line_ids:
            Move.move_line_ids.write({'picked': True})
        self.wizard_id._propagate_weight_to_chain(Move, weight)

    def _register_weight_from_productos_tab(self) -> None:
        """Primer guardado de un peso editado inline desde la pestaña
        Productos (sin PIN — el usuario de Odoo logueado ya identifica
        quién hizo el cambio). Reutiliza la sincronización de stock de
        Picking pero sin su gate de PIN ni su log de operario físico.
        """
        self.ensure_one()
        self._sync_weight_to_stock(self.actual_kg)

        Summary = self.wizard_id.summary_ids.filtered(
            lambda s: s.product_id == self.product_product_id
        )
        if Summary:
            Summary._add_done_kg(self.actual_kg)

        # Sin PIN acá — done_by_employee_id usa el empleado vinculado al
        # usuario de Odoo logueado, si tiene uno (Tech Lead, 2026-11-02:
        # queda False si no, la fecha se estampa igual).
        self.with_context(skip_auto_save=True).write({
            'is_done': True,
            'done_by_employee_id': self.env.user.employee_id.id,
            'done_date': fields.Datetime.now(),
        })

        self.wizard_id.sudo().message_post(
            body=(
                f"Peso registrado desde Productos — Caja #{self.daily_sequence}: "
                f"{self.actual_kg:.3f} kg (por {self.env.user.name})."
            )
        )
        self._maybe_post_dispatch_zero_note(self.env.user.name)

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        pending_total = self.env['guapante.preparation.day.line'].search_count([
            ('wizard_id', '=', self.wizard_id.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0:
            self.wizard_id.action_mark_done()

    def _maybe_post_dispatch_zero_note(self, actor_name: str) -> None:
        """E7 (David/Tech Lead, 2026-11-02): nota propia cuando una línea
        se Termina en 0 — "sin stock", el cliente pidió un producto que
        no hay. Separada de la nota de "Peso registrado"/action_save_
        line_weight (que siempre se postea igual) para que sea fácil de
        encontrar en el chatter. Un solo punto para los dos orígenes que
        llegan a marcar Terminado (tablet vía action_save_line_weight,
        backend vía _register_weight_from_productos_tab o la casilla de
        admin de E4), para no duplicar el texto."""
        self.ensure_one()
        if self.actual_kg == 0:
            self.wizard_id.sudo().message_post(
                body=(
                    f'{actor_name} terminó {self.product_description} '
                    f'(Caja #{self.daily_sequence}) en 0 — sin stock, '
                    'no se despacha.'
                )
            )

    def _register_weight_correction(
        self, old_kg: float, operator_employee_id,
    ) -> None:
        """Corrige el peso de una línea ya Terminada, editada inline desde
        Productos o Picking — re-sincroniza stock/resumen sin repetir los
        efectos de un primer guardado (no re-evalúa auto-finish, no toca
        date_done). Permitido con la sesión cerrada (a diferencia de
        volver una línea a Pendiente, ver action_undo_line) — corregir un
        peso no reabre nada.

        operator_employee_id: id de hr.employee si hay operario con PIN
        activo (Tech Lead/David, 2026-11-02 — antes se mostraba un texto
        genérico "operario con PIN activo" en vez del nombre real);
        False/None para usar self.env.user.
        """
        self.ensure_one()
        new_kg = self.actual_kg
        self._sync_weight_to_stock(new_kg)

        Summary = self.wizard_id.summary_ids.filtered(
            lambda s: s.product_id == self.product_product_id
        )
        if Summary:
            Summary._add_done_kg(new_kg - old_kg)

        actor_name = (
            self.env['hr.employee'].sudo().browse(operator_employee_id).name
            if operator_employee_id else self.env.user.name
        )
        self.wizard_id.sudo().message_post(
            body=(
                f"Corregido — {self.product_description} "
                f"(Caja #{self.daily_sequence}): {actor_name} cambió "
                f"el peso de {old_kg:.3f} kg a {new_kg:.3f} kg."
            )
        )
        self._maybe_post_dispatch_zero_note(actor_name)

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

    @api.model
    def _cron_mirror_inventory_to_preparation(self) -> None:
        """ESPEJO Inventario→Preparación (David/Tech Lead, 2026-11-05).

        Transacción propia, corre cada 2 minutos (ver data/ir_cron_
        mirror_inventory.xml) — procesa las líneas marcadas por el
        hook liviano de stock.move._action_done (ver models/
        stock_move.py). Un SAVEPOINT por línea: si una falla, no tumba
        las demás (mismo patrón que _guapante_relocate_picking).
        """
        # Lote 3 (David/Tech Lead, 2026-11-09): red de seguridad de
        # «cancelar un pedido ⇒ sus líneas pendientes desaparecen».
        # El camino normal es el override de sale.order._action_cancel();
        # esto cubre una cancelación por otra ruta (SQL, script,
        # sesión en uso, fallo del savepoint) — idempotente: solo toma
        # líneas NO hechas de sesiones NO cerradas, así que no repite
        # notas en cada corrida.
        try:
            with self.env.cr.savepoint():
                CancelledPending = self.sudo().search([
                    ('is_done', '=', False),
                    ('sale_order_id.state', '=', 'cancel'),
                    ('wizard_id.state', '!=', 'done'),
                ])
                if CancelledPending:
                    self.env['guapante.preparation.day'].sudo(
                    )._guapante_remove_cancelled_order_lines(
                        CancelledPending.mapped('sale_order_id'),
                    )
        except _PG_CONCURRENCY_ERRORS:
            raise
        except Exception:
            _logger.exception(
                'Guapante: barrido de pedidos cancelados — fallo, se '
                'reintenta en la próxima corrida.',
            )

        Flagged = self.sudo().search([('needs_inventory_mirror', '=', True)])
        for line in Flagged:
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        'SELECT id FROM guapante_preparation_day_line '
                        'WHERE id = %s FOR UPDATE',
                        (line.id,),
                    )
                    line.invalidate_recordset()
                    line._guapante_mirror_from_inventory()
            except Exception:
                _logger.exception(
                    'Guapante: ESPEJO Inventario→Preparación — fallo '
                    'al reflejar la línea %d, se reintenta en la '
                    'próxima corrida.', line.id,
                )

    def _guapante_mirror_from_inventory(self) -> None:
        """Aplica (o descarta) el reflejo de UNA línea marcada —
        llamado solo desde _cron_mirror_inventory_to_preparation, ya
        con el FOR UPDATE tomado.

        NUNCA llama _sync_weight_to_stock/_propagate_weight_to_chain
        (eso volvería a escribir el move y crearía un ciclo con el
        hook de stock_move.py) — escribe la línea directo, con
        skip_auto_save=True para no disparar el track_kg de write().

        Decisión (b) (David/Tech Lead, 2026-11-05): basta con que el
        PICK (self.stock_move_id) esté 'done' — no se espera al
        traslado siguiente (move_dest_ids); ese ya es dueño de su
        propio peso vía _action_done de theme_guapante/ist_
        preparation_day, independiente de esto.
        """
        self.ensure_one()
        move = self.stock_move_id
        if not move:
            self.sudo().with_context(skip_auto_save=True).write({
                'needs_inventory_mirror': False,
            })
            return
        if move.state == 'cancel':
            self._guapante_mirror_from_cancelled_move()
            return
        if move.state != 'done':
            # Se marcó pero el estado retrocedió (raro) — se
            # reintenta en la próxima corrida, sin limpiar la
            # bandera todavía.
            return

        weight = move.quantity

        if self.is_done:
            # Decisión (c): gana quien llegó primero — el operario ya
            # cerró esta línea (tablet o Productos) antes de que
            # corriera el cron. Nunca se pisa is_done/actual_kg; si
            # el peso de Inventario difiere, se deja constancia en el
            # chatter de la sesión, sin cambiar nada más.
            if abs(weight - self.actual_kg) > 0.001:
                self.wizard_id.sudo().message_post(body=(
                    f'Diferencia de peso detectada — Caja #'
                    f'{self.daily_sequence} ({self.product_description}): '
                    f'Preparación registró {self.actual_kg:.3f} kg, '
                    f'Inventario confirmó {weight:.3f} kg en el mismo '
                    f'traslado. Se mantiene el valor de Preparación (ya '
                    f'estaba Terminada primero); revisar manualmente si '
                    f'hace falta corregir.'
                ))
            self.sudo().with_context(skip_auto_save=True).write({
                'needs_inventory_mirror': False,
            })
            return

        # Caso real: el PICK se validó desde Inventario y Preparación
        # nunca cerró esta línea. Reflejar: mismo peso, Terminado, sin
        # operario — done_by_employee_id vacío a propósito (Fase 2,
        # David/Tech Lead 2026-11-05: una línea cerrada así no cuenta
        # en "Pickings por operario", ver el filtro WHERE
        # done_by_employee_id IS NOT NULL en preparation_operator_
        # report.py — ya lo hace, no se tocó).
        self.sudo().with_context(skip_auto_save=True).write({
            'actual_kg': weight,
            'is_done': True,
            'done_by_employee_id': False,
            'done_date': fields.Datetime.now(),
            'needs_inventory_mirror': False,
        })

        Summary = self.wizard_id.summary_ids.filtered(
            lambda s: s.product_id == self.product_product_id
        )
        if Summary:
            Summary._add_done_kg(weight)

        self.wizard_id.sudo().message_post(body=(
            f'Caja #{self.daily_sequence} ({self.product_description}) '
            f'cerrada automáticamente — el traslado se validó desde '
            f'Inventario (sin operario de Picking) con {weight:.3f} kg.'
        ))
        self._maybe_post_dispatch_zero_note('Inventario (sin operario)')

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        pending_total = self.env['guapante.preparation.day.line'].search_count([
            ('wizard_id', '=', self.wizard_id.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0 and self.wizard_id.state != 'done':
            self.wizard_id.action_mark_done()

    def _guapante_mirror_from_cancelled_move(self) -> None:
        """Espejo Inventario→Preparación — caso move 'cancel' (Tech
        Lead/David, 2026-11-06): un PICK que se cancela (ej. "sin
        stock", declinar backorder) SIN que Preparación la haya
        cerrado antes — hueco encontrado por Tech Lead en producción
        (sesión 226, 2026-11-06), simétrico al caso 'done' de arriba
        pero sin ningún peso real que reflejar (nada se despachó).

        Guard (David, vía Tech Lead): si el PEDIDO ENTERO está
        cancelado (sale_order_id.state == 'cancel'), esta cancelación
        del move es solo la cola de la cancelación del pedido, no una
        decisión de despacho — NO se cierra la línea (no tiene sentido
        marcar "Terminado" un despacho de un pedido que ya no existe).
        Se limpia la bandera igual (no reintentar para siempre) y se
        deja nota en el chatter para revisión manual — no se archiva
        ni se cierra distinto, a propósito.

        Fuera de ese guard: se cierra igual que el caso 'done' sin
        operario (mismo done_by_employee_id=False, mismo
        _maybe_post_dispatch_zero_note, mismo cierre de sesión si
        pending_total llega a 0) pero con actual_kg=0 SIEMPRE (nunca
        move.quantity — un move cancelado no tiene un peso real
        despachado que leer, a diferencia del caso 'done').
        Respeta "gana quien llegó primero" (decisión (c) de arriba):
        si Preparación ya la había cerrado, no se pisa nada.
        """
        self.ensure_one()

        if self.sale_order_id.state == 'cancel':
            # Lote 3 (David, 2026-11-09): antes se dejaba la línea con una
            # nota «revisar manualmente»; ahora un pedido cancelado
            # entero RETIRA sus líneas pendientes (nunca las cierra en 0,
            # no hubo despacho). Línea ya hecha o sesión cerrada: solo
            # nota (condición iii del Tech Lead) — lo decide el propio
            # método de retiro. Se limpia la bandera igual (no reintentar
            # para siempre).
            Order = self.sale_order_id
            self.sudo().with_context(skip_auto_save=True).write({
                'needs_inventory_mirror': False,
            })
            self.env['guapante.preparation.day'].sudo(
            )._guapante_remove_cancelled_order_lines(Order)
            return

        if self.is_done:
            self.sudo().with_context(skip_auto_save=True).write({
                'needs_inventory_mirror': False,
            })
            return

        self.sudo().with_context(skip_auto_save=True).write({
            'actual_kg': 0.0,
            'is_done': True,
            'done_by_employee_id': False,
            'done_date': fields.Datetime.now(),
            'needs_inventory_mirror': False,
        })

        Summary = self.wizard_id.summary_ids.filtered(
            lambda s: s.product_id == self.product_product_id
        )
        if Summary:
            Summary._add_done_kg(0.0)

        self.wizard_id.sudo().message_post(body=(
            f'Caja #{self.daily_sequence} ({self.product_description}) '
            f'cerrada automáticamente en 0 — el traslado se canceló '
            f'desde Inventario (sin operario de Picking) sin que '
            f'Preparación la hubiera terminado antes.'
        ))
        self._maybe_post_dispatch_zero_note('Inventario (traslado cancelado)')

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        pending_total = self.env['guapante.preparation.day.line'].search_count([
            ('wizard_id', '=', self.wizard_id.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0 and self.wizard_id.state != 'done':
            self.wizard_id.action_mark_done()

    def action_undo_line(self) -> bool:
        """Devuelve una línea de los Hechos a Pendientes para corregirla."""
        for line in self:
            if line.is_done:
                summary = line.wizard_id.summary_ids.filtered(
                    lambda s: s.product_id == line.product_product_id
                )
                if summary:
                    summary._add_done_kg(-line.actual_kg)
                # Limpiar la cantidad ejecutada en el picking.
                # sudo(): el operario puede no tener permisos
                # de escritura directa sobre stock.move.line.
                # skip_inverse_visual_qty: misma protección que en save.
                if line.stock_move_id:
                    line.stock_move_id.sudo().with_context(
                        skip_inverse_visual_qty=True,
                    ).move_line_ids.write({'quantity': 0})
                line.with_context(skip_auto_save=True).write({
                    'is_done': False,
                    'actual_kg': 0.0,
                    'done_by_employee_id': False,
                    'done_date': False,
                })
        return True


class PreparationDay(models.Model):
    """Session: select a date → see products to prepare → enter weights."""
    _name = 'guapante.preparation.day'
    _description = 'Sesión Permanente de Preparación del Día'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default='Nueva Sesión',
    )
    date = fields.Date(
        # "Fecha programada" (David, observación #5, 2026-10-29): es la
        # jornada — la misma fecha programada del PICK (Regla de la
        # jornada) — no "cuándo se cargó la sesión", que es date_start.
        # El rótulo anterior ("Fecha de entrega a preparar") y el de
        # date_start ("Fecha programada") estaban cruzados y confundían.
        string='Fecha programada',
        required=True,
        default=fields.Date.context_today,
    )
    date_start = fields.Datetime(
        # "Cargada el" (David, observación #5): momento en que la
        # sesión pasó a En Progreso por primera vez — NO es la fecha
        # programada (eso es `date`, arriba).
        string='Cargada el',
        readonly=True,
        copy=False,
        help='Momento en que la sesión pasó a En Progreso por primera vez.',
    )
    date_done = fields.Datetime(
        string='Finalización programada',
        readonly=True,
        copy=False,
        help='Momento en que la sesión se marcó como Finalizada.',
    )
    responsible_employee_id = fields.Many2one(
        'hr.employee',
        string='Responsable de operación',
        # Fase 2, punto 8 (Tech Lead, 2026-11-04): mismo criterio que
        # done_by_employee_id — quién respondió por la sesión es
        # historia, no se pierde en silencio al borrar el empleado.
        ondelete='restrict',
    )
    line_ids = fields.One2many(
        'guapante.preparation.day.line',
        'wizard_id',
        string='Líneas',
    )
    summary_ids = fields.One2many(
        'guapante.preparation.day.summary',
        'wizard_id',
        string='Resumen por producto',
    )
    summary_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_summary_count',
    )
    state = fields.Selection(
        [
            ('draft', 'Nueva Sesión'),
            ('loaded', 'En Progreso'),
            ('done', 'Finalizada'),
        ],
        string='Estado',
        default='draft',
    )
    save_note = fields.Char(string='Resultado', readonly=True)

    global_progress_pct = fields.Float(
        string='Progreso General',
        compute='_compute_global_progress',
        digits=(5, 1),
    )
    total_lines = fields.Integer(
        string='Total líneas',
        compute='_compute_global_progress',
    )
    done_lines = fields.Integer(
        string='Completadas',
        compute='_compute_global_progress',
    )
    pending_lines = fields.Integer(
        string='Pendientes',
        compute='_compute_global_progress',
    )

    # ── Conciliación Cajas: Ventas vs Inventario ──
    so_count = fields.Integer(
        string='Cajas',
        compute='_compute_box_reconciliation',
        help=(
            'Cantidad de pedidos con líneas reales en esta sesión '
            '(incluye cancelados que conservan su número mientras sus '
            'líneas sigan acá). Antes de la corrección #5/#6 (David, '
            '2026-10-31) se calculaba buscando pickings PICK por fecha '
            'programada — podía mostrar un número distinto al real de '
            'la sesión (reprogramaciones, duplicados). Se mantiene ese '
            'cálculo viejo solo como respaldo para una sesión sin '
            'líneas (vacía/borrador).'
        ),
    )
    box_diff = fields.Integer(
        string='Diferencia',
        compute='_compute_box_reconciliation',
    )
    box_match = fields.Boolean(
        string='Coinciden',
        compute='_compute_box_reconciliation',
    )
    draft_count = fields.Integer(
        string='Cotizaciones pendientes',
        compute='_compute_draft_count',
        help='Cotizaciones (draft/sent) que podrían ser cajas si se confirman.',
    )

    # Punto de montaje del widget de refresco en vivo vía bus.bus — el valor
    # no se usa, solo existe para que el campo exista en el arch y el
    # widget OWL se monte (mismo patrón que operator_identification en
    # PreparationDayProductWizard).
    live_refresh_anchor = fields.Char(
        compute='_compute_live_refresh_anchor',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Sesión') == 'Nueva Sesión':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'guapante.preparation.day',
                    )
                    or 'Nueva Sesión'
                )
        return super().create(vals_list)

    def _compute_live_refresh_anchor(self) -> None:
        for session in self:
            session.live_refresh_anchor = ''

    @api.constrains('date')
    def _check_unique_date(self) -> None:
        """Evita crear/editar hacia una fecha duplicada.

        No es un _sql_constraints UNIQUE a propósito: ya existen
        duplicados históricos en la data (de antes de esta regla) y un
        UNIQUE real rompería la actualización del módulo. Esta
        validación solo protege hacia adelante — dispara nada más
        cuando se escribe el campo date, no al editar otros campos de
        un registro histórico que ya viola la regla.
        """
        for session in self:
            if not session.date:
                continue
            duplicate = self.search([
                ('date', '=', session.date),
                ('id', '!=', session.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'Ya existe una sesión de Preparación para el '
                    f'{session.date} ({duplicate.name}). No se pueden '
                    f'crear sesiones duplicadas para la misma fecha.'
                )

    @api.model
    def _ensure_session_for_date(self, date_val):
        """Garantiza que exista una sesión de Preparación para
        date_val — la crea en borrador (Nueva Sesión) si falta, y
        avisa en vivo por bus.bus a quien la tenga abierta.

        Se dispara desde sale.order.action_confirm() y
        stock.picking.write() (reprogramación) para CUALQUIER fecha,
        hoy o futura — Regla de la jornada (David, 2026-10-29): la
        sesión de la fecha D existe en cuanto hay un PICK programado
        para D, sin importar si D es hoy. Antes esto se filtraba a
        solo "hoy"; ya no.

        Carrera entre dos confirmaciones casi simultáneas para la
        misma fecha: el create() va envuelto en un savepoint — si
        _check_unique_date lo rechaza porque la otra transacción ya
        commiteó su sesión, descartamos (rollback quirúrgico) solo
        nuestro intento de create y devolvemos la que ya existe, en
        vez de dejar que el ValidationError se propague y tumbe toda
        la confirmación de la orden por un efecto secundario que no
        tiene nada que ver con ella.
        """
        Session = self.sudo().search([('date', '=', date_val)], limit=1)
        if not Session:
            try:
                with self.env.cr.savepoint():
                    Session = self.sudo().create({'date': date_val})
            except ValidationError:
                Session = self.sudo().search([('date', '=', date_val)], limit=1)
        if Session:
            self.env['bus.bus']._sendone(
                f'guapante_preparation_day-{Session.id}', 'reload', {},
            )
        return Session

    @api.model
    def _guapante_check_no_weighed_lines(self, pickings):
        """Bloquea reprogramar la fecha de pickings cuya orden ya
        tiene algo pesado — a propósito (Tech Lead, 2026-10-29): hay
        dato real ya registrado, dejarlo pasar lo perdería (ver caso
        g de la reproducción: una línea pesada se quedaba huérfana en
        la sesión vieja sin ningún aviso).

        Se mira por ORDEN, no solo por el picking que se está
        moviendo — una orden puede tener líneas repartidas en más de
        un picking (backorders), y mover un picking distinto no debe
        poder esquivar el bloqueo de una línea ya pesada de la misma
        orden.
        """
        Orders = pickings.mapped('sale_id')
        if not Orders:
            return
        WeighedLines = self.env['guapante.preparation.day.line'].sudo().search([
            ('sale_order_id', 'in', Orders.ids),
            ('is_done', '=', True),
        ])
        if WeighedLines:
            names = ', '.join(sorted(set(WeighedLines.mapped('order_name'))))
            raise UserError(
                f'No se puede reprogramar — ya se pesó algo de {names} '
                'en la jornada actual. Corrige esa línea desde la '
                'pestaña Productos de la sesión antes de mover la '
                'fecha programada.'
            )

    def _guapante_relocate_picking(
        self, picking, old_scheduled_date, exclude_picking_ids=None,
    ):
        """Reubica, de forma incremental, la línea de preparación de
        *picking* cuando su scheduled_date cambia de día calendario.

        No reconstruye summaries completos ni toca otras líneas de la
        sesión (regla de David: no se puede correr un action_load
        completo a mitad del pesaje) — solo mueve la línea de ESTE
        picking (conserva su id e historial, no unlink+create) y
        parchea el summary de su producto en las dos sesiones
        involucradas.

        _guapante_check_no_weighed_lines ya garantiza, antes de
        llegar acá, que ninguna línea de la orden está pesada — así
        que siempre es seguro resetear y reasignar daily_sequence.

        Pensado para no poder tumbar una escritura de bodega: cualquier
        error acá se registra y se traga, nunca se propaga (la única
        excepción deliberada es el UserError de arriba, que corre
        ANTES del write real).

        exclude_picking_ids (Propuesta A, Tech Lead 2026-11-04): ids de
        TODOS los pickings reubicados en el mismo stock.picking.write()
        que disparó esto (los pasa StockPicking.write(), ver su
        docstring) — se reenvía tal cual a _assign_daily_sequences/
        _guapante_max_daily_sequence_on_date para que el cálculo del
        "máximo ya existente" no cuente a un hermano todavía sin
        resetear en esta misma vuelta del loop.
        """
        new_scheduled_date = picking.scheduled_date
        if not new_scheduled_date:
            return
        old_date = _utc_datetime_to_session_date(self.env, old_scheduled_date)
        new_date = _utc_datetime_to_session_date(self.env, new_scheduled_date)
        if old_date == new_date:
            return  # Solo cambió la hora dentro del mismo día — no tocar nada.

        # Condición 2 (Tech Lead, 2026-10-29): savepoint alrededor de
        # TODO el cuerpo, con el except AFUERA del with — si algo
        # falla a mitad de camino (una restricción, un fallo de
        # serialización), Postgres deja la transacción abortada y
        # cualquier escritura posterior del picking fallaría con
        # "current transaction is aborted" si no hay savepoint que
        # revertir. El try/except solo (sin savepoint) no alcanza.
        try:
            with self.env.cr.savepoint():
                NewSession = self._ensure_session_for_date(new_date)
                Lines = self.env['guapante.preparation.day.line'].sudo().search([
                    ('stock_move_id.picking_id', '=', picking.id),
                ])
                if not Lines:
                    return  # Nunca se cargó — nada que reubicar, solo la sesión nueva.

                # DEF-01 (Tech Lead/QA, 2026-10-29): un pedido con varias
                # líneas/productos tiene VARIAS Lines acá — Order y
                # OldSession siguen siendo singleton (todas las líneas
                # de un mismo picking son del mismo pedido y ya están en
                # la misma sesión), pero el producto de cada línea no,
                # así que todo lo que dependa de product_product_id (el
                # summary, el claim de Picking) se procesa línea por
                # línea, nunca con el recordset completo de una.
                OldSession = Lines.wizard_id
                Order = Lines.sale_order_id

                # Corrección de Tech Lead (2026-10-30): origen y
                # destino son SIEMPRE sesiones distintas acá (el
                # método ya retornó arriba si old_date == new_date) —
                # se bloquean las DOS, en una sola consulta ordenada
                # por id, antes de tocar nada (ver _guapante_lock_sessions).
                self._guapante_lock_sessions(OldSession | NewSession)

                # Condición A (Tech Lead): _assign_daily_sequences salta
                # las órdenes que ya tienen número — hay que resetear
                # ANTES de pedirle uno nuevo para la fecha nueva, o se
                # queda arrastrando el de la fecha vieja (caso d de la
                # reproducción).
                Order.sudo().write({'daily_sequence': 0})
                self.env['sale.order']._assign_daily_sequences(
                    new_date, exclude_picking_ids=exclude_picking_ids,
                )
                # daily_sequence de la línea es related+store sobre la
                # orden — se sincroniza solo al cambiar el de la orden.

                for Line in Lines:
                    self._guapante_patch_summary(OldSession, Line, add=False)
                Lines.write({'wizard_id': NewSession.id})
                for Line in Lines:
                    self._guapante_patch_summary(NewSession, Line, add=True)

                    # Condición 3 (Tech Lead): gancho de extensión — el
                    # Nivel 1 de Picking (claims por producto) vive en
                    # ist_preparation_day_picking, que lo sobreescribe.
                    # Acá, en el módulo padre, es un no-op. Una llamada
                    # por línea — el gancho razona sobre UN producto.
                    NewSession._guapante_after_relocate(OldSession, NewSession, Line)

                user_name = self.env.user.name
                note = (
                    f'Pedido {Order.name} (Caja #{Order.daily_sequence}) '
                    f'pasó de la jornada {old_date} a {new_date}, '
                    f'por {user_name}.'
                )
                OldSession.sudo().message_post(body=note)
                if NewSession.id != OldSession.id:
                    NewSession.sudo().message_post(body=note)

                self.env['bus.bus']._sendone(
                    f'guapante_preparation_day-{OldSession.id}', 'reload', {},
                )
                self.env['bus.bus']._sendone(
                    f'guapante_preparation_day-{NewSession.id}', 'reload', {},
                )
        except _PG_CONCURRENCY_ERRORS:
            # Nunca atrapar esto — ver _PG_CONCURRENCY_ERRORS arriba.
            raise
        except Exception:
            _logger.exception(
                'Guapante: no se pudo reubicar la línea de preparación '
                'del picking %s (%s) al cambiar su fecha programada — '
                'la reprogramación del picking ya se guardó, pero la '
                'sesión de preparación puede haber quedado '
                'desincronizada y necesita revisión manual.',
                picking.id, picking.name,
            )
            # DEF-01 (Tech Lead, 2026-10-29): que no quede solo en el
            # log técnico — nota visible en el chatter del propio
            # picking, donde está mirando quien acaba de mover la
            # fecha. Nunca debe tumbar la escritura ya guardada (por
            # eso un savepoint propio, aparte del que ya revirtió la
            # reubicación): si hasta esto falla, se registra y se
            # sigue.
            try:
                with self.env.cr.savepoint():
                    picking.sudo().message_post(
                        body=(
                            'La fecha programada cambió, pero la '
                            'sesión de Preparación del Día no se pudo '
                            'actualizar automáticamente — revísala '
                            'manualmente (puede seguir mostrando este '
                            'pedido en la jornada anterior).'
                        ),
                    )
            except Exception:
                _logger.exception(
                    'Guapante: tampoco se pudo dejar la nota de aviso '
                    'en el chatter del picking %s (%s).',
                    picking.id, picking.name,
                )

    def _guapante_after_relocate(self, old_session, new_session, line) -> None:
        """Punto de extensión (Tech Lead, 2026-10-29): no hace nada en
        este módulo — ist_preparation_day_picking lo sobreescribe para
        sincronizar los claims del Nivel 1 de Picking (que viven en
        ese módulo hijo y no se mueven solos con wizard_id). self es
        new_session."""
        return

    def _guapante_after_lines_removed(self, session, templates) -> None:
        """Punto de extensión (lote 3, Tech Lead/David 2026-11-09): no
        hace nada en este módulo — ist_preparation_day_picking lo
        sobreescribe para borrar los claims del Nivel 1 que se quedan
        sin ninguna línea y avisar a las tablets (los claims viven en
        ese módulo hijo). `templates` = product.template de las líneas
        retiradas; self es la sesión (mismo patrón que
        _guapante_after_relocate)."""
        return

    @api.model
    def _guapante_remove_cancelled_order_lines(self, orders) -> None:
        """Lote 3 (David, 2026-11-09): cuando un pedido se cancela, sus
        líneas PENDIENTES desaparecen de Preparación y del Picking —
        no se ponen en 0 (no hubo despacho). Ventas e Inventario no se
        tocan: el pedido y sus traslados quedan en «Cancelado» (las FK
        de la línea hacia pedido/línea de venta/traslado son ON DELETE
        SET NULL y ninguna otra tabla referencia la línea, verificado
        en producción — ver DISENO_retiro_pedido_cancelado.md).

        Reglas (Tech Lead, condiciones iii/iv):
        - Solo líneas NO hechas, solo en sesiones que NO están 'done'.
        - Línea ya hecha en un pedido cancelado, o sesión 'done': NO se
          borra nada, solo se deja una nota con nombres.
        - Las cajas NUNCA se renumeran: la caja del pedido queda como
          hueco (esto no escribe daily_sequence en ninguna otra línea).
        - Idempotente: sin líneas pendientes no hace nada (lo llama
          también el barrido del cron del espejo).

        Cada sesión va en su propio savepoint y con lock de sesión
        (mismo patrón que _guapante_relocate_picking): un fallo acá se
        registra y se traga, NUNCA puede tumbar la cancelación del
        pedido; los errores de concurrencia sí se relanzan para que
        Odoo reintente."""
        Orders = orders.filtered(lambda o: o.state == 'cancel')
        if not Orders:
            return
        Lines = self.env['guapante.preparation.day.line'].sudo().search([
            ('sale_order_id', 'in', Orders.ids),
        ])
        for Session in Lines.mapped('wizard_id'):
            SessionLines = Lines.filtered(lambda l, s=Session: l.wizard_id == s)
            try:
                with self.env.cr.savepoint():
                    Session._guapante_remove_cancelled_lines_in_session(
                        SessionLines,
                    )
            except _PG_CONCURRENCY_ERRORS:
                raise
            except Exception:
                _logger.exception(
                    'Guapante: no se pudieron retirar las líneas de los '
                    'pedidos cancelados %s de la sesión %s (%s) — se '
                    'reintenta en el barrido del cron del espejo.',
                    ', '.join(SessionLines.mapped('order_name')),
                    Session.id, Session.name,
                )

    def _guapante_post_note_once(self, body) -> None:
        """Nota informativa del retiro por pedido cancelado, SIN repetir
        el mismo texto en el chatter de la sesión: el evento de
        cancelación y el guard del espejo pueden pasar los dos por el
        mismo caso (sesión cerrada, línea ya hecha) y la nota no debe
        duplicarse."""
        self.ensure_one()
        if any(body in (m.body or '') for m in self.message_ids):
            return
        self.sudo().message_post(body=body)

    def _guapante_remove_cancelled_lines_in_session(self, lines) -> None:
        """Trabajo de UNA sesión (self) para _guapante_remove_cancelled_
        order_lines — ver su docstring para las reglas."""
        self.ensure_one()
        self._guapante_lock_sessions(self)
        # El lock invalida cachés: releer las líneas con el estado real.
        lines = lines.exists()
        Pending = lines.filtered(lambda l: not l.is_done)
        Done = lines - Pending
        order_names = ', '.join(sorted(set(lines.mapped('order_name'))))

        if self.state == 'done':
            if lines:
                self._guapante_post_note_once(
                    f'Pedido(s) {order_names} cancelado(s), pero esta '
                    'operación ya está cerrada: no se retiró ninguna '
                    'línea. Reábrela para limpiarla si hace falta.'
                )
            return

        if Done:
            done_orders = ', '.join(sorted(set(Done.mapped('order_name'))))
            done_boxes = ', #'.join(
                str(n) for n in sorted(set(Done.mapped('daily_sequence')))
            )
            self._guapante_post_note_once(
                f'Pedido(s) {done_orders} cancelado(s) con {len(Done)} '
                f'línea(s) ya terminada(s) (caja #{done_boxes}): se '
                'conservan, revisar manualmente.'
            )
        if not Pending:
            return

        templates = Pending.mapped('product_id')
        sequences = sorted(set(Pending.mapped('daily_sequence')))
        pending_orders = ', '.join(sorted(set(Pending.mapped('order_name'))))
        count = len(Pending)
        boxes = ', #'.join(str(n) for n in sequences)
        products = ', '.join(sorted({
            ' '.join((l.product_description or '').split()) for l in Pending
        }))
        for Line in Pending:
            self._guapante_patch_summary(self, Line, add=False)
        Pending.unlink()
        self._guapante_after_lines_removed(self, templates)
        self.sudo().message_post(body=(
            f'Pedido {pending_orders} cancelado: se retiraron {count} '
            f'línea(s) pendiente(s) de esta sesión (caja #{boxes}). '
            'Inventario y '
            'Ventas no se tocaron; las cajas no se renumeran. '
            f'Productos: {products}.'
        ))
        self.env['bus.bus']._sendone(
            f'guapante_preparation_day-{self.id}', 'reload', {},
        )

    def _guapante_patch_summary(self, session, line, add) -> None:
        """Ajusta, de forma incremental, el summary de *session* para
        el producto de *line* — suma o resta UNA línea, sin recorrer
        ni recalcular el resto de la sesión (ver _rebuild_summary,
        que sí hace un recálculo completo y no aplica acá)."""
        Summary = self.env['guapante.preparation.day.summary'].sudo().search([
            ('wizard_id', '=', session.id),
            ('product_id', '=', line.product_product_id.id),
        ], limit=1)
        if add:
            if Summary:
                Summary.write({
                    'order_count': Summary.order_count + 1,
                    'total_estimated_kg': round(
                        Summary.total_estimated_kg + line.estimated_kg, 3,
                    ),
                    'stock_ok': (
                        Summary.available_qty
                        >= Summary.total_estimated_kg + line.estimated_kg
                    ),
                })
            else:
                available_qty = line.product_product_id.qty_available
                self.env['guapante.preparation.day.summary'].sudo().create({
                    'wizard_id': session.id,
                    'product_id': line.product_product_id.id,
                    'total_estimated_kg': round(line.estimated_kg, 3),
                    'total_done_kg': 0.0,
                    'order_count': 1,
                    'available_qty': available_qty,
                    'stock_ok': available_qty >= line.estimated_kg,
                })
        else:
            if not Summary:
                return
            remaining = Summary.order_count - 1
            if remaining <= 0:
                Summary.unlink()
                return
            new_est = round(Summary.total_estimated_kg - line.estimated_kg, 3)
            Summary.write({
                'order_count': remaining,
                'total_estimated_kg': max(new_est, 0.0),
                'stock_ok': Summary.available_qty >= max(new_est, 0.0),
            })

    def _guapante_lock_sessions(self, sessions) -> None:
        """Toma el lock (FOR UPDATE) de una o varias sesiones antes de
        leer/renumerar — corrección de Tech Lead (2026-10-30): antes
        había dos candados independientes (uno en
        _guapante_add_confirmed_order, ninguno real en
        _guapante_relocate_picking, aunque su docstring decía lo
        contrario). Único punto de entrada para ambos, SIEMPRE en el
        mismo orden (ORDER BY id) — si se bloqueara origen y destino
        en órdenes distintos entre dos reubicaciones cruzadas (A→B en
        una transacción, B→A en otra), Postgres podría dar un
        deadlock real en vez de la serialización limpia que
        _PG_CONCURRENCY_ERRORS espera poder relanzar.

        flush_recordset() antes del SQL crudo (mismo criterio que
        PreparationDayProductClaim.action_assign): una sesión recién
        creada por _ensure_session_for_date podría no estar aún en la
        tabla real. invalidate_recordset() después — ver la nota de
        REPEATABLE READ en _guapante_add_confirmed_order sobre qué
        garantiza esto realmente (serialización + reintento de Odoo,
        no una lectura fresca dentro de la misma transacción).
        """
        ids = sessions.ids
        if not ids:
            return
        sessions.flush_recordset()
        self.env.cr.execute(
            'SELECT id FROM guapante_preparation_day '
            'WHERE id IN %s ORDER BY id FOR UPDATE',
            (tuple(ids),),
        )
        sessions.invalidate_recordset()

    @api.model
    def _cron_repair_missing_orders(self) -> None:
        """Cron de respaldo del plan de carga automática, paso e4
        (2026-10-30) — RED DE SEGURIDAD para cuando un disparador (e2
        al confirmar, reubicación) falla silenciosamente a mitad de
        camino; nunca es el mecanismo principal. Agrega las órdenes
        confirmadas que debían tener línea en una sesión draft/loaded
        de hoy o futura y no la tienen, y renumera. Nunca toca una
        sesión 'done'.

        Desde 2026-10-31 (Tech Lead, corrección a) también crea, hoy
        a hoy+N días (N configurable, ver
        _CRON_REPAIR_CREATE_DAYS_AHEAD_PARAM_KEY), la sesión que
        falte por completo SI YA hay pedidos elegibles ese día — para
        cubrir pedidos confirmados antes de instalar el módulo (no
        dispararon _ensure_session_for_date porque no existía). Si ya
        existe cualquier sesión para esa fecha (draft/loaded/done), no
        se toca nada — así una sesión 'done' de hoy nunca se recrea,
        y nunca se mira hacia el pasado porque el rango arranca en
        _current_session_date, nunca en date.today().

        Corre en UNA sola transacción — a diferencia de e2/e3, acá un
        error de concurrencia NO se relanza (Tech Lead, 2026-10-30):
        cada sesión va en su propio savepoint, y si choca con el lock
        de otra transacción, se revierte SOLO esa sesión (log info,
        se repara en la próxima corrida 10 min después) sin abortar
        el trabajo ya hecho en las demás sesiones de esta corrida —
        relanzar tumbaría TODO lo reparado hasta ese punto.

        Desde 2026-10-31 (#4, David/Tech Lead, caso real sesión 218;
        corrección de rango 2026-11-01) también borra, como segundo
        paso, una sesión draft/loaded sin líneas/claims/historial de
        pesaje en CUALQUIER fecha, excepto hoy, mañana (solo si ya se
        pasó la hora de corte del tablet) y cualquiera con write_date
        de menos de 30 minutos — ver el comentario junto al segundo
        paso, más abajo, para el detalle completo.
        """
        max_sessions, max_orders = _get_cron_repair_limits(self.env)
        today = _current_session_date(self.env)
        days_ahead = _get_cron_repair_create_days_ahead(self.env)

        sessions_budget = max_sessions
        orders_budget = max_orders

        # Fase nueva (corrección a): crear la sesión que falte por
        # completo, de hoy a hoy+days_ahead, solo si ya hay pedidos
        # elegibles ese día — comparte el mismo presupuesto de
        # sesiones/órdenes que la fase de abajo (condición 4).
        internal_picking_domain_base = [
            ('picking_type_code', '=', 'internal'),
            ('state', 'not in', ('done', 'cancel')),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
        ]
        for day_offset in range(days_ahead + 1):
            if sessions_budget <= 0:
                break
            candidate_date = today + timedelta(days=day_offset)
            if self.sudo().search(
                [('date', '=', candidate_date)], limit=1,
            ):
                # Ya existe una sesión para esta fecha (cualquier
                # estado, incluido 'done') — no es terreno de esta
                # fase nueva, se deja intacta.
                continue

            dt_start, dt_end = _date_to_utc_range(self.env, candidate_date)
            Pickings = self.env['stock.picking'].sudo().search(
                internal_picking_domain_base + [
                    ('scheduled_date', '>=', dt_start),
                    ('scheduled_date', '<', dt_end),
                ]
            )
            if not Pickings:
                _logger.debug(
                    'Guapante: cron de respaldo — %s sin pedidos '
                    'elegibles todavía, no crea sesión.',
                    candidate_date,
                )
                continue

            try:
                with self.env.cr.savepoint():
                    NewSession = self.sudo()._ensure_session_for_date(
                        candidate_date,
                    )
                    if NewSession and NewSession.state == 'draft':
                        NewSession.action_load()
                    sessions_budget -= 1
                    orders_budget -= len(Pickings.mapped('sale_id'))
            except _PG_CONCURRENCY_ERRORS as exc:
                _logger.info(
                    'Guapante: cron de respaldo — no se pudo crear '
                    'la sesión %s (%s), se reintenta en la próxima '
                    'corrida.', candidate_date, exc.__class__.__name__,
                )
            except Exception:
                _logger.exception(
                    'Guapante: cron de respaldo no pudo crear/cargar '
                    'la sesión %s — se reintenta en la próxima '
                    'corrida.', candidate_date,
                )

        if sessions_budget <= 0:
            Sessions = self.browse()
        else:
            Sessions = self.sudo().search([
                ('state', 'in', ('draft', 'loaded')),
                ('date', '>=', today),
            ], order='date', limit=sessions_budget)

        for Session in Sessions:
            try:
                with self.env.cr.savepoint():
                    self._guapante_lock_sessions(Session)

                    if Session.state == 'done':
                        # Cambió entre el search y el lock (p. ej. se
                        # cerró la jornada mientras esta sesión
                        # esperaba su turno en esta misma corrida) —
                        # 'done' nunca se repara, ya se cerró.
                        continue

                    # Mismo dominio de pickings que usa action_load():
                    # se calcula una sola vez y se reutiliza tanto para
                    # decidir si hay algo que cargar como para la rama
                    # de alta incremental de más abajo.
                    dt_start, dt_end = _date_to_utc_range(
                        self.env, Session.date,
                    )
                    Pickings = self.env['stock.picking'].sudo().search([
                        ('scheduled_date', '>=', dt_start),
                        ('scheduled_date', '<', dt_end),
                        ('picking_type_code', '=', 'internal'),
                        ('state', 'not in', ('done', 'cancel')),
                        ('sale_id', '!=', False),
                        ('sale_id.state', 'in', ('sale', 'done')),
                    ])
                    Orders = Pickings.mapped('sale_id')

                    if not Session.line_ids and Session.state == 'draft':
                        if not Orders:
                            # Sesión draft sin pedidos elegibles todavía
                            # (p. ej. quedó vacía tras una reubicación, o
                            # es una fecha futura sin pedidos aún) — NO
                            # es un fallo, action_load() lanzaría
                            # UserError por diseño. Corre cada 10 min;
                            # sin este corte dejaría una nota de fallo
                            # en el chatter para siempre.
                            _logger.debug(
                                'Guapante: cron de respaldo — sesión '
                                '%s draft sin pedidos elegibles aún, '
                                'nada que cargar.', Session.date,
                            )
                            continue
                        Session.action_load()
                        continue

                    if Session.state != 'loaded':
                        _logger.info(
                            'Guapante: cron de respaldo — sesión %s '
                            'en estado %s con líneas a medias, no se '
                            'toca.', Session.date, Session.state,
                        )
                        continue

                    if orders_budget <= 0:
                        continue

                    existing_sale_line_ids = Session.line_ids.mapped(
                        'sale_line_id',
                    ).ids
                    weight_categ = self.env.ref(
                        'uom.product_uom_categ_kgm',
                        raise_if_not_found=False,
                    )

                    all_line_vals = []
                    RepairedOrders = self.env['sale.order']
                    for order in Orders:
                        if orders_budget <= 0:
                            break
                        line_vals = Session._guapante_add_order_lines(
                            order, existing_sale_line_ids, weight_categ,
                        )
                        if not line_vals:
                            continue
                        all_line_vals += line_vals
                        RepairedOrders |= order
                        orders_budget -= 1

                    if not all_line_vals:
                        continue

                    self.env['sale.order']._assign_daily_sequences(
                        Session.date,
                    )
                    NewLines = self.env[
                        'guapante.preparation.day.line'
                    ].create(all_line_vals)
                    for Line in NewLines:
                        Session._guapante_patch_summary(
                            Session, Line, add=True,
                        )
                        Session._guapante_after_incremental_add(Line)
                    self.env['bus.bus']._sendone(
                        f'guapante_preparation_day-{Session.id}',
                        'reload', {},
                    )

                    # Una reparación significa que un disparador
                    # falló — visible y auditable (Tech Lead), no
                    # silenciosa como el resto del log de este cron.
                    # Incluye la Caja # final de cada pedido (David/
                    # Tech Lead, 2026-11-03, tras el incidente de
                    # renumeración) — cada pedido recibió MAX+1 de la
                    # fecha vía _assign_daily_sequences arriba, nunca
                    # se reasigna después.
                    max_listed = 10
                    labeled = [
                        f'{o.name} (Caja #{o.daily_sequence})'
                        for o in RepairedOrders
                    ]
                    listed_text = ', '.join(labeled[:max_listed])
                    extra = len(labeled) - max_listed
                    if extra > 0:
                        listed_text += f'… y {extra} más'
                    Session.sudo().message_post(
                        body=(
                            f'El respaldo automático agregó '
                            f'{len(labeled)} orden(es) que no habían '
                            f'entrado: {listed_text}.'
                        ),
                    )
                    _logger.info(
                        'Guapante: cron de respaldo agregó %d '
                        'orden(es) a la sesión %s: %s',
                        len(labeled), Session.date, listed_text,
                    )
            except _PG_CONCURRENCY_ERRORS as exc:
                # Deliberadamente NO se relanza (a diferencia de e2/
                # e3): esto corre en una sola transacción de cron, y
                # relanzar abortaría también el trabajo ya reparado
                # en las demás sesiones de esta misma corrida.
                _logger.info(
                    'Guapante: cron de respaldo — sesión %s ocupada '
                    '(%s), se reintenta en la próxima corrida.',
                    Session.date, exc.__class__.__name__,
                )
            except Exception:
                _logger.exception(
                    'Guapante: cron de respaldo no pudo reparar la '
                    'sesión %s — se reintenta en la próxima corrida.',
                    Session.date,
                )
                # El log de arriba SIEMPRE queda (no molesta a nadie),
                # pero el cron corre cada 10 min: si ya se dejó esta
                # misma nota de fallo la corrida anterior y nada la
                # resolvió desde entonces, no se repite — evita
                # spamear el chatter ×144/día (Tech Lead, 2026-10-30).
                LastMessage = Session.message_ids.sorted(
                    'id', reverse=True,
                )[:1]
                already_noted = bool(LastMessage) and (
                    'revísala manualmente o espera la próxima corrida'
                    in (LastMessage.body or '')
                )
                if already_noted:
                    continue
                try:
                    with self.env.cr.savepoint():
                        Session.sudo().message_post(
                            body=(
                                'El respaldo automático intentó '
                                'revisar esta sesión y falló — '
                                'revísala manualmente o espera la '
                                'próxima corrida.'
                            ),
                        )
                except Exception:
                    _logger.exception(
                        'Guapante: tampoco se pudo dejar la nota de '
                        'aviso en el chatter de la sesión %s.',
                        Session.date,
                    )

        # Limpieza de sesiones vacías (#4, David/Tech Lead 2026-10-31;
        # corrección de rango, Tech Lead/David 2026-11-01, caso real:
        # la vacía del 2-nov no desaparecía y reaparecía al llegar un
        # pedido — el objetivo original ERA justo que desapareciera).
        # El rango hoy..hoy+days_ahead de la fase de arriba es solo
        # para CREAR por adelantado, no es terreno protegido para el
        # borrado — un pedido nuevo para una fecha sin sesión la
        # recrea por e2 (_ensure_session_for_date), así que borrar acá
        # nunca es definitivo. Las únicas protegidas son:
        #   - la de HOY (today) — la jornada en curso;
        #   - la de MAÑANA (today+1) SOLO si ya se pasó la hora de
        #     corte del tablet (_is_past_picking_switch_hour, #12): el
        #     tablet puede estar entrando ahí mismo, aunque todavía no
        #     tenga líneas;
        #   - cualquiera con write_date de menos de 30 minutos (gracia
        #     contra carreras: recién creada por el tablet o por e2,
        #     todavía sin su primera línea).
        # Nunca una sesión 'done', nunca con líneas, nunca con un
        # claim (incluido uno 'stopped' sin dueño activo — sigue
        # siendo trabajo hecho), nunca con historial de pesaje
        # (guapante.picking.log), y nunca si todavía hay pedidos
        # elegibles sin cargar para esa fecha (mismo dominio que la
        # reparación de arriba) — eso es una sesión rota a medio
        # reparar, no una vacía de verdad. Mismo tope max_sessions que
        # ya limita la fase de creación/reparación, por corrida.
        #
        # 'guapante.preparation.day.product.claim' solo existe si
        # ist_preparation_day_picking está instalado — se verifica
        # contra el registro, nunca con el recordset vacío de
        # self.env[...] (que es siempre falsy aunque el modelo sí
        # exista).
        has_claim_model = (
            'guapante.preparation.day.product.claim' in self.env.registry
        )
        protected_dates = [today]
        if _is_past_picking_switch_hour(self.env):
            protected_dates.append(today + timedelta(days=1))
        grace_cutoff = fields.Datetime.now() - timedelta(minutes=30)
        EmptySessions = self.sudo().search([
            ('state', 'in', ('draft', 'loaded')),
            ('line_ids', '=', False),
            ('date', 'not in', protected_dates),
            ('write_date', '<=', grace_cutoff),
        ], order='date', limit=max_sessions)
        for Session in EmptySessions:
            try:
                with self.env.cr.savepoint():
                    self._guapante_lock_sessions(Session)
                    if Session.state == 'done' or Session.line_ids:
                        continue
                    if has_claim_model and self.env[
                        'guapante.preparation.day.product.claim'
                    ].sudo().search_count(
                        [('wizard_id', '=', Session.id)],
                    ):
                        continue
                    if self.env['guapante.picking.log'].sudo().search_count(
                        [('wizard_id', '=', Session.id)],
                    ):
                        continue
                    dt_start, dt_end = _date_to_utc_range(
                        self.env, Session.date,
                    )
                    if self.env['stock.picking'].sudo().search_count(
                        internal_picking_domain_base + [
                            ('scheduled_date', '>=', dt_start),
                            ('scheduled_date', '<', dt_end),
                        ],
                    ):
                        continue
                    _logger.info(
                        'Guapante: cron de respaldo borra la sesión '
                        'vacía %s (id=%s) — no es hoy ni mañana '
                        'protegida, sin líneas, sin claims, sin '
                        'historial de pesaje y sin pedidos elegibles '
                        'pendientes.', Session.date, Session.id,
                    )
                    Session.unlink()
            except _PG_CONCURRENCY_ERRORS as exc:
                _logger.info(
                    'Guapante: cron de respaldo — no se pudo borrar '
                    'la sesión vacía %s (%s), se reintenta en la '
                    'próxima corrida.', Session.date,
                    exc.__class__.__name__,
                )
            except Exception:
                _logger.exception(
                    'Guapante: cron de respaldo no pudo borrar la '
                    'sesión vacía %s.', Session.date,
                )

    def _guapante_add_confirmed_order(self, date_val, order) -> None:
        """Resuelve (o crea) la sesión de *date_val* y agrega *order* —
        plan de carga automática, paso e2 (2026-10-29).

        self puede ser un recordset vacío — igual patrón que
        _guapante_relocate_picking, llamado desde
        sale.order.action_confirm() con
        Session = self.env['guapante.preparation.day'].
        _ensure_session_for_date resuelve/crea la sesión real.

        TODO el cuerpo, INCLUIDA la resolución/creación de la sesión,
        va dentro de un savepoint propio con el except AFUERA (mismo
        patrón que _guapante_relocate_picking). Condición crítica de
        Tech Lead: confirmar una venta nunca puede fallar por esto, en
        NINGÚN punto — ni siquiera si _ensure_session_for_date explota
        — cualquier fallo se registra y deja una nota visible en el
        chatter de la orden, nunca se propaga a action_confirm().
        """
        try:
            with self.env.cr.savepoint():
                Day = self._ensure_session_for_date(date_val)
                if not Day:
                    return
                Day.ensure_one()

                # Condición §4 del plan (lock de concurrencia, Tech
                # Lead 2026-10-29): dos confirmaciones casi simultáneas
                # del PRIMER pedido de una fecha nueva verían ambas
                # "draft sin líneas" y correrían action_load() dos
                # veces → líneas duplicadas. El FOR UPDATE bloquea a
                # la segunda transacción hasta que la primera comitee;
                # como action_load() SIEMPRE escribe state/date_start
                # en esta misma fila, Postgres (REPEATABLE READ) le da
                # a la segunda un error de serialización al chocar con
                # esa fila ya cambiada — Odoo atrapa eso y reintenta la
                # petición completa desde cero, donde la segunda ya ve
                # la sesión 'loaded' con líneas y toma la rama de alta
                # incremental en vez de duplicar (mismo mecanismo ya
                # documentado en PreparationDayProductClaim.action_assign).
                self._guapante_lock_sessions(Day)

                if Day.state == 'done':
                    # Condición de Tech Lead: no silencioso. No se
                    # agrega nada, pero queda visible en los dos
                    # chatters — a David se le decide después si esto
                    # se reabre; hoy solo visibilidad.
                    note = (
                        f'Orden {order.name} confirmada después del '
                        'cierre de la jornada; no se agregó '
                        'automáticamente a esta sesión — usa '
                        'Actualizar pedidos si hace falta '
                        'incluirla.'
                    )
                    order.sudo().message_post(body=note)
                    Day.sudo().message_post(body=note)
                    _logger.warning(
                        'Guapante: orden %s confirmada para una '
                        'sesión ya cerrada (%s) — no se agregó '
                        'automáticamente.',
                        order.name, Day.date,
                    )
                    return

                if not Day.line_ids and Day.state == 'draft':
                    # Sesión recién creada por _ensure_session_for_date
                    # (nunca se había cargado): autopuebla completo
                    # con TODAS las órdenes ya confirmadas de la
                    # fecha (no solo esta), igual que un action_load()
                    # manual — reusa esa lógica en vez de duplicarla
                    # (incluye _assign_daily_sequences, _rebuild_summary
                    # y los claims del Nivel 1 vía el hook de Picking).
                    Day.action_load()
                    return

                if Day.state != 'loaded':
                    # 'draft' con líneas cargadas a medias a mano, o
                    # cualquier estado no contemplado: no se toca —
                    # mismo comportamiento que antes de e2, Ver
                    # pedidos sigue resolviéndolo manualmente. Nivel
                    # info (no warning): no es un error, solo un caso
                    # fuera del alcance de la autocarga.
                    _logger.info(
                        'Guapante: sesión %s en estado %s al '
                        'confirmar la orden %s — no se autopuebla '
                        'automáticamente (solo una sesión draft '
                        'recién creada o ya loaded reciben alta '
                        'automática).',
                        Day.date, Day.state, order.name,
                    )
                    return

                # Sesión ya 'loaded': alta incremental de SOLO esta
                # orden — nunca un action_load()/_rebuild_summary()
                # completo (rompería claims/progreso en curso de
                # otros productos, condición 1 de Tech Lead).
                existing_sale_line_ids = Day.line_ids.mapped(
                    'sale_line_id',
                ).ids
                weight_categ = self.env.ref(
                    'uom.product_uom_categ_kgm',
                    raise_if_not_found=False,
                )
                line_vals = Day._guapante_add_order_lines(
                    order, existing_sale_line_ids, weight_categ,
                )
                if not line_vals:
                    # Confirmación duplicada (idempotencia) o sin
                    # líneas elegibles — nada que hacer.
                    return

                self.env['sale.order']._assign_daily_sequences(Day.date)
                NewLines = self.env[
                    'guapante.preparation.day.line'
                ].create(line_vals)
                for Line in NewLines:
                    Day._guapante_patch_summary(Day, Line, add=True)
                    Day._guapante_after_incremental_add(Line)
                # e3 (David/Tech Lead, 2026-11-03, tras el incidente de
                # renumeración): el número append-only que la orden
                # recibió arriba vía _assign_daily_sequences es el
                # definitivo — ya no se reparte/reshuffle entre las no
                # pesadas. Nota por pedido con su Caja # final, para
                # que quede visible y auditable igual que antes.
                Day.sudo().message_post(
                    body=(
                        f'Pedido {order.name} confirmado — tomó la '
                        f'Caja #{order.daily_sequence}.'
                    ),
                )
                self.env['bus.bus']._sendone(
                    f'guapante_preparation_day-{Day.id}', 'reload', {},
                )
        except _PG_CONCURRENCY_ERRORS:
            # Nunca atrapar esto — ver _PG_CONCURRENCY_ERRORS arriba:
            # es justo el error que el FOR UPDATE de más arriba está
            # diseñado para producir en la segunda transacción; si lo
            # tragáramos acá, Odoo nunca reintentaría la petición
            # completa y la orden quedaría confirmada sin su línea de
            # Preparación.
            raise
        except Exception:
            _logger.exception(
                'Guapante: no se pudo agregar automáticamente la '
                'orden %s a la Preparación del Día de %s — la '
                'confirmación de la venta ya se guardó, pero la '
                'sesión puede haber quedado desincronizada y '
                'necesita revisión manual.',
                order.name, date_val,
            )
            try:
                with self.env.cr.savepoint():
                    order.sudo().message_post(
                        body=(
                            'La orden no se pudo agregar '
                            'automáticamente a la Preparación del '
                            'Día — usa Actualizar pedidos para '
                            'incluirla manualmente.'
                        ),
                    )
            except Exception:
                _logger.exception(
                    'Guapante: tampoco se pudo dejar la nota de '
                    'aviso en el chatter de la orden %s.', order.name,
                )

    def _guapante_after_incremental_add(self, line) -> None:
        """Punto de extensión (plan de carga automática, e2): no hace
        nada en este módulo — ist_preparation_day_picking lo
        sobreescribe para crear el claim del Nivel 1 si el producto
        es nuevo en la sesión."""
        return

    @api.depends('summary_ids')
    def _compute_summary_count(self) -> None:
        for session in self:
            session.summary_count = len(session.summary_ids)

    @api.depends('line_ids.is_done')
    def _compute_global_progress(self) -> None:
        """Calcula el progreso global de toda la sesión.

        Una sola consulta agregada para TODO el lote de self (Tech
        Lead, 2026-11-02) — la versión anterior recorría
        session.line_ids por cada sesión, y el ORM resuelve cada
        acceso como un search propio: 144 consultas para pintar una
        página de 80 sesiones (medido en staging_main). _read_group
        agrupado por (wizard_id, is_done) da total y hechas en una
        sola pasada, sin importar cuántas sesiones traiga self.
        """
        counts = {}
        if self.ids:
            groups = self.env['guapante.preparation.day.line']._read_group(
                [('wizard_id', 'in', self.ids)],
                groupby=['wizard_id', 'is_done'],
                aggregates=['__count'],
            )
            for wizard, is_done, count in groups:
                entry = counts.setdefault(wizard.id, {'total': 0, 'done': 0})
                entry['total'] += count
                if is_done:
                    entry['done'] += count
        for session in self:
            entry = counts.get(session.id, {'total': 0, 'done': 0})
            total = entry['total']
            done = entry['done']
            session.total_lines = total
            session.done_lines = done
            session.pending_lines = total - done
            session.global_progress_pct = (
                (done / total * 100.0) if total else 0.0
            )

    @api.depends('date', 'line_ids', 'line_ids.sale_order_id')
    def _compute_box_reconciliation(self) -> None:
        """Conciliación de cajas: so_count/box_diff/box_match.

        draft_count (cotizaciones pendientes) vive en su PROPIO
        compute (_compute_draft_count, Tech Lead 2026-11-02) — ver su
        docstring para el porqué.

        so_count (corrección #5, David 2026-10-31): con líneas reales
        ya cargadas, son la fuente de verdad — distinct sale_order_id
        de line_ids, sin filtrar por estado del pedido (así, un pedido
        cancelado que conserva su número sigue contando MIENTRAS sus
        líneas sigan en la sesión; si algo las borra, deja de contar,
        sin necesidad de ningún caso especial acá). El cálculo viejo
        por Pickings/fecha programada queda solo de respaldo para una
        sesión sin líneas todavía (vacía/borrador) — box_diff/box_match
        NO dependen de so_count en ningún lado (ambos fijos en
        0/True desde antes de esta corrección), así que este cambio no
        les afecta.

        so_count vía consulta agregada (Tech Lead, 2026-11-02): una
        sola _read_group para TODO el lote de self, sin recorrer
        line_ids — mismo hallazgo de rendimiento que
        _compute_global_progress. Agrupa SOLO por wizard_id, nunca
        también por is_done: un pedido con líneas en distintos estados
        de is_done contaría dos veces si el distinct de sale_order_id
        se partiera por subgrupo.
        """
        sessions_with_lines = self.filtered('line_ids')
        so_counts = {}
        if sessions_with_lines:
            groups = self.env['guapante.preparation.day.line']._read_group(
                [('wizard_id', 'in', sessions_with_lines.ids)],
                groupby=['wizard_id'],
                aggregates=['sale_order_id:count_distinct'],
            )
            so_counts = {wizard.id: count for wizard, count in groups}

        for session in self:
            if not session.date:
                session.so_count = 0
                session.box_diff = 0
                session.box_match = True
                continue

            dt_start, dt_end = _date_to_utc_range(
                self.env, session.date,
            )

            if session.line_ids:
                session.so_count = so_counts.get(session.id, 0)
            else:
                # Pickings PICK (internal) de órdenes activas para la
                # fecha. Excluir pickings cancelados Y órdenes
                # canceladas (S00217).
                Pickings = self.env['stock.picking'].sudo().search([
                    ('scheduled_date', '>=', dt_start),
                    ('scheduled_date', '<', dt_end),
                    ('picking_type_code', '=', 'internal'),
                    ('sale_id', '!=', False),
                    ('sale_id.state', 'in', ('sale', 'done')),
                    ('state', 'not in', ('cancel',)),
                ])
                pick_orders = Pickings.mapped('sale_id')
                session.so_count = len(pick_orders)

            session.box_diff = 0
            session.box_match = True

    @api.depends('date')
    def _compute_draft_count(self) -> None:
        """Cotizaciones pendientes (draft/sent) que podrían convertirse
        en cajas si el cliente confirma.

        Compute PROPIO, separado de _compute_box_reconciliation (Tech
        Lead, 2026-11-02): antes vivían juntos, y como Odoo calcula de
        una vez todos los campos de un mismo compute, pedir so_count
        (lo que hace la lista de Sesiones) disparaba también esta
        búsqueda de sale.order por sesión — aunque draft_count no se
        muestra en ninguna vista hoy (confirmado por grep). Separarlo
        hace que esta búsqueda solo corra donde de verdad se lee/
        muestra draft_count, sin arrastrar su costo a la lista.

        Mismo cálculo de siempre, sin cambios: por expected_date
        (fecha estimada de entrega) o date_order (fecha de creación).
        """
        for session in self:
            if not session.date:
                session.draft_count = 0
                continue
            dt_start, dt_end = _date_to_utc_range(self.env, session.date)
            DraftOrders = self.env['sale.order'].sudo().search([
                ('state', 'in', ('draft', 'sent')),
                '|',
                '&',
                ('expected_date', '>=', dt_start),
                ('expected_date', '<', dt_end),
                '&',
                ('date_order', '>=', dt_start),
                ('date_order', '<', dt_end),
            ])
            session.draft_count = len(DraftOrders)

    def action_view_draft_orders(self) -> dict:
        """Abre las cotizaciones (draft/sent) pendientes para self.date."""
        self.ensure_one()
        dt_start, dt_end = _date_to_utc_range(self.env, self.date)
        return {
            'name': 'Cotizaciones pendientes',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ('draft', 'sent')),
                '|',
                '&', ('expected_date', '>=', dt_start), ('expected_date', '<', dt_end),
                '&', ('date_order', '>=', dt_start), ('date_order', '<', dt_end),
            ],
        }

    def action_view_summaries(self) -> dict:
        """Abre la vista (kanban agrupado + lista) de resumen por producto."""
        self.ensure_one()
        return {
            'name': 'Productos a preparar',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.summary',
            'view_mode': 'kanban,list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'default_wizard_id': self.id,
                'search_default_group_by_status': 1,
            },
            'target': 'current',
        }

    def action_view_lines(self) -> dict:
        """Abre la lista de líneas de picking de esta sesión (corrección
        #6, David 2026-10-31) — mismo dominio que total_lines
        (len(line_ids)), para que el número del botón y las filas que
        abre siempre coincidan.

        Vista fijada explícitamente (Tech Lead, 2026-10-31): sin
        'views', Odoo elige la lista del modelo por prioridad/id, y
        con otra lista ya registrada para este modelo (la embebida en
        el form no cuenta — es ad hoc del campo, no una vista
        registrada) podría ganar una distinta a
        view_preparation_day_line_list y dejarla sin uso.

        search_view_id fijado igual (Entrega A del buscador, David/Tech
        Lead, 2026-11-01): filtros pendientes/terminadas y agrupar por
        producto/cliente/zona/caja sobre esta misma lista."""
        self.ensure_one()
        list_view = self.env.ref('ist_preparation_day.view_preparation_day_line_list')
        search_view = self.env.ref('ist_preparation_day.view_preparation_day_line_search')
        return {
            'name': 'Líneas de picking',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.line',
            'views': [(list_view.id, 'list')],
            'search_view_id': [search_view.id, search_view.name],
            'domain': [('wizard_id', '=', self.id)],
            'target': 'current',
        }

    def action_load(self) -> bool:
        """Load confirmed SO lines whose picking is scheduled on self.date."""
        if self.state == 'done':
            self.state = 'loaded'

        # Limpieza: desvincular líneas cuya orden fue cancelada o cuyo
        # movimiento ya fue procesado, para mantener la lista al día.
        LinesToUnlink = self.line_ids.filtered(
            lambda l: not l.is_done and (
                l.sale_order_id.state in ('cancel', 'draft')
                or (
                    l.stock_move_id
                    and l.stock_move_id.state in ('done', 'cancel')
                )
            )
        )
        if LinesToUnlink:
            LinesToUnlink.unlink()

        # Recrear summaries desde cero basándose en las líneas actuales.
        self.summary_ids.unlink()

        # ── Buscar órdenes via stock.picking directo ──
        # IMPORTANTE: No usar dominio sobre sale.order.picking_ids
        # porque Odoo evalúa cada condición en picking_ids como un
        # EXISTS independiente (puede matchear pickings DIFERENTES).
        #
        # Solo buscamos pickings de tipo PICK/Recolectar (internal)
        # porque el Preparation Day es para la etapa de alistamiento,
        # NO para la entrega (OUT). Si el warehouse es 1-step (solo
        # OUT), se usa outgoing como fallback.
        dt_start, dt_end = _date_to_utc_range(self.env, self.date)
        base_domain = [
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('state', 'not in', ('done', 'cancel')),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
        ]
        # Solo pickings internos (Recolectar / PICK step).
        # El Preparation Day prepara lo del PICK; el OUT hereda
        # la información que se registró aquí.
        Pickings = self.env['stock.picking'].sudo().search(
            base_domain + [('picking_type_code', '=', 'internal')]
        )
        Orders = Pickings.mapped('sale_id')
        # Solo bloquear en la PRIMERA carga (state sigue en 'draft' en este
        # punto — recién pasa a 'loaded' al final del método). Una recarga
        # posterior que resulte en cero pedidos (p. ej. porque todos se
        # cancelaron) debe dejar la sesión vacía, no romper con error.
        if not Orders and not self.line_ids and self.state == 'draft':
            raise UserError(
                'No hay pedidos pendientes para la fecha seleccionada.'
            )

        # Secuencia diaria: reinicia desde 1 cada día.
        self.env['sale.order']._assign_daily_sequences(self.date)

        existing_sale_line_ids = self.line_ids.mapped('sale_line_id').ids
        line_vals = []
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm',
            raise_if_not_found=False,
        )

        for order in Orders:
            line_vals += self._guapante_add_order_lines(
                order, existing_sale_line_ids, weight_categ,
            )

        added_count = len(line_vals)
        if added_count > 0:
            self.env['guapante.preparation.day.line'].create(line_vals)

        self._rebuild_summary()
        self.state = 'loaded'
        if not self.date_start:
            self.date_start = fields.Datetime.now()

        if added_count == 0:
            self.save_note = (
                'Listado actualizado. No se detectaron productos nuevos.'
            )
        else:
            self.save_note = (
                f'{added_count} líneas nuevas cargadas a la preparación.'
            )

        return False

    def _guapante_add_order_lines(
        self, order, existing_sale_line_ids, weight_categ,
    ) -> list:
        """Construye los line_vals de una orden para action_load().

        Extraído de action_load() (plan de carga automática, paso e1,
        2026-10-29) sin cambio de comportamiento — reusable desde los
        futuros disparadores incrementales (confirmación de orden,
        reubicación) sin tener que reconstruir toda la sesión. No crea
        las líneas: devuelve los dicts para que el llamador haga un
        solo create() en bloque, igual que antes.
        """
        self.ensure_one()
        # Desglose Cliente Principal y Zona.
        # parent_id en vez de commercial_partner_id porque este
        # último está corrupto para contactos tipo "Cocina"/"Bar".
        partner = order.partner_id
        main_cust_name = (
            partner.parent_id.name
            if partner.parent_id
            else partner.name
        )
        shipping_name = order.partner_shipping_id.name or ''

        ProductLines = order.order_line.filtered(
            lambda l: (
                l.product_id
                and not l.display_type
                # Excluir servicios (delivery, shipping charges)
                and l.product_id.type != 'service'
            )
        )
        line_vals = []
        for line in ProductLines:
            if line.id in existing_sale_line_ids:
                # Actualizar nombre retroactivamente si cambió
                ExistingPrepLine = self.line_ids.filtered(
                    lambda x: x.sale_line_id.id == line.id
                )
                if ExistingPrepLine and (
                    ExistingPrepLine.main_customer_name != main_cust_name
                    or ExistingPrepLine.zone_name != shipping_name
                ):
                    ExistingPrepLine.write({
                        'main_customer_name': main_cust_name,
                        'zone_name': shipping_name,
                    })
                continue

            # Buscar stock.move del PICK (internal/Recolectar).
            # En warehouse 2-step cada SO line genera 2 moves:
            # uno para PICK y otro para OUT. Sin este filtro,
            # limit=1 podía agarrar el OUT y el peso nunca
            # llegaba al Recolectar.
            Move = self.env['stock.move'].search([
                ('sale_line_id', '=', line.id),
                ('picking_type_id.code', '=', 'internal'),
                ('state', 'not in', ('done', 'cancel')),
            ], limit=1)
            if not Move:
                # No hay move pendiente → línea ya procesada
                # o cancelada. No cargar en la preparación.
                continue

            mode = line.uom_mode or 'unit'
            is_weight = (
                weight_categ
                and line.product_id.uom_id.category_id == weight_categ
            )
            needs_weighing = (mode == 'unit' and is_weight)

            qty_str, uom_label = self.env[
                'guapante.preparation.day.line'
            ]._get_display_qty(line)

            # Packaging: solo mostrar si el cliente pidió por unidad
            packaging_name = False
            if (
                line.product_packaging_id
                and (line.uom_mode or 'unit') == 'unit'
            ):
                packaging_name = line.product_packaging_id.name

            line_vals.append({
                'wizard_id': self.id,
                'product_id': line.product_id.product_tmpl_id.id,
                'product_product_id': line.product_id.id,
                'product_description': line.name,
                'packaging_name': packaging_name,
                'order_name': order.name,
                'sale_order_id': order.id,
                'sale_line_id': line.id,
                'stock_move_id': Move.id if Move else False,
                'main_customer_name': main_cust_name,
                'zone_name': shipping_name,
                'uom_mode': mode,
                'customer_qty_display': qty_str,
                'customer_uom_label': uom_label,
                'estimated_kg': round(line.product_uom_qty, 3),
                'actual_kg': 0.0,
                'needs_weighing': needs_weighing,
                'is_done': False,
            })
        return line_vals

    def _rebuild_summary(self) -> None:
        """Build per-product summary aggregating all lines.

        Uses an upsert pattern: updates existing summaries where possible
        and creates new ones for products not yet tracked.
        """
        existing_summaries = {
            s.product_id.id: s for s in self.summary_ids
        }
        product_totals = {}

        for line in self.line_ids:
            pid = line.product_product_id.id
            if pid not in product_totals:
                product_totals[pid] = {
                    'total_estimated_kg': 0.0,
                    'total_done_kg': 0.0,
                    'order_count': 0,
                    'available_qty': line.product_product_id.qty_available,
                }
            product_totals[pid]['total_estimated_kg'] += line.estimated_kg
            product_totals[pid]['order_count'] += 1
            if line.is_done:
                product_totals[pid]['total_done_kg'] += line.actual_kg

        # Actualizar existentes y crear nuevos
        seen_pids = set()
        create_vals = []
        for pid, totals in product_totals.items():
            totals['total_estimated_kg'] = round(
                totals['total_estimated_kg'], 3,
            )
            totals['stock_ok'] = (
                totals['available_qty'] >= totals['total_estimated_kg']
            )
            seen_pids.add(pid)

            if pid in existing_summaries:
                existing_summaries[pid].write({
                    'total_estimated_kg': totals['total_estimated_kg'],
                    'total_done_kg': round(totals['total_done_kg'], 3),
                    'order_count': totals['order_count'],
                    'available_qty': totals['available_qty'],
                    'stock_ok': totals['stock_ok'],
                })
            else:
                create_vals.append({
                    'wizard_id': self.id,
                    'product_id': pid,
                    'total_estimated_kg': totals['total_estimated_kg'],
                    'total_done_kg': round(totals['total_done_kg'], 3),
                    'order_count': totals['order_count'],
                    'available_qty': totals['available_qty'],
                    'stock_ok': totals['stock_ok'],
                })

        # Eliminar summaries de productos que ya no están en las líneas
        StaleSummaries = self.summary_ids.filtered(
            lambda s: s.product_id.id not in seen_pids
        )
        if StaleSummaries:
            StaleSummaries.unlink()

        if create_vals:
            self.env['guapante.preparation.day.summary'].create(create_vals)

    def action_save_line_weight(self, line_id: int) -> bool:
        """Called when user sets weight (via JS Enter or manual button).

        Registers the real weight in stock.move.line and marks the
        preparation line as done.
        """
        Line = self.env['guapante.preparation.day.line'].browse(line_id)
        # E7 (David/Tech Lead, 2026-11-02): ya no exige actual_kg>0 —
        # 0 es un despacho válido ("sin stock", el cliente pidió un
        # producto que no hay). El campo de peso nunca llega
        # pre-llenado en 0 por defecto (siempre empieza vacío); 0 solo
        # existe si el operario lo tecleó a propósito. Negativos ya
        # quedan bloqueados antes de este punto, en write().
        if not Line or Line.is_done:
            return False

        # Identificación por PIN (Fase 1, 2026-10-19 — migrada a este módulo 2026-10-21):
        # sin operario identificado en esta sesión de navegador no se registra el peso —
        # no hay default silencioso a la cuenta compartida. El gate solo aplica dentro de
        # un contexto HTTP real (el único camino de este método en producción) —
        # `request` es un LocalProxy sin contexto vinculado en tests/odoo-bin shell
        # (bool(request) es False ahí), donde el concepto de "operario físico" no existe.
        Employee = self.env['hr.employee']
        if request:
            employee_id = get_active_prep_operator_id(
                self.env, request.session, refresh=True,
            )
            if not employee_id:
                raise UserError(
                    'Debes identificarte con tu PIN antes de registrar un peso.'
                )
            # Ya validado (existe, active, is_guapante_prep_operator)
            # dentro de get_active_prep_operator_id.
            Employee = Employee.sudo().browse(employee_id)

        # Move cancelado en Inventario (Tech Lead, 2026-11-07; hallazgo en
        # el log de producción: 20 avisos en 48 h del núcleo «No puede
        # cambiar un movimiento de existencias cancelado…»). Odoo no
        # admite escribir quantity en un move 'cancel' (stock_move.py,
        # write): antes la tablet reventaba con ese mensaje y la línea
        # quedaba pendiente. Ahora: peso 0 → NO se toca el stock (no hay
        # nada que despachar) y la línea se termina en 0 con nota; peso
        # > 0 → error claro, mismo criterio que _sync_weight_to_stock.
        move_cancelled = bool(
            Line.stock_move_id and Line.stock_move_id.state == 'cancel'
        )
        if move_cancelled and Line.actual_kg > 0:
            raise UserError(
                f'No se puede registrar el peso de {Line.product_description} '
                f'(Caja #{Line.daily_sequence}): el movimiento de stock de '
                'esta línea está cancelado en Inventario y no admite '
                'cantidad. Despáchala en 0 (sin stock) o contacta a '
                'Inventario.'
            )

        # Registrar peso real en stock.move.line (cantidad ejecutada).
        # sudo(): el operario de bodega puede no tener permisos de
        # escritura directa sobre stock.move.line del almacén.
        # skip_inverse_visual_qty: evita que el cambio en quantity
        # propague de vuelta a sale.order.line.product_uom_qty
        # a través del campo visual_qty compute/inverse.
        if Line.stock_move_id and not move_cancelled:
            Move = Line.stock_move_id.sudo().with_context(
                skip_inverse_visual_qty=True,
                skip_recolectar_zero_check=True,
                manual_entry=True, # Contexto para Odoo 18
                guapante_wizard_intent=True, # Permitir correcciones humanas
            )

            # Odoo 18 Nativo: Al marcar 'picked' en el movimiento, habilitamos
            # la edición directa de cantidad. Odoo se encargará de crear
            # o actualizar la stock.move.line de forma estable.
            Move.write({
                'picked': True,
                'quantity': Line.actual_kg,
                'is_weight_confirmed': True,
            })

            # Sincronización de estado para asegurar persistencia
            if Move.state == 'confirmed':
                Move.write({'state': 'assigned'})

            # Asegurar que todas las líneas tengan el flag 'picked' (Odoo 18)
            if Move.move_line_ids:
                Move.move_line_ids.write({'picked': True})

            # PROPAGACIÓN EN CADENA: Inyectar peso en los movimientos siguientes (Empaque, Salida)
            # para que la cantidad llegue hasta la factura final.
            self._propagate_weight_to_chain(Move, Line.actual_kg)

        # Marcar como hecho usando skip_auto_save para evitar que
        # el override de write() vuelva a llamar este método.
        # done_by_employee_id (Tech Lead, 2026-11-02): Employee ya
        # resuelto arriba (operario de PIN en Picking) — False si esta
        # llamada corrió sin request (shell/tests).
        Line.with_context(skip_auto_save=True).write({
            'is_done': True,
            'done_by_employee_id': Employee.id,
            'done_date': fields.Datetime.now(),
        })
        Line._maybe_post_dispatch_zero_note(Employee.name or self.env.user.name)
        if move_cancelled:
            self.sudo().message_post(body=(
                f'{Employee.name or self.env.user.name} cerró '
                f'{Line.product_description} (Caja #{Line.daily_sequence}) '
                'en 0: el traslado de esta línea estaba cancelado en '
                'Inventario (no se tocó el stock).'
            ))

        # Actualizar total_done_kg en el resumen del producto
        Summary = self.summary_ids.filtered(
            lambda s: s.product_id == Line.product_product_id
        )
        if Summary:
            Summary._add_done_kg(Line.actual_kg)

        # Log de rendimiento por operario
        LastLog = self.env['guapante.picking.log'].search([
            ('user_id', '=', self.env.user.id),
            ('wizard_id', '=', self.id),
        ], order='create_date desc', limit=1)

        time_taken = 0
        if LastLog:
            time_diff = fields.Datetime.now() - LastLog.create_date
            time_taken = int(time_diff.total_seconds())

        self.env['guapante.picking.log'].create({
            'product_product_id': Line.product_product_id.id,
            'sale_order_id': Line.sale_order_id.id,
            'wizard_id': self.id,
            'actual_kg': Line.actual_kg,
            'time_taken_seconds': time_taken,
            'employee_id': Employee.id,
        })

        self.save_note = (
            f'Peso de {Line.order_name} guardado: {Line.actual_kg} kg.'
        )

        # Forzar invalidación para actualizar importes de la SO.
        # sudo(): lectura cruzada de totales puede requerir acceso
        # a líneas de facturación protegidas.
        Line.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        # Auto-finish si ya no quedan líneas pendientes
        pending_total = self.env[
            'guapante.preparation.day.line'
        ].search_count([
            ('wizard_id', '=', self.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0:
            self.action_mark_done()
            self.save_note = (
                'Todos los productos han sido empaquetados exitosamente. '
                'Sesión finalizada.'
            )

        return True

    def _propagate_weight_to_chain(self, move, weight):
        """Recursivamente inyecta el peso en los movimientos destino."""
        for dest in move.move_dest_ids:
            if dest.state not in ('done', 'cancel'):
                dest.sudo().with_context(
                    skip_recolectar_zero_check=True,
                    manual_entry=True,
                    guapante_wizard_intent=True # Autorizar el peso en toda la cadena
                ).write({
                    'picked': True,
                    'quantity': weight,
                    'is_weight_confirmed': True, # PROTEGER EL PESO EN TODA LA CADENA
                })
                # SEGUIR LA CADENA (Recursivo)
                # Odoo 18: Forzar estado 'assigned' para que acepte el peso manual
                # y no lo borre por estar "esperando otra operación".
                if dest.state in ('waiting', 'confirmed'):
                    dest.sudo().write({'state': 'assigned'})

                self._propagate_weight_to_chain(dest, weight)

    def action_mark_done(self) -> bool:
        """Mark session as done.

        Nota automática (E5, David/Tech Lead, 2026-11-02): quién y
        cuándo — simétrica con la de action_reopen(). Nunca toca
        stock ni resúmenes acá: eso ya se actualizó línea por línea,
        en el momento en que cada una se pesó (_sync_weight_to_stock +
        Summary._add_done_kg, dentro de _register_weight_from_
        productos_tab/action_save_line_weight) — para cuando se llega
        a 'done', todo lo que hay que sincronizar ya está aplicado.
        """
        self.state = 'done'
        self.date_done = fields.Datetime.now()
        self.sudo().message_post(
            body=f'Operación finalizada por {self.env.user.name}.'
        )
        return False

    def action_reopen(self) -> bool:
        """Reopen a finished session to allow adding new orders.

        E5 (David/Tech Lead, 2026-11-02): solo cambia state y
        date_done — NUNCA toca line_ids ni summary_ids. No hace
        falta: el estado de cada línea (is_done, actual_kg, done_by,
        done_date) y su stock/resumen ya quedaron consistentes al
        pesarse, independientemente de si la sesión está 'done' o
        'loaded' (ver action_mark_done) — reabrir solo LEVANTA los
        guards que bloqueaban corregir/deshacer líneas mientras la
        sesión estaba cerrada (action_undo_line de Picking, el
        bloqueo de stock_picking.write() al mover un PICK hacia esta
        sesión), nunca recalcula nada desde cero.

        date_done se limpia: ya no está Finalizada, hasta el próximo
        cierre (automático o manual) que la vuelva a estampar.

        Reapertura y re-cierre NO son simétricos — ojo con esto al dar
        soporte: el auto-cierre (pending_total==0 → action_mark_done())
        solo vive en el camino de "primer guardado" de una línea
        (_register_weight_from_productos_tab/action_save_line_weight),
        nunca en _register_weight_correction (a propósito: una
        corrección no reabre nada, no reevalúa auto-finish). Entonces
        si, tras reabrir, el administrador solo CORRIGE pesos de
        líneas ya Terminadas (sin desmarcar/re-marcar ninguna), el
        auto-cierre nunca se vuelve a disparar — la sesión queda
        'loaded' indefinidamente hasta que alguien pulse manualmente
        "Finalizar Operación" (ya visible para cualquier state==
        'loaded', sin cambios).
        """
        self.state = 'loaded'
        self.date_done = False
        self.sudo().message_post(
            body=(
                f'Operación reabierta por {self.env.user.name} — usa '
                '"Actualizar pedidos" si hay pedidos tardíos que recoger.'
            )
        )
        return False

    def action_export_excel(self) -> dict:
        """Retorna una acción de URL para descargar el consolidado en Excel."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/guapante/preparation_day/{self.id}/export_excel',
            'target': 'new',
        }


class PreparationDaySummary(models.Model):
    """Aggregated view: one row per product variant showing totals."""
    _name = 'guapante.preparation.day.summary'
    _description = 'Resumen de Preparación por Producto'
    _order = 'packing_status asc, product_id'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    total_estimated_kg = fields.Float(
        string='Total kg estimado',
        digits=(10, 3),
        readonly=True,
    )
    total_done_kg = fields.Float(
        string='Total kg hecho',
        digits=(10, 3),
    )
    order_count = fields.Integer(string='Órdenes', readonly=True)
    available_qty = fields.Float(
        string='Disponible (kg)',
        digits=(10, 3),
        readonly=True,
    )
    stock_ok = fields.Boolean(string='Stock OK', readonly=True)
    packing_status = fields.Selection(
        selection=[
            ('1_not_started', 'Sin iniciar'),
            ('2_in_progress', 'En progreso'),
            ('3_done', 'Terminado'),
        ],
        string='Estado de empaque',
        compute='_compute_progress_pct',
        store=True,
    )
    progress_pct = fields.Float(
        string='Progreso',
        compute='_compute_progress_pct',
        digits=(5, 1),
        store=True,
    )

    def _add_done_kg(self, delta: float) -> None:
        """Read-modify-write de total_done_kg bajo lock explícito
        (David/Tech Lead, 2026-11-02): sin ownership, dos líneas
        DISTINTAS del mismo producto pueden terminarse/corregirse casi
        a la vez por dos operarios — ambas tocan este mismo registro de
        resumen. SELECT ... FOR UPDATE antes de leer, para no basar el
        nuevo valor en un snapshot que la otra escritura ya dejó
        obsoleto (no alcanza con confiar en el reintento por
        serialización de Postgres)."""
        self.ensure_one()
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT id FROM guapante_preparation_day_summary '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        self.invalidate_recordset(['total_done_kg'])
        self.total_done_kg = round(max(0.0, self.total_done_kg + delta), 3)

    @api.depends(
        'wizard_id.line_ids.is_done',
        'wizard_id.line_ids.product_product_id',
    )
    def _compute_progress_pct(self) -> None:
        for rec in self:
            AllLines = rec.wizard_id.line_ids.filtered(
                lambda l: l.product_product_id == rec.product_id
            )
            DoneLines = AllLines.filtered(lambda l: l.is_done)
            if AllLines:
                rec.progress_pct = (len(DoneLines) / len(AllLines) * 100.0)
                if len(DoneLines) == 0:
                    rec.packing_status = '1_not_started'
                elif len(DoneLines) < len(AllLines):
                    rec.packing_status = '2_in_progress'
                else:
                    rec.packing_status = '3_done'
            else:
                rec.progress_pct = 0.0
                rec.packing_status = '1_not_started'

    def action_select_product(self) -> dict:
        """Abre un wizard transitorio aislado por usuario para empacar."""
        Wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].create({
            'session_id': self.wizard_id.id,
            'product_id': self.product_id.id,
            'available_qty': self.available_qty,
            'total_estimated_kg': self.total_estimated_kg,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.wizard',
            'res_id': Wizard.id,
            'view_mode': 'form',
            'target': 'current',
        }


class PreparationDayProductWizard(models.TransientModel):
    _name = 'guapante.preparation.day.product.wizard'
    _description = 'Wizard de Empaque por Producto (Aislado por Usuario)'

    session_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
    )

    available_qty = fields.Float(
        string='Disponible en stock',
        digits=(10, 3),
        readonly=True,
    )
    total_estimated_kg = fields.Float(
        string='Total kg pedido',
        digits=(10, 3),
        readonly=True,
    )

    progress_percentage = fields.Float(
        string='Progreso de Empaque',
        compute='_compute_lists',
    )

    operator_identification = fields.Char(
        string='Operario',
        compute='_compute_operator_identification',
        help=(
            'Punto de montaje del widget de identificación por PIN — el '
            'estado real vive en request.session, no en este campo.'
        ),
    )

    # Pendientes y Hechos (separados para las vistas XML)
    detail_line_pending_ids = fields.Many2many(
        'guapante.preparation.day.line',
        compute='_compute_lists',
        readonly=False,
    )
    detail_line_done_ids = fields.Many2many(
        'guapante.preparation.day.line',
        compute='_compute_lists',
        readonly=False,
    )

    @api.depends(
        'session_id.line_ids.is_done',
        'session_id.line_ids.actual_kg',
    )
    def _compute_lists(self) -> None:
        for wiz in self:
            AllLines = wiz.session_id.line_ids.filtered(
                lambda l: l.product_product_id == wiz.product_id
            )
            DoneLines = AllLines.filtered(lambda l: l.is_done)
            PendingLines = AllLines - DoneLines
            wiz.detail_line_done_ids = DoneLines.ids
            wiz.detail_line_pending_ids = PendingLines.ids
            if AllLines:
                wiz.progress_percentage = (
                    (len(DoneLines) / len(AllLines)) * 100.0
                )
            else:
                wiz.progress_percentage = 0.0

    def _compute_operator_identification(self) -> None:
        for wiz in self:
            wiz.operator_identification = ''

    def action_back_to_session(self) -> dict:
        """Regresa a la vista principal de la sesión."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day',
            'res_id': self.session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
