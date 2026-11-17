# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Representación gráfica del documento soporte de pago de nómina electrónica (Frente 5, C6b).

Los datos se leen del XML validado (``_ne_datos_representacion``) y se validan ANTES de renderizar: un documento que no
está aceptado por la DIAN da un error claro (un error dentro del QWeb lo envolvería Odoo como error de plantilla)."""

from odoo import api, models


class ReportRepresentacionGrafica(models.AbstractModel):
    _name = 'report.l10n_co_nomina_electronica.report_representacion_grafica'
    _description = 'Representación gráfica del documento soporte de pago de nómina electrónica (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['l10n.co.ne.documento'].browse(docids)
        return {
            'doc_ids': docids, 'doc_model': 'l10n.co.ne.documento', 'docs': docs, 'data': data,
            'datos_documentos': {doc.id: doc._ne_datos_representacion() for doc in docs},
        }
