# -*- coding: utf-8 -*-
"""Liquidacion: las ausencias en dias HABILES que se descuentan del sueldo pendiente son solo las
del tramo del ultimo mes, no las de toda la vida del contrato.

En liquidacion date_from = inicio de contrato, asi que worked_days cubre todo el contrato mientras
que el sueldo pendiente (CO_LIQ_SALARIOS) es del tramo del ultimo mes. _ne_dias_pagables() resta
de los dias del tramo todos los dias de CO_VAC/CO_LIC_REM/CO_LIC_NR/unpaid de worked_days, de
cualquier mes: vacaciones de marzo descuentan dias del sueldo de agosto.

Caso: contrato desde 2026-01-01, vacaciones de 5 dias habiles (2-6 de marzo, lunes a viernes),
retiro el 2026-08-15 -> el tramo pagable es 1-15 de agosto = 15 dias comerciales, y las
vacaciones de marzo (ya pagadas en su nomina) no deben restarse. Sin la correccion esta prueba
da 10 dias (15 - 5).
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

RETIRO = date(2026, 8, 15)


@tagged('post_install', '-at_install')
class TestLiquidacionTramoAusencias(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Tramo Ausencias Liquidación'})
        # Mismo entorno y datos en la misma compañía (ver test_ausencias_nomina).
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Tramo', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.leave_type_vac = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        cls.leave_type_lic_rem = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_lic_rem')
        cls.leave_type_lic_nr = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_nr')

    def _liquidacion_con_vacaciones(self, name, vac_desde, vac_hasta, leave_type=None):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        # Precondicion operativa real: work entries del contrato antes de validar la ausencia.
        contract.generate_work_entries(date(2026, 1, 1), RETIRO)
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': (leave_type or self.leave_type_vac).id,
            'request_date_from': vac_desde, 'request_date_to': vac_hasta})
        leave.action_validate()
        self.assertEqual(leave.state, 'validate')
        # Como lo crea el asistente: date_from = inicio de contrato.
        slip = self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': RETIRO})
        slip.compute_sheet()
        return slip

    def _salarios(self, slip):
        linea = slip.line_ids.filtered(lambda l: l.code == 'CO_LIQ_SALARIOS')
        self.assertTrue(linea, 'CO_LIQ_SALARIOS no generó línea.')
        return linea

    def test_vacaciones_de_meses_anteriores_no_descuentan_el_sueldo_del_ultimo_tramo(self):
        slip = self._liquidacion_con_vacaciones(
            'VacMarzo', date(2026, 3, 2), date(2026, 3, 6))   # 5 dias habiles, ya pagados
        salarios = self._salarios(slip)
        self.assertEqual(slip._ne_dias_pagables(), 15)        # tramo 1-15 de agosto
        self.assertEqual(salarios.quantity, 15.0)
        self.assertAlmostEqual(salarios.total, 1800000.0 / 30 * 15, places=2)

    def test_vacaciones_dentro_del_ultimo_tramo_si_se_descuentan(self):
        """Control: 3-7 de agosto (5 dias habiles, dentro del tramo 1-15) siguen restando."""
        slip = self._liquidacion_con_vacaciones(
            'VacAgosto', date(2026, 8, 3), date(2026, 8, 7))
        self.assertEqual(slip._ne_dias_pagables(), 10)
        self.assertEqual(self._salarios(slip).quantity, 10.0)

    def test_licencia_remunerada_de_un_mes_anterior_no_descuenta_el_ultimo_tramo(self):
        """Lunes 6 a viernes 10 de abril (5 dias habiles de licencia remunerada) ya se pagaron
        en su nomina: no restan de los 15 dias de agosto."""
        slip = self._liquidacion_con_vacaciones(
            'LicAbril', date(2026, 4, 6), date(2026, 4, 10), leave_type=self.leave_type_lic_rem)
        self.assertEqual(slip._ne_dias_pagables(), 15)
        self.assertEqual(self._salarios(slip).quantity, 15.0)

    def test_licencia_no_remunerada_de_un_mes_anterior_no_cuenta_como_sln_del_tramo(self):
        """La suspension de mayo no es SLN del ultimo tramo: ni resta dias del sueldo de agosto
        ni cuenta en los dias SLN de PILA/UGPP de la liquidacion."""
        slip = self._liquidacion_con_vacaciones(
            'LnrMayo', date(2026, 5, 4), date(2026, 5, 8), leave_type=self.leave_type_lic_nr)
        self.assertEqual(slip._ne_dias_pagables(), 15)
        self.assertEqual(slip._ne_dias_sln(), 0)

    def test_licencia_no_remunerada_dentro_del_tramo_si_cuenta(self):
        slip = self._liquidacion_con_vacaciones(
            'LnrAgosto', date(2026, 8, 3), date(2026, 8, 7), leave_type=self.leave_type_lic_nr)
        self.assertEqual(slip._ne_dias_pagables(), 10)
        self.assertEqual(slip._ne_dias_sln(), 5)

    # --- Pago de las ausencias del ultimo tramo (CO_LIQ_VAC_DISFRUTADAS / CO_LIQ_LIC_REM) ----
    # Contrato $1.800.000: valor dia 60.000; tramo 1-15 de agosto = 15 dias comerciales.

    def _liquidacion_con_ausencias(self, name, ausencias):
        """ausencias = [(tipo, desde, hasta), ...] validadas antes de calcular la liquidacion."""
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

    def test_vacaciones_disfrutadas_del_tramo_se_pagan_y_el_empleado_cobra_los_15_dias(self):
        slip = self._liquidacion_con_ausencias(
            'PagoVac', [(self.leave_type_vac, date(2026, 8, 3), date(2026, 8, 7))])
        salarios = self._linea(slip, 'CO_LIQ_SALARIOS')
        vac = self._linea(slip, 'CO_LIQ_VAC_DISFRUTADAS')
        self.assertEqual((salarios.quantity, salarios.total), (10.0, 600000.0))
        self.assertEqual(vac.quantity, 5.0)
        self.assertAlmostEqual(vac.amount, 60000.0, places=2)
        self.assertAlmostEqual(vac.total, 300000.0, places=2)
        # Salario + vacaciones disfrutadas = 15 dias completos (sin la regla eran solo 600.000).
        self.assertAlmostEqual(salarios.total + vac.total, 900000.0, places=2)

    def test_vacaciones_de_meses_anteriores_no_generan_linea_de_pago(self):
        slip = self._liquidacion_con_ausencias(
            'SinPagoVac', [(self.leave_type_vac, date(2026, 3, 2), date(2026, 3, 6))])
        self.assertFalse(self._linea(slip, 'CO_LIQ_VAC_DISFRUTADAS'))
        self.assertEqual(self._linea(slip, 'CO_LIQ_SALARIOS').quantity, 15.0)

    def test_licencia_remunerada_del_tramo_se_paga(self):
        slip = self._liquidacion_con_ausencias(
            'PagoLic', [(self.leave_type_lic_rem, date(2026, 8, 3), date(2026, 8, 7))])
        lic = self._linea(slip, 'CO_LIQ_LIC_REM')
        self.assertEqual(lic.quantity, 5.0)
        self.assertAlmostEqual(lic.total, 300000.0, places=2)

    def test_xml_solo_reporta_las_vacaciones_del_tramo(self):
        """Marzo (ya declarada en su documento) y 3-7 de agosto (la que paga esta liquidacion):
        el nodo VacacionesComunes trae solo la de agosto, con Cantidad 5 y Pago 300.000."""
        slip = self._liquidacion_con_ausencias('XmlVac', [
            (self.leave_type_vac, date(2026, 3, 2), date(2026, 3, 6)),
            (self.leave_type_vac, date(2026, 8, 3), date(2026, 8, 7))])
        devengados = {}
        slip._dev_prestaciones(slip._group_lines_by_concept(), devengados)
        items = devengados['Vacaciones']['VacacionesComunes']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['FechaInicio'], '2026-08-03')
        self.assertEqual(items[0]['FechaFin'], '2026-08-07')
        self.assertEqual(items[0]['Cantidad'], '5')
        self.assertEqual(items[0]['Pago'], '300000.00')

    def test_ibc_de_la_liquidacion_incluye_las_vacaciones_del_tramo(self):
        """Sin nomina previa el ultimo IBC es el salario: 600.000 (10 dias) + 1.800.000/30 x 5."""
        slip = self._liquidacion_con_ausencias(
            'IbcVac', [(self.leave_type_vac, date(2026, 8, 3), date(2026, 8, 7))])
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SALARIAL').total, 900000.0, places=2)

    def test_ibc_usa_el_ultimo_ibc_de_la_nomina_general_anterior(self):
        """Con una nomina general confirmada (IBC 2.100.000 en julio): 600.000 + 2.100.000/30 x 5
        = 950.000."""
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'IbcPrevio', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato IbcPrevio', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        previa = self.env['hr.payslip'].create({
            'name': 'Nómina julio', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': general.id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31)})
        regla = self.env['hr.salary.rule'].search(
            [('code', '=', 'CO_SS_BASE_IBC'), ('struct_id', '=', general.id)], limit=1)
        self.env['hr.payslip.line'].create({
            'slip_id': previa.id, 'salary_rule_id': regla.id, 'code': 'CO_SS_BASE_IBC',
            'name': 'IBC', 'contract_id': contract.id, 'employee_id': employee.id,
            'quantity': 1.0, 'rate': 100.0, 'amount': 2100000.0, 'total': 2100000.0})
        previa.state = 'done'
        contract.generate_work_entries(date(2026, 1, 1), RETIRO)
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.leave_type_vac.id,
            'request_date_from': date(2026, 8, 3), 'request_date_to': date(2026, 8, 7)})
        leave.action_validate()
        slip = self.env['hr.payslip'].create({
            'name': 'Liquidación IbcPrevio', 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id, 'date_from': contract.date_start,
            'date_to': RETIRO})
        slip.compute_sheet()
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SALARIAL').total, 950000.0, places=2)

    def test_las_reglas_nuevas_se_tratan_como_salario_para_embargos_y_libranzas(self):
        for code in ('CO_LIQ_VAC_DISFRUTADAS', 'CO_LIQ_LIC_REM'):
            regla = self.env['hr.salary.rule'].search(
                [('code', '=', code), ('struct_id', '=', self.liquidacion.id)], limit=1)
            self.assertTrue(regla, code)
            self.assertEqual(regla.l10n_co_liq_tratamiento, 'salario')

    def test_el_neto_aumenta_exactamente_el_valor_de_las_vacaciones_del_tramo(self):
        """CO_LIQ_NETO con la regla de vacaciones disfrutadas es 300.000 mas que el mismo caso con
        la regla inactiva (las deducciones son iguales: el IBC no depende de la regla)."""
        slip = self._liquidacion_con_ausencias(
            'NetoVac', [(self.leave_type_vac, date(2026, 8, 3), date(2026, 8, 7))])
        neto_con = self._linea(slip, 'CO_LIQ_NETO').total
        regla = self.env['hr.salary.rule'].search(
            [('code', '=', 'CO_LIQ_VAC_DISFRUTADAS'), ('struct_id', '=', self.liquidacion.id)],
            limit=1)
        regla.active = False
        slip.compute_sheet()
        self.assertFalse(self._linea(slip, 'CO_LIQ_VAC_DISFRUTADAS'))
        neto_sin = self._linea(slip, 'CO_LIQ_NETO').total
        self.assertAlmostEqual(neto_con - neto_sin, 300000.0, places=2)
