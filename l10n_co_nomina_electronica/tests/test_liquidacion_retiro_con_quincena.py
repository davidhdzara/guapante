# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""P0 (doc 111 §1): la liquidación paga solo los días del mes del retiro que ningún recibo de nómina confirmado haya pagado. Antes pagaba desde el día 1: salario y aportes dos veces.

Salario 3.000.000 (valor día 100.000); mes comercial de 30 días. Los esperados se calculan a mano."""

import re
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

INGRESO = date(2025, 1, 1)
PREFIJO = 'l10n_co_nomina_electronica.'


@tagged('post_install', '-at_install')
class TestLiquidacionRetiroConQuincena(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Retiro con Quincena'})
        cls.env = cls.company.with_company(cls.company).env
        cls.env.user.groups_id = [Command.link(cls.env.ref('hr_payroll.group_hr_payroll_manager').id)]
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Retiro con Quincena', 'country_id': cls.env.ref('base.co').id, 'default_schedule_pay': 'semi-monthly'})
        cls.general = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_nomina')
        cls.liquidacion = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_liquidacion')
        cls.prima = cls.env.ref(PREFIJO + 'hr_payroll_structure_co_prima')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _contrato(self, **extra):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Retirado %s' % self.n, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        return self.env['hr.contract'].create(dict({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Retirado %s' % self.n, 'employee_id': empleado.id,
            'company_id': self.company.id, 'structure_type_id': self.tipo.id, 'wage': 3000000.0, 'date_start': INGRESO, 'state': 'open'}, **extra))

    def _recibo(self, contrato, desde, hasta, estructura=None, **extra):
        type(self).n += 1
        return self.env['hr.payslip'].create(dict({
            'name': 'Recibo Retiro %s' % self.n, 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta}, **extra))

    def _pagado(self, contrato, desde, hasta, **extra):
        recibo = self._recibo(contrato, desde, hasta, **extra)
        recibo.write({'state': 'done'})
        return recibo

    def _liq(self, contrato, retiro):
        return self._recibo(contrato, contrato.date_start, retiro, estructura=self.liquidacion)

    def _total(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def _falla(self, liquidacion, *textos):
        with self.assertRaises(UserError) as error:
            liquidacion._ne_liq_validar_mes()
        for texto in textos:
            self.assertIn(texto, str(error.exception))

    # ── los días ─────────────────────────────────────────────────────
    def test_sin_recibos_del_mes_paga_desde_el_dia_1(self):
        self.assertEqual(self._liq(self._contrato(), date(2026, 5, 20))._ne_dias_pagables(), 20)

    def test_con_la_primera_quincena_pagada_solo_paga_lo_que_falta(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        liquidacion = self._liq(contrato, date(2026, 5, 20))
        liquidacion.compute_sheet()
        self.assertEqual(liquidacion._ne_tramo_pagable_periodo(), (date(2026, 5, 16), date(2026, 5, 20)))
        self.assertAlmostEqual(self._total(liquidacion, 'CO_LIQ_SALARIOS'), 500000.0, delta=0.01)
        self.assertEqual(self._total(liquidacion, 'CO_DIAS_SP'), 5)

    def test_con_todo_pagado_no_vuelve_a_pagar_dias_y_calcula(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        liquidacion = self._liq(contrato, date(2026, 5, 15))
        liquidacion.compute_sheet()
        self.assertEqual(liquidacion._ne_dias_pagables(), 0)
        self.assertEqual(self._total(liquidacion, 'CO_LIQ_SALARIOS'), 0.0)
        self.assertEqual(self._total(liquidacion, 'CO_DIAS_SP'), 0)

    def test_con_todo_pagado_el_xml_no_pide_dias_ni_al_aprendiz(self):
        casos = (('dependiente', {}), ('aprendiz', {'l10n_co_pila_tipo_cotizante': '19', 'l10n_co_ne_contract_type': '4', 'wage': 1750905.0}))
        for nombre, datos in casos:
            with self.subTest(nombre):
                contrato = self._contrato(**datos)
                self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
                liquidacion = self._liq(contrato, date(2026, 5, 15))
                liquidacion.compute_sheet()
                devengados, _deducciones = liquidacion._map_salary_rules_to_xml()
                self.assertNotIn('Basico', devengados)          # los días van en el recibo que los pagó: el documento del mes los suma

    def test_un_recibo_semanal_que_cruza_el_mes(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 4, 27), date(2026, 5, 3))
        self.assertEqual(self._liq(contrato, date(2026, 5, 20))._ne_dias_pagables(), 17)

    def test_el_31_no_se_paga_otra_vez(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 1, 1), date(2026, 1, 30))
        self.assertEqual(self._liq(contrato, date(2026, 1, 31))._ne_dias_pagables(), 0)

    def test_febrero_completa_el_mes_comercial(self):
        for hasta, esperado in ((date(2026, 2, 15), 15), (date(2026, 2, 27), 3)):
            with self.subTest(hasta=hasta):
                contrato = self._contrato()
                self._pagado(contrato, date(2026, 2, 1), hasta)
                self.assertEqual(self._liq(contrato, date(2026, 2, 28))._ne_dias_pagables(), esperado)

    def test_un_recibo_reembolsado_no_cuenta(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15), credit_note=True)
        self.assertEqual(self._liq(contrato, date(2026, 5, 20))._ne_dias_pagables(), 20)

    def test_los_recibos_de_otro_contrato_y_de_meses_anteriores_no_cuentan(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 4, 16), date(2026, 4, 30))
        self._pagado(self._contrato(), date(2026, 5, 1), date(2026, 5, 15))
        self.assertEqual(self._liq(contrato, date(2026, 5, 20))._ne_dias_pagables(), 20)

    # ── nada se adivina ──────────────────────────────────────────────
    def test_un_recibo_del_mes_sin_confirmar_detiene(self):
        contrato = self._contrato()
        borrador = self._recibo(contrato, date(2026, 5, 1), date(2026, 5, 15))
        self._falla(self._liq(contrato, date(2026, 5, 20)), 'sin confirmar', borrador.name)

    def test_un_pago_posterior_al_retiro_detiene_el_calculo(self):
        contrato = self._contrato()
        recibo = self._pagado(contrato, date(2026, 5, 16), date(2026, 5, 30))
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        with self.assertRaisesRegex(UserError, 'posteriores al retiro') as error:
            self._liq(contrato, date(2026, 5, 20)).compute_sheet()
        self.assertIn(recibo.name, str(error.exception))

    def test_un_hueco_sin_pagar_detiene(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 10))
        recibo = self._pagado(contrato, date(2026, 5, 16), date(2026, 5, 20))
        self._falla(self._liq(contrato, date(2026, 5, 25)), 'sin pagar', recibo.name)

    def test_una_prima_confirmada_del_semestre_detiene(self):
        contrato = self._contrato()
        prima = self._pagado(contrato, date(2026, 1, 1), date(2026, 6, 30), estructura=self.prima)
        self._falla(self._liq(contrato, date(2026, 5, 20)), 'prima', prima.name)
        self._liq(self._contrato(), date(2026, 5, 20))._ne_liq_validar_mes()          # sin prima ni recibos: nada que detener

    def test_la_prima_de_otro_semestre_no_detiene(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2025, 7, 1), date(2025, 12, 31), estructura=self.prima)
        self._liq(contrato, date(2026, 5, 20))._ne_liq_validar_mes()

    def test_confirmar_vuelve_a_comprobar_el_mes(self):
        contrato = self._contrato()
        liquidacion = self._liq(contrato, date(2026, 5, 20))
        liquidacion.compute_sheet()
        self._recibo(contrato, date(2026, 5, 1), date(2026, 5, 15))
        for nombre in ('_ne_validar_cuenta_neto', '_ne_validar_pacto_no_salarial', '_ne_validar_afiliaciones'):
            self.patch(type(liquidacion), nombre, lambda s: None)
        with self.assertRaisesRegex(UserError, 'sin confirmar'):
            liquidacion.action_payslip_done()

    def test_un_recibo_confirmado_despues_de_calcular_deja_la_hoja_desactualizada(self):
        contrato = self._contrato(l10n_co_ne_retention_procedure='2')
        self.env['l10n.co.retefuente.procedure2'].create({'contract_id': contrato.id, 'semester_start': date(2026, 1, 1), 'fixed_percentage': 1.0, 'months_considered': 12})
        liquidacion = self._liq(contrato, date(2026, 5, 20))
        liquidacion.compute_sheet()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        with self.assertRaisesRegex(UserError, 'no está al día'):
            liquidacion._ne_validar_hoja_al_dia()

    # ── lo restado queda protegido, en cualquier procedimiento ───────
    def test_lo_restado_no_se_anula_con_la_liquidacion_confirmada(self):
        contrato = self._contrato(l10n_co_ne_retention_procedure='2')
        self.env['l10n.co.retefuente.procedure2'].create({'contract_id': contrato.id, 'semester_start': date(2026, 1, 1), 'fixed_percentage': 1.0, 'months_considered': 12})
        quincena = self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        liquidacion = self._liq(contrato, date(2026, 5, 20))
        liquidacion.compute_sheet()
        self.assertEqual(liquidacion.l10n_co_ne_rete_sumados_ids, quincena)
        liquidacion.write({'state': 'done'})
        for operacion in ('action_payslip_cancel', 'refund_sheet'):
            with self.subTest(operacion=operacion), self.assertRaisesRegex(UserError, re.escape(liquidacion.number or liquidacion.name)):
                getattr(quincena, operacion)()
        self.assertEqual(quincena.state, 'done')

    def test_la_liquidacion_confirmada_conserva_sus_dias(self):
        contrato = self._contrato()
        self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        liquidacion = self._liq(contrato, date(2026, 5, 20))
        liquidacion.compute_sheet()
        liquidacion.write({'state': 'done'})
        self._pagado(contrato, date(2026, 5, 16), date(2026, 5, 18))          # confirmado después: el XML de la liquidación no cambia
        self.assertEqual(liquidacion._ne_dias_pagables(), 5)

    # ── el asistente avisa ───────────────────────────────────────────
    def _aviso(self, contrato, retiro):
        asistente = self.env['l10n.co.hr.liquidacion.wizard'].new({'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'date_end': retiro})
        return (asistente._onchange_ne_pagado_del_mes() or {}).get('warning', {}).get('message', '')

    def test_el_asistente_dice_hasta_cuando_esta_pagado_y_avisa_de_borradores(self):
        contrato = self._contrato()
        self.assertEqual(self._aviso(contrato, date(2026, 5, 20)), '')
        pagado = self._pagado(contrato, date(2026, 5, 1), date(2026, 5, 15))
        mensaje = self._aviso(contrato, date(2026, 5, 20))
        self.assertIn(pagado.name, mensaje)
        self.assertIn('15', mensaje)
        borrador = self._recibo(contrato, date(2026, 5, 16), date(2026, 5, 20))
        self.assertIn(borrador.name, self._aviso(contrato, date(2026, 5, 20)))
