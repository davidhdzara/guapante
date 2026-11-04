# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.ist_preparation_day.models.const_preparation import (
    get_idle_timeout_seconds,
)
from odoo.addons.ist_preparation_day.models.preparation_day import (
    _PG_CONCURRENCY_ERRORS,
)

from .preparation_day_product_claim import STOP_REASONS

_logger = logging.getLogger(__name__)

CLOSE_REASONS = [
    ('left', 'Salió de Nivel 2'),
    ('switched', 'Cambió de producto'),
    ('stopped', 'Detenido'),
    ('resumed', 'Retomado'),
    ('released', 'Liberado'),
    ('finished', 'Producto terminado'),
    ('idle', 'Inactividad (cierre por cron)'),
    ('session_closed', 'Cerró sesión'),
]


class PreparationInterval(models.Model):
    """Fase 2 (Tech Lead, 2026-11-02, diseño revisado con Odoo Engineer
    2026-11-04) — un registro por periodo continuo en que UN operario
    trabaja (o un producto queda detenido) sobre UN producto de UNA
    sesión. Insumo de las pantallas de tiempo (L1/L2) y de los reportes
    de Fase 2; nunca lo toca el operario ni ninguna pantalla por ORM
    directo — todo se abre/cierra desde los mismos puntos del servidor
    que ya existen para asignar/detener/liberar/terminar (ver
    preparation_day_product_claim.py y preparation_day_line.py).

    `kind='stopped'` NO es el reloj personal de nadie — "Detenido" es un
    estado del PRODUCTO (claim), no de un operario (cualquiera puede
    detener el claim de cualquiera, Tech Lead/David 2026-11-03). Por
    eso employee_id es informativo en ese caso (quién lo detuvo) y
    queda fuera de la restricción "un solo intervalo working abierto
    por operario" — ver el índice único parcial en init().
    """
    _name = 'guapante.preparation.interval'
    _description = 'Intervalo de trabajo/detención de Picking (Fase 2)'
    _order = 'start_dt desc'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
        index=True,
    )
    claim_id = fields.Many2one(
        'guapante.preparation.day.product.claim',
        string='Producto (Nivel 1)',
        required=True,
        ondelete='cascade',
        index=True,
    )
    # Stored (no solo related en memoria): los 5 reportes de Fase 2 leen
    # este campo por SQL directo sobre esta tabla — sin store=True cada
    # reporte tendría que unir contra el claim para algo que no cambia
    # una vez creado el intervalo.
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        related='claim_id.product_tmpl_id',
        store=True,
        index=True,
        readonly=True,
    )
    # Nullable (ver docstring de la clase): obligatorio solo para
    # kind='working', exigido por _check_employee_required_for_working.
    # ondelete='restrict' (Fase 2, punto 4, David 2026-11-04): un
    # empleado archivado sigue siendo historia — nunca se borra: ver
    # hr_employee.py para el mensaje claro antes de que esto reviente
    # como un IntegrityError crudo.
    employee_id = fields.Many2one(
        'hr.employee',
        string='Operario',
        ondelete='restrict',
        index=True,
    )
    kind = fields.Selection(
        selection=[('working', 'Trabajando'), ('stopped', 'Detenido')],
        string='Tipo',
        required=True,
    )
    stop_reason = fields.Selection(STOP_REASONS, string='Motivo de detención')
    start_dt = fields.Datetime(string='Inicio', required=True)
    # Nulo = abierto. El índice único parcial de init() es el que
    # garantiza "un solo working abierto por operario" — ver ahí el
    # motivo de por qué un check Python solo no basta bajo concurrencia
    # real (mismo riesgo que el incidente de numeración de cajas,
    # 2026-11-03: nada se decide sin releer bajo lock).
    end_dt = fields.Datetime(string='Fin')
    # Última acción REAL de este operario dentro del intervalo (pesar o
    # corregir una línea) — NUNCA un refresco de pantalla ni una nota
    # (action_add_note ya decide, para el claim, que una nota no cuenta
    # como "sigo trabajando"; se aplica la misma regla acá). Arranca en
    # start_dt (entrar a Nivel 2 ya es una acción real) y es lo que se
    # copia a end_dt en cualquier cierre que NO sea una salida explícita
    # del operario (switched/idle/cron) — nunca now() ni la hora del
    # cron, para no inflar el tiempo de alguien que se fue sin avisar.
    last_touched_dt = fields.Datetime(string='Última actividad real', required=True)
    # Se fija una sola vez, al cerrar — no es compute: a esta escala
    # (cientos de filas por sesión, pero se acumula sesión tras sesión)
    # recalcular en cada lectura no aporta nada sobre un valor que ya no
    # cambia.
    duration_s = fields.Integer(string='Duración (s)', readonly=True)
    close_reason = fields.Selection(CLOSE_REASONS, string='Motivo de cierre')
    # Se fija una sola vez (Fase 2: "100% transparente, cero clics
    # nuevos") — si ya tiene valor, ninguna escritura posterior lo
    # toca.
    first_weigh_dt = fields.Datetime(string='Primer pesaje')
    # Solo cuenta una línea la PRIMERA vez que queda is_done=True dentro
    # de este intervalo (Fase 2: "corregir y volver a pesar una caja...
    # no cuenta como una nueva") — una corrección posterior sobre una
    # línea ya Terminada NO incrementa nada de esto.
    lines_done = fields.Integer(string='Líneas terminadas', default=0)
    # E7 (despacho en 0, "sin stock"): aparte de lines_done, para que
    # los reportes de tiempo por kilo/caja puedan excluirlas sin perder
    # el conteo de líneas hechas.
    zero_lines_done = fields.Integer(string='Líneas en 0 (sin stock)', default=0)
    kg_done = fields.Float(string='Kg pesados', digits=(10, 3), default=0.0)

    @api.constrains('kind', 'employee_id')
    def _check_employee_required_for_working(self):
        for interval in self:
            if interval.kind == 'working' and not interval.employee_id:
                raise ValidationError(
                    'Un intervalo de trabajo necesita un operario — '
                    'solo un intervalo de detención puede quedar sin uno.'
                )

    # ── Apertura/cierre (Fase 2, commit 2/7 — Tech Lead, 2026-11-04) ──
    #
    # Nunca lo llama el operario ni ninguna pantalla por ORM directo —
    # todo pasa por estos métodos desde los mismos puntos del servidor
    # que ya existen para entrar a Nivel 2 / asignar / detener / liberar
    # / terminar (ver preparation_day_product_claim.py y
    # preparation_day_line.py). Principio rector: NINGÚN error visible
    # al operario por un intervalo huérfano o una carrera — el único
    # UserError de todo este archivo es el constraint de arriba
    # (kind='working' sin employee_id), que es un error de programación
    # interno, no algo que un operario pueda disparar desde la UI.

    @api.model
    def _open_working(self, claim, employee_id):
        """Único punto de apertura de un intervalo 'working' — lo llama
        action_open_lines_kanban() (el único lugar por el que se entra
        a Nivel 2, sea por Asignarme/Retomar/Continuar o por clic
        directo en cualquier tarjeta) y, como respaldo, write() de
        PreparationDayLine si llega un pesaje sin haber pasado por ahí.

        pg_advisory_xact_lock por employee_id (condición (a), Tech
        Lead): serializa dos aperturas casi simultáneas del MISMO
        operario (dos tablets con el mismo PIN, o un RPC duplicado) —
        se libera solo al terminar la transacción, nunca hay que
        soltarlo a mano. El índice único parcial de init() queda como
        backstop si esto fallara por algún motivo; en ese caso el
        IntegrityError NUNCA debe llegar a la pantalla del operario —
        lo trata quien llame esto, no este método.

        Si el operario YA tiene un 'working' abierto en OTRO producto,
        lo cierra como 'switched' con end_dt=su propio last_touched_dt
        (nunca now() — no es una salida explícita, es un cambio de
        foco que el sistema detecta, no algo que el operario "hizo
        ahora"). Si ya lo tiene abierto en ESTE MISMO producto
        (reentrada — ej. F5, o Continuar sobre lo que ya tenía
        abierto), lo reutiliza tal cual, nunca lo duplica ni lo
        reinicia.
        """
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))',
            (f'guapante_preparation_interval_employee_{employee_id}',),
        )
        now = fields.Datetime.now()
        Open = self.sudo().search([
            ('employee_id', '=', employee_id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ], limit=1)
        if Open:
            if Open.claim_id == claim:
                return Open
            Open._close('switched', Open.last_touched_dt)
            # flush_recordset() (mismo patrón que el resto del archivo
            # antes de SQL crudo, ej. action_assign): el write() de
            # _close() arriba queda en caché del ORM hasta el próximo
            # flush — sin esto, el INSERT de abajo corre con la fila
            # vieja aún visible como "abierta" (end_dt IS NULL) para el
            # índice único parcial, y Postgres rechaza la inserción con
            # un IntegrityError real (bug encontrado por los tests de
            # este commit) — justo lo que el principio rector prohíbe.
            Open.flush_recordset()
        return self.sudo().create({
            'wizard_id': claim.wizard_id.id,
            'claim_id': claim.id,
            'employee_id': employee_id,
            'kind': 'working',
            'start_dt': now,
            'last_touched_dt': now,
        })

    def _close(self, close_reason, end_dt):
        """Cierre de UN intervalo. Idempotente (no-op si ya estaba
        cerrado) — varios de los puntos que llaman esto pueden coincidir
        en el mismo intervalo (ej. una carrera entre Detener y el cron),
        nunca debe pisar un cierre anterior ni sumarle duración dos
        veces. `end_dt` SIEMPRE lo decide quien llama: now() para una
        salida explícita (Detener/Liberar/Terminar/Cerrar sesión/"←
        Productos"), last_touched_dt para switched/idle/cron (ver el
        campo en la definición de arriba — nunca now() ahí, para no
        inflar el tiempo de alguien que se fue sin avisar)."""
        self.ensure_one()
        if self.end_dt:
            return
        duration = max(int((end_dt - self.start_dt).total_seconds()), 0)
        self.sudo().write({
            'end_dt': end_dt,
            'duration_s': duration,
            'close_reason': close_reason,
        })

    @api.model
    def _close_open_for_claim(self, claim, kind, close_reason, end_dt):
        """Cierra TODOS los intervalos abiertos de este tipo para este
        claim — puede ser más de uno: bajo E3 (sin ownership) nada
        impide que dos operarios distintos tengan Nivel 2 abierto sobre
        el MISMO producto a la vez, y un evento externo (Detener/
        Liberar/Terminar) le pone fin al trabajo de TODOS ellos sobre
        ese producto en este instante, no solo al de uno.

        `end_dt=None` (solo lo usa el cron de abandono de claims, vía
        _release_claim(use_last_touched=True)): cada intervalo cierra
        con SU PROPIO last_touched_dt, nunca con una hora común — un
        cierre no explícito nunca inventa una hora de fin igual para
        todos."""
        Open = self.sudo().search([
            ('claim_id', '=', claim.id),
            ('kind', '=', kind),
            ('end_dt', '=', False),
        ])
        for interval in Open:
            interval._close(close_reason, end_dt if end_dt is not None else interval.last_touched_dt)

    @api.model
    def _close_open_working_for_employee(self, employee_id, close_reason, end_dt):
        """Cierra el 'working' abierto de ESTE operario, sea cual sea
        el claim — lo usa /clear_operator (Cerrar sesión / Cerrar):
        cerrar la sesión del operario es un evento sobre LA PERSONA,
        no sobre un producto en particular, a diferencia de
        _close_open_for_claim (arriba), que es sobre el producto.
        Devuelve True si había algo que cerrar (informativo, no se usa
        para decidir nada)."""
        Open = self.sudo().search([
            ('employee_id', '=', employee_id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ], limit=1)
        if Open:
            Open._close(close_reason, end_dt)
        return bool(Open)

    @api.model
    def _handle_weighing(self, claim, employee_id, is_new_completion, actual_kg):
        """Registra un pesaje/corrección dentro del intervalo 'working'
        abierto de este operario sobre este claim — lo llama write() de
        PreparationDayLine en cada escritura de actual_kg bajo
        guapante_picking_flow. Si el intervalo esperado no existe o es
        de OTRO producto (no debería pasar si el cliente siempre entra
        por action_open_lines_kanban antes de pesar — ver el docstring
        de _open_working), lo abre/cambia acá mismo como respaldo:
        first_weigh_dt quedará en start_dt en ese caso, honesto —no hay
        cómo saber cuánto esperó antes de este pesaje sin haber entrado
        a Nivel 2 primero."""
        Open = self.sudo().search([
            ('employee_id', '=', employee_id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ], limit=1)
        if not Open or Open.claim_id != claim:
            Open = self._open_working(claim, employee_id)
        Open._register_weighing(is_new_completion, actual_kg)

    def _register_weighing(self, is_new_completion, actual_kg):
        """Un pesaje/corrección SIEMPRE actualiza last_touched_dt (es la
        definición misma de "actividad real" — ver el campo) y fija
        first_weigh_dt una sola vez. lines_done/zero_lines_done/kg_done
        SOLO se incrementan si `is_new_completion` (is_done pasó de
        False a True en ESTA escritura) — una corrección sobre una
        línea YA Terminada no cuenta como una nueva (Fase 2: "corregir
        y volver a pesar una caja... no cuenta como una nueva").

        Read-modify-write sin lock de fila explícito (nota de Tech
        Lead, revisión del commit 2/7): es seguro sin uno porque un
        operario tiene como máximo UN intervalo 'working' abierto a la
        vez (índice único parcial + pg_advisory_xact_lock en
        _open_working) — dos pesajes "seguidos" del mismo operario
        sobre el mismo intervalo llegan SIEMPRE serializados por el
        propio advisory lock (toda escritura de Picking de ESE
        operario pasa por _check_picking_ownership(), que también
        exige identificarse, y el flujo real del tablet es síncrono:
        un pesaje a la vez). No es el mismo riesgo que el incidente de
        numeración de cajas (dos operarios DISTINTOS decidiendo sobre
        la MISMA fila) — acá el "mismo operario, dos pesajes" nunca es
        concurrente de verdad."""
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {'last_touched_dt': now}
        if not self.first_weigh_dt:
            vals['first_weigh_dt'] = now
        if is_new_completion:
            vals['lines_done'] = self.lines_done + 1
            if actual_kg:
                vals['kg_done'] = self.kg_done + actual_kg
            else:
                vals['zero_lines_done'] = self.zero_lines_done + 1
        self.sudo().write(vals)

    # ── Aislamiento de fallos (Fase 2, commit 4/7 — Tech Lead,
    #    2026-11-04, principio rector reforzado) ──

    @api.model
    def _run_isolated(self, label, callback):
        """El tiempo es dato SECUNDARIO — ningún fallo inesperado de la
        lógica de intervalos (bug, lock, IntegrityError) puede tumbar
        el camino CRÍTICO que la rodea: pesar, entrar a Nivel 2,
        detener, liberar, cerrar sesión. Todo punto de apertura/cierre
        que un flujo crítico llama de paso (nunca los que SON el
        propio punto de entrada, como esta clase para los reportes)
        pasa por acá — ver cada llamador en preparation_day_line.py,
        preparation_day_product_claim.py y el controlador de NIP.

        SAVEPOINT (flush=True, el default de cr.savepoint()): en una
        excepción, Odoo limpia TODO el caché del ORM antes del
        ROLLBACK TO SAVEPOINT (ver _FlushingSavepoint.rollback() en
        sql_db.py) — nunca queda un valor a medio escribir visible en
        memoria para el resto de la transacción, aunque ya no esté en
        la base. Seguro para el camino crítico que llama esto porque
        ninguno de estos métodos escribe sobre el claim/línea/
        empleado que trae el llamador — solo sobre filas de este
        modelo, que el llamador nunca vuelve a leer (son "fire and
        forget": nadie usa su valor de retorno real, por eso esto
        devuelve None si falla).

        _PG_CONCURRENCY_ERRORS NUNCA se atrapa acá — se relanza igual
        que en el resto del proyecto (ver _cron_release_abandoned_
        intervals): Odoo ya reintenta a nivel de petición completa, y
        tragárselo acá dejaría un intervalo a medio escribir sin el
        reintento normal que lo corrige."""
        try:
            with self.env.cr.savepoint():
                return callback()
        except _PG_CONCURRENCY_ERRORS:
            raise
        except Exception:
            _logger.exception(
                'Guapante: fallo aislado de intervalos (%s) — el '
                'camino crítico que lo rodea continúa sin este dato '
                'de tiempo.', label,
            )
            return None

    # ── Contadores L1 (Fase 2, commit 4/7 — Tech Lead, 2026-11-04) ──

    @api.model
    def _get_time_counters_by_claim(self, wizard_id) -> dict:
        """Tiempo en_proceso/detenido POR CLAIM, para que
        get_claims_for_level1_display() (preparation_day_product_claim.py)
        los pegue a cada tarjeta de Nivel 1 sin una consulta nueva por
        producto — UNA sola lectura agrupada sobre TODOS los intervalos
        del lote (misma idea que el resumen de clientes/touched_by_me de
        ese método: una consulta, agregación en Python).

        time_working_s suma: duration_s de cada 'working' ya CERRADO,
        más — por cada 'working' TODAVÍA abierto (puede haber más de
        uno por claim: bajo E3 dos operarios distintos pueden tener
        Nivel 2 abierto sobre el MISMO producto a la vez, ver el
        docstring de _close_open_for_claim) — el tiempo transcurrido
        con TOPE en min(ahora, last_touched_dt + idle_timeout): el
        contador en vivo nunca muestra más que lo que el propio
        timeout de inactividad todavía considera "actividad real" (ver
        get_idle_timeout_seconds) — más allá de eso ya no es tiempo
        trabajado, es abandono que el cron de intervalos (3/7) o el de
        claims ya se encargan de cerrar. idle_timeout=0 ("sin bloqueo
        NI abandono" — corrección de Tech Lead, revisión de 4/7,
        2026-11-04) es el caso contrario a lo que parece a primera
        vista: NO hay tope, cuenta hasta ahora sin recortar — "sin
        bloqueo" significa que NADA se considera abandonado nunca
        (ver get_idle_timeout_seconds/_cron_release_abandoned_claims),
        así que congelar el contador en last_touched_dt + 0 congelaba
        a un operario que sigue trabajando sin haber pesado todavía
        (ej. acomodando varias cajas antes del primer pesaje) — justo
        lo que este parámetro en 0 promete NO hacer.

        time_stopped_s suma: duration_s de cada 'stopped' ya CERRADO,
        más — el 'stopped' abierto, si lo hay — el tiempo transcurrido
        SIN TOPE (ahora - start_dt): a diferencia de 'working', un
        producto Detenido no tiene una señal propia de "inactividad"
        que lo cierre solo (nadie lo "toca" — ver el docstring de la
        clase), así que su contador en vivo crece sin límite artificial
        mientras siga detenido.
        """
        idle_timeout = get_idle_timeout_seconds(self.env)
        now = fields.Datetime.now()
        rows = self.sudo().search_read(
            domain=[('wizard_id', '=', wizard_id)],
            fields=[
                'claim_id', 'kind', 'start_dt', 'last_touched_dt',
                'end_dt', 'duration_s',
            ],
        )
        counters = {}
        for row in rows:
            if not row['claim_id']:
                continue
            bucket = counters.setdefault(row['claim_id'][0], {
                'time_working_s': 0, 'time_stopped_s': 0,
                # lote 2B, 3b/4 (Tech Lead, revisión de 3/4): cuántos
                # intervalos abiertos de este tipo están TODAVÍA
                # tiqueando en este instante (no congelados por el
                # tope de idle_timeout) — el cronómetro L1 del cliente
                # multiplica su tick de 1s/s por este número en vez de
                # sumar siempre a ritmo 1x, para no: (a) seguir subiendo
                # en pantalla un 'working' ya congelado por el servidor
                # (abandonado, esperando el cron), ni (b) quedarse
                # corto cuando hay más de un operario con 'working'
                # abierto sobre el MISMO claim (E3) — el servidor suma
                # los dos, el cliente debe tiquear al doble.
                'time_working_open_count': 0, 'time_stopped_open_count': 0,
            })
            key = 'time_working_s' if row['kind'] == 'working' else 'time_stopped_s'
            if row['end_dt']:
                bucket[key] += row['duration_s']
                continue
            if row['kind'] == 'working':
                # idle_timeout=0 ("sin bloqueo") = SIN tope (Tech Lead,
                # corrección de 4/7): nunca lo recorta a last_touched_dt,
                # que congelaría a alguien que sigue trabajando sin
                # haber pesado todavía — ver el docstring de arriba.
                still_ticking = (
                    idle_timeout <= 0
                    or now < row['last_touched_dt'] + timedelta(seconds=idle_timeout)
                )
                cap = (
                    min(now, row['last_touched_dt'] + timedelta(seconds=idle_timeout))
                    if idle_timeout > 0 else now
                )
                elapsed = max(int((cap - row['start_dt']).total_seconds()), 0)
                if still_ticking:
                    bucket['time_working_open_count'] += 1
            else:
                elapsed = max(int((now - row['start_dt']).total_seconds()), 0)
                bucket['time_stopped_open_count'] += 1
            bucket[key] += elapsed
        return counters

    def init(self):
        """Índice único parcial — backstop de base de datos para "un
        solo intervalo working abierto por operario" (Tech Lead,
        2026-11-04, condición (a)). El candado real en caliente es un
        pg_advisory_xact_lock por employee_id que toma el código que
        abre/cierra intervalos (ver el método de apertura, próximo
        commit) — este índice nunca debería saltar en operación normal;
        si lo hace (ej. un fallo del advisory lock), es la única razón
        por la que puede fallar un INSERT acá, nunca un UserError visible
        al operario por un intervalo huérfano (principio rector).
        IF NOT EXISTS: idempotente ante un -u repetido, mismo criterio
        que el resto de los índices que Odoo ya crea solo por
        index=True en los campos de arriba.
        """
        self.env.cr.execute(
            '''
            CREATE UNIQUE INDEX IF NOT EXISTS
                guapante_preparation_interval_one_working_per_employee
            ON guapante_preparation_interval (employee_id)
            WHERE end_dt IS NULL AND kind = 'working'
            '''
        )

    # ── Cron diario de abandono (Fase 2, commit 3/7 — Tech Lead,
    #    2026-11-04) ──

    @api.model
    def _cron_release_abandoned_intervals(self) -> None:
        """Red de seguridad DIARIA — NO el mecanismo principal (eso lo
        cubren los puntos de apertura/cierre del commit 2/7). Cubre el
        caso que el cron de 5 minutos de claims
        (_cron_release_abandoned_claims) no alcanza: un operario que
        entró a Nivel 2 de un claim que NUNCA llegó a 'in_progress'
        (ej. abrió una tarjeta Pendiente/Detenida/Terminada bajo E3 sin
        pasar por Asignarme/Retomar) — ese claim nunca entra al dominio
        de ese cron, así que su intervalo quedaría abierto para siempre
        sin esto. Corre una vez al día (10:00 Bogotá, ver el ir.cron).

        Regla corregida (David/Tech Lead, 2026-11-04, commit 3b/7 —
        "abandonada SIEMPRE a las 10:00 de la jornada"): a las 10:00 se
        cierra TODO intervalo aún abierto con start_dt anterior a este
        instante, SIN excepción por jornada. La versión anterior
        comparaba contra la medianoche de hoy ("nunca toca nada de
        hoy") — eso dejaba un intervalo abierto a la 01:00 del día D sin
        cerrar hasta el cron del día D+1 (~24h abierto), cuando debía
        cerrarse YA en el cron de las 10:00 de ESE MISMO día D. Es
        seguro cerrar incluso el de alguien trabajando a esa hora: el
        siguiente pesaje reabre uno nuevo vía el respaldo de
        _handle_weighing, y volver a entrar a Nivel 2 hace
        _open_working — no se pierde nada, solo se corta el intervalo
        en dos. kind='working' y kind='stopped' por igual — un
        'stopped' informativo que nadie liberó también queda
        abandonado, aunque con una regla de fin DISTINTA — ver abajo
        (commit 3c/7).

        end_dt para 'working' = last_touched_dt (condición (b), nunca
        la hora en que corrió el cron) — ver _close().

        end_dt para 'stopped' (commit 3c/7, Tech Lead 2026-11-04):
        last_touched_dt NO sirve acá — en un 'stopped' nadie lo "toca"
        nunca (es informativo, no el reloj de nadie — ver el docstring
        de la clase), así que last_touched_dt == start_dt siempre y
        duration_s saldría 0 SIEMPRE, perdiendo el tiempo detenido real
        de un producto que nadie retomó esa noche (justo lo que David
        quiere medir). Usa en su lugar: wizard_id.date_done si la
        sesión ya cerró ('done' con date_done puesto) — el cierre de
        la sesión es un límite real y conocido para "hasta cuándo
        estuvo detenido"; si la sesión sigue abierta (sin cerrar
        todavía, un caso más raro — normalmente la sesión ya cerró
        para cuando corre el cron del día siguiente), usa el propio
        instante del cron (now) como mejor aproximación disponible, en
        vez de dejarlo en 0 o inventar otra fecha.

        Mismo patrón que _cron_release_abandoned_claims/_cron_repair_
        missing_orders: SAVEPOINT POR FILA, con el estado releído bajo
        FOR UPDATE (por si algo más lo cerró entre el search y el
        lock) y _PG_CONCURRENCY_ERRORS atrapado LOCAL (nunca relanzado
        — Odoo ya reintenta a nivel de petición completa; relanzar
        tumbaría lo ya cerrado en esta misma corrida)."""
        now = fields.Datetime.now()
        Open = self.sudo().search([
            ('end_dt', '=', False),
            ('start_dt', '<', now),
        ])
        for interval in Open:
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        'SELECT last_touched_dt, kind FROM '
                        'guapante_preparation_interval '
                        'WHERE id = %s AND end_dt IS NULL FOR UPDATE',
                        (interval.id,),
                    )
                    row = self.env.cr.fetchone()
                    if not row:
                        # Ya se cerró por otra vía entre el search y el
                        # lock — nada que hacer.
                        continue
                    locked_last_touched, locked_kind = row
                    interval.invalidate_recordset(['last_touched_dt'])
                    if locked_kind == 'stopped':
                        session = interval.wizard_id
                        interval_end = (
                            session.date_done
                            if session.state == 'done' and session.date_done
                            else now
                        )
                    else:
                        interval_end = locked_last_touched
                    interval._close('idle', interval_end)
            except _PG_CONCURRENCY_ERRORS as exc:
                _logger.info(
                    'Guapante: cierre automático de intervalos — '
                    'intervalo %s ocupado (%s), se reintenta en la '
                    'próxima corrida.',
                    interval.id, exc.__class__.__name__,
                )
            except Exception:
                _logger.exception(
                    'Guapante: cierre automático de intervalos — no '
                    'se pudo cerrar el intervalo %s.', interval.id,
                )
