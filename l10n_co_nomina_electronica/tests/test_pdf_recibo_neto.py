# -*- coding: utf-8 -*-
"""PDF del recibo: NETO A PAGAR sale de la linea de neto de la estructura, y no suma las
lineas nativas BASIC/GROSS/NET ni las filas de total (CO_BRUTO, CO_*_NETO).

Incidente evitado (recibo de liquidacion 8092 de staging_main): el PDF listaba BASIC, GROSS
y NET (1.800.000 cada una) y la fila de neto, y "NETO A PAGAR" sumaba todo (12.735.356) en vez
de 3.667.678. Las pruebas con lineas sinteticas fijan valores calculados a mano; las dos de
consistencia usan compute_sheet() real.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

REPORTE = 'l10n_co_nomina_electronica.action_report_payslip_ne'


@tagged('post_install', '-at_install')
class TestPdfReciboNeto(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba PDF Neto'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura PDF', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.est_general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.est_liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.est_prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.est_bonificacion = ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')

    def _recibo(self, estructura, name='Recibo', date_from=date(2026, 9, 1),
                date_to=date(2026, 9, 30)):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date_from, 'date_to': date_to})

    def _linea(self, slip, code, total):
        regla = self.env['hr.salary.rule'].search(
            [('code', '=', code), ('struct_id', '=', slip.struct_id.id)], limit=1)
        self.assertTrue(regla, 'Falta la regla %s en %s' % (code, slip.struct_id.name))
        return self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': regla.id, 'code': code, 'name': code,
            'contract_id': slip.contract_id.id, 'employee_id': slip.employee_id.id,
            'quantity': 1.0, 'rate': 100.0, 'amount': total, 'total': total})

    def _html(self, slip):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [slip.id])
        return html.decode()

    def _con_nativas(self, slip):
        """Las lineas que Odoo agrega a toda estructura, con el valor de las categorias
        nativas (el neto nativo queda igual al basico)."""
        for code in ('BASIC', 'GROSS', 'NET'):
            self._linea(slip, code, 1800000.0)

    def test_liquidacion_no_imprime_nativas_ni_filas_de_total_y_neto_es_el_de_la_linea(self):
        slip = self._recibo(self.est_liquidacion)
        self._con_nativas(slip)
        for code, total in (('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_PRIMA', 600000.0),
                            ('CO_LIQ_CESANTIAS', 1400000.0), ('CO_LIQ_SALUD', -36000.0),
                            ('CO_LIQ_PENSION', -36000.0), ('CO_LIQ_NETO', 2828000.0)):
            self._linea(slip, code, total)
        html = self._html(slip)
        self.assertNotIn('>BASIC<', html)
        self.assertNotIn('>GROSS<', html)
        self.assertNotIn('>NET<', html)
        self.assertNotIn('>CO_LIQ_NETO<', html)
        self.assertNotIn('1,800,000', html)
        self.assertIn('>CO_LIQ_SALARIOS<', html)    # los conceptos reales siguen
        self.assertIn('$ 2,900,000', html)          # devengado: 900.000 + 600.000 + 1.400.000
        self.assertIn('$ 72,000', html)             # deducciones: 36.000 + 36.000
        self.assertIn('$ 2,828,000', html)          # NETO A PAGAR = CO_LIQ_NETO

    def test_nomina_general_sin_fila_de_bruto_ni_neto(self):
        slip = self._recibo(self.est_general)
        self._con_nativas(slip)
        for code, total in (('CO_BASICO', 3000000.0), ('CO_BRUTO', 3000000.0),
                            ('CO_SALUD_EMP', -120000.0), ('CO_PENSION_EMP', -120000.0),
                            ('CO_NETO', 2760000.0)):
            self._linea(slip, code, total)
        html = self._html(slip)
        self.assertNotIn('>CO_BRUTO<', html)
        self.assertNotIn('>CO_NETO<', html)
        self.assertIn('>CO_BASICO<', html)
        self.assertIn('$ 3,000,000', html)
        self.assertIn('$ 240,000', html)
        self.assertIn('$ 2,760,000', html)

    def test_prima_y_bonificacion_usan_su_propia_linea_de_neto(self):
        prima = self._recibo(self.est_prima, 'Prima')
        self._con_nativas(prima)
        for code, total in (('CO_PRIMA_VALOR', 1500000.0), ('CO_PRIMA_RETE', -60000.0),
                            ('CO_PRIMA_NETO', 1440000.0)):
            self._linea(prima, code, total)
        self.assertEqual(prima._ne_pdf_neto(), 1440000.0)
        self.assertIn('$ 1,440,000', self._html(prima))

        bon = self._recibo(self.est_bonificacion, 'Bonificacion')
        self._con_nativas(bon)
        for code, total in (('CO_BON_VALOR', 500000.0), ('CO_BON_SALUD', -20000.0),
                            ('CO_BON_NETO', 480000.0)):
            self._linea(bon, code, total)
        self.assertEqual(bon._ne_pdf_neto(), 480000.0)
        self.assertIn('$ 480,000', self._html(bon))

    def test_lineas_del_pdf_excluyen_solo_nativas_y_totales(self):
        slip = self._recibo(self.est_liquidacion)
        self._con_nativas(slip)
        self._linea(slip, 'CO_LIQ_SALARIOS', 900000.0)
        self._linea(slip, 'CO_LIQ_NETO', 900000.0)
        self.assertEqual(slip._ne_pdf_lineas().mapped('code'), ['CO_LIQ_SALARIOS'])

    def test_sin_linea_de_neto_falla_con_mensaje_claro(self):
        slip = self._recibo(self.est_liquidacion, 'SinCalcular')
        self._linea(slip, 'CO_LIQ_SALARIOS', 900000.0)
        with self.assertRaises(UserError) as cm:
            self._html(slip)
        self.assertIn('línea de neto', str(cm.exception))

    def test_consistencia_conceptos_mostrados_igual_neto_en_liquidacion_real(self):
        slip = self._recibo(self.est_liquidacion, 'ConsistenciaLiq', date(2024, 1, 1),
                            date(2026, 8, 15))
        slip.compute_sheet()
        mostrado = sum(slip._ne_pdf_lineas().mapped('total'))
        self.assertAlmostEqual(mostrado, slip._ne_pdf_neto(), delta=1.0)

    def test_consistencia_conceptos_mostrados_igual_neto_en_nomina_real(self):
        slip = self._recibo(self.est_general, 'ConsistenciaNomina')
        slip.compute_sheet()
        mostrado = sum(slip._ne_pdf_lineas().mapped('total'))
        self.assertAlmostEqual(mostrado, slip._ne_pdf_neto(), delta=1.0)
