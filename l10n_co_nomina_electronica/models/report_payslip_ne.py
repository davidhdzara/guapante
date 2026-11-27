# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Modelo del reporte del comprobante de nomina (PDF).

Valida ANTES de renderizar: un error lanzado dentro del QWeb lo envuelve Odoo como error de
plantilla y el usuario no vería el mensaje claro. Aqui se recorre cada recibo y
HrPayslip._ne_pdf_neto() lanza su UserError fuera del render.

H-QA-034: también calcula AQUÍ (no en la plantilla) los «Días trabajados» del encabezado: los días con que se PAGÓ el recibo, tomados
de la cantidad guardada de su línea de sueldo."""

from odoo import api, models


class ReportPayslipNe(models.AbstractModel):
    _name = 'report.l10n_co_nomina_electronica.report_payslip_ne'
    _description = 'Comprobante de nómina (PDF)'

    # Reglas cuya CANTIDAD guardada son los días con los que se pagó el recibo (H-QA-034, AUD-DIAN-34): CO_BASICO (nómina general) y
    # CO_LIQ_SALARIOS (liquidación) calculan ``result_qty = payslip._ne_dias_pagables()`` (data/hr_payroll_structure_data.xml:156-163 y
    # data/hr_payroll_structure_special_data.xml:268-282), la MISMA fuente que el ``DiasTrabajados`` del XML (``HrPayslip.
    # _dev_basico_y_transporte``). El motor guarda esa cantidad en la línea (``hr_payroll/models/hr_payslip.py:1012``, ``'quantity': qty``)
    # y el nativo la lee de ``hr.payslip.line.quantity`` (``:1236``); ``hr.payslip.line_ids`` es el One2many ``hr.payslip.line``
    # (``:78-80``). Antes la colilla imprimía la línea ``WORK100`` (días lun-vie del calendario): la misma doble fuente que AUD-DIAN-34
    # ya había corregido en el XML. Prima y bonificación no tienen estas líneas: el campo se oculta.
    _NE_LINEAS_DIAS_PAGADOS = ('CO_BASICO', 'CO_LIQ_SALARIOS')

    @api.model
    def _ne_linea_dias_pagados(self, recibo):
        """Línea del recibo cuya cantidad son los días con que se PAGÓ, o un recordset vacío (la plantilla oculta el campo).

        Lee la cantidad GUARDADA, no ``_ne_dias_pagables()``: un comprobante impreso muestra lo pagado, y recalcular al imprimir lo haría
        cambiar si después se modifican ausencias o contrato. NO cae a ``WORK100``. Si hubiera varias líneas de la lista, la primera."""
        recibo.ensure_one()
        return recibo.line_ids.filtered(lambda linea: linea.code in self._NE_LINEAS_DIAS_PAGADOS)[:1]

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.payslip'].browse(docids)
        docs.company_id._ne_exigir_colombia()   # el informe esta en el menu Imprimir de todo recibo: inerte fuera de CO
        # La tabla se arma AQUI y no en la plantilla: ``_ne_colilla`` llama a ``_ne_pdf_neto``, que sin linea de neto lanza un error claro, y un error
        # lanzado dentro del QWeb lo envolveria Odoo como error de plantilla (E11 pieza 5a, .291).
        colillas = {payslip.id: payslip._ne_colilla() for payslip in docs}
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'data': data,
            'colillas': colillas,   # id del recibo -> tabla de la colilla (secciones, totales, neto, diferencia)
            'dias_pagados': {payslip.id: self._ne_linea_dias_pagados(payslip) for payslip in docs},   # id del recibo -> línea de sueldo
        }
