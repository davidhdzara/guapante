# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""E-7 (doc 59 §24): en compañías colombianas el informe NATIVO «Payslip» imprime la colilla propia.

El informe nativo de hr_payroll (``report_payslip_lang`` y su variante ``report_light_payslip_lang``) imprime las líneas nativas
BASIC/GROSS/NET (valores contradictorios con el neto real: «Salario básico 527.670» junto a «Neto a Pagar 1.735.380,10»), el marcador
«Pagar el xxxxxxxx» de la plantilla y las entradas de trabajo. El menú Imprimir es GLOBAL por modelo (no se puede ocultar una acción por
compañía), asi que, cuando el informe pedido es uno de esos dos nativos y TODOS los recibos son de companias colombianas, se renderiza el
«Comprobante de pago» propio. Cualquier otro informe (facturas, otros paises, lotes mixtos) conserva el comportamiento nativo; si la
decision falla por cualquier causa, tambien el nativo (nunca se rompe una impresion por esta redireccion)."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

NE_INFORMES_NATIVOS_DE_RECIBO = ('hr_payroll.report_payslip_lang', 'hr_payroll.report_light_payslip_lang')
NE_INFORME_PROPIO_XMLID = 'l10n_co_nomina_electronica.action_report_payslip_ne'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _ne_informe_propio_si_es_recibo_colombiano(self, report_ref, res_ids):
        """El informe propio (registro) si ``report_ref`` es uno de los 2 nativos de recibo y todos los recibos son de companias
        colombianas; ``False`` en cualquier otro caso o ante cualquier error (nativo)."""
        try:
            if not res_ids:
                return False
            reporte = self._get_report(report_ref)
            if reporte.report_name not in NE_INFORMES_NATIVOS_DE_RECIBO:
                return False
            ids = [res_ids] if isinstance(res_ids, int) else list(res_ids)
            recibos = self.env['hr.payslip'].browse(ids).exists()
            if not recibos or not all(compania._ne_es_colombia() for compania in recibos.company_id):
                return False
            return self.env.ref(NE_INFORME_PROPIO_XMLID)
        except Exception:      # noqa: BLE001 -- defensivo a proposito: la redireccion nunca debe romper una impresion
            _logger.exception('No se pudo decidir la redireccion del informe de recibo; se usa el informe nativo.')
            return False

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        propio = self._ne_informe_propio_si_es_recibo_colombiano(report_ref, res_ids)
        return super()._render_qweb_pdf(propio or report_ref, res_ids, data)

    def _render_qweb_html(self, report_ref, docids, data=None):
        propio = self._ne_informe_propio_si_es_recibo_colombiano(report_ref, docids)
        return super()._render_qweb_html(propio or report_ref, docids, data)
