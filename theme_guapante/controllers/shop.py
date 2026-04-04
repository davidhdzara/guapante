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

        # --- GUAPANTE MERGE ORDER WIDGET LOGIC ---
        # Look for existing eligible orders that are confirmed but not shipped, so the user can append
        if not request.env.user._is_public():
            commercial_p = request.env.user.partner_id.commercial_partner_id
            domain = [
                ('message_partner_ids', 'child_of', [commercial_p.id]),
                ('state', '=', 'sale'),
                ('guapante_delivery_status', 'in', ['received', 'preparing']),
                ('id', '!=', Order.id) # Obviously exclude current cart
            ]
            open_orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')
            render_values['open_orders'] = open_orders

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
            'ref': post.get('order_zone') or False,
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
            return request.redirect('/shop/order/status/%s?access_token=%s' % (order.id, order.access_token))
            
        except Exception as e:
            _logger.error("Error confirming order: %s", e)
            return request.redirect('/shop/checkout?error=confirm_failed')

    @http.route(['/shop/checkout/append_to_order'], type='http', auth="user", website=True, sitemap=False, methods=['POST'], csrf=True)
    def append_to_order(self, target_order_id=None, **post):
        """
        Merge current cart lines into an existing pending order (SOXXXX) and completely cancel current cart.
        """
        target_order_id = int(target_order_id) if target_order_id else 0
        current_cart = request.website.sale_get_order()
        
        if not current_cart or not current_cart.order_line or not target_order_id:
            return request.redirect('/shop')
            
        target_order = request.env['sale.order'].sudo().browse(target_order_id)
        if not target_order.exists() or target_order.state != 'sale':
            return request.redirect('/shop/address?error=invalid_target')
            
        # Security verify ownership
        commercial_p = request.env.user.partner_id.commercial_partner_id
        if target_order.partner_id.commercial_partner_id != commercial_p:
            raise Forbidden("No tienes permiso para fusionar en esta orden.")
            
        try:
            items_added = len(current_cart.order_line)
            # 1. Loop and duplicate lines into the target order
            for line in current_cart.order_line:
                new_line = line.copy({
                    'order_id': target_order.id,
                })
                # Trigger stock rule for each new line since the order is already confirmed
                new_line.sudo()._action_launch_stock_rule()
                
            # 2. Log in chatter with details of what was added
            added_lines_details = ", ".join([f"{int(line.product_uom_qty)}x {line.product_id.name}" for line in current_cart.order_line])
            target_order.message_post(
                body=f"El cliente anexó nuevos productos a esta orden desde la tienda online: {added_lines_details}.",
                subtype_xmlid="mail.mt_note"
            )
            
            # Recalculate totals officially
            target_order._compute_amounts()
            
            # 3. Clean up: destroy the ghost cart and reset session
            current_cart.action_cancel()
            if 'guapante_uom_modes' in request.session:
                del request.session['guapante_uom_modes']
            request.website.sale_reset()
            
            # 4. Success redirect
            return request.redirect('/shop/order/status/%s?access_token=%s&merged=1' % (target_order.id, target_order.access_token))
            
        except Exception as e:
            _logger.error("Guapante Append: Error al fusionar la orden: %s", e)
            return request.redirect('/shop/address?error=append_failed')

    @http.route(['/shop/order/status/<int:order_id>'], type='http', auth="public", website=True, sitemap=False)
    def order_status(self, order_id, **post):
        """
        Render the custom order status page.
        CRIT-01 FIX: Public users must supply a valid access_token.
        """
        Order = request.env['sale.order'].sudo().browse(order_id)
        if not Order.exists():
            return request.redirect('/shop')

        if request.env.user._is_public():
            # Public users MUST provide valid access_token (prevents IDOR)
            token = post.get('access_token', '')
            if not token or token != Order.access_token:
                raise Forbidden()
        else:
            # Logged-in users: verify ownership via commercial partner
            if Order.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
                raise Forbidden()

        return request.render("theme_guapante.guapante_order_status", {
            'order': Order,
            'warehouse_lat': '4.6486',
            'warehouse_lng': '-74.1003',
        })

    def _build_uom_display(self, order):
        """Build a dict of display data per line from session uom_modes.
        Returns {line_id: {'qty': '900', 'label': 'g', 'header': 'PESO (G)', 'mode': 'g'}}
        Reads from DB field first, then session, then falls back to product UoM category.
        """
        uom_modes = request.session.get('guapante_uom_modes', {})
        weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False).sudo()
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
                    # FIX: Use the line's actual packaging (the one the user chose), not the first one.
                    packaging = line.product_packaging_id
                    if not packaging:
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

    # ── VIP B2B: Centralized product filter ──────────────────────

    def _get_b2b_product_filter(self):
        """Compute product IDs to exclude from shop/search for the current user.

        Returns:
            tuple: (exclude_ids, hidden_ids)
                - exclude_ids: VIP products this user is NOT authorized to see.
                - hidden_ids: General products replaced by VIP products this user CAN see.
        """
        all_vip = request.env['product.template'].sudo().search([
            ('is_b2b_exclusive', '=', True),
        ])

        _logger.info("VIP-B2B: Found %s VIP products: %s", len(all_vip), all_vip.mapped('name'))

        if not all_vip:
            return ([], [])

        user = request.env.user
        if user._is_public():
            # Public users see NO VIP products
            _logger.info("VIP-B2B: Public user → excluding ALL VIP IDs: %s", all_vip.ids)
            return (all_vip.ids, [])

        partner_id = user.partner_id.commercial_partner_id.id

        my_vip = all_vip.filtered(
            lambda p: partner_id in p.b2b_exclusive_customer_ids.ids
        )
        not_my_vip = all_vip - my_vip

        # General products that my VIP products replace
        hidden_ids = my_vip.mapped('b2b_replaces_product_ids').ids

        _logger.info("VIP-B2B: Partner %s → my_vip=%s, not_my_vip=%s, hidden=%s",
                      partner_id, my_vip.ids, not_my_vip.ids, hidden_ids)

        return (not_my_vip.ids, hidden_ids)

    @http.route()
    def shop(self, page=0, category=None, search='', is_seasonal=None, **post):
        """Override shop to pass is_seasonal flag."""
        response = super().shop(page=page, category=category, search=search, **post)
        if is_seasonal:
            response.qcontext['is_seasonal'] = True
        return response

    def _get_search_domain(self, search, category, attrib_values, search_in_description=True):
        """Inject VIP B2B + is_seasonal filters into the shop SQL domain."""
        domain = super()._get_search_domain(search, category, attrib_values, search_in_description)
        if request.params.get('is_seasonal'):
            domain.append(('is_seasonal', '=', True))

        # ── VIP B2B: SQL-level exclusion for performance ──
        exclude_ids, hidden_ids = self._get_b2b_product_filter()
        all_invisible = list(set(exclude_ids + hidden_ids))
        if all_invisible:
            domain.append(('id', 'not in', all_invisible))

        _logger.info("VIP-B2B: _get_search_domain called → excluding %s product IDs, domain=%s", len(all_invisible), all_invisible)

        return domain

    @http.route()
    def product(self, product, category='', search='', **kwargs):
        """ Override to inject categories sidebar + VIP B2B access control. """

        # ── VIP B2B: Block unauthorized access to exclusive products ──
        tmpl = product if hasattr(product, 'is_b2b_exclusive') else product.product_tmpl_id
        if tmpl.sudo().is_b2b_exclusive:
            user = request.env.user
            if user._is_public():
                return request.redirect('/shop')
            partner_id = user.partner_id.commercial_partner_id.id
            if partner_id not in tmpl.sudo().b2b_exclusive_customer_ids.ids:
                return request.redirect('/shop')

        # 1. Call super to get standard qcontext
        response = super().product(product, category=category, search=search, **kwargs)
        
        # 2. Extract qcontext from response
        qcontext = response.qcontext

        # 3. Inject Categories for Sidebar
        Category = request.env['product.public.category']
        website = request.website
        categories = Category.search([('parent_id', '=', False)] + website.website_domain())
        qcontext['categories'] = categories
        
        # 4. Ensure 'category' is a recordset for the sidebar active state
        current_category = qcontext.get('category')
        if not current_category:
            if product.public_categ_ids:
                qcontext['category'] = product.public_categ_ids[0]
        elif not isinstance(current_category, models.Model):
              qcontext['category'] = Category.browse(int(current_category))

        return response

    @http.route(['/shop/cart/update'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def update_cart_native(self, line_id=None, quantity=None, product_id=None, **kwargs):
        debug_order = request.website.sale_get_order()
        if debug_order:
            debug_msg = f"\n[NATIVE UPDATE PAYLOAD]: line_id={line_id}, qty={quantity}, product_id={product_id}, kwargs={kwargs}\n"
            current_note = debug_order.sudo().note or ''
            debug_order.sudo().write({'note': current_note + debug_msg})
        return super().update_cart(line_id=line_id, quantity=quantity, product_id=product_id, **kwargs)

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, uom_mode=None, product_packaging_id=None, **kwargs):
        """
        Override to return cart_lines_count and store the user's chosen uom_mode
        in the HTTP session (no DB column needed).
        SEARCH-07 FIX: product_packaging_id is now an explicit parameter.
        """
        if uom_mode:
            _logger.info("Cart update: product_id=%s, uom_mode=%s, add_qty=%s, set_qty=%s", product_id, uom_mode, add_qty, set_qty)

        # SEARCH-07: Forward product_packaging_id explicitly to super()
        if product_packaging_id:
            kwargs['product_packaging_id'] = int(product_packaging_id)

        # ── FIX: Convertir unidades del usuario a kg para productos de peso ──
        # Cuando uom_mode='unit' y el producto tiene UdM base de peso (kg),
        # las "unidades" del usuario se definen por el embalaje (packaging.qty).
        # El JS envía set_qty/add_qty en unidades del usuario, pero super()
        # espera el valor en la UdM base (kg). Sin esta conversión, enviar
        # set_qty=8 (unidades) se guarda como 8 kg en vez de 0.8 kg.
        if uom_mode == 'unit':
            product = request.env['product.product'].sudo().browse(int(product_id))
            weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False).sudo()
            if weight_categ and product.exists() and product.uom_id.category_id == weight_categ:
                packaging = False
                if product_packaging_id:
                    packaging = request.env['product.packaging'].sudo().browse(int(product_packaging_id))
                if not packaging or not packaging.exists():
                    # Fallback to the first available if not provided or invalid
                    packaging = product.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
                
                if packaging:
                    factor = packaging.qty  # ej: 0.1 kg/unidad
                    if set_qty is not None:
                        _logger.info("Unit→kg conversion: %s units × %s = %s kg", set_qty, factor, set_qty * factor)
                        set_qty = set_qty * factor
                    if add_qty is not None:
                        _logger.info("Unit→kg conversion (add): %s units × %s = %s kg", add_qty, factor, add_qty * factor)
                        add_qty = add_qty * factor

        # 1. Spy on Javascript payload for debugging
        debug_order = request.website.sale_get_order()
        if debug_order:
            debug_msg = f"\n[JS PAYLOAD IN CONTROLLER]: args=(product_id={product_id}, uom_mode={uom_mode}, packaging={product_packaging_id}) kwargs={kwargs}\n"
            current_note = debug_order.sudo().note or ''
            debug_order.sudo().write({'note': current_note + debug_msg})

        # 1. Call super to perform standard logic
        response = super().cart_update_json(
            product_id=product_id, 
            line_id=line_id, 
            add_qty=add_qty, 
            set_qty=set_qty, 
            display=display, 
            **kwargs
        )
        
        # 2. Persist uom_mode AND product_packaging_id on the line in the DB.
        # Odoo's native flow does not always save the packaging_id selected by the user.
        # We write it explicitly so _cart_find_product_line can later match correctly.
        line_id_from_response = response.get('line_id') if response else None
        if line_id_from_response:
            try:
                line = request.env['sale.order.line'].sudo().browse(line_id_from_response)
                if line.exists():
                    update_vals = {}
                    if uom_mode and uom_mode in ('g', 'kg', 'unit'):
                        update_vals['uom_mode'] = uom_mode
                    if product_packaging_id and int(product_packaging_id) > 0:
                        pkg = request.env['product.packaging'].sudo().browse(int(product_packaging_id))
                        if pkg.exists():
                            update_vals['product_packaging_id'] = pkg.id
                    if update_vals:
                        line.sudo().write(update_vals)
                        _logger.info("DB: persisted %s for line %s", update_vals, line_id_from_response)
            except Exception as e:
                _logger.error("Error persisting uom_mode/packaging on line: %s", e)

            if uom_mode:
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

    @http.route(['/shop/product/packagings/<int:product_id>'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def get_product_packagings(self, product_id, **kwargs):
        """
        Get packagings for a specific product variant.
        Returns list of packagings with id, name, qty.
        VIP exclusivity now lives at the product level, not packaging level.
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
        
        _logger.info("Packagings for product %s: %s", product_id, result)
        
        return result

    # ── Search API ──────────────────────────────────────────────

    @http.route('/shop/search/products', type='json', auth='public', website=True, csrf=False)
    def search_products(self, query='', limit=12, **kwargs):
        """
        Search products using Odoo's native fuzzy search engine.
        Returns enriched product data for the mobile search overlay.
        VIP B2B filtering is applied at the product level.
        """
        if not query or len(query.strip()) < 2:
            return {'products': [], 'count': 0}

        query = query.strip()

        try:
            website = request.env['website'].get_current_website()
            options = self._get_search_options()

            # Use Odoo's native fuzzy search
            fuzzy_search_term, product_count, search_result = self._shop_lookup_products(
                set(), options, {}, query, website
            )

            _logger.info("Search '%s': found %s templates", query, product_count)

            # ── VIP B2B: Filter search results at product level ──
            exclude_ids, hidden_ids = self._get_b2b_product_filter()
            all_invisible = set(exclude_ids + hidden_ids)
            if all_invisible:
                search_result = search_result.filtered(lambda t: t.id not in all_invisible)
                product_count = len(search_result)

            # Limit results
            templates = search_result[:limit]

            # Reference for weight UoM detection (sudo for public access)
            weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False).sudo()
            weight_categ_id = weight_categ.id if weight_categ else False

            products = []
            for tmpl in templates:
                variant = tmpl.product_variant_id
                if not variant:
                    continue

                # Detect if this is a weight-based product (sudo for public access)
                uom = tmpl.sudo().uom_id
                is_weight = bool(
                    weight_categ_id
                    and uom.category_id.id == weight_categ_id
                )

                # Get sales-enabled packagings (no packaging-level VIP filter)
                packagings_data = []
                sales_packagings = variant.sudo().packaging_ids.filtered(lambda p: p.sales)
                has_packaging = bool(sales_packagings)
                for pkg in sales_packagings:
                    packagings_data.append({
                        'id': pkg.id,
                        'name': pkg.name,
                        'qty': pkg.qty,
                    })

                # Inject variants if product has multiple choices (e.g. Madurez)
                variants_list = []
                if len(tmpl.product_variant_ids) > 1:
                    for v in tmpl.product_variant_ids:
                        var_name = v.display_name.replace(tmpl.name, '').strip(' ()')
                        if not var_name:
                            var_name = 'Estándar'
                        variants_list.append({
                            'id': v.id,
                            'name': var_name
                        })

                products.append({
                    'id': variant.id,
                    'product_tmpl_id': tmpl.id,
                    'name': tmpl.name,
                    'image_url': '/web/image/product.product/%d/image_256' % variant.id,
                    'uom_name': uom.name,
                    'is_weight_uom': is_weight,
                    'has_packaging': has_packaging,
                    'packagings': packagings_data,
                    'variants': variants_list,
                })

            return {
                'products': products,
                'count': product_count,
                'search_term': fuzzy_search_term or query,
            }

        except Exception as e:
            _logger.error("Search products error for query '%s': %s", query, e, exc_info=True)
            return {'products': [], 'count': 0, 'error': str(e)}

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

    @http.route(['/shop/debug_product/<int:tmpl_id>'], type='http', auth="public", website=True, sitemap=False)
    def debug_product(self, tmpl_id, **kwargs):
        """
        Diagnostic endpoint: shows how attributes are configured for a product template.
        Reveals if attributes create real variants (product.product) or are no_variant.
        Usage: /shop/debug_product/123
        """
        tmpl = request.env['product.template'].sudo().browse(tmpl_id)
        if not tmpl.exists():
            return request.make_response(f"Product template {tmpl_id} not found.", headers=[('Content-Type', 'text/plain')])

        output = []
        output.append(f"═══════════════════════════════════════════════════")
        output.append(f"  DIAGNÓSTICO DE PRODUCTO: {tmpl.name}")
        output.append(f"  Template ID: {tmpl.id}")
        output.append(f"  UoM: {tmpl.uom_id.name} (Cat: {tmpl.uom_id.category_id.name})")
        output.append(f"═══════════════════════════════════════════════════\n")

        # Attribute Lines
        output.append(f"─── ATRIBUTOS CONFIGURADOS ({len(tmpl.attribute_line_ids)}) ───")
        for line in tmpl.attribute_line_ids:
            attr = line.attribute_id
            output.append(f"\n  📋 Atributo: {attr.name}")
            output.append(f"     create_variant: {attr.create_variant}")
            output.append(f"     display_type: {attr.display_type}")
            output.append(f"     Valores configurados:")
            for val in line.value_ids:
                output.append(f"       - {val.name} (ID: {val.id})")
            # Product Template Attribute Values (ptav)
            ptavs = line.product_template_value_ids
            output.append(f"     PTAVs (product.template.attribute.value):")
            for ptav in ptavs:
                output.append(f"       - ptav_id={ptav.id} → valor='{ptav.name}' is_active={ptav.ptav_active} price_extra={ptav.price_extra}")

        # Product Variants
        variants = tmpl.product_variant_ids
        output.append(f"\n─── VARIANTES product.product ({len(variants)}) ───")
        for v in variants:
            attrs_desc = []
            for ptav in v.product_template_attribute_value_ids:
                attrs_desc.append(f"{ptav.attribute_id.name}={ptav.name}(ptav:{ptav.id})")
            output.append(f"  🔹 variant_id={v.id}: {v.display_name}")
            output.append(f"     Combinación: {', '.join(attrs_desc) if attrs_desc else 'SIN ATRIBUTOS'}")

        # Conclusión
        output.append(f"\n─── CONCLUSIÓN ───")
        no_var_attrs = [l for l in tmpl.attribute_line_ids if l.attribute_id.create_variant == 'no_variant']
        var_attrs = [l for l in tmpl.attribute_line_ids if l.attribute_id.create_variant != 'no_variant']
        if no_var_attrs:
            output.append(f"  ⚠️  ATRIBUTOS NO_VARIANT (NO crean product.product, se envían via no_variant_attribute_values):")
            for l in no_var_attrs:
                output.append(f"       → {l.attribute_id.name}")
            output.append(f"  👉 Si estos llegan vacíos al carrito, es porque el JS NO los está recolectando.")
        if var_attrs:
            output.append(f"  ✅ ATRIBUTOS QUE CREAN VARIANTES (cada combinación = product.product distinto):")
            for l in var_attrs:
                output.append(f"       → {l.attribute_id.name} (create_variant={l.attribute_id.create_variant})")
            output.append(f"  👉 Si estos no cambian, es porque el product_id que se envía al carrito es siempre el default.")

        return request.make_response("\n".join(output), headers=[('Content-Type', 'text/plain; charset=utf-8')])

    @http.route(['/shop/debug_cart'], type='http', auth="public", website=True, sitemap=False)
    def debug_cart(self, **kwargs):
        """
        Diagnostic endpoint for Guapante developers to inspect cart line attributes and duplication causes.
        Returns a plain text or JSON detailing the exact lines in the current user's cart.
        """
        order = request.website.sale_get_order()
        if not order:
            return request.make_response("No tienes ningún carrito activo en esta sesión.", headers=[('Content-Type', 'text/plain')])

        output = [f"🛒 CARRITO: {order.name} (ID: {order.id})"]
        output.append(f"   Cliente: {order.partner_id.name}\n")
        
        for line in order.order_line:
            if line.display_type:
                continue
            product = line.product_id
            tmpl = product.product_tmpl_id
            output.append(f"═══ LÍNEA {line.id} ═══")
            output.append(f"Producto      : {product.display_name}")
            output.append(f"product_id    : {product.id}")
            output.append(f"template_id   : {tmpl.id}  → Diagnóstico: /shop/debug_product/{tmpl.id}")
            output.append(f"Cantidad      : {line.product_uom_qty} {line.product_uom.name}")
            output.append(f"Modo UoM      : {getattr(line, 'uom_mode', 'N/A')}")
            pkg = getattr(line, 'product_packaging_id', False)
            output.append(f"Empaque       : {pkg.id if pkg else 'Ninguno'} ({pkg.name if pkg else ''})")
            
            # Atributos de la variante (los que CREAN variantes)
            variant_ptavs = product.product_template_attribute_value_ids
            if variant_ptavs:
                output.append(f"Variante(PTAV): {[(ptav.attribute_id.name, ptav.name, ptav.id) for ptav in variant_ptavs]}")
            
            # Atributos nativos no_variant en la línea de venta
            if hasattr(line, 'product_no_variant_attribute_value_ids'):
                no_vars = line.product_no_variant_attribute_value_ids
                output.append(f"NoVariant     : IDs: {no_vars.ids} → {[(a.attribute_id.name, a.name) for a in no_vars]}")
                if not no_vars:
                    output.append(f"  ⚠️  VACÍO - Los atributos no_variant NO llegaron al carrito")
            
            if hasattr(line, 'product_custom_attribute_value_ids'):
                cus_vars = line.product_custom_attribute_value_ids
                output.append(f"Custom        : IDs: {cus_vars.ids}")
                
            output.append(f"Descripción   : {line.name[:80]}")
            output.append("")

        return request.make_response("\n".join(output), headers=[('Content-Type', 'text/plain; charset=utf-8')])

