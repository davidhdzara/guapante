from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_dian_resolution_text(self):
        """
        Lee la resolución DIAN directamente del diario de ventas.
        """
        self.ensure_one()
        resolution_text = ''
        try:
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.id),
                ('type', '=', 'sale'),
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
                        "Numeración autorizada según formulario "
                        "%s del %s al %s. DIAN %s%s al %s%s"
                    ) % (auth_number, date_from, date_to, prefix, min_range, prefix, max_range)
        except Exception as e:
            _logger.warning("Error cargando resolución DIAN para POS: %s", e)
        return resolution_text

    def _get_dian_obligations_text(self):
        """Responsabilidades fiscales del partner de la compañía."""
        self.ensure_one()
        obligations = []
        try:
            partner = self.partner_id
            if hasattr(partner, 'l10n_co_edi_large_taxpayer'):
                if partner.l10n_co_edi_large_taxpayer:
                    obligations.append('Gran Contribuyente')
                else:
                    obligations.append('No somos Grandes Contribuyentes')

            if hasattr(partner, 'l10n_co_edi_obligation_type_ids'):
                for obl in partner.l10n_co_edi_obligation_type_ids:
                    if obl.name:
                        obligations.append(obl.name)

            if hasattr(partner, 'l10n_co_edi_fiscal_regimen'):
                regimen = partner.l10n_co_edi_fiscal_regimen
                if regimen == '48':
                    obligations.append('Responsable de IVA')
                elif regimen == '49':
                    obligations.append('No responsable de IVA')
        except Exception as e:
            _logger.warning("Error cargando obligaciones DIAN para POS: %s", e)
        return ', '.join(obligations) if obligations else ''

    def _get_dian_ciiu_code(self):
        """Código CIIU de actividad económica."""
        self.ensure_one()
        ciiu = ''
        try:
            if hasattr(self, 'l10n_co_edi_ciiu_id') and self.l10n_co_edi_ciiu_id:
                ciiu = self.l10n_co_edi_ciiu_id.name or ''
                if hasattr(self.l10n_co_edi_ciiu_id, 'code') and self.l10n_co_edi_ciiu_id.code:
                    ciiu = "%s - %s" % (self.l10n_co_edi_ciiu_id.code, self.l10n_co_edi_ciiu_id.name)
        except Exception as e:
            _logger.warning("Error cargando CIIU para POS: %s", e)
        return ciiu

    @api.model
    def _load_pos_data(self, data):
        """
        Sobreescribimos _load_pos_data de res.company para inyectar
        los datos DIAN (resolución, obligaciones, CIIU) en el payload
        que se envía al frontend del POS.

        Los campos compute sin store=True NO se serializan con search_read,
        por eso inyectamos manualmente después del super().
        """
        result = super()._load_pos_data(data)
        # result es {'data': [...], 'fields': [...]}
        if result and 'data' in result:
            for company_dict in result['data']:
                company_id = company_dict.get('id')
                if company_id:
                    company = self.browse(company_id)
                    company_dict['dian_resolution_text'] = company._get_dian_resolution_text()
                    company_dict['dian_obligations_text'] = company._get_dian_obligations_text()
                    company_dict['dian_ciiu_code'] = company._get_dian_ciiu_code()
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Asegurar que datos de identificación colombiana se cargan en el POS."""
        result = super()._load_pos_data_fields(config_id)
        extra_fields = ['l10n_latam_identification_type_id', 'street', 'city', 'phone', 'mobile', 'email']
        for f in extra_fields:
            if f not in result:
                result.append(f)
        return result
