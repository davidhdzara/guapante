import base64

from odoo import _, models
from odoo.exceptions import AccessError, UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _portal_is_published(self):
        self.ensure_one()
        if self.state not in ('done', 'paid'):
            return False
        policy = self.company_id.l10n_co_portal_payslip_publication_policy
        return policy == 'finalized' or self.l10n_co_ne_state == 'accepted'

    def _portal_dto(self):
        self.ensure_one()
        return {
            'id': self.id,
            'number': self.number or self.name,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'state': self.state,
            'amount': self.net_wage,
        }

    def _portal_pdf(self):
        """Render the existing payslip report only after the controller authorizes it."""
        self.ensure_one()
        if not self._portal_is_published():
            raise AccessError(_('La colilla no está publicada.'))
        report = self.env.ref('l10n_co_nomina_electronica.action_report_payslip_ne', raise_if_not_found=False)
        if not report:
            report = self.env.ref('hr_payroll.action_report_payslip', raise_if_not_found=False)
        if not report:
            raise UserError(_('No hay reporte de colilla configurado.'))
        return self.env['ir.actions.report'].sudo()._render_qweb_pdf(report.id, [self.id])[0]
