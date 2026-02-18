# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
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

        # 2. Status Filters (Spanish)
        searchbar_filters = {
            'all':       {'label': 'Todos', 'domain': []},
            'received':  {'label': 'Recibido', 'domain': [('guapante_delivery_status', '=', 'received')]},
            'active':    {'label': 'Envíos Activos', 'domain': [('guapante_delivery_status', 'in', ['preparing', 'shipping'])]},
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
        if not order.exists() or order.partner_id != request.env.user.partner_id:
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
