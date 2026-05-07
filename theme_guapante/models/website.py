# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def sale_get_order(self, force_create=False):
        """Enforce cart isolation between sibling portal accounts.

        WHY: Odoo's native sale_get_order() blindly trusts
        session['sale_order_id'] without verifying that:
          1. The order is still a draft (not confirmed/cancelled).
          2. The order belongs to the currently authenticated user.

        When a customer uses the same browser for multiple child accounts
        (e.g. LRFN Bar → Cocina), the session retains the old order_id
        because Session.authenticate() does NOT call sale_reset().
        This causes products to be added to the wrong order — including
        confirmed orders belonging to a different sibling account.

        FIX: Before delegating to super(), validate the session order.
        If it's stale (wrong partner or not draft), clear the pointer.
        The order itself is NEVER deleted — it remains in PostgreSQL
        and will be re-found via last_website_so_id when the correct
        user logs in.
        """
        sale_order_id = request.session.get('sale_order_id')
        if sale_order_id and not self.env.user._is_public():
            order_sudo = (
                self.env['sale.order']
                .sudo()
                .browse(sale_order_id)
                .exists()
            )
            if order_sudo:
                partner = self.env.user.partner_id

                needs_reset = False

                # Guard 1: Order must be a draft (cart), not confirmed
                if order_sudo.state != 'draft':
                    _logger.info(
                        "Cart isolation: clearing session — order %s is "
                        "state=%s (not draft) for partner %s [%s]",
                        order_sudo.name, order_sudo.state,
                        partner.name, partner.id,
                    )
                    needs_reset = True

                # Guard 2: Order must belong to the authenticated partner
                elif order_sudo.partner_id.id != partner.id:
                    _logger.info(
                        "Cart isolation: clearing session — order %s "
                        "belongs to partner %s [%s], but user is %s [%s]",
                        order_sudo.name,
                        order_sudo.partner_id.name,
                        order_sudo.partner_id.id,
                        partner.name, partner.id,
                    )
                    needs_reset = True

                if needs_reset:
                    request.session.pop('sale_order_id', None)
                    request.session.pop('website_sale_cart_quantity', None)

        return super().sale_get_order(force_create=force_create)
