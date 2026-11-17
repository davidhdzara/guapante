# -*- coding: utf-8 -*-
"""Frente 5, C0 (doc 58 §10): la colilla por recibo es un comprobante INTERNO, genérico y multicliente: sin QR, CUNE,
estado DIAN ni referencias a la Res. 13; sin estilos en línea; datos y moneda de la compañía del recibo."""
from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_importes import valores_monetarios

REPORTE = 'l10n_co_nomina_electronica.action_report_payslip_ne'
PROHIBIDOS = ('DIAN', 'Resolucion', 'Resolución', 'CUNE', 'Estado NE', '/report/barcode', 'QR', 'Firma del empleado')


@tagged('post_install', '-at_install')
class TestComprobanteColilla(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Colilla', 'country_id': cls.env.ref('base.co').id})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.a = cls._compania('Empresa Alfa Colilla', 'Empleado Alfa')
        cls.b = cls._compania('Empresa Beta Colilla', 'Empleado Beta')

    @classmethod
    def _compania(cls, nombre, empleado):
        company = cls.env['res.company'].create({
            'name': nombre, 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})
        emp = cls.env['hr.employee'].create({
            'name': empleado, 'company_id': company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = cls.env['hr.contract'].create({
            'name': 'Contrato %s' % empleado, 'employee_id': emp.id, 'company_id': company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        recibo = cls.env['hr.payslip'].create({
            'name': 'Recibo %s' % empleado, 'employee_id': emp.id, 'contract_id': contrato.id,
            'company_id': company.id, 'struct_id': cls.estructura.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        for codigo, total in (('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_NETO', 2880000.0)):
            regla = cls.env['hr.salary.rule'].search(
                [('code', '=', codigo), ('struct_id', '=', cls.estructura.id)], limit=1)
            cls.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                'contract_id': contrato.id, 'employee_id': emp.id, 'quantity': 1.0, 'rate': 100.0,
                'amount': total, 'total': total})
        return recibo

    def _html(self, recibo):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [recibo.id])
        return html.decode().replace('\xa0', ' ')

    def _cuerpo(self, recibo):
        """Solo el cuerpo de la colilla (sin el encabezado y pie del layout nativo de la compañía)."""
        return self._html(recibo).split('class="page"', 1)[-1]

    def test_la_colilla_es_un_comprobante_interno_sin_nada_de_la_dian(self):
        cuerpo = self._cuerpo(self.a)
        self.assertIn('Comprobante de pago', cuerpo)
        self.assertIn('Neto a pagar', cuerpo)
        for texto in PROHIBIDOS:
            self.assertNotIn(texto, cuerpo, 'La colilla no debe contener "%s"' % texto)
        self.assertNotIn('<img', cuerpo)      # sin QR ni imágenes

    def test_sin_estilos_en_linea_ni_colores_propios_en_el_cuerpo(self):
        cuerpo = self._cuerpo(self.a)
        self.assertNotIn('style=', cuerpo)
        self.assertNotIn('background-color', cuerpo)

    def test_multicliente_los_datos_son_de_la_compania_del_recibo(self):
        html_a, html_b = self._html(self.a), self._html(self.b)
        self.assertIn('Empleado Alfa', html_a)
        self.assertNotIn('Empleado Beta', html_a)
        self.assertNotIn('Empresa Beta Colilla', html_a)
        self.assertIn('Empleado Beta', html_b)
        self.assertNotIn('Empleado Alfa', html_b)
        self.assertNotIn('Empresa Alfa Colilla', html_b)

    def test_los_importes_usan_la_moneda_de_la_compania(self):
        euro = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'EUR')], limit=1)
        euro.active = True
        self.b.company_id.currency_id = euro
        html = self._html(self.b)
        self.assertIn('€', html)
        self.assertIn(2880000.0, valores_monetarios(html))

    def test_los_bloques_comunes_existen_para_reutilizarlos(self):
        for xmlid in ('ne_comprobante_encabezado', 'ne_comprobante_conceptos'):
            self.assertTrue(self.env.ref('l10n_co_nomina_electronica.' + xmlid, raise_if_not_found=False), xmlid)
