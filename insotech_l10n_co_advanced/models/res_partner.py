# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.addons.insotech_core.utils.dian import compute_dv
import logging

_logger = logging.getLogger(__name__)


def _compute_dv_local(nit_str):
    """Wrapper de compatibilidad — delega a insotech_core.utils.dian."""
    return compute_dv(nit_str)



class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('vat')
    def _l10n_co_dian_onchange_identification_type(self):
        """Sobrescribe el onchange nativo peligroso de Odoo 19.
        
        El core de Odoo intenta consumir el servicio SOAP de la DIAN para 
        consultar el RUT en cada pulsación del teclado o cambio de documento.
        Esto causa severos bloqueos de UI (RPC_ERROR) y arroja TypeError si 
        la llave PEM no está encriptada con contraseña en el módulo certificate.
        
        InSoTech desactiva esta arriesgada consulta en vivo y pre-calcula
        el Dígito de Verificación matemáticamente en modo Offline.
        """
        for partner in self:
            # Prevent calling super() because that's where the DIAN request happens.
            
            # Use getattr to prevent AttributeError due to field volatility in Odoo 19
            doc_type = getattr(partner, 'l10n_co_document_type', False)
            
            # Additional fallback check for standard LATAM field
            if not doc_type and hasattr(partner, 'l10n_latam_identification_type_id'):
                doc_type = getattr(partner.l10n_latam_identification_type_id, 'l10n_co_document_code', False)
            
            if doc_type == 'rut' or doc_type == '31':
                if partner.vat:
                    try:
                        # In Odoo 19 l10n_co, the verification code field varies, 
                        # but typically it's l10n_co_verification_code
                        if hasattr(partner, 'l10n_co_verification_code'):
                            partner.l10n_co_verification_code = _compute_dv_local(partner.vat)
                    except Exception as e:
                        _logger.debug("Insotech Partner Onchange: Error calculando DV autómata: %s", e)
