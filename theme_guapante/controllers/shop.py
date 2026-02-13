# -*- coding: utf-8 -*-
from odoo import http, models
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from werkzeug.exceptions import Forbidden
import logging

_logger = logging.getLogger(__name__)

class GuapanteWebsiteSale(WebsiteSale):

    @http.route(['/shop/address'], type='http', methods=['GET'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        """
        Custom checkout page (GET only).
        
        Shows partner info (read-only) and shipping address selector.
        Address changes are handled via Odoo's native /shop/update_address JSON API.
        The 'Confirmar Pedido' button is a simple link to /shop/checkout/confirm.
        No form submission is needed.
        """
        Partner = request.env['res.partner']
        Order = request.website.sale_get_order()
        
        if not Order or not Order.order_line:
            return request.redirect('/shop')

        render_values = {
            'website_sale_order': Order,
            'shippings': [],
        }

        # If logged in, get shipping addresses from contacts module
        if not request.env.user._is_public():
            render_values['shippings'] = Partner.search([
                ("id", "child_of", request.env.user.partner_id.commercial_partner_id.ids),
                '|', ("type", "in", ["delivery", "other"]), ("id", "=", request.env.user.partner_id.id)
            ], order='id desc')

        return request.render("theme_guapante.guapante_checkout", render_values)

    @http.route(['/shop/checkout/confirm'], type='http', auth="public", website=True, sitemap=False)
    def confirm_order_skip_payment(self, **post):
        """
        Confirm order immediately, skipping payment, and redirect to status page.
        """
        order = request.website.sale_get_order()
        if not order or not order.order_line:
            return request.redirect('/shop')
        
        try:
            # 1. Confirm Order (Action Confirm)
            # This creates the picking(s)
            order.action_confirm()
            
            # 2. Clear Session
            request.website.sale_reset()
            
            # 3. Redirect to Status Page
            return request.redirect(f'/shop/order/status/{order.id}')
            
        except Exception as e:
            _logger.error(f"Error confirming order: {str(e)}")
            return request.redirect('/shop/checkout?error=confirm_failed')

    @http.route(['/shop/order/status/<int:order_id>'], type='http', auth="public", website=True, sitemap=False)
    def order_status(self, order_id, **post):
        """
        Render the custom order status page.
        """
        # Security Check: Ensure user can view this order
        Order = request.env['sale.order'].sudo().browse(order_id)
        if not Order.exists():
            return request.redirect('/shop')
            
        # Basic security: If public, we might need a token or just allow it if within session?
        # For simplicity in this dev phase, allowing if it matches session or user, 
        # but since we reset session, we rely on ID. 
        # Ideally we validat access_token if user is not logged in.
        
        # If user is logged in, check ownership
        if not request.env.user._is_public():
             if Order.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
                 return Forbidden()
        
        return request.render("theme_guapante.guapante_order_status", {
            'order': Order,
        })

    @http.route()
    def shop(self, page=0, category=None, search='', is_seasonal=None, **post):
        """Override shop to add is_seasonal filter"""
        _logger.info(f"=== SHOP METHOD ===")
        _logger.info(f"is_seasonal: {is_seasonal}")
        
        # Call parent
        response = super().shop(page=page, category=category, search=search, **post)
        
        # If is_seasonal is active, filter products AFTER parent processes everything
        if is_seasonal:
            _logger.info("Filtering by seasonal products")
            
            # Get bins (the grid structure that template uses)
            bins = response.qcontext.get('bins', [])
            _logger.info(f"Original bins structure: {type(bins)}, length: {len(bins) if hasattr(bins, '__len__') else 'N/A'}")
            
            # Filter bins to only keep seasonal products, maintaining the grid structure
            if bins:
                seasonal_bins = []
                for row in bins:
                    seasonal_row = []
                    for product_dict in row:
                        # Each item in the row is a dict with product info
                        product = product_dict.get('product') if isinstance(product_dict, dict) else product_dict
                        if hasattr(product, 'is_seasonal') and product.is_seasonal:
                            seasonal_row.append(product_dict)
                    if seasonal_row:
                        seasonal_bins.append(seasonal_row)
                
                # Update with filtered bins
                response.qcontext['bins'] = seasonal_bins
                
                # Count total seasonal products
                total_seasonal = sum(len(row) for row in seasonal_bins)
                response.qcontext['search_count'] = total_seasonal
                response.qcontext['is_seasonal'] = True
                
                _logger.info(f"Filtered to {total_seasonal} seasonal products in {len(seasonal_bins)} rows")
        
        return response

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

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, uom_mode=None, **kwargs):
        """
        Override to return cart_lines_count (number of unique items).
        uom_mode is now computed from product UoM, no need to persist.
        """
        if uom_mode:
            _logger.info(f"Cart update: product_id={product_id}, uom_mode={uom_mode}, add_qty={add_qty}")

        # 1. Call super to perform standard logic
        response = super().cart_update_json(
            product_id=product_id, 
            line_id=line_id, 
            add_qty=add_qty, 
            set_qty=set_qty, 
            display=display, 
            **kwargs
        )
        
        # 2. Add line count to response
        order = request.website.sale_get_order()
        if order:
            response['cart_lines_count'] = len(order.order_line)
        else:
            response['cart_lines_count'] = 0
            
        return response

    @http.route(['/shop/product/packagings/<int:product_id>'], type='json', auth="public", methods=['GET'], website=True, csrf=False)
    def get_product_packagings(self, product_id, **kwargs):
        """
        Get packagings for a specific product variant
        Returns list of packagings with id, name, qty
        """
        product = request.env['product.product'].sudo().browse(product_id)
        
        if not product.exists():
            return []
        
        # Get packagings that are enabled for sales
        packagings = product.packaging_ids.filtered(lambda p: p.sales)
        
        result = []
        for pkg in packagings:
            result.append({
                'id': pkg.id,
                'name': pkg.name,
                'qty': pkg.qty,
            })
        
        _logger.info(f"Packagings for product {product_id}: {result}")
        
        return result

