# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def unlink(self):
        """Fase 2, commit 7/7 (Tech Lead, 2026-11-04): employee_id en
        guapante.preparation.interval es ondelete='restrict' (Fase 2,
        punto 4, David: un empleado que se retira es historia real,
        nunca se borra — se archiva) — mismo guard que
        ist_preparation_day/models/hr_employee.py sobre
        done_by_employee_id, acá porque el modelo de intervalos solo
        existe en este módulo (Picking)."""
        Interval = self.env['guapante.preparation.interval']
        for employee in self:
            if Interval.sudo().search_count(
                [('employee_id', '=', employee.id)], limit=1,
            ):
                raise UserError(
                    f'No se puede eliminar a {employee.name}: tiene '
                    'intervalos de tiempo de Picking registrados. '
                    'Archívalo en vez de eliminarlo.'
                )
        return super().unlink()
