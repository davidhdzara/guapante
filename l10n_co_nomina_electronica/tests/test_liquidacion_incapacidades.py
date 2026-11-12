# -*- coding: utf-8 -*-
"""Incapacidades y licencias de maternidad/paternidad dentro del ultimo tramo de la liquidacion.

Antes el sueldo pendiente las restaba (_ne_dias_pagables) y la liquidacion no las pagaba ni las
reportaba. Ahora las reglas de la estructura 6 (mismos codigos que la general) usan el calculo
unico HrPayslip._ne_pago_ausencia_calendario(). Contrato $1.800.000 desde 2026-01-01, retiro
2026-08-15 (tramo de 15 dias comerciales), valor dia 60.000; parametros 2026: empleador 2 dias al
66,67 %, EPS 3-90 al 66,67 %, 91+ al 50 %. Valores esperados a mano.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

RETIRO = date(2026, 8, 15)


@tagged('post_install', '-at_install')
class TestLiquidacionIncapacidades(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Incapacidades Liquidación'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Incapacidades', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        ref = cls.env.ref
        cls.inc_comun = ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.inc_laboral = ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_laboral')
        cls.lic_mat = ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_mat')

    def _liquidacion(self, name, ausencias):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        contract.generate_work_entries(date(2026, 1, 1), RETIRO)
        for tipo, desde, hasta in ausencias:
            leave = self.env['hr.leave'].create({
                'employee_id': employee.id, 'holiday_status_id': tipo.id,
                'request_date_from': desde, 'request_date_to': hasta})
            leave.action_validate()
        slip = self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': RETIRO})
        slip.compute_sheet()
        return slip

    def _linea(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def _novedades_xml(self, slip):
        devengados = {}
        slip._dev_novedades(slip._group_lines_by_concept(), devengados)
        return devengados

    def test_incapacidad_comun_del_tramo_se_paga_por_tramos_y_el_neto_sube_ese_valor(self):
        slip = self._liquidacion('IncComun', [(self.inc_comun, date(2026, 8, 3), date(2026, 8, 7))])
        inc = self._linea(slip, 'CO_INC_COMUN')
        self.assertEqual(inc.quantity, 5.0)
        # .163: valor dia 60.000 x 0,6667 = 40.002 < piso 1 SMMLV/30 = 1.750.905/30 = 58.363,5
        # -> 5 dias x 58.363,5 = 291.817,5
        self.assertAlmostEqual(inc.total, 291817.5, delta=0.01)
        salarios = self._linea(slip, 'CO_LIQ_SALARIOS')
        self.assertEqual((salarios.quantity, salarios.total), (10.0, 600000.0))
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_INCAP').total, 291817.5, delta=0.01)
        # CO_LIQ_NETO frente a la regla inactiva: sube el valor de la incapacidad MENOS el mayor
        # descuento de salud y pension (4 % + 4 %), porque con la incapacidad el IBC deja de ser el
        # piso: sin la regla el IBC es el piso de 1 SMMLV x 15/30 = 875.452,5; con ella,
        # 600.000 + 291.817,5 = 891.817,5 -> 8 % x 16.365 = 1.309,2 de descuento adicional.
        # (.163: antes, con 200.010, el IBC 800.010 quedaba bajo el piso y las deducciones eran
        # iguales.) Neto: 291.817,5 - 1.309,2 = 290.508,3.
        neto_con = self._linea(slip, 'CO_LIQ_NETO').total
        regla = self.env['hr.salary.rule'].search(
            [('code', '=', 'CO_INC_COMUN'), ('struct_id', '=', self.liquidacion.id)], limit=1)
        regla.active = False
        slip.compute_sheet()
        self.assertFalse(self._linea(slip, 'CO_INC_COMUN'))
        self.assertAlmostEqual(
            neto_con - self._linea(slip, 'CO_LIQ_NETO').total, 290508.3, delta=0.01)

    def test_xml_reporta_la_incapacidad_del_tramo(self):
        slip = self._liquidacion('XmlInc', [(self.inc_comun, date(2026, 8, 3), date(2026, 8, 7))])
        items = self._novedades_xml(slip)['Incapacidades']
        self.assertEqual(len(items), 1)
        self.assertEqual(
            (items[0]['FechaInicio'], items[0]['FechaFin'], items[0]['Cantidad'], items[0]['Tipo']),
            ('2026-08-03', '2026-08-07', '5', '1'))
        self.assertEqual(items[0]['Pago'], '291817.50')

    def test_incapacidad_de_un_mes_anterior_no_se_paga_ni_se_descuenta_ni_va_al_xml(self):
        slip = self._liquidacion('IncAbril', [(self.inc_comun, date(2026, 4, 6), date(2026, 4, 10))])
        self.assertFalse(self._linea(slip, 'CO_INC_COMUN'))
        self.assertEqual(self._linea(slip, 'CO_LIQ_SALARIOS').quantity, 15.0)
        self.assertNotIn('Incapacidades', self._novedades_xml(slip))

    def test_licencia_de_maternidad_que_cruza_el_retiro_se_recorta_al_contrato(self):
        """10 de agosto al 14 de diciembre (126 dias): solo 10 al 15 de agosto = 6 dias."""
        slip = self._liquidacion('LicMat', [(self.lic_mat, date(2026, 8, 10), date(2026, 12, 14))])
        lic = self._linea(slip, 'CO_LIC_MAT')
        self.assertEqual(lic.quantity, 6.0)
        self.assertAlmostEqual(lic.total, 360000.0, delta=0.01)
        salarios = self._linea(slip, 'CO_LIQ_SALARIOS')
        self.assertEqual((salarios.quantity, salarios.total), (9.0, 540000.0))
        item = self._novedades_xml(slip)['Licencias']['LicenciaMP'][0]
        self.assertEqual(
            (item['FechaInicio'], item['FechaFin'], item['Cantidad']),
            ('2026-08-10', '2026-08-15', '6'))

    def test_incapacidad_laboral_del_tramo_se_paga_al_100(self):
        slip = self._liquidacion('IncLab', [(self.inc_laboral, date(2026, 8, 3), date(2026, 8, 7))])
        lab = self._linea(slip, 'CO_INC_LABORAL')
        self.assertEqual(lab.quantity, 5.0)
        self.assertAlmostEqual(lab.total, 300000.0, delta=0.01)

    def test_ibc_de_la_liquidacion_lee_la_base_de_incapacidades(self):
        slip = self._liquidacion('IbcInc', [(self.inc_comun, date(2026, 8, 3), date(2026, 8, 7))])
        esperado = slip._ne_ibc_limites(
            self._linea(slip, 'CO_IBC_SALARIAL').total, self._linea(slip, 'CO_IBC_INCAP').total,
            self._linea(slip, 'CO_IBC_REMUN').total, self._linea(slip, 'CO_IBC_PACTADOS').total,
            self._linea(slip, 'CO_DIAS_SP').total)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, esperado, delta=0.01)

    def test_las_reglas_nuevas_son_salario_para_embargos_y_libranzas(self):
        for code in ('CO_INC_COMUN', 'CO_INC_LABORAL', 'CO_LIC_MAT', 'CO_LIC_PAT'):
            regla = self.env['hr.salary.rule'].search(
                [('code', '=', code), ('struct_id', '=', self.liquidacion.id)], limit=1)
            self.assertTrue(regla, code)
            self.assertEqual(regla.l10n_co_liq_tratamiento, 'salario')

    # --- Equivalencia del metodo compartido con las formulas que tenia la regla general ---------
    # Salario $3.000.000 (valor dia 100.000), quincena de septiembre 2026.

    def _general(self):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Equivalencia', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Equivalencia', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Equivalencia', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})

    def test_equivalencia_incapacidad_comun_con_las_formulas_anteriores(self):
        slip = self._general()
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_INC_COMUN', 2), 133340.0, delta=0.01)
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_INC_COMUN', 10), 666700.0, delta=0.01)
        # 90 dias al 66,67 % + 10 dias al 50 % (50.000/dia < piso 1 SMMLV/30 = 58.363,5, .163):
        # 90 x 66.670 + 10 x 58.363,5 = 6.583.935
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_INC_COMUN', 100), 6583935.0, delta=0.01)
        self.assertEqual(slip._ne_pago_ausencia_calendario('CO_INC_COMUN', 0), 0.0)

    def test_equivalencia_licencias_e_incapacidad_laboral_valor_dia_por_dias(self):
        slip = self._general()
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_INC_LABORAL', 5), 500000.0, delta=0.01)
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_LIC_MAT', 126), 12600000.0, delta=0.01)
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_LIC_PAT', 14), 1400000.0, delta=0.01)

    def test_codigo_de_ausencia_sin_formula_falla_con_mensaje_claro(self):
        with self.assertRaises(UserError):
            self._general()._ne_pago_ausencia_calendario('CO_VAC', 5)
