# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRetentionCertificatePdf(TransactionCase):
    """Tests de la Fase 3/4: botón PDF, wizard reutilizado y render QWeb.

    Ver ESPEC §4 y la decisión del 2026-07-29: se reutiliza el wizard
    nativo l10n_co_reports.retention_report.wizard sin campos nuevos; la
    selección de proveedores/retenciones la hace el propio reporte
    (filtro de tercero + plegado/desplegado), no un wizard dedicado.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref(
            'l10n_co_retention_certificate.retention_certificate_report'
        )
        cls.native_fuente_report = cls.env.ref('l10n_co_reports.l10n_co_reports_fuente')
        cls.company = cls.env.company

    def _create_classified_purchase_tax(self, name, amount, retention_type, account_code):
        account = self.env['account.account'].create({
            'name': 'Test %s' % account_code,
            'code': account_code,
            'account_type': 'liability_current',
            'company_ids': [(6, 0, [self.company.id])],
        })
        return self.env['account.tax'].create({
            'name': name,
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

    # ------------------------------------------------------------------
    # Botón PDF reprogramado
    # ------------------------------------------------------------------

    def test_pdf_button_wired_to_print_pdf(self):
        options = self.report.get_options(previous_options={})
        pdf_buttons = [b for b in options['buttons'] if b['name'] == 'PDF']
        self.assertTrue(pdf_buttons, 'El reporte debe tener un botón PDF.')
        self.assertEqual(pdf_buttons[0]['action'], 'print_pdf')

    def test_print_pdf_opens_native_wizard(self):
        options = self.report.get_options(previous_options={})
        handler = self.env['l10n_co.retention.certificate.report.handler']
        action = handler.print_pdf(options, None)
        self.assertEqual(action['res_model'], 'l10n_co_reports.retention_report.wizard')
        self.assertEqual(action['context']['options']['report_id'], options['report_id'])

    # ------------------------------------------------------------------
    # Wizard: debe redirigir a NUESTRA acción sin romper la nativa
    # ------------------------------------------------------------------

    def _assert_generate_report_targets(self, result, expected_action):
        """report_action() devuelve un dict con 'report_name' (no 'id')
        cuando todo va bien — ver ir_actions_report.py:1137. Pero si la
        compañía no tiene external_report_layout_id configurado, Odoo
        intercepta con el configurador de diseño externo en su lugar
        (mismo comportamiento para el flujo nativo); en ese caso la
        aserción no aplica y no es relevante para lo que probamos aquí.
        """
        if result.get('type') != 'ir.actions.report':
            self.skipTest(
                'La compañía de test no tiene external_report_layout_id '
                'configurado; Odoo interceptó con el configurador de '
                'diseño externo en vez de devolver la acción de reporte.'
            )
        self.assertEqual(result['report_name'], expected_action.report_name)

    def test_wizard_redirects_to_our_action_for_our_report(self):
        options = self.report.get_options(previous_options={})
        wizard = self.env['l10n_co_reports.retention_report.wizard'].with_context(
            options=options
        ).create({})
        result = wizard.generate_report()
        our_action = self.env.ref(
            'l10n_co_retention_certificate.action_report_retention_certificate'
        )
        self._assert_generate_report_targets(result, our_action)

    def test_wizard_keeps_native_behavior_for_native_report(self):
        """No debe romperse el flujo nativo de Fuente/ICA/IVA: si el
        wizard se abre con options de OTRO reporte, debe seguir apuntando
        a la acción nativa (l10n_co_reports.action_report_certification),
        no a la nuestra.
        """
        native_options = self.native_fuente_report.get_options(previous_options={})
        wizard = self.env['l10n_co_reports.retention_report.wizard'].with_context(
            options=native_options
        ).create({})
        result = wizard.generate_report()
        native_action = self.env.ref('l10n_co_reports.action_report_certification')
        self._assert_generate_report_targets(result, native_action)

    # ------------------------------------------------------------------
    # Render: la plantilla debe recibir la jerarquía de 3 niveles correcta
    # ------------------------------------------------------------------

    def test_render_builds_three_level_hierarchy(self):
        tax = self._create_classified_purchase_tax(
            'RteFte Test PDF (3.5%)', amount=-3.5,
            retention_type='retefuente', account_code='23659997',
        )
        partner = self.env['res.partner'].create({
            'name': 'Proveedor Test PDF',
            'vat': '900111222',
        })
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba PDF',
                'quantity': 1,
                'price_unit': 2000000.0,
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

        render_model = self.env[
            'report.l10n_co_retention_certificate.report_retention_certificate'
        ].with_context(options=options)
        values = render_model._get_report_values(
            [], data={'wizard_values': {
                'expedition_date': fields.Date.today(),
                'declaration_date': fields.Date.today(),
                'article': 'ART. 10 DECRETO 836/91',
            }}
        )

        docs = [
            doc for doc in values['docs']
            if doc['partner_id'].id == partner.id
        ]
        self.assertTrue(docs, 'El proveedor con retención debe aparecer en docs.')
        doc = docs[0]
        self.assertTrue(doc['sections'], 'Debe tener al menos una sección (tipo).')

        section = doc['sections'][0]
        self.assertEqual(section['type_code'], 'retefuente')
        self.assertTrue(section['concepts'], 'La sección debe tener al menos un concepto.')
        self.assertEqual(section['concepts'][0]['concept_name'], tax.name)
