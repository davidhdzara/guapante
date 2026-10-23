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


def get_active_prep_operator_id(session, refresh=True):
    """Devuelve el employee_id identificado en esta sesión de navegador, o False si
    no hay ninguno o si pasaron más de PREP_OPERATOR_IDLE_TIMEOUT_SECONDS desde la
    última acción válida — en ese caso limpia la sesión (expira) en vez de devolver
    un valor viejo.

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
