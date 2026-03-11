# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestControllerRoutes(HttpCase):
    """HTTP-level tests for theme_guapante custom portal routes."""

    def test_my_orders_page_loads(self):
        """The /my/orders route should return 200 for an authenticated portal user."""
        self.authenticate('portal', 'portal')
        response = self.url_open('/my/orders')
        self.assertEqual(
            response.status_code, 200,
            "GET /my/orders should return 200 for authenticated portal user",
        )

    def test_my_profile_page_loads(self):
        """The /my/profile route should return 200 for an authenticated portal user."""
        self.authenticate('portal', 'portal')
        response = self.url_open('/my/profile')
        self.assertEqual(
            response.status_code, 200,
            "GET /my/profile should return 200 for authenticated portal user",
        )

    def test_get_cities_json_endpoint(self):
        """The /my/addresses/get_cities endpoint should return JSON."""
        self.authenticate('portal', 'portal')
        # Get a valid state_id from Colombia
        state = self.env['res.country.state'].search([
            ('country_id.code', '=', 'CO'),
        ], limit=1)
        if state:
            response = self.make_jsonrpc_request(
                '/my/addresses/get_cities',
                {'state_id': state.id}
            )
            self.assertIsInstance(response, list, "get_cities should return a list")

    def test_my_orders_requires_auth(self):
        """The /my/orders route should redirect unauthenticated users to login."""
        response = self.url_open('/my/orders', allow_redirects=False)
        self.assertIn(
            response.status_code, [302, 303],
            "GET /my/orders should redirect unauthenticated users",
        )
