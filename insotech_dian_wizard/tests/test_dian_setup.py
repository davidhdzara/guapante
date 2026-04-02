# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDIANSetup(TransactionCase):
    """Pruebas unitarias básicas para las configuraciones DIAN."""

    def test_dian_company_fields(self):
        """Verifica que los nuevos campos DIAN se asocian correctamente a la compañía."""
        company = self.env.company
        
        # Validar existencia y fallback por defecto
        self.assertEqual(company.insotech_dian_config_state, 'not_configured')
        self.assertEqual(company.insotech_radian_mode, 'manual')
        self.assertTrue(company.insotech_contingency_retries > 0)
