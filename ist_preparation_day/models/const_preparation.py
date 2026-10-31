# -*- coding: utf-8 -*-
import time

# Clave de sesión de navegador para la identificación por PIN del operario en el paso de
# pesaje (Preparation Day) — constante única, importada por el controlador de
# identificación y por el modelo que la lee en action_save_line_weight(), para no duplicar
# el string literal entre los dos (gap de la Fase 1 original, cerrado en este módulo).
PREP_OPERATOR_SESSION_KEY = 'guapante_prep_employee_id'

# Timestamp (time.time(), epoch en segundos) de la última acción válida del operario
# identificado — base del cierre por inactividad de Picking (Fase A, 2026-10-22).
PREP_OPERATOR_LAST_ACTIVITY_KEY = 'guapante_prep_employee_last_activity'

# 5 minutos. Decisión de David/Tech Lead para Picking: el tablet vuelve solo a la
# pantalla de NIP si nadie confirma una acción real en ese lapso.
PREP_OPERATOR_IDLE_TIMEOUT_SECONDS = 300

# Margen extra (Tech Lead, 2026-10-31, plan f1) sobre PREP_OPERATOR_IDLE_TIMEOUT_SECONDS
# antes de tratar un claim "En progreso" como abandonado (visible para otros
# operarios en Nivel 1, liberable por el cron). Son dos relojes distintos — el
# timeout de sesión del operario (por request) y la última actividad del claim
# (por acción sobre ESE producto) — este margen evita que un claim parpadee
# oculto/visible justo en el borde por esa diferencia de granularidad.
CLAIM_STALE_MARGIN_SECONDS = 60

# Límite de intentos del NIP (Tech Lead, 2026-10-31, punto b): disuade
# adivinar un PIN a fuerza bruta en el tablet compartido, no es una
# medida de seguridad fuerte — vive en la sesión de navegador (igual
# que la identificación misma), así que borrar las cookies del tablet
# la evade por completo. Suficiente para un tablet interno compartido
# (disuade un intento casual, no protege contra alguien decidido a
# evadirla); NO usar este mismo patrón como control de acceso real en
# ningún otro contexto.
PREP_OPERATOR_PIN_FAILURES_KEY = 'guapante_prep_pin_failures'
PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY = 'guapante_prep_pin_lockout_until'
PREP_OPERATOR_PIN_MAX_FAILURES = 5
PREP_OPERATOR_PIN_LOCKOUT_SECONDS = 60


def get_active_prep_operator_id(env, session, refresh=True):
    """Devuelve el employee_id identificado en esta sesión de navegador, o False si
    no hay ninguno, si pasaron más de PREP_OPERATOR_IDLE_TIMEOUT_SECONDS desde la
    última acción válida, o si el empleado ya no es un operario válido — en
    cualquiera de esos casos limpia la sesión en vez de devolver un valor viejo.

    El servidor es la única fuente de verdad del timeout (Fase A, hallazgo de
    Tech Lead): un timer solo en JS no cubre pantalla apagada, app cerrada o
    conexión caída — el próximo request del operario siguiente debe encontrar la
    sesión ya vencida, no heredar al operario anterior.

    refresh=False es para lecturas de solo consulta (ej. el watchdog del cliente
    preguntando "¿sigo activo?" para decidir si redirige a la pantalla de NIP) —
    si esa sola pregunta extendiera la sesión, el timeout nunca se cumpliría
    mientras la pestaña quede abierta. refresh=True (default) es para acciones
    reales del operario (identificarse, asignarse, pesar, Listo, Corregir, nota,
    etc.) — esas sí extienden la ventana de 5 minutos.

    Validación de empleado (Tech Lead, 2026-10-31): vive ACÁ, no solo en el
    controlador de identificación — esta es la compuerta que usan TODAS las
    escrituras de Picking (nota, peso, claim, scrap), así que si un operario
    se desactiva o pierde is_guapante_prep_operator a mitad de turno, ninguna
    de ellas debe seguir aceptándolo, no solo la pantalla de NIP.

    Tolera session=None/falsy (cron, tests, odoo-bin shell sin contexto HTTP)
    devolviendo False, igual que el patrón `request and ...` ya usado en este
    módulo antes de este helper.
    """
    if not session:
        return False
    employee_id = session.get(PREP_OPERATOR_SESSION_KEY)
    if not employee_id:
        return False
    last_activity = session.get(PREP_OPERATOR_LAST_ACTIVITY_KEY)
    if not last_activity or (time.time() - last_activity) > PREP_OPERATOR_IDLE_TIMEOUT_SECONDS:
        clear_active_prep_operator(session)
        return False
    Employee = env['hr.employee'].sudo().browse(employee_id)
    if not Employee.exists() or not Employee.active or not Employee.is_guapante_prep_operator:
        clear_active_prep_operator(session)
        return False
    if refresh:
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = time.time()
    return employee_id


def set_active_prep_operator(session, employee_id):
    """Identifica al operario en esta sesión de navegador (login por PIN) y arranca
    la ventana de inactividad desde ahora."""
    session[PREP_OPERATOR_SESSION_KEY] = employee_id
    session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = time.time()


def clear_active_prep_operator(session):
    """Cierra la identificación del operario en esta estación — logout explícito o
    expiración por inactividad."""
    if not session:
        return
    session.pop(PREP_OPERATOR_SESSION_KEY, None)
    session.pop(PREP_OPERATOR_LAST_ACTIVITY_KEY, None)


def get_pin_lockout_remaining_seconds(session):
    """Segundos que faltan del bloqueo por intentos fallidos del NIP en esta
    sesión de navegador, o 0 si no hay bloqueo activo (nunca falló, o el
    bloqueo ya venció). Limpia el bloqueo vencido en vez de dejarlo
    acumulado en la sesión.

    `session is None` a propósito, no `not session`: una sesión recién
    creada (sin fallos todavía) es un diccionario vacío, que en Python
    es falsy — `not session` la trataría como "no hay sesión" y nunca
    contaría el primer fallo."""
    if session is None:
        return 0
    lockout_until = session.get(PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY)
    if not lockout_until:
        return 0
    remaining = int(lockout_until - time.time())
    if remaining <= 0:
        session.pop(PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY, None)
        session.pop(PREP_OPERATOR_PIN_FAILURES_KEY, None)
        return 0
    return remaining


def register_pin_failure(session):
    """Cuenta un intento de NIP fallido ('no reconocido' o ambiguo — nunca el
    de PIN vacío, ese no es un intento). Al llegar a
    PREP_OPERATOR_PIN_MAX_FAILURES activa el bloqueo de
    PREP_OPERATOR_PIN_LOCKOUT_SECONDS y reinicia el contador.

    `session is None` a propósito — ver get_pin_lockout_remaining_
    seconds, mismo motivo."""
    if session is None:
        return
    failures = session.get(PREP_OPERATOR_PIN_FAILURES_KEY, 0) + 1
    if failures >= PREP_OPERATOR_PIN_MAX_FAILURES:
        session[PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY] = (
            time.time() + PREP_OPERATOR_PIN_LOCKOUT_SECONDS
        )
        session[PREP_OPERATOR_PIN_FAILURES_KEY] = 0
    else:
        session[PREP_OPERATOR_PIN_FAILURES_KEY] = failures


def clear_pin_failures(session):
    """Reinicia el contador de intentos fallidos del NIP — identificación
    exitosa."""
    if session is None:
        return
    session.pop(PREP_OPERATOR_PIN_FAILURES_KEY, None)
    session.pop(PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY, None)
