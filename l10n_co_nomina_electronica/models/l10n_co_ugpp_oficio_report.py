# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportUgppOficio(models.AbstractModel):
    """Datos del oficio de respuesta a la UGPP: se calculan (y validan) en el modelo del reporte, no en la plantilla."""
    _name = 'report.l10n_co_nomina_electronica.report_ugpp_oficio'
    _description = 'Oficio de respuesta UGPP (borrador)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['l10n_co_nomina.ugpp'].browse(docids)
        return {
            'doc_ids': docs.ids, 'doc_model': 'l10n_co_nomina.ugpp', 'docs': docs,
            'datos': {doc.id: doc._ugpp_datos_oficio() for doc in docs},
        }
