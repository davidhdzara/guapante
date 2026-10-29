# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

from ..models.const_preparation import (
    clear_active_prep_operator,
    get_active_prep_operator_id,
    set_active_prep_operator,
)

_logger = logging.getLogger(__name__)


class PreparationDayIdentificationController(http.Controller):

    @http.route(
        '/web/guapante/preparation_day/identify',
        type='json',
        auth='user',
    )
    def identify_operator(self, pin=None, **kwargs):
        """Identifica, por PIN, qué operario físico está pesando.

        sudo(): hoy no hay ACL de base.group_user sobre hr.employee.
        Busca SIN limit=1: si el PIN es ambiguo (dos empleados con el
        mismo PIN, dato mal poblado) bloquea con error claro en vez de
        identificar en silencio al primero que matchee.

        Tener PIN configurado es suficiente para identificarse (Tech
        Lead/David, 2026-10-29) — ya no existe un marcador aparte
        (is_guapante_prep_operator); por eso el chequeo de PIN duplicado
        de abajo ahora cubre a CUALQUIER empleado con ese PIN, no solo a
        los que antes estaban marcados.
        """
        pin = (pin or '').strip()
        if not pin:
            return {'success': False, 'error': 'Ingresa tu PIN.'}

        Employees = request.env['hr.employee'].sudo().search([
            ('pin', '=', pin),
            ('active', '=', True),
        ])
        if not Employees:
            return {'success': False, 'error': 'PIN no reconocido.'}
        if len(Employees) > 1:
            return {
                'success': False,
                'error': (
                    'Este PIN está asignado a más de un operario — avisa '
                    'a un supervisor antes de continuar.'
                ),
            }

        set_active_prep_operator(request.session, Employees.id)
        return {
            'success': True,
            'employee_id': Employees.id,
            'employee_name': Employees.name,
        }

    @http.route(
        '/web/guapante/preparation_day/current_operator',
        type='json',
        auth='user',
    )
    def current_operator(self, **kwargs):
        """Lectura de solo consulta (refresh=False): la usa tanto el estado
        inicial del gate de Picking como el watchdog de inactividad del
        cliente — si esta sola pregunta extendiera la sesión, el cierre por
        5 minutos de inactividad nunca se cumpliría mientras la pestaña
        quede abierta (Fase A, hallazgo de Tech Lead)."""
        employee_id = get_active_prep_operator_id(request.session, refresh=False)
        if not employee_id:
            return {'employee_id': False, 'employee_name': False}

        Employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not Employee.exists():
            clear_active_prep_operator(request.session)
            return {'employee_id': False, 'employee_name': False}

        return {'employee_id': Employee.id, 'employee_name': Employee.name}

    @http.route(
        '/web/guapante/preparation_day/clear_operator',
        type='json',
        auth='user',
    )
    def clear_operator(self, **kwargs):
        """Cierra la identificación del operario en esta estación (gap #2 de la Fase 1:
        antes solo se podía re-identificar, no había una salida explícita)."""
        clear_active_prep_operator(request.session)
        return {'success': True}
