from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dian_resolution_text = fields.Char(compute='_compute_dian_resolution_text')
    dian_obligations_text = fields.Char(compute='_compute_dian_obligations_text')
    dian_ciiu_code = fields.Char(compute='_compute_dian_ciiu_code')

    def _compute_dian_resolution_text(self):
        """
        Lee la resolución DIAN directamente del diario de ventas POS.
        Los campos están en account.journal (módulo enterprise l10n_co_dian):
          - l10n_co_edi_dian_authorization_number
          - l10n_co_edi_dian_authorization_date
          - l10n_co_edi_dian_authorization_end_date
          - l10n_co_edi_min_range_number
          - l10n_co_edi_max_range_number
          - code (prefijo)
        """
        for company in self:
            resolution_text = ''
            try:
                # Buscar el diario del POS (tipo 'sale' o 'general' con resolución)
                journal = self.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('type', '=', 'sale'),
                ], limit=1)

                if not journal:
                    journal = self.env['account.journal'].search([
                        ('company_id', '=', company.id),
                    ], limit=1)

                if journal and hasattr(journal, 'l10n_co_edi_dian_authorization_number'):
                    auth_number = journal.l10n_co_edi_dian_authorization_number
                    if auth_number:
                        date_from = journal.l10n_co_edi_dian_authorization_date or ''
                        date_to = journal.l10n_co_edi_dian_authorization_end_date or ''
                        prefix = journal.code or ''
                        min_range = journal.l10n_co_edi_min_range_number or 0
                        max_range = journal.l10n_co_edi_max_range_number or 0
                        resolution_text = (
                            f"Numeración autorizada según formulario "
                            f"{auth_number} del {date_from} al {date_to}. "
                            f"DIAN {prefix}{min_range} al {prefix}{max_range}"
                        )
            except Exception as e:
                _logger.warning("Error cargando resolución DIAN para POS: %s", e)
            company.dian_resolution_text = resolution_text

    def _compute_dian_obligations_text(self):
        for company in self:
            obligations = []
            try:
                partner = company.partner_id
                # Gran contribuyente
                if hasattr(partner, 'l10n_co_edi_large_taxpayer'):
                    if partner.l10n_co_edi_large_taxpayer:
                        obligations.append('Gran Contribuyente')
                    else:
                        obligations.append('No somos Grandes Contribuyentes')

                # Responsabilidades fiscales
                if hasattr(partner, 'l10n_co_edi_obligation_type_ids'):
                    for obl in partner.l10n_co_edi_obligation_type_ids:
                        if obl.name:
                            obligations.append(obl.name)

                # Régimen fiscal
                if hasattr(partner, 'l10n_co_edi_fiscal_regimen'):
                    regimen = partner.l10n_co_edi_fiscal_regimen
                    if regimen == '48':
                        obligations.append('Responsable de IVA')
                    elif regimen == '49':
                        obligations.append('No responsable de IVA')
            except Exception as e:
                _logger.warning("Error cargando obligaciones DIAN para POS: %s", e)
            company.dian_obligations_text = ', '.join(obligations) if obligations else ''

    def _compute_dian_ciiu_code(self):
        for company in self:
            ciiu = ''
            try:
                if hasattr(company, 'l10n_co_edi_ciiu_id') and company.l10n_co_edi_ciiu_id:
                    ciiu = company.l10n_co_edi_ciiu_id.name or ''
                    if hasattr(company.l10n_co_edi_ciiu_id, 'code') and company.l10n_co_edi_ciiu_id.code:
                        ciiu = f"{company.l10n_co_edi_ciiu_id.code} - {company.l10n_co_edi_ciiu_id.name}"
            except Exception as e:
                _logger.warning("Error cargando CIIU para POS: %s", e)
            company.dian_ciiu_code = ciiu


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _load_pos_data_fields(self, model_name):
        """
        Cargar campos DIAN de la empresa y del contacto en el frontend del POS.
        """
        result = super()._load_pos_data_fields(model_name)
        if model_name == 'res.company':
            result.extend([
                'company_registry',
                'dian_resolution_text',
                'dian_obligations_text',
                'dian_ciiu_code',
            ])
        if model_name == 'res.partner':
            extra_fields = ['l10n_latam_identification_type_id', 'street', 'city', 'phone', 'mobile', 'email']
            for f in extra_fields:
                if f not in result:
                    result.append(f)
        return result
