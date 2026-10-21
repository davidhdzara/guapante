# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

from ..models.const_preparation import PREP_OPERATOR_SESSION_KEY

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
        """
        pin = (pin or '').strip()
        if not pin:
            return {'success': False, 'error': 'Ingresa tu PIN.'}

        Employees = request.env['hr.employee'].sudo().search([('pin', '=', pin)])
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

        request.session[PREP_OPERATOR_SESSION_KEY] = Employees.id
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
        employee_id = request.session.get(PREP_OPERATOR_SESSION_KEY)
        if not employee_id:
            return {'employee_id': False, 'employee_name': False}

        Employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not Employee.exists():
            request.session.pop(PREP_OPERATOR_SESSION_KEY, None)
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
        request.session.pop(PREP_OPERATOR_SESSION_KEY, None)
        return {'success': True}
