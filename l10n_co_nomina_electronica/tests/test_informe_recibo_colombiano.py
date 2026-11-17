# -*- coding: utf-8 -*-
"""E-7 (doc 59 §24): en companias colombianas el informe nativo «Payslip» imprime la colilla propia (el nativo mostraba BASIC/GROSS/NET
contradictorios con el neto real y el marcador «xxxxxxxx»). Solo cuando el informe pedido es uno de los 2 nativos de recibo y TODOS los
recibos son de companias CO; cualquier otro informe, otro pais o un lote mixto: nativo; ante cualquier error de la decision: nativo."""

from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

NATIVO = 'hr_payroll.report_payslip_lang'
NATIVO_LIGERO = 'hr_payroll.report_light_payslip_lang'


@tagged('post_install', '-at_install')
class TestInformeReciboColombiano(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tipo = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_type_co')
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.propio = cls.env.ref('l10n_co_nomina_electronica.action_report_payslip_ne')
        cls.company = cls._compania('Compañía Informe Colombiano A')
        cls.otra = cls._compania('Compañía Informe Colombiano B')
        cls.Informe = cls.env['ir.actions.report']

    @classmethod
    def _compania(cls, nombre):
        return cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': nombre})

    def _recibo(self, company, calcular=True):
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Informe %s' % company.id, 'company_id': company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Informe %s' % company.id, 'employee_id': empleado.id, 'company_id': company.id,
            'structure_type_id': self.tipo.id, 'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00', 'wage': 1750905.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Informe %s' % company.id, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': company.id, 'struct_id': self.general.id, 'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 15)})
        if calcular:
            recibo.compute_sheet()
        return recibo

    # ── la redireccion ───────────────────────────────────────────────
    def test_el_informe_nativo_de_un_recibo_colombiano_imprime_la_colilla_propia(self):
        recibo = self._recibo(self.company)
        for nombre in (NATIVO, NATIVO_LIGERO):
            html, _tipo = self.Informe._render_qweb_html(nombre, [recibo.id])
            html = html.decode() if isinstance(html, bytes) else html
            self.assertIn('Comprobante de pago', html, nombre)          # el encabezado de la colilla propia
            self.assertNotIn('Basic Salary', html, nombre)             # la linea nativa BASIC no aparece
            self.assertNotIn('xxxxxxxx', html, nombre)

    def test_la_decision_devuelve_el_informe_propio_solo_para_recibos_colombianos(self):
        recibo = self._recibo(self.company, calcular=False)
        for nombre in (NATIVO, NATIVO_LIGERO):
            self.assertEqual(self.Informe._ne_informe_propio_si_es_recibo_colombiano(nombre, [recibo.id]), self.propio)
            self.assertEqual(self.Informe._ne_informe_propio_si_es_recibo_colombiano(nombre, recibo.id), self.propio)

    def test_una_compania_no_colombiana_conserva_el_informe_nativo(self):
        recibo = self._recibo(self.company, calcular=False)
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            self.assertFalse(self.Informe._ne_informe_propio_si_es_recibo_colombiano(NATIVO, [recibo.id]))

    def test_un_lote_mixto_conserva_el_informe_nativo(self):
        colombiano, otro = self._recibo(self.company, calcular=False), self._recibo(self.otra, calcular=False)
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: s == self.company):
            self.assertFalse(self.Informe._ne_informe_propio_si_es_recibo_colombiano(NATIVO, [colombiano.id, otro.id]))
            self.assertEqual(self.Informe._ne_informe_propio_si_es_recibo_colombiano(NATIVO, [colombiano.id]), self.propio)

    # ── no afecta a otros informes ───────────────────────────────────
    def test_otros_informes_no_se_redirigen(self):
        recibo = self._recibo(self.company, calcular=False)
        otros = [self.propio, self.env.ref('hr_payroll.action_report_register', raise_if_not_found=False),
                 self.env.ref('account.account_invoices', raise_if_not_found=False)]
        for informe in filter(None, otros):
            self.assertFalse(
                self.Informe._ne_informe_propio_si_es_recibo_colombiano(informe, [recibo.id]), informe.report_name)

    def test_una_referencia_invalida_o_sin_ids_cae_al_nativo_sin_romper(self):
        recibo = self._recibo(self.company, calcular=False)
        self.assertFalse(self.Informe._ne_informe_propio_si_es_recibo_colombiano('no.existe.informe', [recibo.id]))
        self.assertFalse(self.Informe._ne_informe_propio_si_es_recibo_colombiano(NATIVO, []))
        self.assertFalse(self.Informe._ne_informe_propio_si_es_recibo_colombiano(NATIVO, [999999999]))

    def test_el_informe_propio_se_renderiza_igual_pidiendolo_directamente(self):
        recibo = self._recibo(self.company)
        html, _tipo = self.Informe._render_qweb_html(self.propio.report_name, [recibo.id])
        self.assertIn('Comprobante de pago', html.decode() if isinstance(html, bytes) else html)

    # ── estructuras ──────────────────────────────────────────────────
    def test_las_cuatro_estructuras_propias_imprimen_la_colilla_propia(self):
        for xmlid in ('hr_payroll_structure_co_nomina', 'hr_payroll_structure_co_liquidacion',
                      'hr_payroll_structure_co_prima', 'hr_payroll_structure_co_bonificacion'):
            self.assertEqual(self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).report_id, self.propio, xmlid)

    def test_el_pdf_por_estructura_de_un_recibo_colombiano_es_el_propio(self):
        recibo = self._recibo(self.company, calcular=False)
        self.assertEqual(list(recibo._get_pdf_reports().keys()), [self.propio])

    def test_la_funcion_de_datos_respeta_un_informe_elegido_a_mano(self):
        elegido = self.env.ref('hr_payroll.action_report_register')
        self.general.report_id = elegido
        self.env['hr.payroll.structure']._ne_alinear_informe_recibo()
        self.assertEqual(self.general.report_id, elegido)
        self.general.report_id = self.env.ref('hr_payroll.action_report_payslip')     # el nativo si se alinea
        self.env['hr.payroll.structure']._ne_alinear_informe_recibo()
        self.assertEqual(self.general.report_id, self.propio)
