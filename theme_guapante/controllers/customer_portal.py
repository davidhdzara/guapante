# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from collections import OrderedDict
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GuapanteCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'active_shipments_count' in counters:
            domain = [
                ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
                ('state', 'in', ['sale', 'done']),
                ('guapante_delivery_status', 'in', ['preparing', 'shipping'])
            ]
            values['active_shipments_count'] = request.env['sale.order'].sudo().search_count(domain)

        return values

    @http.route(['/my/orders', '/my/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_orders(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']

        # Base domain: all orders for this partner (sale, done, cancel)
        base_domain = [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sale', 'done', 'cancel'])
        ]

        # --- Total orders count (ALL, unfiltered — for KPI card) ---
        total_orders_count = SaleOrder.search_count(base_domain)

        # --- Active shipments count (KPI card) ---
        # Only sale/done orders that are preparing or shipping (never cancelled)
        active_domain = [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sale', 'done']),
            ('guapante_delivery_status', 'in', ['preparing', 'shipping'])
        ]
        active_shipments_count = SaleOrder.sudo().search_count(active_domain)

        # Build filtered domain from base
        domain = list(base_domain)

        # 1. Sortings
        searchbar_sortings = {
            'date': {'label': 'Más reciente', 'order': 'date_order desc'},
            'name': {'label': 'Nombre', 'order': 'name desc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # 2. Status Filters (Spanish — ordered by lifecycle)
        searchbar_filters = {
            'all':       {'label': 'Todos', 'domain': []},
            'received':  {'label': 'Recibido', 'domain': [('guapante_delivery_status', '=', 'received')]},
            'preparing': {'label': 'Preparando', 'domain': [('guapante_delivery_status', '=', 'preparing')]},
            'shipping':  {'label': 'En Camino', 'domain': [('guapante_delivery_status', '=', 'shipping')]},
            'delivered': {'label': 'Entregado', 'domain': [('guapante_delivery_status', '=', 'delivered')]},
            'cancelled': {'label': 'Cancelado', 'domain': [('state', '=', 'cancel')]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # 3. Date Range Filters
        date_range_filters = {
            'all':        {'label': 'Todo el tiempo'},
            'last_7':     {'label': 'Últimos 7 días',   'days': 7},
            'last_15':    {'label': 'Últimos 15 días',  'days': 15},
            'last_30':    {'label': 'Últimos 30 días',  'days': 30},
            'last_90':    {'label': 'Últimos 3 meses',  'days': 90},
            'last_180':   {'label': 'Últimos 6 meses',  'days': 180},
            'last_365':   {'label': 'Último año',       'days': 365},
        }
        date_filter = kw.get('date_filter', 'all')
        if date_filter not in date_range_filters:
            date_filter = 'all'

        if date_filter != 'all':
            days = date_range_filters[date_filter]['days']
            date_limit = datetime.now() - timedelta(days=days)
            domain.append(('date_order', '>=', date_limit))

        # 4. Pager
        order_count = SaleOrder.search_count(domain)
        pager = portal_pager(
            url="/my/orders",
            url_args={
                'sortby': sortby,
                'filterby': filterby,
                'date_filter': date_filter,
            },
            total=order_count,
            page=page,
            step=self._items_per_page
        )

        # 5. Search
        orders = SaleOrder.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_orders_history'] = orders.ids[:100]

        # 6. Pager display numbers (avoid raw dict in template)
        page_start_num = pager['offset'] + 1 if order_count else 0
        page_end_num = min(pager['offset'] + self._items_per_page, order_count)

        values.update({
            'orders': orders,
            'page_name': 'order',
            'pager': pager,
            'default_url': '/my/orders',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            'date_filter': date_filter,
            'date_range_filters': date_range_filters,
            'total_orders_count': total_orders_count,
            'active_shipments_count': active_shipments_count,
            'page_start_num': page_start_num,
            'page_end_num': page_end_num,
            'order_count': order_count,
        })
        return request.render("sale.portal_my_orders", values)

    @http.route(['/my/orders/reorder/<int:order_id>'], type='http', auth="user", website=True)
    def portal_reorder(self, order_id, **kw):
        """Re-add products from a past order to the current cart.
        Does NOT check for stock availability.
        """
        order = request.env['sale.order'].browse(order_id)
        if not order.exists() or order.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
            return request.redirect('/my/orders')

        current_order = request.website.sale_get_order(force_create=True)

        for line in order.order_line:
            if not line.product_id.active:
                continue
            current_order._cart_update(
                product_id=line.product_id.id,
                add_qty=line.product_uom_qty,
            )

        return request.redirect('/shop/cart')

    @http.route(['/my/orders/cancel/<int:order_id>'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_cancel_order(self, order_id, **kw):
        """Cancel a sale order from the portal.

        Only allowed when:
        - The order belongs to the authenticated user
        - The order is in 'sale' state (confirmed)
        - The delivery status is 'received' (no pickings processed yet)

        This cancels:
        1. Associated stock.picking records (inventory)
        2. The sale.order itself via _action_cancel()
        """
        order = request.env['sale.order'].sudo().browse(order_id)

        # Security: verify ownership
        if not order.exists():
            return request.redirect('/my/orders')

        partner = request.env.user.partner_id
        if order.partner_id.id != partner.id and order.partner_id.id != partner.commercial_partner_id.id:
            _logger.warning("Guapante Cancel: User %s tried to cancel order %s that doesn't belong to them", partner.id, order_id)
            return request.redirect('/my/orders')

        # Only allow cancellation if order is confirmed and in 'received' status
        if order.state != 'sale' or order.guapante_delivery_status != 'received':
            _logger.warning("Guapante Cancel: Order %s cannot be cancelled (state=%s, delivery=%s)", order.name, order.state, order.guapante_delivery_status)
            return request.redirect('/my/orders')

        try:
            # 1. Cancel associated stock pickings (inventory)
            pickings_to_cancel = order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            if pickings_to_cancel:
                pickings_to_cancel.action_cancel()
                _logger.info("Guapante Cancel: Cancelled %d pickings for order %s", len(pickings_to_cancel), order.name)

            # 2. Cancel the sale order (also handles procurement cleanup)
            order._action_cancel()
            _logger.info("Guapante Cancel: Order %s cancelled successfully by user %s", order.name, partner.name)

        except Exception as e:
            _logger.error("Guapante Cancel: Error cancelling order %s: %s", order.name, str(e))
            return request.redirect('/my/orders?error=cancel_failed')

        return request.redirect('/my/orders')

    # ------------------------------------------------------------------
    # MI PERFIL
    # ------------------------------------------------------------------

    def _get_optional_fields(self):
        """Add identification type to the optional fields so /my/account also
        accepts it without raising 'Unknown field' errors."""
        return super()._get_optional_fields() + ["l10n_latam_identification_type_id"]

    @http.route(['/my/profile'], type='http', auth='user', website=True, methods=['GET'])
    def portal_my_profile(self, **kw):
        """Render the Mi Perfil page with the user's partner data."""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        # Identification types for Colombia
        country_co = request.env.ref('base.co', raise_if_not_found=False)
        id_type_domain = [('country_id', '=', country_co.id)] if country_co else []
        identification_types = request.env['l10n_latam.identification.type'].sudo().search(id_type_domain)

        values.update({
            'partner': partner,
            'identification_types': identification_types,
            'page_name': 'home',  # Highlights "Mi Perfil" in sidebar
            'error': {},
            'error_message': [],
            'success': kw.get('success'),
        })

        return request.render('theme_guapante.guapante_my_profile', values)

    @http.route(['/my/profile'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_my_profile_save(self, **post):
        """Validate and save profile changes to res.partner (bidirectional)."""
        partner = request.env.user.partner_id
        error = {}
        error_message = []

        # --- Validation ---
        if not post.get('name', '').strip():
            error['name'] = 'missing'
            error_message.append(_('El nombre es obligatorio.'))

        if not post.get('email', '').strip():
            error['email'] = 'missing'
            error_message.append(_('El correo electrónico es obligatorio.'))

        if not post.get('phone', '').strip():
            error['phone'] = 'missing'
            error_message.append(_('El teléfono es obligatorio.'))

        if error:
            # Re-render with errors
            values = self._prepare_portal_layout_values()
            country_co = request.env.ref('base.co', raise_if_not_found=False)
            id_type_domain = [('country_id', '=', country_co.id)] if country_co else []
            identification_types = request.env['l10n_latam.identification.type'].sudo().search(id_type_domain)

            values.update({
                'partner': partner,
                'identification_types': identification_types,
                'page_name': 'home',
                'error': error,
                'error_message': error_message,
                # Preserve submitted values so the form doesn't reset
                'post': post,
            })
            return request.render('theme_guapante.guapante_my_profile', values)

        # --- Build write values ---
        write_vals = {
            'name': post['name'].strip(),
            'email': post['email'].strip(),
            'phone': post['phone'].strip(),
        }

        # VAT / identification number
        vat = post.get('vat', '').strip()
        write_vals['vat'] = vat if vat else False

        # Identification type (Many2one)
        id_type = post.get('l10n_latam_identification_type_id')
        if id_type:
            try:
                write_vals['l10n_latam_identification_type_id'] = int(id_type)
            except (ValueError, TypeError):
                pass

        # --- Write to res.partner (bidirectional with Contacts module) ---
        partner.sudo().write(write_vals)
        _logger.info("Guapante Profile: Updated partner %s (%s)", partner.id, partner.name)

        return request.redirect('/my/profile?success=1')

    # ------------------------------------------------------------------
    # MIS DIRECCIONES
    # ------------------------------------------------------------------

    @http.route(['/my/addresses/get_cities'], type='json', auth='user', website=True)
    def portal_get_cities(self, state_id=None, **kw):
        """Return cities for a given state (department) as JSON."""
        domain = []
        default_country = request.env.ref('base.co', raise_if_not_found=False)
        if state_id:
            domain.append(('state_id', '=', int(state_id)))
        elif default_country:
            domain.append(('country_id', '=', default_country.id))
        cities = request.env['res.city'].sudo().search(domain, order='name')
        return [{'id': c.id, 'name': c.name, 'zipcode': c.zipcode or ''} for c in cities]

    @http.route(['/my/addresses'], type='http', auth='user', website=True, methods=['GET'])
    def portal_my_addresses(self, **kw):
        """Render the Addresses page with all child contacts for this partner."""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        # Use the commercial partner (company) — addresses belong to the company
        company_partner = partner.commercial_partner_id

        # Get only DELIVERY addresses of the COMPANY (portal only manages delivery)
        addresses = company_partner.child_ids.filtered(lambda c: c.active and c.type == 'delivery')

        # Countries & states for the add/edit modal
        countries = request.env['res.country'].sudo().search([])
        # Default country to Colombia — pre-filter states
        default_country = request.env.ref('base.co', raise_if_not_found=False)
        if default_country:
            states = request.env['res.country.state'].sudo().search(
                [('country_id', '=', default_country.id)]
            )
        else:
            states = request.env['res.country.state'].sudo().search([])

        values.update({
            'partner': partner,
            'company_partner': company_partner,
            'addresses': addresses,
            'countries': countries,
            'states': states,
            'default_country_id': default_country.id if default_country else False,
            'page_name': 'details',  # Highlights "Direcciones" in sidebar
            'success': kw.get('success'),
            'error_message': kw.get('error'),
        })

        return request.render('theme_guapante.guapante_my_addresses', values)

    @http.route(['/my/addresses/add'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_address_add(self, **post):
        """Create a new child partner (address) under the COMPANY partner."""
        partner = request.env.user.partner_id
        company_partner = partner.commercial_partner_id

        # Portal only creates delivery addresses
        vals = {
            'parent_id': company_partner.id,  # Child of the COMPANY, not the user
            'type': 'delivery',
            'name': post.get('name', '').strip() or company_partner.name,
            'street': post.get('street', '').strip(),
            'street2': post.get('street2', '').strip() or False,
            'zip': post.get('zip', '').strip() or False,
            'comment': post.get('comment', '').strip() or False,
            'ref': post.get('order_zone') or False,
        }

        # City (from res.city dropdown — auto-fills city text, state, zip)
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
                vals['city'] = post.get('city_fallback', '').strip() or False
        except (ValueError, TypeError):
            vals['city_id'] = False
            vals['city'] = post.get('city_fallback', '').strip() or False

        # Country — only set if city didn't already set it
        if 'country_id' not in vals:
            country_id = post.get('country_id', '').strip()
            try:
                vals['country_id'] = int(country_id) if country_id else False
            except (ValueError, TypeError):
                vals['country_id'] = False

        # State — only set if city didn't already set it
        if 'state_id' not in vals:
            state_id = post.get('state_id', '').strip()
            try:
                vals['state_id'] = int(state_id) if state_id else False
            except (ValueError, TypeError):
                vals['state_id'] = False

        # Phone (optional for child contacts)
        phone = post.get('phone', '').strip()
        if phone:
            vals['phone'] = phone

        request.env['res.partner'].sudo().create(vals)
        _logger.info("Guapante Addresses: Created child address for company partner %s", company_partner.id)

        return request.redirect('/my/addresses?success=added')

    @http.route(['/my/addresses/edit/<int:address_id>'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_address_edit(self, address_id, **post):
        """Update an existing child partner (address)."""
        partner = request.env.user.partner_id
        company_partner = partner.commercial_partner_id
        address = request.env['res.partner'].sudo().browse(address_id)

        # Security: verify the address belongs to this COMPANY
        if not address.exists() or address.parent_id.id != company_partner.id:
            return request.redirect('/my/addresses?error=not_found')

        # Portal only manages delivery addresses
        vals = {
            'type': 'delivery',
            'name': post.get('name', '').strip() or address.name,
            'street': post.get('street', '').strip(),
            'street2': post.get('street2', '').strip() or False,
            'zip': post.get('zip', '').strip() or False,
            'comment': post.get('comment', '').strip() or False,
            'ref': post.get('order_zone') or False,
        }

        # City (from res.city dropdown — auto-fills city text, state, zip)
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
                vals['city'] = post.get('city_fallback', '').strip() or False
        except (ValueError, TypeError):
            vals['city_id'] = False
            vals['city'] = post.get('city_fallback', '').strip() or False

        # Country — only set if city didn't already set it
        if 'country_id' not in vals:
            country_id = post.get('country_id', '').strip()
            try:
                vals['country_id'] = int(country_id) if country_id else False
            except (ValueError, TypeError):
                vals['country_id'] = False

        # State — only set if city didn't already set it
        if 'state_id' not in vals:
            state_id = post.get('state_id', '').strip()
            try:
                vals['state_id'] = int(state_id) if state_id else False
            except (ValueError, TypeError):
                vals['state_id'] = False

        # Phone
        phone = post.get('phone', '').strip()
        vals['phone'] = phone if phone else False

        address.write(vals)
        _logger.info("Guapante Addresses: Updated address %s for company partner %s", address_id, company_partner.id)

        return request.redirect('/my/addresses?success=updated')

    @http.route(['/my/addresses/delete/<int:address_id>'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_address_delete(self, address_id, **post):
        """Archive (deactivate) a child partner address."""
        partner = request.env.user.partner_id
        company_partner = partner.commercial_partner_id
        address = request.env['res.partner'].sudo().browse(address_id)

        # Security: verify the address belongs to this COMPANY
        if not address.exists() or address.parent_id.id != company_partner.id:
            return request.redirect('/my/addresses?error=not_found')

        # Archive instead of unlink to preserve references in existing orders
        address.write({'active': False})
        _logger.info("Guapante Addresses: Archived address %s for company partner %s", address_id, company_partner.id)

        return request.redirect('/my/addresses?success=deleted')


    @http.route(['/my/invoices', '/my/invoices/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_invoices(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='name', **kw):
        """
        Override the default invoices portal to add KPI logic and use Guapante layout.
        """
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        AccountInvoice = request.env['account.move']

        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')),
            ('state', 'not in', ('draft', 'cancel'))
        ]
        
        # Determine strict or allowed partners based on portal configuration if needed
        # We simplify here to just use the user's commercial partner for standard portal behavior
        domain += [('partner_id', 'child_of', [partner.commercial_partner_id.id])]

        # --- KPI Calculations ---
        
        # 1. Total por Pagar (Amount Due)
        # We only sum the residual amount of unpaid invoices
        unpaid_domain = domain + [('payment_state', 'in', ('not_paid', 'partial'))]
        unpaid_invoices = AccountInvoice.search(unpaid_domain)
        total_por_pagar = sum(unpaid_invoices.mapped('amount_residual'))
        unpaid_count = len(unpaid_invoices)
        
        # 2. Facturas del Mes (Invoices this month)
        today = datetime.today()
        first_day_month = today.replace(day=1).strftime('%Y-%m-%d')
        month_domain = domain + [('invoice_date', '>=', first_day_month)]
        facturas_mes = AccountInvoice.search_count(month_domain)
        
        # 3. Último Pago (Last Payment)
        AccountPayment = request.env['account.payment']
        payment_domain = [
            ('partner_id', 'child_of', [partner.commercial_partner_id.id]),
            ('state', '=', 'posted')
        ]
        last_payment = AccountPayment.search(payment_domain, order='date desc', limit=1)

        # --- Base Portal Logic (Pagination, Filters) ---
        
        # 1. Search
        searchbar_inputs = {
            'name': {'input': 'name', 'label': _('Referencia')},
        }
        if not search_in:
            search_in = 'name'
        if search:
            domain += [('name', 'ilike', search)]

        # 2. Date Range Filters
        date_range_filters = {
            'all':        {'label': 'Todo el tiempo'},
            'last_7':     {'label': 'Últimos 7 días',   'days': 7},
            'last_15':    {'label': 'Últimos 15 días',  'days': 15},
            'last_30':    {'label': 'Últimos 30 días',  'days': 30},
            'last_90':    {'label': 'Últimos 3 meses',  'days': 90},
            'last_180':   {'label': 'Últimos 6 meses',  'days': 180},
            'last_365':   {'label': 'Último año',       'days': 365},
        }
        date_filter = kw.get('date_filter', 'all')
        if date_filter not in date_range_filters:
            date_filter = 'all'

        if date_filter != 'all':
            days = date_range_filters[date_filter]['days']
            date_limit = datetime.now() - timedelta(days=days)
            domain.append(('invoice_date', '>=', date_limit.date()))

        # 3. Sortings
        searchbar_sortings = {
            'date': {'label': _('Fecha de Factura'), 'order': 'invoice_date desc, id desc'},
            'duedate': {'label': _('Fecha de Vencimiento'), 'order': 'invoice_date_due desc, id desc'},
            'name': {'label': _('Referencia'), 'order': 'name desc, id desc'},
            'state': {'label': _('Estado'), 'order': 'state desc, id desc'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # 4. Status Filters
        searchbar_filters = {
            'all': {'label': _('Todas'), 'domain': []},
            'invoices': {'label': _('Facturas'), 'domain': [('move_type', 'in', ('out_invoice', 'out_refund'))]},
            'bills': {'label': _('Recibos'), 'domain': [('move_type', 'in', ('in_invoice', 'in_refund'))]},
        }
        
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # count for pager
        invoice_count = AccountInvoice.search_count(domain)
        
        # make pager
        pager = portal_pager(
            url="/my/invoices",
            url_args={
                'date_begin': date_begin,
                'date_end': date_end,
                'sortby': sortby,
                'filterby': filterby,
                'search': search,
                'search_in': search_in,
                'date_filter': date_filter,
            },
            total=invoice_count,
            page=page,
            step=self._items_per_page
        )
        
        # search the count to display, according to the pager data
        invoices = AccountInvoice.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_invoices_history'] = invoices.ids[:100]

        # Pager offsets
        current_page = page
        items_per_page = self._items_per_page
        page_start_num = (current_page - 1) * items_per_page + 1 if invoice_count > 0 else 0
        page_end_num = min(current_page * items_per_page, invoice_count)
        
        month_names_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        mes_actual_es = month_names_es[today.month - 1]
        facturas_mes_str = f"Emisiones de {mes_actual_es} {today.year}"

        values.update({
            'page_start_num': page_start_num,
            'page_end_num': page_end_num,
            'invoice_count': invoice_count,
            'facturas_mes_str': facturas_mes_str,
            'date': date_begin,
            'invoices': invoices,
            'page_name': 'invoice',
            'pager': pager,
            'default_url': '/my/invoices',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
            
            'searchbar_inputs': searchbar_inputs,
            'search': search,
            'search_in': search_in,
            'date_filter': date_filter,
            'date_range_filters': date_range_filters,
            'today_date': datetime.now().date(),
            
            # --- Custom Guapante Values ---
            'total_por_pagar': total_por_pagar,
            'unpaid_count': unpaid_count,
            'facturas_mes': facturas_mes,
            'last_payment_amount': last_payment.amount if last_payment else 0,
            'last_payment_date': last_payment.date if last_payment else None,
            'currency_id': request.env.company.currency_id,
        })
        
        return request.render("theme_guapante.portal_my_invoices_guapante", values)
