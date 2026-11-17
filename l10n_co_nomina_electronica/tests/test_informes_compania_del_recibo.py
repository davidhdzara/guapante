# -*- coding: utf-8 -*-
"""Frente 6, P6-4 (doc 59 3 B5, F6-INF-001): los informes con el diseno de la compania (colilla y comprobante de pago; la representacion
grafica fija la compania del documento en su propio diseno y lo cubre test_representacion_grafica_informe) llevan los datos de la compania del RECIBO/documento, no los de la compania
activa del usuario. Dos companias colombianas; usuario con ambas y la otra como activa."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture

PIE_A = 'PieActivaAlcanceInforme'
PIE_B = 'PieDelReciboAlcanceInforme'


@tagged('post_install', '-at_install')
class TestInformesCompaniaDelRecibo(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Informe Recibo')        # la compania del recibo (B)
        cls.company.report_footer = PIE_B
        cls.activa = cls.env['res.company'].create({
            'name': 'Compañía Informe Activa', 'country_id': cls.env.ref('base.co').id, 'report_footer': PIE_A})
        cls.usuario = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Informe Multi', 'login': 'informe_multi', 'email': 'informe_multi@example.com',
            'company_id': cls.activa.id, 'company_ids': [(6, 0, (cls.activa | cls.company).ids)],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('hr_payroll.group_hr_payroll_manager').id])]})

    def _html(self, reporte, registro):
        reporte = self.env.ref(reporte)
        env = self.env(user=self.usuario, context=dict(allowed_company_ids=(self.activa | self.company).ids))
        html, _tipo = env['ir.actions.report']._render_qweb_html(reporte.report_name, registro.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _lineas_de_neto(self, doc):
        """Los informes exigen un recibo calculado (linea de neto): se cargan las lineas CO como en test_comprobante_colilla."""
        for recibo in doc.payslip_ids:
            for codigo, total in (('CO_BASICO', 1500000.0), ('CO_NETO', 1500000.0)):
                regla = self.env['hr.salary.rule'].search(
                    [('code', '=', codigo), ('struct_id', '=', recibo.struct_id.id)], limit=1)
                self.env['hr.payslip.line'].create({
                    'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                    'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id,
                    'quantity': 1.0, 'rate': 100.0, 'amount': total, 'total': total})

    def _verifica(self, html):
        self.assertIn(PIE_B, html)
        self.assertNotIn(PIE_A, html)

    def test_colilla_y_comprobante_llevan_la_compania_del_recibo(self):
        doc = self._documento(date(2024, 3, 1))
        recibo = doc.payslip_ids[:1]
        self._lineas_de_neto(doc)
        self._verifica(self._html('l10n_co_nomina_electronica.action_report_payslip_ne', recibo))
        self._verifica(self._html('l10n_co_nomina_electronica.action_report_comprobante_pago', recibo))
