# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLicensing(TransactionCase):
    """Pruebas unitarias básicas para los campos de InSoTech."""

    def test_company_licensing_fields(self):
        """Verifica que los campos de InSoTech existan en la compañía."""
        company = self.env.company
        
        # Simplemente validamos que los campos responden sin error
        token = company.insotech_license_token
        usage = company.insotech_usage_count
        
        self.assertTrue(True, "Company fields exist")
