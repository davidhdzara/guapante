# -*- coding: utf-8 -*-
from odoo import models


class RetentionReportWizard(models.TransientModel):
    """Extiende el wizard nativo de Certificados de Retención
    (l10n_co_reports.retention_report.wizard: fecha de expedición, fecha
    de declaración, artículo) sin agregar campos nuevos ni una vista
    nueva.

    Decisión tomada el 2026-07-29 (ver ESPEC §4, decisión sobre la
    simplificación de la Fase 3): la selección de qué proveedores y qué
    retenciones entran al certificado NO se resuelve en un wizard propio,
    sino reutilizando lo que el framework de account.report ya ofrece:
    - Proveedores: el filtro de tercero del reporte (filter_partner),
      que admite selección múltiple.
    - Qué retenciones incluir: el estado de plegado/desplegado del
      reporte en el momento de imprimir (todo desplegado por defecto;
      plegar una línea es el acto consciente de excluirla).

    Este wizard solo captura las 3 fechas/artículo, exactamente igual que
    para los certificados nativos de Fuente/ICA/IVA. Lo único que se
    extiende es generate_report(), para que sepa a qué plantilla dirigir
    el PDF según cuál reporte lo haya invocado.
    """

    _inherit = 'l10n_co_reports.retention_report.wizard'

    def generate_report(self):
        options = self.env.context.get('options') or {}
        report_id = options.get('report_id')
        report = (
            self.env['account.report'].browse(report_id)
            if report_id else self.env['account.report']
        )

        if report and report.custom_handler_model_name == 'l10n_co.retention.certificate.report.handler':
            data = {'wizard_values': self.read()[0]}
            return self.env.ref(
                'l10n_co_retention_certificate.action_report_retention_certificate'
            ).report_action([], data=data)

        # Cualquier otro llamador (Fuente/ICA/IVA nativos, o algún otro
        # reporte que en el futuro reutilice este mismo wizard) conserva
        # su comportamiento original, sin ningún cambio.
        return super().generate_report()
