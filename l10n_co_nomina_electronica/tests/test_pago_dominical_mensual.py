# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-07 (doc 92; decisiones D-07 del TL del 22-nov): la compañia elige como se pagan las horas de la JORNADA ORDINARIA en dia de descanso obligatorio (recargo dominical/festivo diurno y nocturno) a quien tiene
salario mensual: «dia ordinario + recargo» (concepto MinTrabajo 24429 de 2026; la decision D1 de David del 17-nov, lo que se pagaba) o «solo el recargo» (CSJ SL3567-2019: el dia de descanso ya esta en el sueldo
mensual). Una sola decision, ``HrPayslip._ne_factor_dominical``; las horas EXTRA dominicales no cambian; sin elegir, un error que dice donde. La migracion deja las companias colombianas que ya existian en
«dia ordinario + recargo».

Valores a mano (agosto de 2026): sueldo 3.000.000, divisor 210 (jornada de 42 h desde el 15-jul-2026, Ley 2101/2021) -> valor hora 14.285,71; recargo del 90 % desde el 1-jul-2026 (Ley 2466/2025 art. 14): factores
HRDDF 1,90 y HRNDF 2,25; ocho horas de cada concepto."""

import importlib.util
import os
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

HORAS = 8.0
VALOR_HORA = 3000000.0 / 210


@tagged('post_install', '-at_install')
class TestPagoDominicalMensual(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Dominical Mensual'})
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Dominical', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, forma='dia_mas_recargo'):
        self.company.l10n_co_ne_pago_dominical_mensual = forma
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Dominical %s' % forma, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Dominical', 'employee_id': empleado.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        contrato.generate_work_entries(date(2026, 8, 1), date(2026, 8, 31))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Dominical', 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2026, 8, 1), 'date_to': date(2026, 8, 31)})
        entradas = []
        for codigo in ('CO_HRDDF', 'CO_HRNDF', 'CO_HEDDF', 'CO_HENDF'):
            tipo = self.env['hr.payslip.input.type'].search([('code', '=', codigo)], limit=1)
            self.assertTrue(tipo, codigo)
            entradas.append((0, 0, {'input_type_id': tipo.id, 'amount': HORAS}))
        recibo.write({'input_line_ids': entradas})
        return recibo

    def _total(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def test_las_premisas_de_los_factores_y_el_divisor(self):
        recibo = self._recibo()
        fecha = date(2026, 8, 1)
        self.assertEqual(recibo._rule_parameter('l10n_co_horas_mensuales', fecha), 210)
        self.assertAlmostEqual(recibo._rule_parameter('l10n_co_factor_hrddf', fecha), 1.90, places=4)
        self.assertAlmostEqual(recibo._rule_parameter('l10n_co_factor_hrndf', fecha), 2.25, places=4)

    def test_dia_mas_recargo_es_lo_que_se_pagaba(self):
        """HRDDF 8 x 14.285,71 x 1,90 = 217.142,86; HRNDF x 2,25 = 257.142,86; HEDDF y HENDF (extra) con su factor total."""
        recibo = self._recibo('dia_mas_recargo')
        recibo.compute_sheet()
        self.assertAlmostEqual(self._total(recibo, 'CO_HRDDF'), 217142.86, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_HRNDF'), 257142.86, delta=0.01)
        for codigo, parametro in (('CO_HEDDF', 'l10n_co_factor_heddf'), ('CO_HENDF', 'l10n_co_factor_hendf')):
            self.assertAlmostEqual(self._total(recibo, codigo), HORAS * VALOR_HORA * recibo._rule_parameter(parametro, date(2026, 8, 1)), delta=0.01, msg=codigo)

    def test_solo_recargo_resta_uno_al_factor_de_recargo_y_no_toca_las_horas_extra(self):
        """HRDDF 8 x 14.285,71 x 0,90 = 102.857,14; HRNDF x 1,25 = 142.857,14; HEDDF y HENDF iguales que en el otro modo."""
        extra = self._recibo('dia_mas_recargo')
        extra.compute_sheet()
        recibo = self._recibo('solo_recargo')
        recibo.compute_sheet()
        self.assertAlmostEqual(self._total(recibo, 'CO_HRDDF'), 102857.14, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_HRNDF'), 142857.14, delta=0.01)
        for codigo in ('CO_HEDDF', 'CO_HENDF'):
            self.assertAlmostEqual(self._total(recibo, codigo), self._total(extra, codigo), delta=0.01, msg=codigo)

    def test_sin_elegir_un_error_que_dice_donde(self):
        recibo = self._recibo('dia_mas_recargo')
        self.company.l10n_co_ne_pago_dominical_mensual = False
        with self.assertRaises(UserError) as exc:
            recibo.compute_sheet()
        texto = str(exc.exception)
        for esperado in (self.company.name, 'Pago del dominical con salario mensual', 'Parámetros Nómina Colombia'):
            self.assertIn(esperado, texto)

    def test_sin_horas_dominicales_no_se_exige_la_eleccion(self):
        """Una compañia que no ha elegido calcula sus recibos normales: el error solo sale cuando hay horas de recargo dominical."""
        recibo = self._recibo('dia_mas_recargo')
        recibo.input_line_ids.unlink()
        self.company.l10n_co_ne_pago_dominical_mensual = False
        recibo.compute_sheet()
        self.assertFalse(self._total(recibo, 'CO_HRDDF'))

    def test_la_migracion_deja_las_companias_colombianas_en_dia_mas_recargo_y_respeta_lo_demas(self):
        ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '18.0.3.0.310', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('postmigrate_310', ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        colombiana = {'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
                      'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        sin_elegir = self.env['res.company'].create(dict(colombiana, name='Colombiana sin elegir'))
        ya_elegida = self.env['res.company'].create(dict(colombiana, name='Colombiana ya elegida', l10n_co_ne_pago_dominical_mensual='solo_recargo'))
        sin_pais = self.env['res.company'].create({'name': 'Sin país'})
        for compania in (sin_elegir, ya_elegida, sin_pais):
            compania.invalidate_recordset()
        self.env.cr.execute("UPDATE res_company SET l10n_co_ne_pago_dominical_mensual = NULL WHERE id IN %s", ((sin_elegir.id, sin_pais.id),))
        self.env.invalidate_all()
        modulo.migrate(self.env.cr, '18.0.3.0.309')
        self.env.invalidate_all()
        self.assertEqual(sin_elegir.l10n_co_ne_pago_dominical_mensual, 'dia_mas_recargo')
        self.assertEqual(ya_elegida.l10n_co_ne_pago_dominical_mensual, 'solo_recargo')
        self.assertFalse(sin_pais.l10n_co_ne_pago_dominical_mensual)
        modulo.migrate(self.env.cr, '18.0.3.0.309')                                                  # idempotente
        self.env.invalidate_all()
        self.assertEqual(sin_elegir.l10n_co_ne_pago_dominical_mensual, 'dia_mas_recargo')

    def test_el_ajuste_esta_en_los_ajustes_de_nomina(self):
        from lxml import etree
        arch = etree.fromstring(self.env['res.config.settings'].get_view(view_type='form')['arch'].encode())
        self.assertTrue(arch.xpath("//field[@name='l10n_co_ne_pago_dominical_mensual']"))
