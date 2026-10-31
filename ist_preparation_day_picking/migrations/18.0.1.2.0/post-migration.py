# -*- coding: utf-8 -*-
"""Gracia de un ciclo completo para last_activity (Tech Lead, 2026-10-31,
corrección sobre un incidente real de f1): el campo nace NULL en cualquier
claim En progreso que ya existiera antes de este despliegue — sin esto, el
cron de abandono (_cron_release_abandoned_claims) los trataría como
"viejos" por su assigned_date (que nunca se actualizaba antes de este
plan) y los liberaría de golpe apenas el cron naciera activo, desde el
primer minuto del deploy.

Incidente real en staging (2026-10-31): el cron corrió solo a los 5
minutos del rebuild y liberó 2 claims reales de la sesión del día —
antes de que hubiera chance de revisar nada. Esta migración evita que
se repita: pone last_activity=now() en todo claim En progreso, dándole
el MISMO ciclo de gracia completo (PREP_OPERATOR_IDLE_TIMEOUT_SECONDS +
CLAIM_STALE_MARGIN_SECONDS) que ya tiene cualquier claim asignado
DESPUÉS de este despliegue — nunca toca Pendiente/Detenido/Terminado,
ni falta que haga (esos estados no usan last_activity para nada)."""
from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Claim = env['guapante.preparation.day.product.claim']
    InProgress = Claim.search([('status', '=', 'in_progress')])
    if InProgress:
        InProgress.write({'last_activity': fields.Datetime.now()})
