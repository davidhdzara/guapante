# -*- coding: utf-8 -*-
# Part of l10n_co_accounting_reports.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPartnerBalanceReport(TransactionCase):
    """Tests para el reporte Balance de Prueba por Terceros."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref(
            'l10n_co_accounting_reports.partner_balance_report'
        )
        cls.handler = cls.env[
            'account.partner.balance.report.handler'
        ]

    def test_report_exists(self):
        """El reporte debe existir con el handler correcto."""
        self.assertTrue(self.report)
        self.assertEqual(
            self.report.custom_handler_model_name,
            'account.partner.balance.report.handler',
        )

    def test_report_columns(self):
        """El reporte debe tener 7 columnas con los labels esperados."""
        expected_labels = [
            'doc_type', 'partner_vat', 'partner_name',
            'initial_balance', 'debit', 'credit', 'balance',
        ]
        self.assertEqual(len(self.report.column_ids), 7)
        actual_labels = self.report.column_ids.mapped('expression_label')
        self.assertEqual(actual_labels, expected_labels)

    def test_report_filters(self):
        """El reporte debe tener los filtros esperados configurados."""
        self.assertTrue(self.report.filter_show_draft)
        self.assertTrue(self.report.filter_journals)
        self.assertTrue(self.report.filter_analytic)
        self.assertTrue(self.report.filter_partner)
        self.assertTrue(self.report.search_bar)
        self.assertEqual(self.report.filter_hide_0_lines, 'by_default')
        self.assertEqual(self.report.filter_multi_company, 'selector')

    def test_options_generation(self):
        """Las opciones del reporte deben generarse sin errores."""
        options = self.report.get_options(previous_options={})
        self.assertIn('date', options)
        self.assertIn('columns', options)
        self.assertIn('column_groups', options)
        # FIX #1: ignore_totals_below_sections debe estar activo
        self.assertTrue(options.get('ignore_totals_below_sections'))

    def test_lines_generation(self):
        """_get_lines debe ejecutarse sin errores y devolver una lista."""
        options = self.report.get_options(previous_options={})
        lines = self.report._get_lines(options)
        self.assertIsInstance(lines, list)
        # Siempre debe haber al menos la línea de total
        self.assertGreaterEqual(len(lines), 1)

    def test_total_line(self):
        """La última línea debe ser el total general con class='total'."""
        options = self.report.get_options(previous_options={})
        lines = self.report._get_lines(options)
        total_line = lines[-1]
        self.assertEqual(total_line.get('class'), 'total')
        self.assertEqual(total_line.get('level'), 1)

    def test_no_duplicate_total_lines(self):
        """No debe haber líneas 'Total' duplicadas (fix #1)."""
        options = self.report.get_options(previous_options={})
        lines = self.report._get_lines(options)
        for i in range(1, len(lines)):
            prev_name = lines[i - 1].get('name', '')
            curr_name = lines[i].get('name', '')
            if prev_name and curr_name:
                # No debe haber "Total XXXX" justo después de "XXXX"
                if curr_name.startswith('Total '):
                    account_code = prev_name.split()[0]
                    total_code = curr_name.replace('Total ', '').split()[0]
                    self.assertNotEqual(
                        account_code, total_code,
                        msg='Duplicate total line found: "%s" followed by "%s"'
                        % (prev_name, curr_name),
                    )

    def test_format_partner_vat_nit(self):
        """El NIT colombiano debe formatearse correctamente."""
        fmt = self.handler._format_partner_vat
        # NIT con dígito de verificación
        self.assertEqual(fmt('9001234567', is_nit=True), '900.123.456-7')
        self.assertEqual(fmt('8009020661', is_nit=True), '800.902.066-1')
        # NIT vacío
        self.assertEqual(fmt('', is_nit=True), '')
        self.assertEqual(fmt(None, is_nit=False), '')

    def test_format_partner_vat_cc(self):
        """La cédula de ciudadanía NO debe formatearse como NIT."""
        fmt = self.handler._format_partner_vat
        # CC no debe tener puntos ni guion
        self.assertEqual(fmt('1037659041', is_nit=False), '1037659041')
        self.assertEqual(fmt('43585184', is_nit=False), '43585184')

    def test_menu_exists(self):
        """El menú del reporte debe existir en Audit Reports."""
        menu = self.env.ref(
            'l10n_co_accounting_reports.menu_partner_balance_report'
        )
        self.assertTrue(menu)
        self.assertEqual(
            menu.parent_id,
            self.env.ref('account_reports.account_reports_audit_reports_menu'),
        )
