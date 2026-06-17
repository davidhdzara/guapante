from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dian_resolution_text = fields.Char(compute='_compute_dian_resolution_text')
    dian_obligations_text = fields.Char(compute='_compute_dian_obligations_text')

    def _compute_dian_resolution_text(self):
        for company in self:
            resolution_text = ''
            try:
                if 'l10n_co_dian_document' in self.env:
                    dian_doc = self.env['l10n_co_dian_document'].search([
                        ('company_id', '=', company.id),
                        ('active', '=', True)
                    ], limit=1)
                    if dian_doc:
                        resolution_text = (
                            f"Autorización DIAN {dian_doc.resolution_number} "
                            f"desde {dian_doc.date_from} hasta {dian_doc.date_to} "
                            f"prefijo {dian_doc.prefix} desde {dian_doc.number_from} "
                            f"hasta {dian_doc.number_to}"
                        )
            except Exception as e:
                _logger.warning("Error al cargar resolución DIAN para POS: %s", e)
            company.dian_resolution_text = resolution_text

    def _compute_dian_obligations_text(self):
        for company in self:
            obligations = []
            try:
                if hasattr(company.partner_id, 'l10n_co_edi_obligation_type_ids'):
                    for obl in company.partner_id.l10n_co_edi_obligation_type_ids:
                        if obl.name:
                            obligations.append(obl.name)
            except Exception as e:
                _logger.warning("Error al cargar obligaciones DIAN para POS: %s", e)
            company.dian_obligations_text = ', '.join(obligations) if obligations else ''


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _load_pos_data_fields(self, model_name):
        """
        Cargar campos DIAN de la empresa en el frontend del POS.
        """
        result = super()._load_pos_data_fields(model_name)
        if model_name == 'res.company':
            result.extend(['company_registry', 'dian_resolution_text', 'dian_obligations_text'])
        return result
