# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""E-7 (doc 59 §24): las 4 estructuras propias imprimen (y envian por correo) la colilla propia.

``hr.payroll.structure.report_id`` elige el PDF por estructura (``hr.payslip._get_pdf_reports`` -> ``_generate_pdf``, correo nativo): por
defecto el informe nativo «Payslip». Funcion de datos idempotente: lo cambia al «Comprobante de pago» propio SOLO si la estructura trae el
informe nativo o ninguno (un informe elegido a mano no se pisa)."""

from odoo import api, fields, models

NE_ESTRUCTURAS_PROPIAS = (
    'hr_payroll_structure_co_nomina', 'hr_payroll_structure_co_liquidacion', 'hr_payroll_structure_co_prima',
    'hr_payroll_structure_co_bonificacion')


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    l10n_co_ne_conceptos_de_pago = fields.Boolean(
        string='Usa «Conceptos de pago»',
        help='E11 (doc 71c): la estructura usa la vista «Conceptos de pago» y sus reglas admiten, por defecto, el ajuste de la empresa '
             '(según la sección de su categoría). Por ahora solo la estructura general; las demás se activan marcando esto.')

    @api.model
    def _ne_alinear_informe_recibo(self):
        propio = self.env.ref('l10n_co_nomina_electronica.action_report_payslip_ne', raise_if_not_found=False)
        nativos = [self.env.ref(xmlid, raise_if_not_found=False) for xmlid in (
            'hr_payroll.action_report_payslip', 'hr_payroll.action_report_light_payslip')]
        nativos = self.env['ir.actions.report'].browse([r.id for r in nativos if r])
        if not propio:
            return
        for xmlid in NE_ESTRUCTURAS_PROPIAS:
            estructura = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid, raise_if_not_found=False)
            if estructura and (not estructura.report_id or estructura.report_id in nativos):
                estructura.report_id = propio
