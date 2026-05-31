"""
Tests de integracion del flujo completo de exportacion bancaria.
Verifica el modelo, el wizard y la generacion del Excel.
"""
import base64
import io

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
except ImportError:
    openpyxl = None


@tagged('post_install', '-at_install')
class TestBankPaymentExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Banco con codigo ACH configurado
        cls.bank_davivienda = cls.env['res.bank'].create({
            'name':             'Banco Davivienda Test',
            'l10n_co_ach_code': '051',
        })

        # Partner proveedor
        cls.partner = cls.env['res.partner'].create({
            'name':                   'Proveedor Test SAS',
            'is_company':             True,
            'vat':                    '9001234561',
            'l10n_co_document_type':  'NIT',
            'email':                  'proveedor@test.co',
        })

        # Cuenta bancaria del proveedor
        cls.partner_bank = cls.env['res.partner.bank'].create({
            'acc_number': '0043001234567',
            'partner_id': cls.partner.id,
            'bank_id':    cls.bank_davivienda.id,
            'acc_type':   'savings',
        })

        # Diario de banco
        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)],
            limit=1,
        )

    def _create_posted_payment(self, amount=1000000.0):
        """Crea un pago a proveedor publicado con cuenta bancaria asignada."""
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

    def _create_export(self, payments, bank='davivienda', source='vendor'):
        """Crea un registro de exportacion desde el ORM (simula el wizard)."""
        export = self.env['bank.payment.export'].create({
            'bank':           bank,
            'payment_source': source,
            'payment_ids':    [(6, 0, payments.ids)],
        })
        return export

    # -- Creacion y secuencia ------------------------------------------------

    def test_sequence_assigned_on_create(self):
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        self.assertNotEqual(export.name, 'Nuevo')
        self.assertIn('BANCO', export.name)

    def test_initial_state_is_draft(self):
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        self.assertEqual(export.state, 'draft')

    # -- Generacion del archivo ----------------------------------------------

    def test_generate_produces_binary(self):
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        export._generate_file()
        self.assertTrue(export.excel_file)
        self.assertTrue(export.excel_filename.endswith('.xlsx'))
        self.assertEqual(export.state, 'generated')
        self.assertEqual(export.line_count, 1)

    def test_generated_excel_has_correct_columns(self):
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        export._generate_file()

        raw = base64.b64decode(export.excel_file)
        wb  = openpyxl.load_workbook(io.BytesIO(raw))
        ws  = wb.active

        # Exactamente una hoja (requerimiento Davivienda)
        self.assertEqual(len(wb.sheetnames), 1)
        self.assertEqual(ws.title, 'Hoja1')

        # Encabezados en fila 1
        headers = [ws.cell(row=1, column=i).value for i in range(1, 12)]
        self.assertIn('Tipo de Identificacion', headers)
        self.assertIn('Valor del pago o de la recarga', headers)
        self.assertIn('Numero del Producto o Servicio', headers)

        # Datos en fila 2
        id_type = ws.cell(row=2, column=1).value
        self.assertEqual(id_type, '03')  # NIT

        # Numero de cuenta como string (preserva ceros iniciales)
        acc = ws.cell(row=2, column=7).value
        self.assertIsInstance(acc, str)
        self.assertTrue(acc.startswith('00'))

    def test_multiple_payments_produce_multiple_rows(self):
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        p1 = self._create_posted_payment(500000)
        p2 = self._create_posted_payment(750000)
        export = self._create_export(p1 | p2)
        export._generate_file()
        self.assertEqual(export.line_count, 2)

    # -- Validaciones --------------------------------------------------------

    def test_error_when_no_payments_selected(self):
        export = self.env['bank.payment.export'].create({
            'bank':           'davivienda',
            'payment_source': 'vendor',
            'payment_ids':    [(5,)],
        })
        with self.assertRaises(UserError):
            export._generate_file()

    def test_error_when_bank_has_no_ach_code(self):
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        bank_sin_codigo = self.env['res.bank'].create({'name': 'Banco Sin Codigo'})
        partner_bank    = self.env['res.partner.bank'].create({
            'acc_number': '1234567890',
            'partner_id': self.partner.id,
            'bank_id':    bank_sin_codigo.id,
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
        export = self._create_export(payment)
        with self.assertRaises(UserError):
            export._generate_file()

    def test_error_when_partner_has_no_vat(self):
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        partner_sin_vat = self.env['res.partner'].create({
            'name':       'Sin NIT',
            'is_company': True,
        })
        partner_bank = self.env['res.partner.bank'].create({
            'acc_number': '9876543210',
            'partner_id': partner_sin_vat.id,
            'bank_id':    self.bank_davivienda.id,
        })
        payment = self.env['account.payment'].create({
            'payment_type':    'outbound',
            'partner_type':    'supplier',
            'partner_id':      partner_sin_vat.id,
            'partner_bank_id': partner_bank.id,
            'amount':          200000,
            'journal_id':      self.journal.id,
            'currency_id':     self.company.currency_id.id,
        })
        payment.action_post()
        export = self._create_export(payment)
        with self.assertRaises(UserError):
            export._generate_file()

    # -- Accion de cancelar --------------------------------------------------

    def test_cancel_in_draft_state(self):
        """Solo se puede cancelar un registro en estado borrador."""
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        # No generar - dejarlo en draft
        export.action_cancel()
        self.assertEqual(export.state, 'cancelled')

    def test_cannot_cancel_generated_export(self):
        """Un registro generado no se puede cancelar, solo restablecer."""
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        export._generate_file()
        self.assertEqual(export.state, 'generated')
        with self.assertRaises(UserError):
            export.action_cancel()

    def test_reset_to_draft_clears_file(self):
        """Restablecer a borrador limpia el archivo generado."""
        if not openpyxl:
            self.skipTest('openpyxl no esta instalado')
        payment = self._create_posted_payment()
        export  = self._create_export(payment)
        export._generate_file()
        self.assertTrue(export.excel_file)
        export.action_reset_to_draft()
        self.assertEqual(export.state, 'draft')
        self.assertFalse(export.excel_file)
        self.assertEqual(export.line_count, 0)
