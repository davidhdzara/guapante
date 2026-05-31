# -*- coding: utf-8 -*-
"""
Tests de integracion para el generador de Banco de Bogota.
Verifica que el archivo generado tenga exactamente 250 caracteres por linea
y que todas las posiciones contengan los valores correctos.
"""
import base64

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestBogotaGenerator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Banco destino con codigo ACH
        cls.bank_bogota = cls.env['res.bank'].create({
            'name':             'Banco de Bogota Test',
            'l10n_co_ach_code': '001',
        })

        # Proveedor
        cls.partner = cls.env['res.partner'].create({
            'name':                  'Empresa Test SAS',
            'is_company':            True,
            'vat':                   '9001234561',
            'l10n_co_document_type': 'NIT',
        })

        # Cuenta bancaria del proveedor con tipo configurado
        cls.partner_bank = cls.env['res.partner.bank'].create({
            'acc_number':            '0043001234567',
            'partner_id':            cls.partner.id,
            'bank_id':               cls.bank_bogota.id,
            'l10n_co_account_type':  'CA',  # Ahorros
        })

        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)],
            limit=1,
        )

        # Cuenta dispersora requerida para generar archivos de Bogota
        cls.company.write({
            'l10n_co_dispersal_account':      '03000123456',
            'l10n_co_dispersal_account_type': 'D',
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

    def _create_bogota_export(self, payments):
        return self.env['bank.payment.export'].create({
            'bank':           'bogota',
            'payment_source': 'vendor',
            'payment_ids':    [(6, 0, payments.ids)],
        })

    # ---------------------------------------------------------------
    # Tests de generacion
    # ---------------------------------------------------------------

    def test_bogota_generates_text_file(self):
        """El archivo de Bogota debe ser .txt no .xlsx."""
        payment = self._create_payment()
        export = self._create_bogota_export(payment)
        export._generate_file()
        self.assertTrue(export.excel_filename.endswith('.txt'))
        self.assertEqual(export.state, 'generated')

    def test_bogota_lines_are_exactly_250_chars(self):
        """Cada linea debe tener exactamente 250 caracteres."""
        payment = self._create_payment()
        export = self._create_bogota_export(payment)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        # Eliminar CRLF y dividir
        lines = content.replace('\r', '').split('\n')
        # Filtrar lineas vacias (la ultima despues del salto final)
        lines = [l for l in lines if l]

        for i, line in enumerate(lines, start=1):
            self.assertEqual(
                len(line), 250,
                'Linea %d tiene %d chars (se esperaban 250). Linea: %r'
                % (i, len(line), line)
            )

    def test_bogota_header_starts_with_1(self):
        """El primer registro (header) debe comenzar con '1'."""
        payment = self._create_payment()
        export = self._create_bogota_export(payment)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        self.assertEqual(lines[0][0], '1', 'Header debe iniciar con "1"')

    def test_bogota_detail_starts_with_2(self):
        """Cada registro de detalle debe comenzar con '2'."""
        payment = self._create_payment()
        export = self._create_bogota_export(payment)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        for i, line in enumerate(lines[1:], start=2):
            self.assertEqual(
                line[0], '2',
                'Linea %d debe iniciar con "2" (es detalle)' % i
            )

    def test_bogota_value_in_correct_position(self):
        """El valor debe estar en posiciones 73-90 sin punto decimal."""
        payment = self._create_payment(amount=5000.50)
        export = self._create_bogota_export(payment)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        detalle = lines[1]
        valor_str = detalle[72:90]  # Pos 73-90 (0-indexed)
        # 5000.50 * 100 = 500050 centavos
        self.assertEqual(valor_str, '000000000000500050')

    def test_bogota_account_number_alfanumeric(self):
        """Numero de cuenta (pos 56-72) alineado izquierda con espacios."""
        payment = self._create_payment()
        export = self._create_bogota_export(payment)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        detalle = lines[1]
        cuenta = detalle[55:72]  # Pos 56-72
        # Comienza con la cuenta y rellena con espacios
        self.assertTrue(cuenta.startswith('0043001234567'))

    def test_bogota_multiple_payments(self):
        """Multiples pagos producen multiples lineas de detalle."""
        p1 = self._create_payment(100000)
        p2 = self._create_payment(200000)
        p3 = self._create_payment(300000)
        export = self._create_bogota_export(p1 | p2 | p3)
        export._generate_file()

        content = base64.b64decode(export.excel_file).decode('latin-1')
        lines = [l for l in content.replace('\r', '').split('\n') if l]
        # 1 header + 3 detalles = 4 lineas
        self.assertEqual(len(lines), 4)
        self.assertEqual(export.line_count, 3)
