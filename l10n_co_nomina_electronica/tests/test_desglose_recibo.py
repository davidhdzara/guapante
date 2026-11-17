# -*- coding: utf-8 -*-
"""Frente 5, C1 (doc 58 §3): ``hr.payslip._ne_desglose()``. Valores calculados a mano; todo sale de las líneas que ya
trae el recibo (nada se recalcula) y devengado - deducciones = neto en los recibos que cuadran."""
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesgloseRecibo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Desglose', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Desglose', 'country_id': cls.env.ref('base.co').id})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Desglose', 'company_id': cls.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato Desglose', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})

    def _recibo(self, estructura, *lineas, pagado=None):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % estructura.name, 'employee_id': self.empleado.id,
            'contract_id': self.contrato.id, 'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 15)})
        for codigo, total in lineas:
            regla = self.env['hr.salary.rule'].search(
                [('code', '=', codigo), ('struct_id', '=', estructura.id)], limit=1)
            self.assertTrue(regla, 'Falta la regla %s en %s' % (codigo, estructura.name))
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                'contract_id': self.contrato.id, 'employee_id': self.empleado.id, 'quantity': 1.0, 'rate': 100.0,
                'amount': total, 'total': total})
        if pagado:
            recibo.write({'state': 'done', 'paid_date': pagado})
        return recibo

    def _estructura(self, xmlid):
        return self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_' + xmlid)

    def test_quincena_con_salud_pension_fsp_retencion_y_otra_deduccion(self):
        recibo = self._recibo(
            self._estructura('co_nomina'), ('CO_BASICO', 3000000.0), ('CO_AUX_TRANS', 200000.0),
            ('CO_SALUD_EMP', -120000.0), ('CO_PENSION_EMP', -120000.0), ('CO_FSP', -30000.0),
            ('CO_RETEFUENTE', -50000.0), ('CO_SINDICATO', -10000.0), ('CO_NETO', 2870000.0), pagado=date(2026, 6, 15))
        d = recibo._ne_desglose()
        self.assertEqual(d['recibo'], recibo)
        self.assertEqual(d['origen'], recibo.struct_id.name)
        self.assertEqual(d['paid_date'], date(2026, 6, 15))
        self.assertEqual((d['devengado'], d['deducciones']), (3200000.0, 330000.0))
        self.assertEqual((d['salud'], d['pension'], d['fsp'], d['retencion']), (120000.0, 120000.0, 30000.0, 50000.0))
        self.assertEqual(d['otras_deducciones'], 10000.0)
        self.assertEqual(d['neto'], 2870000.0)
        self.assertEqual(d['diferencia'], 0.0)                    # devengado - deducciones = neto

    def test_prima_sin_salud_ni_pension_y_con_su_retencion(self):
        recibo = self._recibo(
            self._estructura('co_prima'), ('CO_PRIMA_VALOR', 1500000.0), ('CO_PRIMA_RETE', -60000.0),
            ('CO_PRIMA_NETO', 1440000.0))
        d = recibo._ne_desglose()
        self.assertEqual((d['salud'], d['pension'], d['fsp']), (0.0, 0.0, 0.0))
        self.assertEqual((d['devengado'], d['retencion'], d['neto']), (1500000.0, 60000.0, 1440000.0))
        self.assertEqual(d['diferencia'], 0.0)

    def test_liquidacion_y_bonificacion_con_su_retencion_propia(self):
        liq = self._recibo(
            self._estructura('co_liquidacion'), ('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_SALUD', -36000.0),
            ('CO_LIQ_PENSION', -36000.0), ('CO_LIQ_RETE', -10000.0), ('CO_LIQ_NETO', 818000.0))
        d = liq._ne_desglose()
        self.assertEqual((d['salud'], d['pension'], d['retencion'], d['neto']), (36000.0, 36000.0, 10000.0, 818000.0))
        bon = self._recibo(
            self._estructura('co_bonificacion'), ('CO_BON_VALOR', 500000.0), ('CO_BON_SALUD', -20000.0),
            ('CO_BON_PENSION', -20000.0), ('CO_BON_RETE', -5000.0), ('CO_BON_NETO', 455000.0))
        d = bon._ne_desglose()
        self.assertEqual((d['devengado'], d['retencion'], d['neto'], d['diferencia']),
                         (500000.0, 5000.0, 455000.0, 0.0))

    def test_las_lineas_nativas_y_los_totales_no_cuentan(self):
        recibo = self._recibo(
            self._estructura('co_nomina'), ('BASIC', 3000000.0), ('GROSS', 3000000.0), ('NET', 3000000.0),
            ('CO_BASICO', 3000000.0), ('CO_BRUTO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_NETO', 2880000.0))
        d = recibo._ne_desglose()
        self.assertEqual((d['devengado'], d['deducciones'], d['neto']), (3000000.0, 120000.0, 2880000.0))

    def test_una_deduccion_sin_clasificar_va_a_otras_y_el_desglose_siempre_se_explica(self):
        recibo = self._recibo(
            self._estructura('co_nomina'), ('CO_BASICO', 3000000.0), ('CO_EMBARGO', -200000.0), ('CO_NETO', 2800000.0))
        d = recibo._ne_desglose()
        self.assertEqual(d['otras_deducciones'], 200000.0)
        self.assertEqual(d['salud'] + d['pension'] + d['fsp'] + d['retencion'] + d['otras_deducciones'],
                         d['deducciones'])

    def test_un_recibo_que_no_cuadra_expone_la_diferencia_en_vez_de_ocultarla(self):
        recibo = self._recibo(self._estructura('co_nomina'), ('CO_BASICO', 3000000.0), ('CO_NETO', 2900000.0))
        self.assertEqual(recibo._ne_desglose()['diferencia'], 100000.0)

    def test_sin_fecha_de_pago_el_desglose_no_falla_y_da_false(self):
        recibo = self._recibo(self._estructura('co_nomina'), ('CO_BASICO', 1000.0), ('CO_NETO', 1000.0))
        self.assertFalse(recibo._ne_desglose()['paid_date'])
        recibo.write({'state': 'done', 'paid_date': False})
        self.assertFalse(recibo._ne_desglose()['paid_date'])

    def test_no_recalcula_ni_escribe(self):
        recibo = self._recibo(self._estructura('co_nomina'), ('CO_BASICO', 3000000.0), ('CO_NETO', 3000000.0))
        antes = recibo.line_ids.mapped('total')
        with patch.object(type(recibo), 'compute_sheet', side_effect=AssertionError('no debe recalcular')):
            recibo._ne_desglose()
        self.assertEqual(recibo.line_ids.mapped('total'), antes)
