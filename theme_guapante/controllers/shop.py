# -*- coding: utf-8 -*-
from odoo import http, models
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

class GuapanteWebsiteSale(WebsiteSale):

    @http.route()
    def product(self, product, category='', search='', **kwargs):
        """ Override to inject categories sidebar context into product page. """
        # 1. Call super to get standard qcontext
        response = super().product(product, category=category, search=search, **kwargs)
        
        # 2. Extract qcontext from response
        qcontext = response.qcontext

        # 3. Inject Categories for Sidebar
        # Logic copied from WebsiteSale.shop to ensure consistency
        Category = request.env['product.public.category']
        website = request.website
        
        # Get root categories (same as in /shop)
        search_product = qcontext.get('search_product')
        if search_product:
            # If searching, show all categories (standard odoo behavior)
            categories = Category.search([('parent_id', '=', False)] + website.website_domain())
        else:
            categories = Category.search([('parent_id', '=', False)] + website.website_domain())
            
        qcontext['categories'] = categories
        
        # 4. Ensure 'category' is a recordset for the sidebar active state
        # The standard controller might define 'category' as an ID, recordset, or None/False.
        # Our XML template expects a recordset to check "c.id == category.id"
        current_category = qcontext.get('category')
        
        if not current_category:
            # If no category came from URL, try to pick one from the product
            # to highlight it in the sidebar (UX improvement)
            if product.public_categ_ids:
                qcontext['category'] = product.public_categ_ids[0]
        elif not isinstance(current_category, models.Model):
             # Ensure it's a recordset if it came as ID (unlikely in Odoo 18 but safe)
             qcontext['category'] = Category.browse(int(current_category))

        return response
