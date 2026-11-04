# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_guapante_prep_operator = fields.Boolean(
        string='Operario de Preparación (Guapante)',
        default=False,
        help=(
            'Habilita a este empleado para identificarse con su PIN como '
            'operario físico en Preparación del Día / Picking. Sin esto '
            'marcado, su PIN no identifica aunque esté configurado — '
            'evita que cualquier empleado con PIN pueda registrar pesos. '
            'Se gestiona desde Preparación > Configuración > Operarios '
            'autorizados — no aparece en la ficha del empleado (David, '
            '2026-10-29: ahí solo se ve el NIP).'
        ),
    )

    def unlink(self):
        """Fase 2, commit 7/7 (Tech Lead, 2026-11-04): done_by_employee_id
        (guapante.preparation.day.line) es ondelete='restrict' (Fase 2,
        punto 4, David: un empleado que se retira es historia real,
        nunca se borra — se archiva). Sin este guard, intentar eliminar
        a un empleado con historial de Picking revienta con un
        IntegrityError crudo de Postgres en vez de un mensaje que diga
        qué hacer.

        ist_preparation_day_picking agrega su PROPIO guard (sobre
        guapante.preparation.interval.employee_id) en su propio
        hr_employee.py — cada módulo revisa solo lo que define, nunca
        al revés: este módulo no depende de Picking y no puede saber
        si está instalado."""
        Line = self.env['guapante.preparation.day.line']
        for employee in self:
            if Line.sudo().search_count(
                [('done_by_employee_id', '=', employee.id)], limit=1,
            ):
                raise UserError(
                    f'No se puede eliminar a {employee.name}: tiene '
                    'líneas de Picking pesadas a su nombre. Archívalo '
                    'en vez de eliminarlo.'
                )
        return super().unlink()
