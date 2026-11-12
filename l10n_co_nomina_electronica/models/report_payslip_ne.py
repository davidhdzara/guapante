# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Modelo del reporte del comprobante de nomina (PDF).

Valida ANTES de renderizar: un error lanzado dentro del QWeb lo envuelve Odoo como error de
plantilla y el usuario no vería el mensaje claro. Aqui se recorre cada recibo y
HrPayslip._ne_pdf_neto() lanza su UserError fuera del render."""

from odoo import api, models


class ReportPayslipNe(models.AbstractModel):
    _name = 'report.l10n_co_nomina_electronica.report_payslip_ne'
    _description = 'Comprobante de nómina (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.payslip'].browse(docids)
        for payslip in docs:
            payslip._ne_pdf_neto()
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'data': data,
        }
