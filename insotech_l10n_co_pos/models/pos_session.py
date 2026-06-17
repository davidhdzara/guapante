from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    dian_resolution_text = fields.Char(compute='_compute_dian_resolution_text')
    dian_obligations_text = fields.Char(compute='_compute_dian_obligations_text')

    def _compute_dian_resolution_text(self):
        for company in self:
            resolution_text = 'Resolución de Facturación Electrónica no configurada.'
            # Buscar cualquier documento DIAN activo de la compañía
            dian_doc = self.env['l10n_co_dian_document'].search([
                ('company_id', '=', company.id),
                ('active', '=', True)
            ], limit=1)
            
            if dian_doc:
                resolution_text = f"Autorización DIAN {dian_doc.resolution_number} desde {dian_doc.date_from} hasta {dian_doc.date_to} prefijo {dian_doc.prefix} desde {dian_doc.number_from} hasta {dian_doc.number_to}"
            
            company.dian_resolution_text = resolution_text

    def _compute_dian_obligations_text(self):
        for company in self:
            obligations = []
            if hasattr(company.partner_id, 'l10n_co_edi_obligation_type_ids'):
                for obl in company.partner_id.l10n_co_edi_obligation_type_ids:
                    if obl.name:
                        obligations.append(obl.name)
            
            company.dian_obligations_text = ', '.join(obligations) if obligations else 'Responsable de IVA'


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _load_pos_data_fields(self, model_name):
        """
        Odoo 18 modern way to load custom fields into POS models.
        """
        fields = super()._load_pos_data_fields(model_name)
        if model_name == 'res.company':
            fields.extend(['company_registry', 'dian_resolution_text', 'dian_obligations_text'])
        return fields
