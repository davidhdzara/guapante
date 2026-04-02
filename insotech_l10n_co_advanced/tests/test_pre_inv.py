# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestPreInv(AccountTestInvoicingCommon):
    """Test suite for the PRE-INV sequence protection mechanism.
    
    Validates that Colombian EDI invoices do not consume the legal DIAN
    resolution consecutive until they are officially accepted, avoiding
    'huecos en la numeración'.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.cr.savepoint()

        # 1. Update company to Colombia
        co_country = cls.env.ref('base.co', raise_if_not_found=False)
        if not co_country:
            co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        
        cls.company_data['company'].write({
            'country_id': co_country.id if co_country else False,
        })

        # 2. Set up a generic Colombian Partner
        cls.partner_co = cls.env['res.partner'].create({
            'name': 'Colombian Corp SAS',
            'is_company': True,
            'country_id': co_country.id if co_country else False,
            'vat': '901797249-5',
        })
        nit_type = cls.env.ref('l10n_latam_base.it_nit', raise_if_not_found=False)
        if nit_type:
            cls.partner_co.l10n_latam_identification_type_id = nit_type.id

        # 3. DIAN Sales Journal
        cls.journal_dian = cls.env['account.journal'].create({
            'name': 'Ventas DIAN (Test)',
            'code': 'TV_DI',
            'type': 'sale',
            'company_id': cls.company_data['company'].id,
        })
        # Add DIAN-specific fields if available in the environment
        if 'l10n_co_dian_provider' in cls.journal_dian._fields:
            cls.journal_dian.l10n_co_dian_provider = 'DIAN: Free Service'
        if 'l10n_co_edi_dian_authorization_number' in cls.journal_dian._fields:
            cls.journal_dian.l10n_co_edi_dian_authorization_number = '18760000001'

        # 4. Standard Sales Journal (No DIAN config)
        standard_vals = {
            'name': 'Ventas Standard (Test)',
            'code': 'TV_STD',
            'type': 'sale',
            'company_id': cls.company_data['company'].id,
        }
        if 'l10n_co_dian_provider' in cls.env['account.journal']._fields:
            standard_vals['l10n_co_dian_provider'] = False
        if 'l10n_co_edi_dian_authorization_number' in cls.env['account.journal']._fields:
            standard_vals['l10n_co_edi_dian_authorization_number'] = False

        cls.journal_standard = cls.env['account.journal'].create(standard_vals)

        # 5. Ensure the test PRE-INV sequence exists
        seq = cls.env['ir.sequence'].search([('code', '=', 'insotech.pre.inv')], limit=1)
        if not seq:
            cls.env['ir.sequence'].create({
                'name': 'Test PRE-INV Sequence',
                'code': 'insotech.pre.inv',
                'prefix': 'PRE-INV/%(year)s/',
                'padding': 5,
                'company_id': cls.company_data['company'].id,
            })

    def _create_invoice(self, journal, partner=None):
        """Helper to create a draft invoice."""
        if not partner:
            partner = self.partner_co

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'partner_id': partner.id,
            'invoice_date': '2026-03-25',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'price_unit': 1000.0,
                })
            ],
        })
        return invoice

    def test_01_pre_inv_injection(self):
        """Escenario 1: La Inyección (Confirmación)."""
        invoice = self._create_invoice(self.journal_dian)
        self.assertEqual(invoice.state, 'draft')

        # Confirm the invoice
        invoice.action_post()

        # Check injection took place
        self.assertTrue(bool(invoice.name and invoice.name.startswith('PRE-INV')), "The move name should start with PRE-INV.")
        self.assertEqual(invoice.insotech_dian_status, 'pending', "Status should be 'pending'.")
        self.assertEqual(invoice.insotech_pre_inv_name, invoice.name, "Pre-inv name should match.")
        
        # Ensure the legal consecutive was reserved and is distinct from PRE-INV
        self.assertTrue(bool(invoice.insotech_reserved_dian_name), "The legal DIAN consecutive should be reserved.")
        self.assertFalse(invoice.insotech_reserved_dian_name.startswith('PRE-INV'), "Reserved name must not be a PRE-INV.")

    def test_02_simulated_acceptance(self):
        """Escenario 2: El Éxito Simulado (Aceptación DIAN)."""
        invoice = self._create_invoice(self.journal_dian)
        invoice.action_post()

        pre_inv_name = invoice.name
        self.assertTrue(pre_inv_name.startswith('PRE-INV'))

        # Simulate DIAN acceptance
        invoice._insotech_process_dian_acceptance()

        # Check mutation
        self.assertFalse(invoice.name.startswith('PRE-INV'), "Name should be mutated to a legal sequence.")
        self.assertEqual(invoice.insotech_dian_status, 'accepted', "Status should be 'accepted'.")

    def test_03_simulated_rejection(self):
        """Escenario 3: El Fracaso Simulado (Rechazo DIAN)."""
        invoice = self._create_invoice(self.journal_dian)
        invoice.action_post()

        pre_inv_name = invoice.name

        # Simulate DIAN rejection
        invoice._insotech_process_dian_rejection('Simulated Error DIAN 400')

        # Check restoration
        self.assertEqual(invoice.name, pre_inv_name, "Name should remain PRE-INV permanently.")
        self.assertEqual(invoice.insotech_dian_status, 'rejected', "Status should be 'rejected'.")

    def test_04_isolation_standard_journal(self):
        """Escenario 4: El Aislamiento (Diarios estándar y Documentos internos)."""
        # Testing an internal document (Vendor Bill) which bypasses DIAN EDI logic
        vendor_bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
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
        
        # Confirm
        vendor_bill.action_post()

        # The PRE-INV mechanism should NOT trigger for this internal document
        if vendor_bill.name:
            self.assertFalse(vendor_bill.name.startswith('PRE-INV'), "Standard internal document should not be PRE-INV.")
        self.assertEqual(vendor_bill.insotech_dian_status, 'not_applicable', "Status should bypass to 'not_applicable'.")
        self.assertFalse(vendor_bill.insotech_pre_inv_name, "No PRE-INV name should be allocated.")

    def test_05_contingency_mutation_immediate(self):
        """Escenario 5: Contingency Mutation (Tipo 04).
        
        Al pasar a contingencia, el nombre PRE-INV debe mutar inmediatamente al nombre legal
        sin importar la red DIAN, porque se imprime un PDF legal offline.
        """
        invoice = self._create_invoice(self.journal_dian)
        invoice.action_post()

        # Step 1: Verify it is PRE-INV
        pre_inv_name = invoice.name
        self.assertTrue(pre_inv_name.startswith('PRE-INV'), "Invoice did not acquire PRE-INV name.")
        self.assertEqual(invoice.insotech_dian_status, 'pending')

        # Step 2: User changes to Contingency Type 04 (Simulating PDF print need)
        invoice.write({'l10n_co_edi_operation_type': '04'})

        # Step 3: Validate immediate mutation to legal sequence and PRE-INV memory destruction
        self.assertFalse(invoice.name.startswith('PRE-INV'), "Contingency invoice must drop PRE-INV immediately.")
        self.assertTrue(invoice.name.startswith('TV_DI'), "Invoice must adopt the legal DIAN sequence prefix.")
        self.assertFalse(invoice.insotech_pre_inv_name, "PRE-INV memory must be wiped to lock the sequence.")
