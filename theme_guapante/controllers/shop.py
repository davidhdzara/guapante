# -*- coding: utf-8 -*-
from odoo import http, models
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from werkzeug.exceptions import Forbidden
import logging

_logger = logging.getLogger(__name__)

class GuapanteWebsiteSale(WebsiteSale):

    @http.route(['/shop/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        """Override address to use custom single-page checkout logic"""
        Partner = request.env['res.partner']
        Order = request.website.sale_get_order()
        
        if not Order or not Order.order_line:
            return request.redirect('/shop')

        mode = (False, False)
        can_edit_vat = False
        def_country_id = Order.partner_id.country_id
        values, errors = {}, {}

        partner_id = int(kw.get('partner_id', -1))

        # IF LOGGED IN
        if partner_id > 0:
             if partner_id == Order.partner_id.id:
                mode = ('edit', 'billing')
                can_edit_vat = Order.partner_id.can_edit_vat()
             else:
                shippings = Partner.search([('id', 'child_of', Order.partner_id.commercial_partner_id.ids)])
                if partner_id in shippings.mapped('id'):
                    mode = ('edit', 'shipping')
                else:
                    return Forbidden()
        # IF GUEST
        else:
             mode = ('new', 'shipping')
             values = kw

        # HANDLE POST REQUEST (Form Submission)
        if request.httprequest.method == 'POST':
            # 1. Validate required fields
            required_fields = ['name', 'email', 'phone', 'street', 'city', 'country_id']
            # Add state_id if country requires it (assuming Colombia for now)
            # if 'state_id' in kw and kw['state_id']: required_fields.append('state_id')

            errors = {}
            for field in required_fields:
                if not kw.get(field):
                    # We can be smarter here, checking if we are using an existing address
                    # If shipping_id is providing, we don't need address fields
                    if field in ['street', 'city'] and kw.get('shipping_id') and kw.get('shipping_id') != '0' and kw.get('shipping_id') != '-1':
                        continue
                    errors[field] = 'missing'
            
            # 2. Process specific logic
            if not errors:
                try:
                    # Logic to Update/Create Partner
                    # If shipping_id is selected (existing address)
                    shipping_id = kw.get('shipping_id', 0)
                    try:
                        shipping_id = int(shipping_id)
                    except:
                        shipping_id = 0

                    partner_values = {
                        'name': kw.get('name'),
                        'email': kw.get('email'),
                        'phone': kw.get('phone'),
                        'street': kw.get('street'),
                        'city': kw.get('city'),
                        'state_id': int(kw.get('state_id')) if kw.get('state_id') else False,
                        'country_id': int(kw.get('country_id')) if kw.get('country_id') else request.env.ref('base.co').id, # Default Colombia
                        'type': 'delivery',
                        'comment': kw.get('comment'), # Additional notes
                    }
                    
                    # Handle WhatsApp Checkbox (store in comment for now or specific field later)
                    if kw.get('whatsapp_notifications'):
                        partner_values['comment'] = (partner_values.get('comment') or '') + "\n[WhatsApp: SI]"

                    # LOGIC:
                    # A. Public User -> Create new partner
                    # B. Logged User -> 
                    #    - If 'shipping_id' > 0 -> Use that address (update order)
                    #    - If 'shipping_id' == -1 (New) -> Create child partner
                    #    - If 'shipping_id' == 0 (Default/None) -> Check if we are editing main address?

                    if request.env.user._is_public():
                        # Create standard partner
                        partner = Partner.sudo().create(partner_values)
                        Order.partner_id = partner.id
                        Order.partner_invoice_id = partner.id
                        Order.partner_shipping_id = partner.id
                    else:
                        # Logged User
                        user_partner = request.env.user.partner_id
                        
                        # Update main contact info (phone/mobile) if changed? 
                        # Ideally we keep billing separate, but for this simple flow we might want to sync
                        # checks if values differ significantly? For now let's just create shipping address.

                        if shipping_id and shipping_id > 0:
                            # Use existing
                            Order.partner_shipping_id = shipping_id
                            # Maybe update notes?
                            Order.note = kw.get('comment')
                        else:
                            # Create new shipping address for this user
                            partner_values['parent_id'] = user_partner.id
                            partner_values['type'] = 'delivery'
                            # Remove email from shipping address to avoid confusion? or keep it.
                            # Usually shipping address doesn't need email if parent has it.
                            
                            new_shipping = Partner.create(partner_values)
                            Order.partner_shipping_id = new_shipping.id
                            Order.note = kw.get('comment')

                    # Redirect to Confirmation (skip payment if simple flow, or go to payment)
                    # Standard Odoo flow: Address -> Confirm -> Payment
                    # We can redirect to /shop/confirm_order
                    return request.redirect('/shop/confirm_order')

                except Exception as e:
                    _logger.error(f"Error processing checkout: {str(e)}")
                    errors['form'] = str(e)
            
            if errors:
                values = kw

        # 2. Get Data for the template (same as before)
        country = request.env['res.country'].search([('code', '=', 'CO')], limit=1) # Default Colombia
        if not country:
            country = request.env['res.country'].search([], limit=1)

        render_values = {
            'website_sale_order': Order,
            'partner_id': partner_id,
            'mode': mode,
            'checkout': values,
            'can_edit_vat': can_edit_vat,
            'error': errors,
            'countries': request.env['res.country'].search([]),
            'states': country.state_ids, # Filter states by default country
            'shippings': [],
        }

        # 3. If logged in, get shipping addresses
        if not request.env.user._is_public():
            render_values['shippings'] = Partner.search([
                ("id", "child_of", request.env.user.partner_id.commercial_partner_id.ids),
                '|', ("type", "in", ["delivery", "other"]), ("id", "=", request.env.user.partner_id.id)
            ], order='id desc')

        return request.render("theme_guapante.guapante_checkout", render_values)

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

