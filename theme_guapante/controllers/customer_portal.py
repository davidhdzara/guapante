# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)

class GuapanteCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """ Override to inject custom KPI counters for Guapante portal home. """
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'active_shipments_count' in counters:
            # Active Shipments: 'preparing' or 'shipping'
            domain = [
                ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
                ('state', 'in', ['sale', 'done']),
                ('guapante_delivery_status', 'in', ['preparing', 'shipping'])
            ]
            values['active_shipments_count'] = request.env['sale.order'].sudo().search_count(domain)
        
        return values

    @http.route(['/my/orders', '/my/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_orders(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """ Override completely to inject custom filtering logic and context. """
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']

        domain = [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sale', 'done', 'cancel']) # Include Cancelled as requested
        ]

        # 1. Sortings
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'date_order desc'},
            'name': {'label': _('Name'), 'order': 'name desc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # 2. Filters (Status)
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'active': {'label': _('Active Shipments'), 'domain': [('guapante_delivery_status', 'in', ['preparing', 'shipping'])]},
            'delivered': {'label': _('Delivered'), 'domain': [('guapante_delivery_status', '=', 'delivered')]},
            'cancelled': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancel')]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # 3. Date Filter (Custom Logic)
        # Using 'kw' to get custom date range if passed (e.g. from a dropdown)
        date_filter = kw.get('date_filter', 'all')
        if date_filter == 'last_30_days':
             from datetime import datetime, timedelta
             date_limit = datetime.now() - timedelta(days=30)
             domain.append(('date_order', '>=', date_limit))
        # Add more date logic here if needed (3 months, 6 months)

        # 4. Pager
        order_count = SaleOrder.search_count(domain)
        pager = portal_pager(
            url="/my/orders",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=order_count,
            page=page,
            step=self._items_per_page
        )

        # 5. Search
        orders = SaleOrder.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_orders_history'] = orders.ids[:100]

        # 6. Active Shipments Count (KPI for Sidebar/Header)
        active_domain = [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sale', 'done']),
            ('guapante_delivery_status', 'in', ['preparing', 'shipping'])
        ]
        active_shipments_count = SaleOrder.sudo().search_count(active_domain)

        values.update({
            'date': date_begin,
            'orders': orders,
            'page_name': 'order',
            'pager': pager,
            'default_url': '/my/orders',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            'date_filter': date_filter, # Pass to view to highlight active filter
            'active_shipments_count': active_shipments_count, # Pass KPI
        })
        return request.render("portal.portal_my_orders", values)

    @http.route(['/my/orders/reorder/<int:order_id>'], type='http', auth="user", website=True)
    def portal_reorder(self, order_id, **kw):
        """ Re-add products from a past order to the current cart.
            Does NOT check for stock availability (allow selling out of stock).
        """
        order = request.env['sale.order'].browse(order_id)
        if not order.exists() or order.partner_id != request.env.user.partner_id:
            return request.redirect('/my/orders')

        current_order = request.website.sale_get_order(force_create=True)
        
        added_products = []
        for line in order.order_line:
            # Skip if product is archived or service (unless reordering services is desired)
            if not line.product_id.active:
                continue

            # Add to cart
            current_order._cart_update(
                product_id=line.product_id.id,
                add_qty=line.product_uom_qty,
            )
            added_products.append(line.product_id.name)

        # Optional: Add a flash message using session (requires custom logic in layout to display)
        # request.session['guapante_notification'] = {'type': 'success', 'message': f"Reordered {len(added_products)} items!"}

        return request.redirect('/shop/cart')
