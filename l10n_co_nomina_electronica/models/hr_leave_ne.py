# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HrPayslipLeaveIntegration(models.Model):
    """Extensión de hr.payslip para integración con hr.leave.

    Detecta automáticamente las ausencias aprobadas del empleado
    durante el período de la nómina y las convierte en novedades
    para la nómina electrónica DIAN.
    """
    _inherit = 'hr.payslip'

    # ------------------------------------------------------------------
    # Campos de resumen de novedades detectadas
    # ------------------------------------------------------------------
    l10n_co_ne_leave_summary = fields.Text(
        string='Resumen Novedades Detectadas',
        readonly=True,
        help='Resumen automático de las ausencias detectadas en el período.',
    )
    l10n_co_ne_dias_incapacidad = fields.Integer(
        string='Días Incapacidad',
        readonly=True,
        help='Días de incapacidad detectados automáticamente desde hr.leave.',
    )
    l10n_co_ne_dias_licencia_mat = fields.Integer(
        string='Días Licencia Mat/Pat',
        readonly=True,
        help='Días de licencia de maternidad o paternidad detectados.',
    )
    l10n_co_ne_dias_licencia_rem = fields.Integer(
        string='Días Licencia Remunerada',
        readonly=True,
        help='Días de licencia remunerada detectados automáticamente.',
    )
    l10n_co_ne_dias_vacaciones = fields.Integer(
        string='Días Vacaciones',
        readonly=True,
        help='Días de vacaciones detectados automáticamente.',
    )
    l10n_co_ne_dias_licencia_nr = fields.Integer(
        string='Días Licencia No Remunerada',
        readonly=True,
        help='Días de licencia no remunerada detectados automáticamente.',
    )

    # ------------------------------------------------------------------
    # Constantes de mapeo: código de tipo de ausencia → categoría NE
    # ------------------------------------------------------------------
    _LEAVE_CODE_MAP = {
        # Incapacidades
        'INCAPACIDAD': 'incapacidad',
        'SICK': 'incapacidad',
        'INC_COMUN': 'incapacidad',
        'INC_LABORAL': 'incapacidad',
        # Licencia maternidad / paternidad
        'MATERNIDAD': 'licencia_mat',
        'MATERNITY': 'licencia_mat',
        'PATERNIDAD': 'licencia_mat',
        'PATERNITY': 'licencia_mat',
        'LIC_MAT': 'licencia_mat',
        'LIC_PAT': 'licencia_mat',
        # Vacaciones
        'VACACIONES': 'vacaciones',
        'VACATION': 'vacaciones',
        'VAC': 'vacaciones',
        # Licencia remunerada
        'LICENCIA_REM': 'licencia_rem',
        'LIC_REM': 'licencia_rem',
        'PERMISO': 'licencia_rem',
        # Licencia no remunerada
        'LICENCIA_NR': 'licencia_nr',
        'LIC_NR': 'licencia_nr',
        'UNPAID': 'licencia_nr',
        'SIN_SUELDO': 'licencia_nr',
    }

    # Etiquetas legibles para el resumen
    _CATEGORY_LABELS = {
        'incapacidad': 'Incapacidad',
        'licencia_mat': 'Licencia Mat/Pat',
        'vacaciones': 'Vacaciones',
        'licencia_rem': 'Lic. Remunerada',
        'licencia_nr': 'Lic. No Remunerada',
    }

    # Mapeo categoría → campo en el modelo
    _CATEGORY_FIELD_MAP = {
        'incapacidad': 'l10n_co_ne_dias_incapacidad',
        'licencia_mat': 'l10n_co_ne_dias_licencia_mat',
        'vacaciones': 'l10n_co_ne_dias_vacaciones',
        'licencia_rem': 'l10n_co_ne_dias_licencia_rem',
        'licencia_nr': 'l10n_co_ne_dias_licencia_nr',
    }

    # ------------------------------------------------------------------
    # Métodos auxiliares
    # ------------------------------------------------------------------

    def _get_leave_category(self, leave_code):
        """Devuelve la categoría NE para un código de tipo de ausencia.

        :param leave_code: código del tipo de ausencia (str)
        :returns: clave de categoría NE o ``None`` si no está mapeado.
        """
        return self._LEAVE_CODE_MAP.get((leave_code or '').strip().upper())

    def _compute_leave_days_in_period(self, leave):
        """Calcula los días de una ausencia que caen dentro del período de la nómina.

        Recorta las fechas de la ausencia a los límites ``[date_from, date_to]``
        de la nómina para obtener solo los días efectivos dentro del período.

        :param leave: registro ``hr.leave``
        :returns: número de días (int, ≥ 0)
        """
        # hr.leave.date_from / date_to son Datetime; convertir a date
        leave_start_dt = leave.date_from
        leave_end_dt = leave.date_to
        leave_start = leave_start_dt.date() if isinstance(leave_start_dt, datetime) else leave_start_dt
        leave_end = leave_end_dt.date() if isinstance(leave_end_dt, datetime) else leave_end_dt

        # Recortar al período de la nómina
        period_start = max(leave_start, self.date_from)
        period_end = min(leave_end, self.date_to)

        days = (period_end - period_start).days + 1
        return max(days, 0)

    # ------------------------------------------------------------------
    # Cálculo automático
    # ------------------------------------------------------------------

    def compute_sheet(self):
        res = super(HrPayslipLeaveIntegration, self).compute_sheet()
        for payslip in self:
            payslip.action_detect_leaves()
        return res

    # ------------------------------------------------------------------
    # Acción principal
    # ------------------------------------------------------------------

    def action_detect_leaves(self):
        """Detecta ausencias aprobadas en el período de la nómina.

        Busca en ``hr.leave`` las ausencias del empleado que se solapen
        con el período ``[date_from, date_to]`` de la nómina.

        **Mapeo de tipos de ausencia a novedades NE:**

        +---------------------------+-------------------------+
        | Código tipo ausencia      | Novedad NE              |
        +===========================+=========================+
        | INCAPACIDAD, SICK,        | Incapacidad             |
        | INC_COMUN, INC_LABORAL    |                         |
        +---------------------------+-------------------------+
        | MATERNIDAD, MATERNITY,    | Licencia Mat/Pat        |
        | PATERNIDAD, PATERNITY,    |                         |
        | LIC_MAT, LIC_PAT         |                         |
        +---------------------------+-------------------------+
        | VACACIONES, VACATION, VAC | Vacaciones              |
        +---------------------------+-------------------------+
        | LICENCIA_REM, LIC_REM,    | Licencia remunerada     |
        | PERMISO                   |                         |
        +---------------------------+-------------------------+
        | LICENCIA_NR, LIC_NR,     | Licencia no remunerada  |
        | UNPAID, SIN_SUELDO       |                         |
        +---------------------------+-------------------------+
        | Otros                     | Se registran en resumen |
        |                           | pero no suman días      |
        +---------------------------+-------------------------+

        :returns: acción de notificación al usuario.
        :rtype: dict
        """
        self.ensure_one()

        if not self.date_from or not self.date_to:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Advertencia'),
                    'message': _('Defina las fechas de la nómina antes de detectar novedades.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        # Buscar ausencias validadas que se solapen con el período
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])

        # Acumuladores por categoría
        totals = {cat: 0 for cat in self._CATEGORY_FIELD_MAP}
        summary_lines = []

        for leave in leaves:
            days = self._compute_leave_days_in_period(leave)
            if days <= 0:
                continue

            leave_code = (leave.holiday_status_id.work_entry_type_id.code or leave.holiday_status_id.name or '').strip().upper()
            leave_name = leave.holiday_status_id.name or _('Sin nombre')
            category = self._get_leave_category(leave_code)

            if category:
                totals[category] += days
                label = self._CATEGORY_LABELS.get(category, category)
                summary_lines.append(f'{label}: {days} días ({leave_name})')
            else:
                summary_lines.append(
                    f'Otra ausencia (no mapeada): {days} días '
                    f'({leave_name} [{leave_code or "SIN CÓDIGO"}])'
                )

        # Preparar valores para escritura
        vals = {
            field: totals[cat]
            for cat, field in self._CATEGORY_FIELD_MAP.items()
        }
        vals['l10n_co_ne_leave_summary'] = (
            '\n'.join(summary_lines) if summary_lines
            else _('Sin novedades detectadas')
        )

        self.write(vals)

        _logger.info(
            'Novedades detectadas para %s [nómina %s]: '
            'Inc=%d, Mat=%d, Vac=%d, LicRem=%d, LicNR=%d',
            self.employee_id.name,
            self.number or self.id,
            totals.get('incapacidad', 0),
            totals.get('licencia_mat', 0),
            totals.get('vacaciones', 0),
            totals.get('licencia_rem', 0),
            totals.get('licencia_nr', 0),
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Novedades Detectadas'),
                'message': _('%d ausencia(s) procesadas.') % len(leaves),
                'type': 'success' if leaves else 'info',
                'sticky': False,
            },
        }
