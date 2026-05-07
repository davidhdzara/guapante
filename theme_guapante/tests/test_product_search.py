# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductSearchRelevance(TransactionCase):
    """Tests for eCommerce search: description exclusion + name relevance sort.

    Validates that _search_get_detail excludes the 'description' (HTML) field
    from fuzzy search to avoid false positives, and that results are sorted
    by name relevance (starts_with > contains > rest).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].get_current_website()
        # Products with name matches
        cls.ajo = cls.env['product.template'].create({
            'name': 'Ajo',
            'sale_ok': True,
            'list_price': 5000.0,
            'description': '<p>El ajo es un condimento esencial.</p>',
        })
        cls.ajo_limpio = cls.env['product.template'].create({
            'name': 'Ajo Limpio',
            'sale_ok': True,
            'list_price': 7000.0,
            'description': '<p>Ajo pelado y listo para usar.</p>',
        })
        # Product with FALSE POSITIVE: 'ajo' only in description via 'bajo'
        cls.banano = cls.env['product.template'].create({
            'name': 'Banano',
            'sale_ok': True,
            'list_price': 3000.0,
            'description': (
                '<p>Disfruta del auténtico sabor tropical. '
                'Cultivado bajo un clima privilegiado.</p>'
            ),
        })
        # Product with 'manzana' in name
        cls.manzana_verde = cls.env['product.template'].create({
            'name': 'Manzana Verde',
            'sale_ok': True,
            'list_price': 4000.0,
            'description': '<p>Manzana verde fresca y crujiente.</p>',
        })
        # Product with 'manzana' only in description (false positive)
        cls.papa = cls.env['product.template'].create({
            'name': 'Papa Nevada',
            'sale_ok': True,
            'list_price': 2000.0,
            'description': (
                '<p>También conocida como Papa manzana nevada, '
                'se distingue por su textura suave.</p>'
            ),
        })
        # Product where search term appears mid-name (contains, not starts)
        cls.guayaba_manzana = cls.env['product.template'].create({
            'name': 'Guayaba Manzana',
            'sale_ok': True,
            'list_price': 6000.0,
            'description': '<p>Guayaba con sabor a manzana.</p>',
        })

    # ── Component 1: _search_get_detail excludes 'description' ──

    def test_search_fields_exclude_description(self):
        """_search_get_detail should NOT include 'description' in search_fields."""
        options = {
            'displayImage': True,
            'displayDescription': True,
            'displayDetail': True,
            'displayExtraDetail': True,
            'displayExtraLink': True,
            'allowFuzzy': True,
            'display_currency': self.env.company.currency_id,
        }
        detail = self.env['product.template']._search_get_detail(
            self.website, 'relevance', options
        )
        self.assertNotIn(
            'description', detail['search_fields'],
            "Field 'description' must be excluded from search to avoid "
            "false positives from marketing HTML content.",
        )

    def test_search_fields_keep_name_and_code(self):
        """_search_get_detail should still include name and default_code."""
        options = {
            'displayImage': True,
            'displayDescription': True,
            'displayDetail': True,
            'displayExtraDetail': True,
            'displayExtraLink': True,
            'allowFuzzy': True,
            'display_currency': self.env.company.currency_id,
        }
        detail = self.env['product.template']._search_get_detail(
            self.website, 'relevance', options
        )
        self.assertIn('name', detail['search_fields'])
        self.assertIn('default_code', detail['search_fields'])

    # ── Component 2: _sort_by_name_relevance ──

    def test_sort_starts_with_before_contains(self):
        """Products whose name starts with the term should come before contains."""
        # Mix of: starts_with (Manzana Verde) and contains (Guayaba Manzana)
        products = self.manzana_verde | self.guayaba_manzana
        # Simulate controller method by calling it statically
        from odoo.addons.theme_guapante.controllers.shop import GuapanteWebsiteSale
        controller = GuapanteWebsiteSale()
        sorted_result = controller._sort_by_name_relevance(products, 'manzana')
        sorted_names = [p.name for p in sorted_result]
        # Manzana Verde starts with 'manzana' → must come first
        self.assertEqual(
            sorted_names[0], 'Manzana Verde',
            "Product whose name starts with the term must come first.",
        )

    def test_sort_name_match_before_description_only(self):
        """Products with name match should rank before description-only matches."""
        products = self.papa | self.manzana_verde | self.guayaba_manzana
        from odoo.addons.theme_guapante.controllers.shop import GuapanteWebsiteSale
        controller = GuapanteWebsiteSale()
        sorted_result = controller._sort_by_name_relevance(products, 'manzana')
        sorted_names = [p.name for p in sorted_result]
        # Papa Nevada has no 'manzana' in name → must be last
        self.assertEqual(
            sorted_names[-1], 'Papa Nevada',
            "Product with match only in description must come last.",
        )

    def test_sort_empty_term_preserves_order(self):
        """Empty search term should not change the order."""
        products = self.banano | self.ajo
        from odoo.addons.theme_guapante.controllers.shop import GuapanteWebsiteSale
        controller = GuapanteWebsiteSale()
        sorted_result = controller._sort_by_name_relevance(products, '')
        self.assertEqual(
            sorted_result.ids, products.ids,
            "Empty search term must preserve original order.",
        )

    def test_sort_empty_recordset_returns_empty(self):
        """Empty recordset input should return empty recordset."""
        empty = self.env['product.template']
        from odoo.addons.theme_guapante.controllers.shop import GuapanteWebsiteSale
        controller = GuapanteWebsiteSale()
        result = controller._sort_by_name_relevance(empty, 'ajo')
        self.assertFalse(result, "Empty recordset should return empty.")

    def test_sort_case_insensitive(self):
        """Sorting should be case-insensitive."""
        products = self.guayaba_manzana | self.manzana_verde
        from odoo.addons.theme_guapante.controllers.shop import GuapanteWebsiteSale
        controller = GuapanteWebsiteSale()
        sorted_result = controller._sort_by_name_relevance(products, 'MANZANA')
        sorted_names = [p.name for p in sorted_result]
        self.assertEqual(
            sorted_names[0], 'Manzana Verde',
            "Case-insensitive: 'MANZANA' must still match 'Manzana Verde' first.",
        )
