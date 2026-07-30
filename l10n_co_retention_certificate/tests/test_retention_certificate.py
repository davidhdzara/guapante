# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRetentionCertificateReport(TransactionCase):
    """Tests del motor de datos del Certificado de Retenciones (Fase 2).

    Sigue el mismo patrón de
    l10n_co_accounting_reports/tests/test_partner_balance_report.py:
    tests estructurales livianos (reporte, columnas, filtros, generación
    de opciones/líneas sin errores) más un test de integración de extremo
    a extremo con una factura de proveedor real.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref(
            'l10n_co_retention_certificate.retention_certificate_report'
        )
        cls.handler = cls.env[
            'l10n_co.retention.certificate.report.handler'
        ]
        cls.company = cls.env.company

    # ------------------------------------------------------------------
    # Tests estructurales
    # ------------------------------------------------------------------

    def test_report_exists(self):
        self.assertTrue(self.report)
        self.assertEqual(
            self.report.custom_handler_model_name,
            'l10n_co.retention.certificate.report.handler',
        )

    def test_report_columns(self):
        expected_labels = ['concept_name', 'tax_base_amount', 'balance']
        self.assertEqual(len(self.report.column_ids), 3)
        self.assertEqual(
            self.report.column_ids.mapped('expression_label'),
            expected_labels,
        )

    def test_report_filters(self):
        self.assertTrue(self.report.filter_partner)
        self.assertTrue(self.report.filter_date_range)
        self.assertTrue(self.report.filter_unfold_all)
        self.assertTrue(self.report.search_bar)
        self.assertEqual(self.report.default_opening_date_filter, 'this_year')

    def test_options_generation(self):
        options = self.report.get_options(previous_options={})
        self.assertIn('date', options)
        self.assertIn('columns', options)
        self.assertIn('column_groups', options)

    def test_lines_generation_without_data(self):
        """No debe fallar aunque no haya ninguna retención en el período."""
        options = self.report.get_options(previous_options={})
        lines = self.report._get_lines(options)
        self.assertIsInstance(lines, list)
        self.assertGreaterEqual(len(lines), 1)

    def test_total_line(self):
        options = self.report.get_options(previous_options={})
        lines = self.report._get_lines(options)
        total_line = lines[-1]
        self.assertEqual(total_line.get('class'), 'total')
        self.assertEqual(total_line.get('level'), 1)

    def test_menu_exists(self):
        menu = self.env.ref(
            'l10n_co_retention_certificate.menu_retention_certificate_report'
        )
        self.assertTrue(menu)
        self.assertEqual(
            menu.parent_id,
            self.env.ref('l10n_co_reports.account_reports_co_statements_menu'),
        )

    # ------------------------------------------------------------------
    # Test de integración de extremo a extremo
    # ------------------------------------------------------------------

    def _get_or_create_account(self, code, account_type='liability_current'):
        # get-or-create: estas pruebas también corren contra clones de la
        # BD real de Guapante (staging_dev), donde algunos códigos PUC de
        # ejemplo ya podrían existir.
        account = self.env['account.account'].search([
            ('code', '=', code),
            ('company_ids', 'in', self.company.id),
        ], limit=1)
        if account:
            return account
        return self.env['account.account'].create({
            'name': 'Test %s' % code,
            'code': code,
            'account_type': account_type,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _create_classified_purchase_tax(self, name, amount, retention_type, account_code):
        account = self._get_or_create_account(account_code)
        return self.env['account.tax'].create({
            'name': 'TEST %s' % name,
            'amount_type': 'percent',
            'amount': amount,
            'type_tax_use': 'purchase',
            'company_id': self.company.id,
            'l10n_co_retention_type': retention_type,
            'invoice_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'account_id': account.id,
                }),
            ],
        })

    def test_end_to_end_partner_with_retention_appears(self):
        """Una factura de proveedor con retención clasificada debe generar
        una línea de Nivel 1 (tercero) con el monto correcto, y al
        desplegar debe verse el tipo (Nivel 2) y el concepto (Nivel 3).
        """
        tax = self._create_classified_purchase_tax(
            'RteFte Test (3.5%)', amount=-3.5,
            retention_type='retefuente', account_code='23659999',
        )
        partner = self.env['res.partner'].create({
            'name': 'Proveedor Test Certificado',
            'vat': '900123456',
        })
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba',
                'quantity': 1,
                'price_unit': 1000000.0,
                'tax_ids': [(6, 0, [tax.id])],
            })],
        })
        move.action_post()

        options = self.report.get_options(previous_options={
            'date': {
                'date_from': fields.Date.today().replace(month=1, day=1),
                'date_to': fields.Date.today().replace(month=12, day=31),
                'mode': 'range',
            },
            'unfold_all': True,
        })
        lines = self.report._get_lines(options)

        partner_lines = [
            line for line in lines
            if partner.name in (line.get('name') or '')
        ]
        self.assertTrue(
            partner_lines,
            'El proveedor con retención clasificada debe aparecer en el '
            'certificado (Nivel 1).',
        )

        type_lines = [
            line for line in lines
            if line.get('parent_id') == partner_lines[0]['id']
        ]
        self.assertTrue(
            type_lines,
            'Debe existir al menos una línea de Nivel 2 (tipo de retención) '
            'bajo el tercero.',
        )
        self.assertIn('Retención en la Fuente', [tl['name'] for tl in type_lines])

        concept_lines = [
            line for line in lines
            if line.get('parent_id') == type_lines[0]['id']
        ]
        self.assertTrue(
            concept_lines,
            'Debe existir al menos una línea de Nivel 3 (concepto/impuesto) '
            'bajo el tipo de retención.',
        )
        self.assertEqual(concept_lines[0]['name'], tax.name)

    def test_unclassified_tax_does_not_appear(self):
        """Un impuesto de compra sin l10n_co_retention_type no debe generar
        ninguna línea en el certificado (regla de la Fase 1: sin
        clasificar = no aparece).
        """
        account = self._get_or_create_account('23659998')
        tax = self.env['account.tax'].create({
            'name': 'TEST Descuento Sin Clasificar',
            'amount_type': 'percent',
            'amount': -1.0,
            'type_tax_use': 'purchase',
            'company_id': self.company.id,
            'invoice_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'account_id': account.id,
                }),
            ],
        })
        self.assertFalse(tax.l10n_co_retention_type)

        partner = self.env['res.partner'].create({
            'name': 'Proveedor Sin Clasificar Test',
            'vat': '900654321',
        })
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba',
                'quantity': 1,
                'price_unit': 500000.0,
                'tax_ids': [(6, 0, [tax.id])],
            })],
        })
        move.action_post()

        options = self.report.get_options(previous_options={
            'date': {
                'date_from': fields.Date.today().replace(month=1, day=1),
                'date_to': fields.Date.today().replace(month=12, day=31),
                'mode': 'range',
            },
            'unfold_all': True,
        })
        lines = self.report._get_lines(options)
        partner_lines = [
            line for line in lines
            if partner.name in (line.get('name') or '')
        ]
        self.assertFalse(
            partner_lines,
            'Un proveedor cuya única retención no está clasificada no debe '
            'aparecer en el certificado.',
        )
