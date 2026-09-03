# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Jornada y Recargos de Nomina Colombiana, versionados por fecha de vigencia.

A diferencia de l10n.co.payroll.annual.params (que cambia una vez al ano,
el 1 de enero), estos valores pueden cambiar a mitad de ano por ley --
como ocurrio en 2026 con la Ley 2101/2021 (jornada) y la Ley 2466/2025
(recargos), en fechas de corte distintas dentro del mismo ano. Por eso
se versionan por date_from en vez de por year.

Referencia: correcciones_normativas_2026/10a_adenda_versionado_fechas_y_uvt.md
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_MIN_HORAS_MENSUALES = 168
_MAX_HORAS_MENSUALES = 260


class L10nCoPayrollTimeParams(models.Model):
    _name = 'l10n.co.payroll.time.params'
    _description = 'Jornada y Recargos Colombia (versionado por vigencia)'
    _order = 'date_from desc'

    date_from = fields.Date(
        string='Vigente Desde',
        required=True,
        help='Fecha desde la cual aplican estos valores. Se busca el '
             'registro mas reciente con date_from <= fecha de la nomina.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
    )

    # Jornada (Ley 2101/2021)
    horas_semanales = fields.Integer(
        string='Jornada Semanal (h)', required=True, default=42,
        help='Jornada maxima semanal legal vigente.',
    )
    horas_mensuales = fields.Integer(
        string='Divisor Horas Mensuales', required=True, default=210,
        help='Divisor usado para calcular el valor de la hora ordinaria '
             '(salario / horas_mensuales).',
    )

    # Recargos y horas extra (Ley 2466/2025)
    factor_hed = fields.Float(string='HE Diurna', required=True, default=1.25)
    factor_hen = fields.Float(string='HE Nocturna', required=True, default=1.75)
    factor_hrn = fields.Float(string='Recargo Nocturno', required=True, default=0.35)
    factor_hrddf = fields.Float(string='Recargo Dom/Fest', required=True, default=1.90)
    factor_heddf = fields.Float(string='HE Diurna Dom/Fest', required=True, default=2.15)
    factor_hendf = fields.Float(string='HE Nocturna Dom/Fest', required=True, default=2.65)
    factor_hrndf = fields.Float(string='Recargo Noct. Dom/Fest', required=True, default=2.25)

    # Franja nocturna (Ley 2466/2025: 9pm -> 7pm)
    hora_inicio_franja_nocturna = fields.Float(
        string='Hora Inicio Franja Nocturna', required=True, default=19.0,
        help='En formato 24h. 19.0 = 7:00pm (Ley 2466/2025). Antes: 21.0 = 9:00pm.',
    )

    _sql_constraints = [
        ('unique_date_from_company',
         'unique(date_from, company_id)',
         'Ya existe un registro de jornada/recargos vigente desde esa '
         'fecha para esta compania.'),
    ]

    @api.depends('date_from', 'company_id', 'company_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (
                rec.date_from and rec.date_from.isoformat() or '',
                rec.company_id.name or '',
            )

    @api.constrains('horas_mensuales')
    def _check_horas_mensuales(self):
        for rec in self:
            if rec.horas_mensuales < _MIN_HORAS_MENSUALES or rec.horas_mensuales > _MAX_HORAS_MENSUALES:
                raise ValidationError(_(
                    'Las horas mensuales deben estar entre %(min)d y %(max)d. '
                    'Valor: %(val)d.',
                    min=_MIN_HORAS_MENSUALES,
                    max=_MAX_HORAS_MENSUALES,
                    val=rec.horas_mensuales,
                ))
