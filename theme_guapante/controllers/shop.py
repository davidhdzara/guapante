# -*- coding: utf-8 -*-
from odoo import http, models
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
import logging

_logger = logging.getLogger(__name__)

class GuapanteWebsiteSale(WebsiteSale):

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
        Override to return cart_lines_count (number of unique items)
        instead of just quantity sum.
        Also handles uom_mode for traceability.
        """
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
            
            # 3. Update uom_mode if provided
            # We need to find the line that was just updated/created.
            # Since cart_update_json doesn't return the line ID directly in all cases,
            # we look for the line with the matching product_id.
            # NOTE: This might be inexact if multiple lines exist for same product (unlikely in standard website_sale),
            # but it is the best approximation without overriding the whole method.
            if uom_mode and uom_mode in ['kg', 'g', 'unit']:
                # If we have a line_id from arguments, use it (update case)
                target_line = None
                if line_id:
                     target_line = order.order_line.filtered(lambda l: l.id == line_id)
                else:
                    # If it was an add, find the line for this product
                    # We sort by write_date desc to get the most recently modified
                    domain = [('product_id', '=', product_id)]
                    target_line = order.order_line.filtered_domain(domain).sorted('write_date', reverse=True)[:1]
                
                if target_line:
                    target_line.sudo().write({'uom_mode': uom_mode})
                    _logger.info(f"Updated uom_mode to {uom_mode} for line {target_line.id}")

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

