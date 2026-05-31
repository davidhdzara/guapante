# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.addons.insotech_l10n_co_advanced.tests.test_pre_inv import TestPreInv

@tagged('post_install', '-at_install')
class TestDianRetryAndCancellation(TestPreInv):
    """Test suite for the new Retry and Cancellation mechanics.
    
    Ensures that timeouts (pending) can be retried, and that cancellation
    releases the DIAN consecutive properly.
    """

    def test_01_retry_pending_invoice(self):
        """Test that an invoice in 'pending' status can be retried."""
        invoice = self._create_invoice(self.journal_dian)
        invoice.action_post()
        
        self.assertEqual(invoice.insotech_dian_status, 'pending')
        
        # This should not raise UserError now
        try:
            invoice.action_insotech_retry_dian()
        except Exception as e:
            self.fail(f"action_insotech_retry_dian raised Exception unexpectedly: {e}")
            
    def test_02_cancellation_releases_consecutive(self):
        """Test that cancelling an invoice releases its consecutive."""
        invoice1 = self._create_invoice(self.journal_dian)
        invoice1.action_post()
        
        reserved_name_1 = invoice1.insotech_reserved_dian_name
        self.assertTrue(bool(reserved_name_1))
        self.assertEqual(invoice1.insotech_dian_status, 'pending')
        
        # Cancel the invoice
        invoice1.button_cancel()
        
        # Verify fields are cleared
        self.assertFalse(invoice1.insotech_reserved_dian_name, "Reserved name should be cleared upon cancellation.")
        self.assertFalse(invoice1.insotech_dian_xml_sent, "XML sent flag should be cleared upon cancellation.")
        
        # Create a second invoice and post it
        invoice2 = self._create_invoice(self.journal_dian)
        invoice2.action_post()
        
        # It should receive the exact same consecutive that invoice1 had released
        reserved_name_2 = invoice2.insotech_reserved_dian_name
        self.assertEqual(reserved_name_1, reserved_name_2, "Invoice 2 did not reuse the released consecutive from Invoice 1.")
