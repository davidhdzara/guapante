# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Comprobante de pago único por empleado y fecha de pago (Frente 5, C3).

Agrupa y valida ANTES de renderizar (un error dentro del QWeb lo envolvería Odoo como error de plantilla): los recibos sin
confirmar o sin fecha de pago no tienen comprobante agrupado y se informan con un error que nombra cada recibo y dice cómo
corregirlo (no se inventa una fecha)."""

from odoo import _, api, models
from odoo.exceptions import UserError


class ReportComprobantePago(models.AbstractModel):
    _name = 'report.l10n_co_nomina_electronica.report_comprobante_pago'
    _description = 'Comprobante de pago por fecha de pago (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        recibos = self.env['hr.payslip'].browse(docids)
        recibos.company_id._ne_exigir_colombia()   # el informe esta en el menu Imprimir de todo recibo: inerte fuera de CO
        agrupados = self.env['hr.payslip']._ne_comprobantes(recibos)
        if agrupados['sin_fecha']:
            raise UserError(_(
                'No se puede imprimir el comprobante de pago agrupado:\n%s',
                '\n'.join(motivo for _recibo, motivo in agrupados['sin_fecha'])))
        grupos = []
        for grupo in agrupados['grupos']:
            secciones = [{'desglose': recibo._ne_desglose(), 'lineas': recibo._ne_pdf_lineas()}
                         for recibo in grupo['recibos']]
            grupos.append({
                'empleado': grupo['empleado'],
                'fecha_pago': grupo['fecha_pago'],
                'recibos': grupo['recibos'],
                'moneda': grupo['recibos'][:1].company_id.currency_id,
                'secciones': secciones,
                'neto_total': sum(s['desglose']['neto'] for s in secciones),
            })
        return {'doc_ids': docids, 'doc_model': 'hr.payslip', 'docs': recibos, 'data': data, 'grupos': grupos}
