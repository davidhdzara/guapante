# -*- coding: utf-8 -*-
from odoo import http, models
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from werkzeug.exceptions import Forbidden
import logging

_logger = logging.getLogger(__name__)

class GuapanteHomepage(http.Controller):

    @http.route('/shop/seasonal-products', type='http', auth='public', website=True, sitemap=False)
    def seasonal_products(self, **kwargs):
        """Return rendered HTML of seasonal products — always fresh, no cache.
        HTML is built in Python to avoid dependency on a DB-registered template.
        """
        domain = request.website.sale_product_domain() + [('is_seasonal', '=', True)]
        products = request.env['product.template'].sudo().search(domain, limit=8)

        if not products:
            html = (
                '<div class="col-12">'
                '<div class="alert alert-info text-center">'
                '<p class="mb-0">No hay productos de temporada disponibles en este momento.</p>'
                '</div></div>'
            )
        else:
            parts = []
            for p in products:
                slug = request.env['ir.http']._slug(p)
                img_url = '/web/image/product.template/%d/image_1024' % p.id
                price = request.env['ir.qweb.field.monetary'].value_to_html(
                    p.list_price,
                    {'display_currency': p.currency_id},
                ) if p.list_price else ''
                discount = ''
                if p.compare_list_price and p.compare_list_price > p.list_price:
                    pct = int(((p.compare_list_price - p.list_price) / p.compare_list_price) * 100)
                    discount = '<span class="badge bg-success rounded-2 fw-bold">-%d%%</span>' % pct
                add_url = '/shop/cart/update?product_id=%d&add_qty=1' % p.product_variant_id.id
                parts.append(
                    '<div class="col-6 col-md-4 col-lg-3">'
                    '<div class="product-card h-100 bg-white rounded-4 border overflow-hidden position-relative hover-shadow transition-base">'
                    '<div class="position-absolute top-0 start-0 w-100 p-3 d-flex justify-content-between align-items-start z-1">'
                    '%s'
                    '<button type="button" class="btn btn-light rounded-circle shadow-sm p-0 d-flex align-items-center justify-content-center" style="width:35px;height:35px;" onclick="event.preventDefault();">'
                    '<i class="fa fa-heart-o text-muted"></i></button></div>'
                    '<a href="/shop/product/%s" class="d-block ratio ratio-1x1 bg-light">'
                    '<img src="%s" class="img-fluid object-fit-cover w-100 h-100" alt="%s" loading="lazy"/></a>'
                    '<div class="p-3 d-flex justify-content-between align-items-end">'
                    '<div><a href="/shop/product/%s" class="text-decoration-none">'
                    '<h5 class="fw-bold text-dark mb-1" style="font-size:1rem;">%s</h5></a>'
                    '<p class="text-muted small mb-0">%s</p></div>'
                    '<a href="%s" class="btn btn-light rounded-3 shadow-sm d-flex align-items-center justify-content-center" style="width:40px;height:40px;">'
                    '<i class="fa fa-plus text-dark"></i></a></div>'
                    '</div></div>'
                    % (discount, slug, img_url, p.name, slug, p.name, price, add_url)
                )
            html = ''.join(parts)

        from werkzeug.wrappers import Response as WerkzeugResponse
        response = request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
        ])
        return response


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

        # States for the "add address" modal (filtered to Colombia)
        default_country = request.env.ref('base.co', raise_if_not_found=False)
        if default_country:
            render_values['states'] = request.env['res.country.state'].sudo().search(
                [('country_id', '=', default_country.id)]
            )
            render_values['default_country_id'] = default_country.id
        else:
            render_values['states'] = request.env['res.country.state'].sudo().search([])
            render_values['default_country_id'] = False

        # Build display data from session for the template
        render_values['uom_display'] = self._build_uom_display(Order)

        return request.render("theme_guapante.guapante_checkout", render_values)

    @http.route(['/shop/address/add_from_checkout'], type='http', methods=['POST'], auth="user", website=True, csrf=True)
    def add_address_from_checkout(self, **post):
        """
        Create a delivery address from the checkout modal and set it
        as the shipping address on the current order.
        """
        partner = request.env.user.partner_id
        company_partner = partner.commercial_partner_id
        Order = request.website.sale_get_order()

        if not Order:
            return request.redirect('/shop')

        vals = {
            'parent_id': company_partner.id,
            'type': 'delivery',
            'name': post.get('name', '').strip() or company_partner.name,
            'street': post.get('street', '').strip(),
            'street2': post.get('street2', '').strip() or False,
            'zip': post.get('zip', '').strip() or False,
            'comment': post.get('comment', '').strip() or False,
        }

        # City (from res.city dropdown)
        city_id = post.get('city_id', '').strip()
        try:
            if city_id:
                city_rec = request.env['res.city'].sudo().browse(int(city_id))
                if city_rec.exists():
                    vals['city_id'] = city_rec.id
                    vals['city'] = city_rec.name
                    if city_rec.state_id:
                        vals['state_id'] = city_rec.state_id.id
                    if city_rec.zipcode:
                        vals['zip'] = city_rec.zipcode
                    if city_rec.country_id:
                        vals['country_id'] = city_rec.country_id.id
            else:
                vals['city_id'] = False
                vals['city'] = False
        except (ValueError, TypeError):
            vals['city_id'] = False
            vals['city'] = False

        # Country/state fallback if city didn't set them
        if 'country_id' not in vals:
            country_id = post.get('country_id', '').strip()
            try:
                vals['country_id'] = int(country_id) if country_id else False
            except (ValueError, TypeError):
                vals['country_id'] = False

        if 'state_id' not in vals:
            state_id = post.get('state_id', '').strip()
            try:
                vals['state_id'] = int(state_id) if state_id else False
            except (ValueError, TypeError):
                vals['state_id'] = False

        phone = post.get('phone', '').strip()
        if phone:
            vals['phone'] = phone

        new_address = request.env['res.partner'].sudo().create(vals)
        _logger.info("Checkout: Created delivery address %s for company %s", new_address.id, company_partner.id)

        # Set the new address as shipping address on the current order
        Order.partner_shipping_id = new_address.id

        return request.redirect('/shop/address')

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
            
            # 2. Clear Session (cart + uom display modes)
            if 'guapante_uom_modes' in request.session:
                del request.session['guapante_uom_modes']
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
                 raise Forbidden()
        
        return request.render("theme_guapante.guapante_order_status", {
            'order': Order,
            'warehouse_lat': '4.6486',   # Bodega Central latitude (Bogotá default)
            'warehouse_lng': '-74.1003', # Bodega Central longitude (Bogotá default)
        })

    def _build_uom_display(self, order):
        """Build a dict of display data per line from session uom_modes.
        Returns {line_id: {'qty': '900', 'label': 'g', 'header': 'PESO (G)', 'mode': 'g'}}
        Reads from DB field first, then session, then falls back to product UoM category.
        """
        uom_modes = request.session.get('guapante_uom_modes', {})
        weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        result = {}

        for line in order.order_line:
            # Determine mode: DB first, then session, then fallback
            mode = line.uom_mode
            if not mode:
                mode = uom_modes.get(str(line.id))
            
            if not mode:
                is_weight = weight_categ and line.product_id.uom_id.category_id == weight_categ
                mode = 'kg' if is_weight else 'unit'

            if mode == 'g':
                grams = int(round(line.product_uom_qty * 1000))
                result[line.id] = {'qty': str(grams), 'label': 'g', 'header': 'PESO (G)', 'mode': 'g'}
            elif mode == 'kg':
                val = round(line.product_uom_qty, 2)
                qty_str = str(int(val)) if val == int(val) else str(val)
                result[line.id] = {'qty': qty_str, 'label': 'kg', 'header': 'PESO (KG)', 'mode': 'kg'}
            else:
                # Unit mode: for weight products, convert kg back to units via packaging
                qty_val = line.product_uom_qty
                is_weight = weight_categ and line.product_id.uom_id.category_id == weight_categ
                if is_weight:
                    # Find the sales packaging to get the conversion factor
                    packaging = line.product_id.packaging_ids.filtered(
                        lambda p: p.sales and p.qty > 0
                    )[:1]
                    if packaging:
                        qty_val = round(line.product_uom_qty / packaging.qty)
                    else:
                        qty_val = int(line.product_uom_qty) if line.product_uom_qty == int(line.product_uom_qty) else line.product_uom_qty
                else:
                    qty_val = int(line.product_uom_qty) if line.product_uom_qty == int(line.product_uom_qty) else line.product_uom_qty
                
                result[line.id] = {'qty': str(int(qty_val)), 'label': 'Unidades', 'header': 'CANTIDAD (UNIDADES)', 'mode': 'unit'}

        return result

    @http.route()
    def cart(self, **post):
        """Override cart to inject uom display data from session."""
        response = super().cart(**post)
        order = request.website.sale_get_order()
        if order:
            response.qcontext['uom_display'] = self._build_uom_display(order)
        return response

    @http.route()
    def shop(self, page=0, category=None, search='', is_seasonal=None, **post):
        """Override shop to pass is_seasonal flag."""
        response = super().shop(page=page, category=category, search=search, **post)
        if is_seasonal:
            response.qcontext['is_seasonal'] = True
        return response

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        """Filter search results to seasonal products when is_seasonal param is present."""
        fuzzy_search_term, product_count, search_result = super()._shop_lookup_products(
            attrib_set, options, post, search, website
        )
        if request.params.get('is_seasonal'):
            search_result = search_result.filtered(lambda p: p.is_seasonal)
            product_count = len(search_result)
        return fuzzy_search_term, product_count, search_result

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
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, uom_mode=None, product_packaging_id=None, **kwargs):
        """
        Override to return cart_lines_count and store the user's chosen uom_mode
        in the HTTP session (no DB column needed).
        SEARCH-07 FIX: product_packaging_id is now an explicit parameter.
        """
        if uom_mode:
            _logger.info(f"Cart update: product_id={product_id}, uom_mode={uom_mode}, add_qty={add_qty}")

        # SEARCH-07: Forward product_packaging_id explicitly to super()
        if product_packaging_id:
            kwargs['product_packaging_id'] = int(product_packaging_id)

        # 1. Call super to perform standard logic
        response = super().cart_update_json(
            product_id=product_id, 
            line_id=line_id, 
            add_qty=add_qty, 
            set_qty=set_qty, 
            display=display, 
            **kwargs
        )
        
        # 2. Save the user's chosen uom_mode to the line (Persistent) and session (Legacy/Fallback)
        if uom_mode and uom_mode in ('g', 'kg', 'unit'):
            try:
                line_id_from_response = response.get('line_id')
                if line_id_from_response:
                    line = request.env['sale.order.line'].browse(line_id_from_response)
                    if line.exists():
                        # Use sudo() to ensure public/portal users can update this field
                        line.sudo().write({'uom_mode': uom_mode})
                        _logger.info(f"DB: saved uom_mode='{uom_mode}' for line {line_id_from_response}")
            except Exception as e:
                _logger.error(f"Error saving uom_mode to DB: {e}")
            
            # Keep session update for immediate consistency slightly, but DB is source of truth now
            # This can be removed later if fully robust
            line_id_from_response = response.get('line_id')
            if line_id_from_response:
                uom_modes = request.session.get('guapante_uom_modes', {})
                uom_modes[str(line_id_from_response)] = uom_mode
                request.session['guapante_uom_modes'] = uom_modes

        # 3. Add line count + cart_quantity to response (SEARCH-03 FIX)
        order = request.website.sale_get_order()
        if order:
            response['cart_lines_count'] = len(order.order_line)
            response['cart_quantity'] = order.cart_quantity
        else:
            response['cart_lines_count'] = 0
            response['cart_quantity'] = 0
            
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

    # ── Search API ──────────────────────────────────────────────

    @http.route('/shop/search/products', type='json', auth='public', website=True, csrf=False)
    def search_products(self, query='', limit=12, **kwargs):
        """
        Search products using Odoo's native fuzzy search engine.
        Returns enriched product data for the mobile search overlay.
        """
        if not query or len(query.strip()) < 2:
            return {'products': [], 'count': 0}

        query = query.strip()
        website = request.env['website'].get_current_website()
        options = self._get_search_options()

        # Use Odoo's native fuzzy search
        fuzzy_search_term, product_count, search_result = self._shop_lookup_products(
            set(), options, {}, query, website
        )

        # Limit results
        templates = search_result[:limit]

        # Reference for weight UoM detection
        weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)

        products = []
        for tmpl in templates:
            variant = tmpl.product_variant_id
            if not variant:
                continue

            # Detect if this is a weight-based product
            is_weight = bool(
                weight_categ
                and tmpl.uom_id.category_id.id == weight_categ.id
            )

            # Get sales-enabled packagings
            packagings_data = []
            sales_packagings = variant.sudo().packaging_ids.filtered(lambda p: p.sales)
            has_packaging = bool(sales_packagings)
            for pkg in sales_packagings:
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'qty': pkg.qty,
                })

            products.append({
                'id': variant.id,
                'product_tmpl_id': tmpl.id,
                'name': tmpl.name,
                'image_url': '/web/image/product.product/%d/image_256' % variant.id,
                'uom_name': tmpl.uom_id.name,
                'is_weight_uom': is_weight,
                'has_packaging': has_packaging,
                'packagings': packagings_data,
            })

        return {
            'products': products,
            'count': product_count,
            'search_term': fuzzy_search_term or query,
        }

    @http.route('/shop/search/categories', type='json', auth='public', website=True, csrf=False)
    def search_categories(self, **kwargs):
        """Return root-level published categories for the search overlay empty state."""
        website = request.env['website'].get_current_website()
        Category = request.env['product.public.category']
        categs = Category.search(
            [('parent_id', '=', False)] + website.website_domain(),
            order='sequence, name',
        )
        return [{
            'id': c.id,
            'name': c.name,
            'url': '/shop/category/%s' % request.env['ir.http']._slug(c),
            'has_image': bool(c.image_128),
            'image_url': '/web/image/product.public.category/%d/image_128' % c.id if c.image_128 else '',
        } for c in categs]

