# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from .const_preparation import get_active_prep_operator_id

_logger = logging.getLogger(__name__)

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

        Usa flag de contexto 'skip_auto_save' para evitar recursión
        cuando estos mismos métodos vuelven a escribir en la línea.
        """
        track_kg = (
            'actual_kg' in vals
            and not self.env.context.get('skip_auto_save')
        )
        old_snapshot = {}
        if track_kg:
            old_snapshot = {
                line.id: (line.actual_kg, line.is_done) for line in self
            }

        res = super().write(vals)

        if track_kg:
            is_picking_flow = bool(self.env.context.get('guapante_picking_flow'))
            operator_employee_id = (
                get_active_prep_operator_id(request.session, refresh=True)
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
                    if new_kg > 0 and new_kg != old_kg:
                        line._register_weight_correction(
                            old_kg, is_picking_flow,
                        )
                elif new_kg > 0:
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
            Summary.total_done_kg = round(
                Summary.total_done_kg + self.actual_kg, 3,
            )

        self.with_context(skip_auto_save=True).write({'is_done': True})

        self.wizard_id.sudo().message_post(
            body=(
                f"Peso registrado desde Productos — Caja #{self.daily_sequence}: "
                f"{self.actual_kg:.3f} kg (por {self.env.user.name})."
            )
        )

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

        pending_total = self.env['guapante.preparation.day.line'].search_count([
            ('wizard_id', '=', self.wizard_id.id),
            ('is_done', '=', False),
        ])
        if pending_total == 0:
            self.wizard_id.action_mark_done()

    def _register_weight_correction(
        self, old_kg: float, has_pin_operator: bool,
    ) -> None:
        """Corrige el peso de una línea ya Terminada, editada inline desde
        Productos — re-sincroniza stock/resumen sin repetir los efectos de
        un primer guardado (no re-evalúa auto-finish, no toca date_done).
        """
        self.ensure_one()
        new_kg = self.actual_kg
        self._sync_weight_to_stock(new_kg)

        Summary = self.wizard_id.summary_ids.filtered(
            lambda s: s.product_id == self.product_product_id
        )
        if Summary:
            Summary.total_done_kg = round(
                max(0.0, Summary.total_done_kg - old_kg + new_kg), 3,
            )

        quien = 'operario con PIN activo' if has_pin_operator else self.env.user.name
        self.wizard_id.sudo().message_post(
            body=(
                f"Corrección post-cierre — Caja #{self.daily_sequence}: "
                f"peso de {old_kg:.3f} kg a {new_kg:.3f} kg "
                f"(la línea ya estaba Terminada; corregido por {quien})."
            )
        )

        self.sale_order_id.sudo().invalidate_recordset(
            ['amount_untaxed', 'amount_tax', 'amount_total']
        )

    def action_undo_line(self) -> bool:
        """Devuelve una línea de los Hechos a Pendientes para corregirla."""
        for line in self:
            if line.is_done:
                summary = line.wizard_id.summary_ids.filtered(
                    lambda s: s.product_id == line.product_product_id
                )
                if summary:
                    summary.total_done_kg = round(
                        max(0.0, summary.total_done_kg - line.actual_kg),
                        3,
                    )
                # Limpiar la cantidad ejecutada en el picking.
                # sudo(): el operario puede no tener permisos
                # de escritura directa sobre stock.move.line.
                # skip_inverse_visual_qty: misma protección que en save.
                if line.stock_move_id:
                    line.stock_move_id.sudo().with_context(
                        skip_inverse_visual_qty=True,
                    ).move_line_ids.write({'quantity': 0})
                line.with_context(skip_auto_save=True).write(
                    {'is_done': False, 'actual_kg': 0.0}
                )
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
        string='Fecha de entrega a preparar',
        required=True,
        default=fields.Date.context_today,
    )
    date_start = fields.Datetime(
        string='Fecha programada',
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
        string='Órdenes de Venta',
        compute='_compute_box_reconciliation',
        help='Cantidad de órdenes de venta confirmadas para la fecha.',
    )
    pick_count = fields.Integer(
        string='Pickings (Recolectar)',
        compute='_compute_box_reconciliation',
        help='Cantidad de pickings PICK programados para la fecha.',
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
        compute='_compute_box_reconciliation',
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

    def _guapante_relocate_picking(self, picking, old_scheduled_date):
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

                # Condición A (Tech Lead): _assign_daily_sequences salta
                # las órdenes que ya tienen número — hay que resetear
                # ANTES de pedirle uno nuevo para la fecha nueva, o se
                # queda arrastrando el de la fecha vieja (caso d de la
                # reproducción).
                Order.sudo().write({'daily_sequence': 0})
                self.env['sale.order']._assign_daily_sequences(new_date)
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

    @api.depends('summary_ids')
    def _compute_summary_count(self) -> None:
        for session in self:
            session.summary_count = len(session.summary_ids)

    @api.depends('line_ids.is_done')
    def _compute_global_progress(self) -> None:
        """Calcula el progreso global de toda la sesión."""
        for session in self:
            total = len(session.line_ids)
            done = len(session.line_ids.filtered(lambda l: l.is_done))
            session.total_lines = total
            session.done_lines = done
            session.pending_lines = total - done
            session.global_progress_pct = (
                (done / total * 100.0) if total else 0.0
            )

    @api.depends('date', 'line_ids')
    def _compute_box_reconciliation(self) -> None:
        """Conciliación de cajas: confirmadas vs cotizaciones pendientes.

        En Guapante, toda orden confirmada genera un PICK
        inmediatamente, así que so_count == pick_count siempre.
        El valor real de este indicador es mostrar cotizaciones
        draft/sent que podrían convertirse en cajas adicionales.
        """
        for session in self:
            if not session.date:
                session.so_count = 0
                session.pick_count = 0
                session.box_diff = 0
                session.box_match = True
                session.draft_count = 0
                continue

            dt_start, dt_end = _date_to_utc_range(
                self.env, session.date,
            )

            # Pickings PICK (internal) de órdenes activas para la fecha.
            # Excluir pickings cancelados Y órdenes canceladas (S00217).
            Pickings = self.env['stock.picking'].sudo().search([
                ('scheduled_date', '>=', dt_start),
                ('scheduled_date', '<', dt_end),
                ('picking_type_code', '=', 'internal'),
                ('sale_id', '!=', False),
                ('sale_id.state', 'in', ('sale', 'done')),
                ('state', 'not in', ('cancel',)),
            ])
            pick_orders = Pickings.mapped('sale_id')
            session.pick_count = len(pick_orders)
            session.so_count = len(pick_orders)

            session.box_diff = 0
            session.box_match = True

            # Cotizaciones pendientes (draft/sent) que podrían
            # llegar si el cliente confirma.
            # Buscan por expected_date (fecha estimada de entrega
            # calculada por Odoo) o date_order (fecha de creación).
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

    def action_view_confirmed_orders(self) -> dict:
        """Abre las órdenes con picking PICK confirmado para self.date."""
        self.ensure_one()
        dt_start, dt_end = _date_to_utc_range(self.env, self.date)
        Pickings = self.env['stock.picking'].sudo().search([
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
            ('state', 'not in', ('cancel',)),
        ])
        return {
            'name': 'Cajas confirmadas',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', Pickings.mapped('sale_id').ids)],
        }

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
        if not Line or Line.is_done or Line.actual_kg <= 0:
            return False

        # Identificación por PIN (Fase 1, 2026-10-19 — migrada a este módulo 2026-10-21):
        # sin operario identificado en esta sesión de navegador no se registra el peso —
        # no hay default silencioso a la cuenta compartida. El gate solo aplica dentro de
        # un contexto HTTP real (el único camino de este método en producción) —
        # `request` es un LocalProxy sin contexto vinculado en tests/odoo-bin shell
        # (bool(request) es False ahí), donde el concepto de "operario físico" no existe.
        Employee = self.env['hr.employee']
        if request:
            employee_id = get_active_prep_operator_id(request.session, refresh=True)
            if not employee_id:
                raise UserError(
                    'Debes identificarte con tu PIN antes de registrar un peso.'
                )
            Employee = Employee.sudo().browse(employee_id)
            if not Employee.exists():
                raise UserError(
                    'Tu identificación de operario ya no es válida — vuelve a '
                    'ingresar tu PIN.'
                )

        # Registrar peso real en stock.move.line (cantidad ejecutada).
        # sudo(): el operario de bodega puede no tener permisos de
        # escritura directa sobre stock.move.line del almacén.
        # skip_inverse_visual_qty: evita que el cambio en quantity
        # propague de vuelta a sale.order.line.product_uom_qty
        # a través del campo visual_qty compute/inverse.
        if Line.stock_move_id:
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
        Line.with_context(skip_auto_save=True).write({'is_done': True})

        # Actualizar total_done_kg en el resumen del producto
        Summary = self.summary_ids.filtered(
            lambda s: s.product_id == Line.product_product_id
        )
        if Summary:
            Summary.total_done_kg = round(
                Summary.total_done_kg + Line.actual_kg, 3,
            )

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
        """Mark session as done."""
        self.state = 'done'
        self.date_done = fields.Datetime.now()
        return False

    def action_reopen(self) -> bool:
        """Reopen a finished session to allow adding new orders."""
        self.state = 'loaded'
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
