# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
import logging

_logger = logging.getLogger(__name__)

class GuapanteWebsiteSaleAddress(WebsiteSale):
    
    @http.route()
    def address(self, **kw):
        """Override to add detailed logging of validation errors"""
        
        # If this is a POST (form submission), log what we received
        if request.httprequest.method == 'POST':
            _logger.info("=" * 80)
            _logger.info("GUAPANTE CHECKOUT DEBUG - Form submission received")
            _logger.info("=" * 80)
            _logger.info(f"All POST data: {dict(kw)}")
            _logger.info(f"Form keys received: {list(kw.keys())}")
            
            # Log each field
            for field_name in ['name', 'email', 'phone', 'street', 'street2', 'city', 'zip', 'country_id', 'state_id']:
                value = kw.get(field_name, '[NOT PROVIDED]')
                _logger.info(f"  {field_name}: {value}")
        
        try:
            # Call parent method
            response = super().address(**kw)
            
            if request.httprequest.method == 'POST':
                _logger.info("✅ Address validation PASSED")
            
            return response
            
        except Exception as e:
            _logger.error("=" * 80)
            _logger.error("❌ CHECKOUT ERROR DETECTED")
            _logger.error(f"Error type: {type(e).__name__}")
            _logger.error(f"Error message: {str(e)}")
            _logger.error("=" * 80)
            
            # Re-raise to let Odoo handle it normally
            raise
