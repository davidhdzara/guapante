from odoo import api, fields, models, _
from odoo.exceptions import UserError

import datetime


class L10nCoNominaUGPPWizard(models.TransientModel):
    _name = 'l10n_co_nomina.ugpp.wizard'
    _description = 'Asistente para generar Reporte UGPP'

    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    month = fields.Selection(
        selection=[
            ('1', 'Enero'),
            ('2', 'Febrero'),
            ('3', 'Marzo'),
            ('4', 'Abril'),
            ('5', 'Mayo'),
            ('6', 'Junio'),
            ('7', 'Julio'),
            ('8', 'Agosto'),
            ('9', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
    )

    def action_generate(self):
        """Create a UGPP report record and trigger report generation."""
        self.ensure_one()

        if not self.year or not self.month:
            raise UserError(_('Debe seleccionar el año y el mes para generar el reporte.'))

        month_int = int(self.month)
        date_from = datetime.date(self.year, month_int, 1)
        # Calculate last day of the month
        if month_int == 12:
            date_to = datetime.date(self.year, 12, 31)
        else:
            date_to = datetime.date(self.year, month_int + 1, 1) - datetime.timedelta(days=1)

        ugpp_report = self.env['l10n_co_nomina.ugpp'].create({
            'year': self.year,
            'month': self.month,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.env.company.id,
        })

        ugpp_report.action_generate_report()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_co_nomina.ugpp',
            'res_id': ugpp_report.id,
            'view_mode': 'form',
            'target': 'current',
        }
