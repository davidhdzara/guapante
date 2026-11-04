# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.ist_preparation_day.models.const_preparation import (
    CLAIM_STALE_MARGIN_SECONDS,
    get_active_prep_operator_id,
    get_idle_timeout_seconds,
)
from odoo.addons.ist_preparation_day.models.preparation_day import (
    _PG_CONCURRENCY_ERRORS,
)

_logger = logging.getLogger(__name__)

STOP_REASONS = [
    ('sin_stock', 'Sin stock'),
    ('mal_estado', 'Producto en mal estado'),
    ('esperando_proveedor', 'Esperando proveedor'),
    ('otro', 'Otro'),
]

# Mismos campos que CLAIM_FIELDS en preparation_picking_level1_display.js —
# duplicado a propósito (un archivo Python, uno JS, no hay forma limpia de
# compartir la constante entre los dos) — si se agrega un campo a la
# tarjeta de Nivel 1, hay que agregarlo en AMBOS lados.
CLAIM_DISPLAY_FIELDS = [
    'product_tmpl_id', 'product_tmpl_name', 'status', 'assigned_employee_id',
    'stop_reason', 'stopped_by_employee_id', 'is_mine',
    'pending_line_count', 'total_line_count',
]

# Umbral de historia mínima para confiar en la mediana de kg/unidad de una
# plantilla (Fase C, punto 1 de Tech Lead). Dato real de producción
# (2026-10-22, 23,227 líneas needs_weighing=True terminadas): con >=10
# líneas de historia, 91 de 140 plantillas quedan cubiertas y quedan
# cubiertas el 99.4% de las líneas — por debajo de eso no hay alerta,
# nunca un valor inventado.
MIN_WEIGHT_HISTORY_LINES = 10


class PreparationDayProductClaim(models.Model):
    """Nivel 1 de Picking (Fase B) — estado de trabajo por producto base
    (plantilla), una fila por (wizard_id, product_tmpl_id).

    Separado de guapante.preparation.day.summary (que es por VARIANTE, para
    la pestaña Productos) a propósito: asignar/detener/liberar es una
    operación sobre la unidad de trabajo del Nivel 1 — la plantilla, no la
    variante — y Summary ya tiene su propio ciclo de vida (se recrea en
    cada action_load) que no es el dueño natural de "quién lo tiene tomado
    ahora mismo".
    """
    _name = 'guapante.preparation.day.product.claim'
    _description = 'Nivel 1 de Picking — estado por producto base'
    _order = 'status, product_tmpl_id'
    _sql_constraints = [
        (
            'wizard_product_tmpl_uniq',
            'unique(wizard_id, product_tmpl_id)',
            'Ya existe un registro de Nivel 1 para este producto en esta sesión.',
        ),
    ]

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
    )
    # .name (no .display_name): la tarjeta de Nivel 1 no debe mostrar el
    # código interno [XXX-0000] (especificación visual, David 2026-10-23)
    # — <field name="product_tmpl_id"/> en kanban renderiza display_name,
    # que sí lo trae.
    product_tmpl_name = fields.Char(
        related='product_tmpl_id.name', string='Producto (sin código)',
    )
    assigned_employee_id = fields.Many2one(
        'hr.employee', string='Asignado a',
    )
    assigned_date = fields.Datetime(string='Asignado el')
    last_activity = fields.Datetime(
        string='Última actividad',
        help=(
            'Cuándo se registró la última acción real sobre este producto '
            '(asignarse, retomar, pesar) mientras está En progreso — base '
            'del plan f1 (Tech Lead, 2026-10-31) para distinguir un claim '
            'realmente activo de uno abandonado (operario que se fue sin '
            'cerrar sesión o cuyo tablet se quedó sin conexión). Un reloj '
            'distinto del timeout de sesión del operario (ese es por '
            'request; este es por producto) — por eso necesita su propio '
            'campo, no basta con assigned_date (se fija una sola vez al '
            'asignar/retomar, nunca se actualiza después).'
        ),
    )
    stop_reason = fields.Selection(STOP_REASONS, string='Motivo de detención')
    stopped_by_employee_id = fields.Many2one(
        'hr.employee', string='Detenido por',
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pendiente'),
            ('in_progress', 'En progreso'),
            ('stopped', 'Detenido'),
            ('done', 'Terminado'),
        ],
        compute='_compute_status',
        store=True,
    )
    # No almacenado: depende de quién está identificado AHORA en esta
    # sesión de navegador (request.session), no de un dato del registro —
    # tiene que recalcularse en cada lectura, igual que el resto de la
    # identificación por PIN en este proyecto.
    is_mine = fields.Boolean(compute='_compute_is_mine')
    pending_line_count = fields.Integer(compute='_compute_line_counts')
    total_line_count = fields.Integer(compute='_compute_line_counts')
    expected_kg_per_unit = fields.Float(
        string='Kg esperado por unidad',
        digits=(10, 4),
        readonly=True,
        help=(
            'Mediana histórica de actual_kg/estimated_kg de esta plantilla, '
            'calculada solo con líneas Terminadas y con repesaje de OTRAS '
            'sesiones (Fase C). En 0.0 cuando esa plantilla no llega a '
            f'{MIN_WEIGHT_HISTORY_LINES} líneas de historia — en ese caso la '
            'tarjeta de Nivel 2 no muestra alerta de peso, nunca un valor '
            'inventado.'
        ),
    )

    def _get_lines(self):
        self.ensure_one()
        return self.wizard_id.line_ids.filtered(
            lambda l: l.product_id == self.product_tmpl_id
        )

    @api.depends(
        'wizard_id.line_ids.is_done',
        'wizard_id.line_ids.product_id',
        'assigned_employee_id',
        'stop_reason',
    )
    def _compute_status(self) -> None:
        for claim in self:
            Lines = claim._get_lines()
            if Lines and all(line.is_done for line in Lines):
                claim.status = 'done'
            elif claim.stop_reason:
                claim.status = 'stopped'
            elif claim.assigned_employee_id:
                claim.status = 'in_progress'
            else:
                claim.status = 'pending'

    @api.depends('wizard_id.line_ids.is_done', 'wizard_id.line_ids.product_id')
    def _compute_line_counts(self) -> None:
        for claim in self:
            Lines = claim._get_lines()
            claim.total_line_count = len(Lines)
            claim.pending_line_count = len(Lines.filtered(lambda l: not l.is_done))

    def _compute_is_mine(self) -> None:
        current_employee_id = (
            get_active_prep_operator_id(self.env, request.session, refresh=False)
            if request else False
        )
        for claim in self:
            claim.is_mine = bool(
                current_employee_id
                and claim.assigned_employee_id.id == current_employee_id
            )

    # ── Infraestructura compartida ──

    def _check_picking_access(self) -> None:
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError('No tienes acceso a la pantalla de Picking.')

    def _require_active_operator(self) -> int:
        employee_id = (
            get_active_prep_operator_id(self.env, request.session, refresh=True)
            if request else False
        )
        if not employee_id:
            raise UserError(
                'Tu sesión de operario expiró por inactividad. '
                'Ingresa tu NIP de nuevo.'
            )
        return employee_id

    def _find_other_in_progress_claim(self, employee_id, exclude_self=True):
        """Mismo claim En progreso de este operario, si existe —
        extraído de _check_single_claim_per_operator (plan f2, Tech
        Lead 2026-10-31) para que action_assign()/action_resume()
        puedan recuperar el REGISTRO y armar el wizard de conflicto,
        no solo recibir un mensaje de texto."""
        domain = [
            ('wizard_id', '=', self.wizard_id.id),
            ('assigned_employee_id', '=', employee_id),
            ('status', '=', 'in_progress'),
        ]
        if exclude_self:
            domain.append(('id', '!=', self.id))
        return self.search(domain, limit=1)

    def _check_single_claim_per_operator(self, employee_id, exclude_self=True) -> None:
        """Un operario no puede tener dos productos "En progreso" al mismo
        tiempo (decisión de David, vía Tech Lead, Fase B).

        Sigue levantando UserError tal cual (Tech Lead, plan f2,
        condición 1) — NO se toca este comportamiento. action_assign()/
        action_resume() atrapan ESTE error puntual para ofrecer el
        wizard de conflicto en vez de dejarlo como mensaje seco;
        cualquier otro llamador (o un test que pruebe este helper en
        aislamiento) sigue viendo exactamente el comportamiento de
        siempre."""
        Other = self._find_other_in_progress_claim(employee_id, exclude_self)
        if Other:
            raise UserError(
                f'Ya tienes asignado {Other.product_tmpl_id.name} — '
                'termínalo o libéralo primero.'
            )

    def _open_claim_conflict_wizard(self, other_claim) -> dict:
        self.ensure_one()
        Wizard = self.env[
            'guapante.preparation.day.product.claim.conflict.wizard'
        ].create({
            'claim_id': self.id,
            'other_claim_id': other_claim.id,
        })
        return {
            'name': 'Ya tienes un producto en proceso',
            'type': 'ir.actions.act_window',
            'res_model': Wizard._name,
            'res_id': Wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _notify_bus(self) -> None:
        self.ensure_one()
        self.env['bus.bus']._sendone(
            f'guapante_preparation_day-{self.wizard_id.id}',
            'picking_claim_updated',
            {'claim_id': self.id},
        )

    @api.model
    def get_claims_for_level1_display(self, wizard_id) -> list:
        """Reemplaza el orm.searchRead directo de Nivel 1 (plan f1, Tech
        Lead 2026-10-31, puntos 1-3) — filtro en SERVIDOR, método propio y
        explícito, NUNCA un _search()/search_read() genérico: _check_
        single_claim_per_operator y action_assign necesitan ver TODOS los
        claims sin filtrar para detectar conflictos; filtrar ahí los
        dejaría ciegos.

        Sin filtro de visibilidad (E3, David/Tech Lead, 2026-11-02 —
        rediseño "operarios administradores absolutos de Picking"):
        TODOS los claims de la sesión, de cualquier estado y dueño,
        salen siempre — incluido En progreso ajeno. La ocultación de En
        progreso de otro operario que vivía acá (ver historial de este
        método antes de E3) quedó descartada junto con el resto de las
        restricciones de ownership eliminadas en E1 — ningún operario
        tiene nada que no pueda ver.

        El refresco por bus NO cambia (picking_claim_updated /
        onBusNotif() ya dispara loadRecords() en cualquier cambio) — solo
        cambia QUÉ devuelve este método, nunca el mecanismo.

        Además de CLAIM_DISPLAY_FIELDS, cada dict trae:
        - `touched_by_me` (toggle "Mis productos" del L1, Tech Lead/
          David 2026-11-02): si YO tengo el claim en progreso, lo
          detuve, o pesé al menos una línea de un producto ya Terminado.
        - `done_by_employee_name`/`done_time_label` (tarjeta "Terminado
          por X (hh:mm)", E3): nombre y hora (zona del usuario) de quien
          pesó la línea MÁS RECIENTE de un producto Terminado — False en
          ambos si el producto no tiene ninguna línea con done_date (p.
          ej. terminado antes de 4a, sin ese dato), nunca un valor
          inventado.
        - `customer_names_summary` (buscador de Nivel 1, E6, David/Tech
          Lead, 2026-11-02): nombres de cliente distintos (join con ', ',
          orden alfabético para que el resultado sea estable) de TODAS
          las líneas del producto, Terminadas y Pendientes por igual —
          alguien puede buscar un cliente cuyo pedido ya se despachó. No
          se guarda en el modelo (se recalcula en cada lectura, igual que
          touched_by_me) — el dataset es el de una sola sesión.
        - `time_working_s`/`time_stopped_s` (contadores L1, Fase 2,
          commit 4/7, Tech Lead 2026-11-04): tiempo total en_proceso/
          detenido de este producto en la sesión, en segundos — ver
          _get_time_counters_by_claim() en preparation_interval.py para
          el tope de un 'working' todavía abierto y por qué un
          'stopped' abierto no lleva tope.
        - `time_working_open_count`/`time_stopped_open_count` (lote 2B,
          3b/4): cuántos intervalos abiertos de cada tipo siguen
          tiqueando AHORA (no congelados por el tope de idle_timeout)
          — el cronómetro L1 del cliente multiplica su tick local por
          esto en vez de sumar siempre a ritmo 1x.
        Ninguno sale de un `.read()` — se calculan acá con la MISMA
        consulta agrupada sobre las líneas del lote (ver más abajo) o
        sobre los intervalos del lote (_get_time_counters_by_claim),
        nunca una consulta nueva por tarjeta.
        """
        self._check_picking_access()
        Claims = self.sudo().search([('wizard_id', '=', wizard_id)])
        my_employee_id = (
            get_active_prep_operator_id(self.env, request.session, refresh=False)
            if request else False
        )
        records = Claims.read(CLAIM_DISPLAY_FIELDS)

        # "Mis productos" + "Terminado por X (hh:mm)" + resumen de
        # clientes del buscador (L1, Tech Lead/David 2026-11-02, E3/E6):
        # UNA sola consulta sobre TODAS las líneas del lote (no solo las
        # de productos ya Terminados) sirve para las tres cosas — nunca
        # una búsqueda por claim (serían hasta ~100 por sesión).
        # search_read (no _read_group): necesitamos la IDENTIDAD del
        # último pesaje (quién + cuándo), no solo un conteo — agregar
        # done_by_employee_id y done_date por separado no garantiza que
        # vengan del MISMO renglón. Un producto terminado antes de 4a
        # (sin done_by_employee_id) no cuenta como "mío" ni aporta dato
        # de reparto — no hay dato que lo respalde, no se inventa.
        my_done_tmpl_ids = set()
        last_finisher_by_tmpl = {}
        customer_names_by_tmpl = {}
        # Contadores L1 de tiempo (Fase 2, commit 4/7, Tech Lead
        # 2026-11-04): UNA sola consulta agrupada más (igual criterio
        # que la de abajo) — nunca una por tarjeta. Ver el docstring de
        # _get_time_counters_by_claim para el tope de 'working' abierto
        # y por qué 'stopped' abierto no lleva tope.
        time_counters_by_claim = self.env[
            'guapante.preparation.interval'
        ]._get_time_counters_by_claim(wizard_id)
        all_lines = self.env['guapante.preparation.day.line'].sudo().search_read(
            domain=[('wizard_id', '=', wizard_id)],
            fields=[
                'product_id', 'main_customer_name',
                'done_by_employee_id', 'done_date',
            ],
        )
        for line in all_lines:
            if not line['product_id']:
                continue
            tmpl_id = line['product_id'][0]
            if line['main_customer_name']:
                customer_names_by_tmpl.setdefault(tmpl_id, set()).add(
                    line['main_customer_name']
                )
            if line['done_by_employee_id']:
                employee_id, employee_name = line['done_by_employee_id']
                if my_employee_id and employee_id == my_employee_id:
                    my_done_tmpl_ids.add(tmpl_id)
                current = last_finisher_by_tmpl.get(tmpl_id)
                if not current or line['done_date'] > current['done_date']:
                    last_finisher_by_tmpl[tmpl_id] = {
                        'employee_name': employee_name,
                        'done_date': line['done_date'],
                    }
        for record in records:
            tmpl_id = record['product_tmpl_id'][0] if record['product_tmpl_id'] else False
            record['touched_by_me'] = bool(my_employee_id) and (
                record['is_mine']
                or (
                    record['stopped_by_employee_id']
                    and record['stopped_by_employee_id'][0] == my_employee_id
                )
                or (record['status'] == 'done' and tmpl_id in my_done_tmpl_ids)
            )
            finisher = (
                last_finisher_by_tmpl.get(tmpl_id)
                if record['status'] == 'done' else None
            )
            record['done_by_employee_name'] = (
                finisher['employee_name'] if finisher else False
            )
            record['done_time_label'] = (
                fields.Datetime.context_timestamp(
                    self.env.user, finisher['done_date'],
                ).strftime('%H:%M')
                if finisher else False
            )
            record['customer_names_summary'] = ', '.join(
                sorted(customer_names_by_tmpl.get(tmpl_id, set()))
            )
            counters = time_counters_by_claim.get(record['id'], {
                'time_working_s': 0, 'time_stopped_s': 0,
                'time_working_open_count': 0, 'time_stopped_open_count': 0,
            })
            record['time_working_s'] = counters['time_working_s']
            record['time_stopped_s'] = counters['time_stopped_s']
            # lote 2B, 3b/4: cuántos intervalos abiertos de cada tipo
            # siguen tiqueando AHORA mismo — el cronómetro L1 del
            # cliente multiplica su tick local por esto en vez de
            # sumar siempre a ritmo 1x (ver docstring de
            # _get_time_counters_by_claim).
            record['time_working_open_count'] = counters['time_working_open_count']
            record['time_stopped_open_count'] = counters['time_stopped_open_count']
        return records

    # ── Acciones ──

    def action_assign(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        try:
            self._check_single_claim_per_operator(employee_id)
        except UserError:
            # Plan f2 (Tech Lead, 2026-10-31): SOLO este conflicto puntual
            # (el operario ya tiene otro En progreso) abre el wizard — el
            # UserError de más abajo (OTRO operario ya se asignó ESTE
            # mismo claim, o está Detenido/Terminado) sigue siendo un
            # mensaje seco normal, nunca pasa por acá.
            Other = self._find_other_in_progress_claim(employee_id)
            return self._open_claim_conflict_wizard(Other)

        # Postgres corre en REPEATABLE READ: este SELECT ... FOR UPDATE no
        # hace que un segundo tablet "vea" el valor recién escrito por el
        # primero en cuanto se libera el lock dentro de su misma
        # transacción — a ese nivel de aislamiento, Postgres le devuelve un
        # error de serialización ("could not serialize access due to
        # concurrent update"), que Odoo captura y reintenta el request
        # completo. Es en ESE reintento (una ejecución nueva de este mismo
        # método, con una transacción nueva) donde la lectura de abajo ya
        # ve assigned_employee_id puesto y lanza el UserError — no es que
        # este SELECT vea el dato fresco dentro de la transacción actual.
        # El resultado neto es el mismo (el segundo tablet nunca pisa al
        # primero), pero el mecanismo real es "falla y reintenta", no
        # "espera y lee fresco".
        #
        # flush_recordset() antes del SQL crudo: el write() del ORM no
        # manda el UPDATE a la base de inmediato, lo deja en el caché en
        # memoria hasta el próximo flush — sin esto, un SELECT crudo justo
        # después de otra acción de este mismo método (ej. la propia
        # action_assign() de un test, dentro de la misma transacción)
        # puede leer el valor viejo de la tabla real y dar un falso
        # negativo (bug encontrado por los tests de la Fase B).
        #
        # El SELECT bloqueado tiene que leer TODO lo que decide si este
        # claim es tomable — no solo assigned_employee_id (hallazgo de
        # Tech Lead): un claim Detenido queda sin dueño, así que mirar
        # solo assigned_employee_id dejaba que "Asignarme" tomara un
        # producto detenido (saltándose Retomar y su chatter) o uno ya
        # Terminado.
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id, stop_reason FROM '
            'guapante_preparation_day_product_claim WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        locked_assigned_id, locked_stop_reason = row if row else (False, False)
        Lines = self._get_lines()
        is_done = bool(Lines) and all(line.is_done for line in Lines)
        if locked_assigned_id:
            self.invalidate_recordset(['assigned_employee_id'])
            raise UserError(
                f'{self.assigned_employee_id.name} ya se asignó '
                f'{self.product_tmpl_id.name} — actualiza la pantalla.'
            )
        if locked_stop_reason:
            raise UserError(
                f'{self.product_tmpl_id.name} está detenido — usa Retomar. '
                'Actualiza la pantalla.'
            )
        if is_done:
            raise UserError(
                f'{self.product_tmpl_id.name} ya está terminado — '
                'actualiza la pantalla.'
            )
        now = fields.Datetime.now()
        self.write({
            'assigned_employee_id': employee_id,
            'assigned_date': now,
            'last_activity': now,
        })
        self._notify_bus()
        return self.action_open_lines_kanban()

    def action_resume(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        try:
            self._check_single_claim_per_operator(employee_id)
        except UserError:
            # Mismo wizard de conflicto que action_assign() — ver su
            # comentario (plan f2, Tech Lead 2026-10-31).
            Other = self._find_other_in_progress_claim(employee_id)
            return self._open_claim_conflict_wizard(Other)

        # Misma protección, misma explicación y mismo flush_recordset()
        # previo que action_assign.
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT stop_reason FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row or not row[0]:
            self.invalidate_recordset(['stop_reason'])
            raise UserError(
                f'{self.product_tmpl_id.name} ya no está detenido — '
                'actualiza la pantalla.'
            )
        # Caso borde (Tech Lead): si todas las líneas quedaron is_done por
        # otra vía (ej. edición directa en la pestaña Productos) mientras
        # el claim seguía con stop_reason puesto, el status computado ya
        # muestra 'done' — Retomar no debe revivirlo.
        Lines = self._get_lines()
        if Lines and all(line.is_done for line in Lines):
            raise UserError(
                f'{self.product_tmpl_id.name} ya está terminado — '
                'actualiza la pantalla.'
            )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        now = fields.Datetime.now()
        self.write({
            'assigned_employee_id': employee_id,
            'assigned_date': now,
            'last_activity': now,
            'stop_reason': False,
            'stopped_by_employee_id': False,
        })
        self.wizard_id.sudo().message_post(
            body=f"Retomado — {self.product_tmpl_id.name}: por {Employee.name}.",
        )
        # Fase 2 (bug encontrado por Odoo Engineer, 2026-11-04): a
        # diferencia de action_unstop(), esto NO cerraba el intervalo
        # 'stopped' que action_stop() dejó abierto — quedaba huérfano
        # para siempre (nunca lo cierra el cron de abandono de claims,
        # que solo mira status='in_progress'). end_dt=now() (acción
        # explícita del operario, igual que el resto del archivo) —
        # nunca last_touched_dt, que en un 'stopped' es siempre igual a
        # start_dt (ver el campo en preparation_interval.py).
        Interval = self.env['guapante.preparation.interval']
        Interval._run_isolated(
            f'action_resume claim={self.id}',
            lambda: Interval._close_open_for_claim(self, 'stopped', 'resumed', now),
        )
        self._notify_bus()
        return self.action_open_lines_kanban()

    def action_unstop(self) -> bool:
        """"Liberar" un Detenido (entrega 2, Tech Lead/David, 2026-11-02):
        a diferencia de action_resume(), NO lo toma para quien lo libera
        — solo quita el motivo y vuelve a Pendiente, sin dueño, para que
        cualquiera lo tome después con Asignarme. Mismo motivo que
        action_resume() para no exigir ownership: un Detenido no tiene
        dueño, así que cualquier operario con NIP vigente puede hacerlo."""
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()

        # Mismo flush_recordset()/SELECT ... FOR UPDATE que el resto del
        # archivo. Se bloquea también stopped_by_employee_id porque el
        # chatter necesita su valor de ANTES de limpiarlo (punto 2 de
        # Tech Lead) — leerlo de la fila bloqueada es la misma garantía
        # de concurrencia que ya usa action_assign() con assigned_employee_id.
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT stop_reason, stopped_by_employee_id FROM '
            'guapante_preparation_day_product_claim WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        locked_stop_reason, locked_stopped_by_id = row if row else (False, False)
        if not locked_stop_reason:
            self.invalidate_recordset(['stop_reason'])
            raise UserError(
                f'{self.product_tmpl_id.name} ya no está detenido — '
                'actualiza la pantalla.'
            )
        # Mismo caso borde que action_resume(): si las líneas ya quedaron
        # is_done por otra vía mientras seguía con stop_reason puesto, no
        # revive — ya está Terminado.
        Lines = self._get_lines()
        if Lines and all(line.is_done for line in Lines):
            raise UserError(
                f'{self.product_tmpl_id.name} ya está terminado — '
                'actualiza la pantalla.'
            )
        ReleasingEmployee = self.env['hr.employee'].sudo().browse(employee_id)
        StoppedByEmployee = (
            self.env['hr.employee'].sudo().browse(locked_stopped_by_id)
            if locked_stopped_by_id else False
        )
        self.write({
            'stop_reason': False,
            'stopped_by_employee_id': False,
        })
        # Fase 2: cierra el intervalo 'stopped' de este producto — y,
        # por si alguien entró a verlo bajo E3 (sin ownership, Nivel 2
        # no exige que el claim esté 'in_progress'), también cualquier
        # 'working' que hubiera quedado abierto ahí. Liberar deja el
        # producto disponible para cualquiera; el contexto de quien
        # estuviera adentro queda cerrado con este evento.
        now = fields.Datetime.now()
        Interval = self.env['guapante.preparation.interval']

        def _close_stopped_and_working():
            Interval._close_open_for_claim(self, 'stopped', 'released', now)
            Interval._close_open_for_claim(self, 'working', 'released', now)
        # _run_isolated (Tech Lead, revisión de 4/7, 2026-11-04): el
        # tiempo es dato secundario — un fallo acá nunca debe tumbar
        # la liberación misma (ya escrita arriba).
        Interval._run_isolated(
            f'action_unstop claim={self.id}', _close_stopped_and_working,
        )
        reason_label = dict(STOP_REASONS).get(
            locked_stop_reason, locked_stop_reason,
        )
        stopped_by_name = StoppedByEmployee.name if StoppedByEmployee else 'nadie'
        self.wizard_id.sudo().message_post(
            body=(
                f"Liberado — {self.product_tmpl_id.name}: vuelve a "
                f"Pendiente (por {ReleasingEmployee.name}; estaba "
                f"detenido por {reason_label}, por {stopped_by_name})."
            ),
        )
        self._notify_bus()
        return True

    def action_release(self) -> bool:
        """Sin ownership (David/Tech Lead, 2026-11-03 — "operarios
        administradores absolutos del módulo de Picking"): cualquier
        operario con NIP vigente puede liberar el claim de CUALQUIERA,
        no solo el suyo — mismo criterio que ya tenía action_unstop()
        para un Detenido ("un Detenido no tiene dueño, cualquier
        operario con NIP vigente puede hacerlo"), ahora extendido a un
        claim En progreso. El control de "esta caja no es tuya" que
        vivía acá se elimina a propósito, no es un descuido — igual
        que _check_picking_ownership() en preparation_day_line.py.

        Trazabilidad cruzada: nota automática en el chatter SOLO
        cuando el actor no es el dueño actual (quién liberó el
        producto de quién) — si el actor es el propio dueño, no hace
        falta ninguna nota nueva (_notify_bus() ya avisa a los demás
        tablets)."""
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()

        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        current_owner_id = row[0] if row else False
        self.invalidate_recordset(['assigned_employee_id'])
        if not current_owner_id:
            raise UserError(
                f'{self.product_tmpl_id.name} ya no está asignado a '
                'nadie — actualiza la pantalla.'
            )
        if current_owner_id != employee_id:
            Actor = self.env['hr.employee'].sudo().browse(employee_id)
            Owner = self.env['hr.employee'].sudo().browse(current_owner_id)
            self.wizard_id.sudo().message_post(
                body=(
                    f"{Actor.name} liberó {self.product_tmpl_id.name}: "
                    f"estaba asignado a {Owner.name}."
                ),
            )
        self._release_claim()
        return True

    def _release_claim(self, close_reason='released', use_last_touched=False) -> None:
        """Núcleo de la liberación — SIN `request`, sin validar ownership
        (eso ya lo hizo el llamador, que sabe POR QUÉ libera): comparte el
        mismo invariante (estado limpio + aviso de bus) entre action_release()
        (el propio operario), _release_claims_for_employee() ("Cerrar") y el
        cron de abandono (plan f1, Tech Lead 2026-10-31) — un solo lugar
        que mantener si algún día esto necesita tocar algo más (ej. Fase 2
        de tiempos).

        Fase 2 (condición (b), Tech Lead 2026-11-04): action_release()
        y _release_claims_for_employee() son SIEMPRE explícitos (alguien
        clicó Liberar, o Cerrar sesión) — usan los defaults
        (close_reason='released', end_dt=now()). El cron de abandono de
        claims NO es explícito — pasa close_reason='idle',
        use_last_touched=True, para que el intervalo cierre con su
        propio last_touched_dt (última actividad real), nunca con la
        hora en que corrió el cron."""
        self.ensure_one()
        self.write({
            'assigned_employee_id': False,
            'assigned_date': False,
            'last_activity': False,
        })
        end_dt = None if use_last_touched else fields.Datetime.now()
        Interval = self.env['guapante.preparation.interval']
        # _run_isolated (Tech Lead, revisión de 4/7): el tiempo es
        # dato secundario — un fallo acá nunca debe tumbar la
        # liberación del claim (ya escrita arriba) ni el aviso de bus
        # de abajo.
        Interval._run_isolated(
            f'_close_open_for_claim claim={self.id} {close_reason}',
            lambda: Interval._close_open_for_claim(
                self, 'working', close_reason, end_dt,
            ),
        )
        self._notify_bus()

    def _effective_last_activity(self):
        """Corrección de Tech Lead (2026-10-31, defecto bloqueante del
        primer diff): un claim En progreso HEREDADO de antes de que
        existiera `last_activity` (los que ya hay hoy en producción y
        staging) tiene ese campo en False — tratarlo como "sin
        actividad nunca" lo dejaba OCULTO para todos los no-admin Y
        fuera del dominio del cron (`last_activity != False`): huérfano
        invisible para siempre. COALESCE con assigned_date y, si
        tampoco hay, write_date — ambos son una fecha real de cuándo se
        tocó el claim por última vez, aunque menos precisa que
        last_activity."""
        self.ensure_one()
        return self.last_activity or self.assigned_date or self.write_date

    @api.model
    def _release_claims_for_employee(self, employee_id) -> None:
        """Libera TODOS los claims En progreso de este operario — llamada
        desde /clear_operator ("Cerrar" explícito, plan f1): propia
        petición, propio commit, nunca desde get_active_prep_operator_id
        (ver docstring del controlador)."""
        Claims = self.sudo().search([
            ('assigned_employee_id', '=', employee_id),
            ('status', '=', 'in_progress'),
        ])
        for claim in Claims:
            claim._release_claim()

    def action_stop(self, reason: str) -> bool:
        """Sin ownership (David/Tech Lead, 2026-11-03 — "operarios
        administradores absolutos del módulo de Picking"): cualquier
        operario con NIP vigente puede detener el claim de
        CUALQUIERA, no solo el suyo — ver el mismo razonamiento en
        action_release(). El motivo sigue siendo obligatorio
        (reason not in STOP_REASONS ya lo exige, sin cambios).

        Trazabilidad cruzada: la nota de "Detenido" ya incluye quién
        lo detuvo; cuando el actor no es el dueño actual, se le agrega
        a quién se le quitó."""
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        if reason not in dict(STOP_REASONS):
            raise UserError('Motivo de detención inválido.')

        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        current_owner_id = row[0] if row else False
        self.invalidate_recordset(['assigned_employee_id'])
        if not current_owner_id:
            raise UserError(
                f'{self.product_tmpl_id.name} ya no está asignado a '
                'nadie — actualiza la pantalla.'
            )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        now = fields.Datetime.now()
        self.write({
            'assigned_employee_id': False,
            'assigned_date': False,
            'stop_reason': reason,
            'stopped_by_employee_id': employee_id,
        })
        # Fase 2: Detener cierra el trabajo de TODOS los que tuvieran
        # Nivel 2 abierto sobre este producto en este instante (end_dt=
        # now(), acción explícita que le pone fin al trabajo de
        # cualquiera ahí, sea o no quien detiene) y abre un 'stopped'
        # informativo (employee_id = quien detiene, no es el reloj de
        # nadie — ver docstring del modelo).
        Interval = self.env['guapante.preparation.interval']

        def _close_working_and_open_stopped():
            Interval._close_open_for_claim(self, 'working', 'stopped', now)
            Interval.sudo().create({
                'wizard_id': self.wizard_id.id,
                'claim_id': self.id,
                'employee_id': employee_id,
                'kind': 'stopped',
                'stop_reason': reason,
                'start_dt': now,
                'last_touched_dt': now,
            })
        # _run_isolated (Tech Lead, revisión de 4/7): el tiempo es
        # dato secundario — un fallo acá nunca debe tumbar el Detener
        # mismo (ya escrito arriba, stop_reason/stopped_by_employee_id).
        Interval._run_isolated(
            f'action_stop claim={self.id}', _close_working_and_open_stopped,
        )
        cross_operator_note = ''
        if current_owner_id != employee_id:
            Owner = self.env['hr.employee'].sudo().browse(current_owner_id)
            cross_operator_note = f' — se lo quitó a {Owner.name}.'
        self.wizard_id.sudo().message_post(
            body=(
                f"Detenido — {self.product_tmpl_id.name}: "
                f"{dict(STOP_REASONS)[reason]} (por {Employee.name})."
                f"{cross_operator_note}"
            ),
        )
        self._notify_bus()
        return True

    def action_open_stop_wizard(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        return {
            'name': f'¿Por qué se detiene {self.product_tmpl_id.name}?',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.claim.stop.wizard',
            'view_mode': 'form',
            # 'views' explícito — ver nota en action_view_product_claims
            # (preparation_day.py): _preprocessAction del cliente web
            # hace action.views.map(...) sin validar que exista.
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_claim_id': self.id},
        }

    def action_open_scrap_wizard(self) -> dict:
        """Fase D — engrane de Nivel 1, "Desechar": abre el MISMO diálogo
        nativo que stock.picking.button_scrap (stock_scrap_form_view2,
        target=new), sin formulario propio. Sin default_origin (Tech
        Lead, corrección 1: ese campo no está en la vista form2 — los
        default_* solo aplican a campos que la vista pide en
        default_get — el Documento origen quedaría vacío; se escribe en
        preparation_day_scrap.py:StockScrap.do_scrap(), el único punto
        por el que pasan tanto el camino feliz como el del asistente de
        cantidad insuficiente).

        picking_wizard_id/picking_claim_id en contexto (no
        default_picking_id — Tech Lead: "un producto abarca varios
        pedidos"): do_scrap() los exige cuando ve guapante_picking_flow,
        nunca cae al flujo sin chequeo (corrección 2 de Tech Lead).
        """
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        if self.assigned_employee_id.id != employee_id:
            raise UserError(
                f'No puedes desechar {self.product_tmpl_id.name} — '
                'no está asignado a ti.'
            )
        View = self.env.ref('stock.stock_scrap_form_view2')
        return {
            'name': 'Desechar productos',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.scrap',
            'view_mode': 'form',
            'view_id': View.id,
            'views': [(View.id, 'form')],
            'target': 'new',
            'context': {
                'product_ids': self.product_tmpl_id.product_variant_ids.ids,
                # guapante.preparation.day no tiene company_id propio
                # (bug real encontrado en navegador: "object has no
                # attribute 'company_id'") — la compañía activa del
                # entorno es la correcta acá, igual que para cualquier
                # otro flujo de Picking (single-company en Guapante).
                'default_company_id': self.env.company.id,
                'guapante_picking_flow': True,
                'picking_wizard_id': self.wizard_id.id,
                'picking_claim_id': self.id,
            },
        }

    def action_open_lines_kanban(self) -> dict:
        """Nivel 2 real (Fase C) como client action propio
        (especificación visual, 2026-10-23 — decisión final de Tech
        Lead tras dos rondas de kanban nativo + t-inherit que nunca
        igualaron la tarjeta de Taller real). El componente OWL
        (preparation_picking_level2_display.js) resuelve este claim por
        su id (orm.read) y carga las líneas con orm.searchRead — ya no
        hace falta 'views'/'help' ni domain armado acá (eso era
        específico de un ir.actions.act_window), ni picking_wizard_id en
        contexto: el componente lo obtiene leyendo el propio claim.

        context: 'guapante_picking_flow' vive en la ACCIÓN (no solo en
        llamadas RPC sueltas) porque el watcher de inactividad lo lee de
        action.currentController.action.context
        (preparation_picking_idle_watcher.js) — mismo motivo que en
        action_view_product_claims (preparation_day.py).

        Fase 2 (Tech Lead, 2026-11-04): ÚNICO punto de apertura de un
        intervalo 'working' (ver guapante.preparation.interval._open_
        working) — Asignarme/Retomar terminan llamando este método, y
        la tarjeta de CUALQUIER estado en el L1 también lo llama
        directo (onContinue, sin pasar por asignar/retomar), así que
        acá cubre los tres caminos sin tocar el cliente para esto. Se
        abre SIEMPRE, sin importar el estado del claim — entrar a
        corregir un producto ya Terminado también es trabajo real que
        debe contar.
        """
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        Interval = self.env['guapante.preparation.interval']
        # _run_isolated (Tech Lead, revisión de 4/7, 2026-11-04): el
        # tiempo es dato secundario — un fallo de _open_working nunca
        # debe impedir entrar a Nivel 2 (lo que este método devuelve
        # abajo).
        Interval._run_isolated(
            f'_open_working claim={self.id} empleado={employee_id}',
            lambda: Interval._open_working(self, employee_id),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'guapante_picking_level2',
            'name': self.product_tmpl_id.name,
            'target': 'fullscreen',
            'context': {
                'guapante_picking_flow': True,
                'claim_id': self.id,
            },
        }

    def action_close_my_interval(self) -> bool:
        """Fase 2 (servidor listo para el lote 2B, Tech Lead
        2026-11-04) — cierra el intervalo 'working' ABIERTO de ESTE
        operario sobre ESTE claim cuando sale de Nivel 2 por su cuenta
        ("← Productos", "Cerrar", "Cerrar sesión"). close_reason=
        'left', end_dt=now() (salida explícita: cuenta como actividad
        real en este instante, no se usa last_touched_dt).

        Sin cliente que lo llame todavía (lote 2B agrega el orm.call en
        preparation_picking_level2_display.js) — hoy "Cerrar"/"Cerrar
        sesión" ya cierran el intervalo por otra vía (ver
        _close_open_working_for_employee en el controlador de NIP);
        este método cubre específicamente "← Productos", que hoy es
        navegación pura del cliente sin ningún RPC.

        No-op si no hay nada abierto acá (ya se cerró por otra vía, o
        el operario solo entró a mirar y nunca pesó nada — en ese caso
        el intervalo sigue abierto hasta que algo más lo cierre, nunca
        se fuerza un cierre falso por no encontrar uno activo)."""
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        Interval = self.env['guapante.preparation.interval']

        def _close_my_open_interval():
            Open = Interval.sudo().search([
                ('employee_id', '=', employee_id),
                ('claim_id', '=', self.id),
                ('kind', '=', 'working'),
                ('end_dt', '=', False),
            ], limit=1)
            if Open:
                Open._close('left', fields.Datetime.now())
        # _run_isolated (Tech Lead, revisión de 4/7): el tiempo es
        # dato secundario — un fallo acá nunca debe impedir la
        # navegación ("← Productos"/Cerrar) que este método acompaña.
        Interval._run_isolated(
            f'action_close_my_interval claim={self.id} '
            f'empleado={employee_id}', _close_my_open_interval,
        )
        return True

    def get_my_open_interval(self) -> dict:
        """Fase 2 (lote 2B, Tech Lead 2026-11-04) — lectura de solo
        consulta para el cronómetro de Nivel 2: fuente de verdad del
        start_dt del intervalo 'working' ABIERTO de este operario
        sobre este claim, más la hora del servidor en el mismo
        instante, para que el cliente calcule el tiempo transcurrido
        sin depender del reloj de la tablet. UN solo mecanismo tanto
        para la carga inicial de Nivel 2 como para cada
        resincronización (bus 'reload', visibilitychange) — nunca dos
        caminos distintos para leer lo mismo.

        refresh=False (mismo criterio que _compute_is_mine arriba):
        una resincronización pasiva en segundo plano no debe extender
        la ventana de inactividad del operario — si lo hiciera, dejar
        la pestaña abierta nunca vencería la sesión.

        Nunca escribe nada. Si no hay intervalo abierto (ya se cerró
        por otra vía, o el operario solo entró a mirar sin pesar),
        start_dt viene en False — el cronómetro del cliente se queda
        en 00:00 sin tiquear, nunca inventa un inicio."""
        self.ensure_one()
        self._check_picking_access()
        employee_id = (
            get_active_prep_operator_id(self.env, request.session, refresh=False)
            if request else False
        )
        server_now = fields.Datetime.now()
        if not employee_id:
            return {'start_dt': False, 'server_now': server_now}
        Interval = self.env['guapante.preparation.interval']
        open_interval = Interval.sudo().search([
            ('employee_id', '=', employee_id),
            ('claim_id', '=', self.id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ], limit=1)
        return {
            'start_dt': open_interval.start_dt if open_interval else False,
            'server_now': server_now,
        }

    # ── Ciclo de vida (Tech Lead, Fase B: robusto en creación de líneas,
    #    no solo en action_load; nunca borrar un claim con líneas, aunque
    #    estén todas done — solo los que no tienen ninguna) ──

    @api.model
    def _refresh_expected_kg_per_unit(self, wizard, templates) -> None:
        """Recalcula expected_kg_per_unit de los claims de `templates` en
        `wizard` (Fase C, punto 1 de Tech Lead).

        Una sola consulta agrupada, acotada a las plantillas de ESTA
        sesión (10-30 típico, nunca las ~140 plantillas pesables del
        catálogo completo) — evita 1 query por tarjeta. Excluye
        explícitamente las líneas de `wizard` (wizard_id != %s): lo que se
        está pesando HOY no puede colarse en su propia referencia
        histórica (pedido explícito de Tech Lead) — si no, un operario
        quedaría comparado contra pesos que él mismo acaba de teclear en
        esta misma sesión.
        """
        if not templates:
            return
        # flush_model() sobre Line, no sobre self: lo que puede estar sin
        # bajar a la tabla real es el write() de action_save_line_weight
        # de otra línea en esta misma transacción (ej. action_load
        # corriendo justo después de un pesaje), no un write de Claim.
        self.env['guapante.preparation.day.line'].flush_model()
        self.env.cr.execute(
            '''
            SELECT product_id,
                   percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY actual_kg / estimated_kg
                   ) AS median_kg_per_unit
            FROM guapante_preparation_day_line
            WHERE is_done = true
              AND needs_weighing = true
              AND estimated_kg > 0
              AND actual_kg > 0
              AND wizard_id != %s
              AND product_id = ANY(%s)
            GROUP BY product_id
            HAVING count(*) >= %s
            ''',
            (wizard.id, templates.ids, MIN_WEIGHT_HISTORY_LINES),
        )
        medians = dict(self.env.cr.fetchall())
        Claims = self.sudo().search([
            ('wizard_id', '=', wizard.id),
            ('product_tmpl_id', 'in', templates.ids),
        ])
        for claim in Claims:
            claim.expected_kg_per_unit = medians.get(
                claim.product_tmpl_id.id, 0.0,
            )

    @api.model
    def _ensure_claims_for_templates(self, wizard, templates) -> None:
        if not templates:
            return
        # sudo(): la creación de claims es mantenimiento interno, no una
        # acción de UI — el ACL del grupo de Picking no da create (Tech
        # Lead, punto 10), a propósito, para que nadie cree uno a mano.
        Existing = self.sudo().search([
            ('wizard_id', '=', wizard.id),
            ('product_tmpl_id', 'in', templates.ids),
        ])
        existing_tmpl_ids = set(Existing.mapped('product_tmpl_id').ids)
        Missing = templates.filtered(lambda t: t.id not in existing_tmpl_ids)
        if Missing:
            self.sudo().create([
                {'wizard_id': wizard.id, 'product_tmpl_id': tmpl.id}
                for tmpl in Missing
            ])

    @api.model
    def _cron_release_abandoned_claims(self) -> None:
        """Plan f1 (Tech Lead, 2026-10-31) — libera de verdad en base de
        datos los claims En progreso que get_claims_for_level1_display ya
        trata como abandonados (mismo umbral: get_idle_timeout_seconds(env)
        + CLAIM_STALE_MARGIN_SECONDS sin actividad, mismo instante
        efectivo — ver _effective_last_activity). Corre cada 5 minutos,
        no es el mecanismo de visibilidad (eso ya lo cubre el método de
        lectura) — es la red de seguridad que de verdad libera el
        producto para que otro pueda tomarlo con Asignarme, no solo
        verlo.

        Dominio por `status`, no por `assigned_employee_id` a secas
        (Tech Lead, corrección 2): un Detenido es una pausa JUSTIFICADA,
        nunca abandono — y aunque hoy action_stop() ya limpia
        assigned_employee_id (así que nunca calificaría de todas formas),
        filtrar por status es la verificación explícita, no un supuesto
        sobre cómo se comporta otro método.

        Timeout 0 ("sin bloqueo", fila 3 del backlog, 2026-11-01): no
        libera nada — sale temprano. Igual que en
        get_claims_for_level1_display, no tiene sentido colapsar el
        umbral a solo CLAIM_STALE_MARGIN_SECONDS.

        Mismo patrón que _cron_repair_missing_orders (e4, preparation_day.py):
        savepoint por claim, un error de concurrencia se atrapa LOCAL
        (nunca se relanza — no debe tumbar el trabajo ya hecho en otros
        claims de esta misma corrida)."""
        idle_timeout = get_idle_timeout_seconds(self.env)
        if not idle_timeout:
            return
        stale_cutoff = fields.Datetime.now() - timedelta(
            seconds=idle_timeout + CLAIM_STALE_MARGIN_SECONDS,
        )
        Claims = self.sudo().search([('status', '=', 'in_progress')])
        Claims = Claims.filtered(
            lambda c: (
                c._effective_last_activity()
                and c._effective_last_activity() < stale_cutoff
            )
        )
        for claim in Claims:
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        'SELECT assigned_employee_id, stop_reason, '
                        'last_activity, assigned_date, write_date FROM '
                        'guapante_preparation_day_product_claim WHERE id = %s '
                        'FOR UPDATE',
                        (claim.id,),
                    )
                    row = self.env.cr.fetchone()
                    if not row or not row[0] or row[1]:
                        # Ya se liberó, o pasó a Detenido, entre el search
                        # y el lock — en ambos casos, nada que hacer.
                        continue
                    locked_effective = row[2] or row[3] or row[4]
                    if locked_effective and locked_effective >= stale_cutoff:
                        continue  # hubo actividad real entre el search y el lock.
                    claim.invalidate_recordset([
                        'assigned_employee_id', 'stop_reason',
                        'last_activity', 'assigned_date',
                    ])
                    employee_name = claim.assigned_employee_id.name
                    product_name = claim.product_tmpl_id.name
                    # Fase 2 (condición (b), Tech Lead 2026-11-04): este
                    # cron NO es un cierre explícito — el intervalo
                    # 'working' que pudiera estar abierto en este claim
                    # cierra con su propio last_touched_dt, nunca con
                    # la hora en que corrió el cron.
                    claim._release_claim(close_reason='idle', use_last_touched=True)
                    claim.wizard_id.sudo().message_post(
                        body=(
                            f'Producto {product_name} liberado '
                            f'automáticamente por inactividad de '
                            f'{employee_name}.'
                        ),
                    )
            except _PG_CONCURRENCY_ERRORS as exc:
                _logger.info(
                    'Guapante: liberación automática de claims — claim '
                    '%s ocupado (%s), se reintenta en la próxima corrida.',
                    claim.id, exc.__class__.__name__,
                )
            except Exception:
                _logger.exception(
                    'Guapante: liberación automática de claims — no se '
                    'pudo liberar el claim %s.', claim.id,
                )
