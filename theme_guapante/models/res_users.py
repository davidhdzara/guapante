# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _signup_create_user(self, values):
        """Override to inject custom partner fields during signup."""
        _logger.info("[Guapante] Signup _signup_create_user called with: %s", values)

        # Extract custom values from context
        company_type = self.env.context.get('signup_company_type', 'person')
        vat = self.env.context.get('signup_vat')
        identification_type_id = self.env.context.get('signup_identification_type_id')

        _logger.debug(
            "[Guapante] Custom values from context - company_type: %s, vat: %s, id_type: %s",
            company_type, vat, identification_type_id,
        )

        # Call parent method to create user
        new_user = super()._signup_create_user(values)

        _logger.info("[Guapante] User created: %s (Partner ID: %s)", new_user.id, new_user.partner_id.id)

        # Update partner with custom fields
        partner_values = {
            'company_type': company_type,
            'email': new_user.login,
        }

        # Establecer País por defecto a Colombia para evitar errores con Facturación Electrónica DIAN
        country_co = self.env.ref('base.co', raise_if_not_found=False)
        if country_co:
            partner_values['country_id'] = country_co.id

        if vat:
            partner_values['vat'] = vat

        if identification_type_id:
            partner_values['l10n_latam_identification_type_id'] = identification_type_id

        _logger.debug("[Guapante] Writing to partner: %s", partner_values)

        # Write with sudo to ensure permissions
        new_user.partner_id.sudo().write(partner_values)

        _logger.debug(
            "[Guapante] Partner after write - company_type: %s, vat: %s, id_type: %s",
            new_user.partner_id.company_type,
            new_user.partner_id.vat,
            new_user.partner_id.l10n_latam_identification_type_id.id
            if new_user.partner_id.l10n_latam_identification_type_id else None,
        )

        return new_user
