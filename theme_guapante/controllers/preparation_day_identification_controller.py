# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Clave de sesión propia de Preparation Day — deliberadamente distinta de la que usa
# mrp_workorder.hr.employee.login()/logout() (cronómetro de Taller) para no acoplar la
# identificación de pesaje a una entitlement de Manufactura Enterprise que Guapante podría no
# mantener a futuro. Ver decisión de diseño en Obsidian (preparacion del dia/02 - Fase 1).
SESSION_KEY = 'guapante_prep_employee_id'


class PreparationDayIdentificationController(http.Controller):

    @http.route(
        '/web/guapante/preparation_day/identify',
        type='json',
        auth='user',
    )
    def identify_operator(self, pin=None, **kwargs):
        """Identifica, por PIN, qué operario físico está pesando.

        sudo(): hoy no hay ACL de base.group_user sobre hr.employee.
        """
        pin = (pin or '').strip()
        if not pin:
            return {'success': False, 'error': 'Ingresa tu PIN.'}

        Employee = request.env['hr.employee'].sudo().search(
            [('pin', '=', pin)], limit=1,
        )
        if not Employee:
            return {'success': False, 'error': 'PIN no reconocido.'}

        request.session[SESSION_KEY] = Employee.id
        return {
            'success': True,
            'employee_id': Employee.id,
            'employee_name': Employee.name,
        }

    @http.route(
        '/web/guapante/preparation_day/current_operator',
        type='json',
        auth='user',
    )
    def current_operator(self, **kwargs):
        employee_id = request.session.get(SESSION_KEY)
        if not employee_id:
            return {'employee_id': False, 'employee_name': False}

        Employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not Employee.exists():
            request.session.pop(SESSION_KEY, None)
            return {'employee_id': False, 'employee_name': False}

        return {'employee_id': Employee.id, 'employee_name': Employee.name}
