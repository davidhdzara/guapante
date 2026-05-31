# -*- coding: utf-8 -*-
"""
Tests de integracion para los generadores de Bancolombia (PAB y SAP).
Verifica longitudes exactas de las lineas y posiciones de campos clave.
"""
import base64

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestBancolombiaGenerator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.bank_bcol = cls.env['res.bank'].create({
            'name':             'Bancolombia Test',
            'l10n_co_ach_code': '007',
        })

        cls.partner = cls.env['res.partner'].create({
            'name':                  'Cliente Test SAS',
            'is_company':            True,
            'vat':                   '9001234561',
            'l10n_co_document_type': 'NIT',
        })

        cls.partner_bank = cls.env['res.partner.bank'].create({
            'acc_number':           '12345678901',
            'partner_id':           cls.partner.id,
            'bank_id':              cls.bank_bcol.id,
            'l10n_co_account_type': 'CA',
        })

        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)],
            limit=1,
        )

        # Cuenta dispersora requerida para generar archivos de Bancolombia
        cls.company.write({
            'l10n_co_dispersal_account':      '03000123456',
            'l10n_co_dispersal_account_type': 'S',
        })

    def _create_payment(self, amount=1000000.0):
        payment = self.env['account.payment'].create({
            'payment_type':    'outbound',
            'partner_type':    'supplier',
            'partner_id':      self.partner.id,
            'partner_bank_id': self.partner_bank.id,
            'amount':          amount,
            'journal_id':      self.journal.id,
            'currency_id':     self.company.currency_id.id,
        })
        payment.action_post()
        return payment

    def _create_export(self, payments, fmt='pab'):
        return self.env['bank.payment.export'].create({
            'bank':           'bancolombia_%s' % fmt,
            'payment_source': 'vendor',
            'payment_ids':    [(6, 0, payments.ids)],
        })

    # ---------------------------------------------------------------
    # PAB - 264 chars por linea
    # ---------------------------------------------------------------

    def test_pab_lines_are_exactly_264_chars(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'pab')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        for i, line in enumerate(lines, start=1):
            self.assertEqual(
                len(line), 264,
                'PAB linea %d tiene %d chars (esperados 264)' % (i, len(line))
            )

    def test_pab_header_class_220_for_vendor(self):
        """Pago a proveedores debe usar clase 220 en pos 33-35."""
        payment = self._create_payment()
        export = self._create_export(payment, 'pab')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        header = lines[0]
        clase = header[32:35]  # Pos 33-35
        self.assertEqual(clase, '220', 'Clase debe ser 220 para proveedores')

    def test_pab_detail_value_position(self):
        """Valor de la transaccion en pos 76-92 (17 chars, 15+2)."""
        payment = self._create_payment(amount=1234.56)
        export = self._create_export(payment, 'pab')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        detalle = lines[1]
        valor = detalle[75:92]  # Pos 76-92
        # 1234.56 * 100 = 123456 centavos
        self.assertEqual(valor, '00000000000123456')

    def test_pab_filename_contains_pab(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'pab')
        export._generate_file()
        self.assertIn('PAB', export.excel_filename)

    # ---------------------------------------------------------------
    # SAP - 95 chars por linea
    # ---------------------------------------------------------------

    def test_sap_lines_are_exactly_95_chars(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'sap')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        for i, line in enumerate(lines, start=1):
            self.assertEqual(
                len(line), 95,
                'SAP linea %d tiene %d chars (esperados 95)' % (i, len(line))
            )

    def test_sap_filename_contains_sap(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'sap')
        export._generate_file()
        self.assertIn('SAP', export.excel_filename)

    def test_sap_header_starts_with_1(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'sap')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        self.assertEqual(lines[0][0], '1')

    def test_sap_detail_starts_with_6(self):
        payment = self._create_payment()
        export = self._create_export(payment, 'sap')
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        self.assertEqual(lines[1][0], '6')

    # ---------------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------------

    def test_pab_requires_ach_code(self):
        """Si el banco no tiene codigo ACH, debe fallar."""
        bank_sin = self.env['res.bank'].create({'name': 'Sin codigo'})
        partner_bank = self.env['res.partner.bank'].create({
            'acc_number': '9999',
            'partner_id': self.partner.id,
            'bank_id':    bank_sin.id,
        })
        payment = self.env['account.payment'].create({
            'payment_type':    'outbound',
            'partner_type':    'supplier',
            'partner_id':      self.partner.id,
            'partner_bank_id': partner_bank.id,
            'amount':          100000,
            'journal_id':      self.journal.id,
            'currency_id':     self.company.currency_id.id,
        })
        payment.action_post()
        export = self._create_export(payment, 'pab')
        with self.assertRaises((UserError, Exception)):
            export._generate_file()
