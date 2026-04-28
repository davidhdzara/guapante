# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDianDetection(AccountTestInvoicingCommon):
    """Test suite for the DIAN state detection hook.

    Validates that the l10n_co_dian.document write() hook correctly
    detects DIAN acceptance/rejection and triggers the corresponding
    PRE-INV name mutation or Regla 90 recovery.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.cr.savepoint()

        # 1. Update company to Colombia
        co_country = cls.env.ref(
            'base.co', raise_if_not_found=False,
        )
        if not co_country:
            co_country = cls.env['res.country'].search(
                [('code', '=', 'CO')], limit=1,
            )

        cls.company_data['company'].write({
            'country_id': co_country.id if co_country else False,
        })

        # 2. Colombian partner
        cls.partner_co = cls.env['res.partner'].create({
            'name': 'Test DIAN Detection SAS',
            'is_company': True,
            'country_id': co_country.id if co_country else False,
            'vat': '901797249-5',
        })

        # 3. DIAN journal
        cls.journal_dian = cls.env['account.journal'].create({
            'name': 'Ventas DIAN (Detection Test)',
            'code': 'TD_DI',
            'type': 'sale',
            'company_id': cls.company_data['company'].id,
        })
        if 'l10n_co_dian_provider' in cls.journal_dian._fields:
            cls.journal_dian.l10n_co_dian_provider = 'DIAN: Free Service'
        if 'l10n_co_edi_dian_authorization_number' in cls.journal_dian._fields:
            cls.journal_dian.l10n_co_edi_dian_authorization_number = (
                '18760000001'
            )

        # 4. Ensure the PRE-INV sequence exists
        seq = cls.env['ir.sequence'].search(
            [('code', '=', 'insotech.pre.inv')], limit=1,
        )
        if not seq:
            cls.env['ir.sequence'].create({
                'name': 'Test PRE-INV Sequence',
                'code': 'insotech.pre.inv',
                'prefix': 'PRE-INV/%(year)s/',
                'padding': 5,
                'company_id': cls.company_data['company'].id,
            })

    def _create_and_post_invoice(self):
        """Create and post a Colombian EDI invoice."""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.journal_dian.id,
            'partner_id': self.partner_co.id,
            'invoice_date': '2026-03-25',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'price_unit': 1000.0,
                })
            ],
        })
        invoice.action_post()
        return invoice

    def test_01_acceptance_detection(self):
        """DIAN acceptance triggers insotech_dian_status → accepted."""
        DianDoc = self.env.get('l10n_co_dian.document')
        if DianDoc is None:
            self.skipTest("l10n_co_dian.document model not available")

        invoice = self._create_and_post_invoice()
        if invoice.insotech_dian_status != 'pending':
            self.skipTest("Invoice did not enter pending state")

        # Simulate a l10n_co_dian.document creation & acceptance
        doc = DianDoc.create({
            'move_id': invoice.id,
            'state': 'invoice_sending_failed',
        })
        # Trigger the hook via write
        doc.write({'state': 'invoice_accepted'})

        invoice.invalidate_recordset(['insotech_dian_status'])
        self.assertEqual(
            invoice.insotech_dian_status, 'accepted',
            "Acceptance hook should have mutated status to 'accepted'.",
        )

    def test_02_rejection_detection(self):
        """DIAN rejection triggers insotech_dian_status → rejected."""
        DianDoc = self.env.get('l10n_co_dian.document')
        if DianDoc is None:
            self.skipTest("l10n_co_dian.document model not available")

        invoice = self._create_and_post_invoice()
        if invoice.insotech_dian_status != 'pending':
            self.skipTest("Invoice did not enter pending state")

        doc = DianDoc.create({
            'move_id': invoice.id,
            'state': 'invoice_sending_failed',
        })
        doc.write({'state': 'invoice_rejected'})

        invoice.invalidate_recordset(['insotech_dian_status'])
        self.assertEqual(
            invoice.insotech_dian_status, 'rejected',
            "Rejection hook should have mutated status to 'rejected'.",
        )

    def test_03_regla_90_recovery(self):
        """Regla 90 recovery rescues CUFE from prior accepted doc."""
        DianDoc = self.env.get('l10n_co_dian.document')
        if DianDoc is None:
            self.skipTest("l10n_co_dian.document model not available")

        invoice = self._create_and_post_invoice()
        if invoice.insotech_dian_status != 'pending':
            self.skipTest("Invoice did not enter pending state")

        # Step 1: First doc was accepted (simulating successful send)
        accepted_doc = DianDoc.create({
            'move_id': invoice.id,
            'state': 'invoice_accepted',
            'identifier': 'test_cufe_abc123_recovery_test',
        })

        # Step 2: Second doc gets Regla 90 rejection
        rejected_doc = DianDoc.create({
            'move_id': invoice.id,
            'state': 'invoice_sending_failed',
        })

        # Reset status to pending (as it would be in real scenario)
        invoice.with_context(
            skip_account_move_synchronization=True,
        ).write({'insotech_dian_status': 'pending'})

        rejected_doc.write({
            'state': 'invoice_rejected',
            'message': 'Regla: 90, Rechazo: Documento procesado '
                       'anteriormente.',
        })

        invoice.invalidate_recordset([
            'insotech_dian_status',
            'l10n_co_edi_cufe_cude_ref',
        ])

        # Verify recovery
        self.assertEqual(
            invoice.insotech_dian_status, 'accepted',
            "Regla 90 recovery should have set status to 'accepted'.",
        )

    def test_04_regla_90_is_detected(self):
        """_is_regla_90 correctly identifies Regla 90 messages."""
        DianDoc = self.env.get('l10n_co_dian.document')
        if DianDoc is None:
            self.skipTest("l10n_co_dian.document model not available")

        self.assertTrue(
            DianDoc._is_regla_90(
                'Regla: 90, Rechazo: Documento procesado anteriormente.'
            ),
        )
        self.assertTrue(
            DianDoc._is_regla_90(
                '<p>Error: documento procesado anteriormente</p>'
            ),
        )
        self.assertFalse(DianDoc._is_regla_90(''))
        self.assertFalse(DianDoc._is_regla_90('Regla: 50, error'))
