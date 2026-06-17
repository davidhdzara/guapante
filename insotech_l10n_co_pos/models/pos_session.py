from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dian_resolution_text = fields.Char(compute='_compute_dian_resolution_text')
    dian_obligations_text = fields.Char(compute='_compute_dian_obligations_text')
    dian_ciiu_code = fields.Char(compute='_compute_dian_ciiu_code')

    def _compute_dian_resolution_text(self):
        for company in self:
            resolution_text = ''
            try:
                if 'l10n_co_dian.document' in self.env:
                    dian_doc = self.env['l10n_co_dian.document'].search([
                        ('company_id', '=', company.id),
                    ], limit=1)
                    if dian_doc:
                        prefix = dian_doc.prefix or ''
                        resolution_text = (
                            f"Numeración autorizada según formulario "
                            f"{dian_doc.resolution_number} del "
                            f"{dian_doc.date_from} al {dian_doc.date_to}. "
                            f"DIAN {prefix}{dian_doc.number_from} al "
                            f"{prefix}{dian_doc.number_to}"
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
                    ciiu = company.l10n_co_edi_ciiu_id.name or company.l10n_co_edi_ciiu_id.code or ''
                elif company.company_registry:
                    ciiu = company.company_registry
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
            # Asegurar que datos de identificación colombiana se cargan
            extra_fields = ['l10n_latam_identification_type_id', 'street', 'city', 'phone', 'mobile', 'email']
            for f in extra_fields:
                if f not in result:
                    result.append(f)
        return result
