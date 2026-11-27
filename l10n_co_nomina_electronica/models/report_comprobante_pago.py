# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Comprobante de pago único por empleado y fecha de pago (Frente 5, C3; E11 pieza 5b, .292).

.292: UNA media página por GRUPO (empleado, fecha de pago) con una SECCIÓN POR ORIGEN (la estructura salarial de cada recibo: doc 58 §5(a), D5-1,
D5-5, D5-7), cada una con la tabla compacta de la colilla (``HrPayslip._ne_colilla``) y su subtotal, y el neto total pagado al pie. El agrupador
(``_ne_comprobantes``, C2) y el desglose por recibo (``_ne_desglose``, C1) son los del Frente 5.

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
        Colilla = self.env['report.l10n_co_nomina_electronica.report_payslip_ne']
        grupos = []
        for grupo in agrupados['grupos']:
            # Todo se arma AQUÍ (fuera del QWeb): un recibo sin línea de neto lanza su error claro antes de renderizar. Una sección por recibo del grupo,
            # con el origen (nombre de su estructura salarial, ``_ne_desglose``) y la tabla compacta de su colilla (``_ne_colilla``).
            secciones = []
            for recibo in grupo['recibos']:
                desglose = recibo._ne_desglose()
                secciones.append({
                    'recibo': recibo, 'origen': desglose['origen'], 'neto': desglose['neto'], 'colilla': recibo._ne_colilla(),
                    'linea_dias': Colilla._ne_linea_dias_pagados(recibo)})
            grupos.append({
                'empleado': grupo['empleado'],
                'fecha_pago': grupo['fecha_pago'],
                'recibos': grupo['recibos'],
                'moneda': grupo['recibos'][:1].company_id.currency_id,
                'secciones': secciones,
                'neto_total': sum(s['neto'] for s in secciones),
                'dias_pagados': {s['recibo'].id: s['linea_dias'] for s in secciones},
            })
        return {'doc_ids': docids, 'doc_model': 'hr.payslip', 'docs': recibos, 'data': data, 'grupos': grupos}
