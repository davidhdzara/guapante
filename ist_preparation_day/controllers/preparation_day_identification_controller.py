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

        David (2026-10-29, corrección sobre la decisión anterior):
        "Operarios autorizados" se queda — is_guapante_prep_operator
        sigue siendo obligatorio para identificarse, no basta con
        tener PIN. active=True se agrega aparte (un empleado
        archivado no debe poder identificarse aunque siga marcado).
        """
        pin = (pin or '').strip()
        if not pin:
            return {'success': False, 'error': 'Ingresa tu PIN.'}

        Employees = request.env['hr.employee'].sudo().search([
            ('pin', '=', pin),
            ('is_guapante_prep_operator', '=', True),
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
        employee_id = get_active_prep_operator_id(
            request.env, request.session, refresh=False,
        )
        if not employee_id:
            return {'employee_id': False, 'employee_name': False}

        # Ya validado (existe, active, is_guapante_prep_operator) dentro
        # de get_active_prep_operator_id — Tech Lead, 2026-10-31: esa
        # validación vive en el helper, no acá, porque también la usan
        # las escrituras de Picking (nota, peso, claim, scrap).
        Employee = request.env['hr.employee'].sudo().browse(employee_id)
        return {'employee_id': Employee.id, 'employee_name': Employee.name}

    @http.route(
        '/web/guapante/preparation_day/clear_operator',
        type='json',
        auth='user',
    )
    def clear_operator(self, **kwargs):
        """Cierra la identificación del operario en esta estación (gap #2 de la Fase 1:
        antes solo se podía re-identificar, no había una salida explícita).

        Libera primero (plan f1, Tech Lead 2026-10-31) cualquier claim de
        Nivel 1 que este operario tuviera En progreso — propia petición,
        propio commit, nunca desde get_active_prep_operator_id (ese helper
        corre DENTRO de acciones de escritura que pueden fallar después y
        hacer rollback; si liberara ahí, un rollback dejaría el claim
        huérfano e invisible para todos, por la regla de visibilidad).

        'guapante.preparation.day.product.claim' en request.env: Nivel 1
        vive en ist_preparation_day_picking, que depende de este módulo,
        no al revés — este controlador no puede asumir que ese modelo
        existe (aunque en Guapante hoy los dos módulos siempre van
        instalados juntos).
        """
        employee_id = get_active_prep_operator_id(
            request.env, request.session, refresh=False,
        )
        if employee_id and 'guapante.preparation.day.product.claim' in request.env:
            request.env[
                'guapante.preparation.day.product.claim'
            ].sudo()._release_claims_for_employee(employee_id)
        clear_active_prep_operator(request.session)
        return {'success': True}
