# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website

class GuapanteWebsite(Website):

    def _login_redirect(self, uid, redirect=None):
        """ Override default login redirect for portal users from /my to /shop.
        If a specific redirect is provided (e.g. from checkout), it is preserved.
        """
        # Call super first to get the default behavior (or we can just override it directly)
        # But Odoo's Website._login_redirect forces /my if not redirect and not employee.
        # So we can intercept that.
        
        # If no redirect is specified, and the logged in user is not an internal user (employee)
        if not redirect and not request.env.user.has_group('base.group_user'):
            redirect = '/shop'
            
        return super(GuapanteWebsite, self)._login_redirect(uid, redirect=redirect)
