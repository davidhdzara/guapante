# -*- coding: utf-8 -*-
"""DiasTrabajados desde una sola fuente de verdad (Ronda 1 DIAN, hallazgo real 2026-10-05):

I-1 (básico, mes completo, noviembre 2026) generó
<Basico DiasTrabajados="19" SueldoTrabajado="1800000.00"/> -- el sueldo era el de un mes
completo pero los días eran 19 (conteo de líneas WORK100, calendario lun-vie), mientras la
regla CO_BASICO calculaba el sueldo con días comerciales (30, doctrina colombiana de "mes
comercial"). Dos fuentes de días distintas para el mismo devengado: la DIAN lo aceptó (no
valida esa coherencia), pero es un dato incoherente en un documento fiscal.

El Anexo Técnico (NIE069/NIE070) define SueldoTrabajado como "el Sueldo Trabajado por los
días laborados" -- ambos deben contar exactamente lo mismo. HrPayslip._ne_dias_pagables() es
ahora esa única fuente: CO_BASICO la llama para el sueldo (data/hr_payroll_structure_data.xml)
y _dev_basico_y_transporte() la llama para DiasTrabajados. Se prueba aquí _ne_dias_pagables()
directamente (sin depender de las otras 51 reglas de la estructura real) y el guard de
_dev_basico_y_transporte()/_collect_payslip_data() que ahora falla con UserError en vez de
inventar 30 cuando el dato no se puede determinar.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestDiasTrabajadosCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable -- la build de Odoo.sh corre los tests sobre una
        # COPIA de la BD real de Guapante (ver AUD-DIAN-34 en test_dian_matching.py).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba DiasTrabajados',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura DiasTrabajados',
            'country_id': co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba DiasTrabajados',
            'type_id': cls.structure_type.id,
        })

    def _make_contract(self, name, date_start=date(2024, 1, 1), date_end=None, wage=1800000.0):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '40' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # l10n_co_ne_payment_method default es '1' (Transferencia Bancaria), que exige
            # l10n_co_ne_bank_account -- sin interés aquí, 'Efectivo' evita datos bancarios falsos.
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'date_start': date_start,
            'date_end': date_end,
            'state': 'open',
        })
        return employee, contract

    def _make_payslip(self, employee, contract, date_from, date_to):
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % employee.name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
        })


class TestNeDiasPagables(TestDiasTrabajadosCommon):
    """(a)(b)(c) del criterio de aceptación: _ne_dias_pagables() es la única fuente de días."""

    def test_mes_completo_30_dias(self):
        employee, contract = self._make_contract('Sep')
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_mes_completo_31_dias(self):
        employee, contract = self._make_contract('Oct')
        payslip = self._make_payslip(employee, contract, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_mes_completo_febrero_28_dias(self):
        employee, contract = self._make_contract('Feb')
        payslip = self._make_payslip(employee, contract, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_regresion_incidente_real_noviembre_2026(self):
        """Caso exacto del hallazgo real: básico, mes completo, noviembre 2026 -> 30, no 19."""
        employee, contract = self._make_contract('NovIncidente')
        payslip = self._make_payslip(employee, contract, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_ingreso_a_mitad_de_mes(self):
        """(b): contrato inicia el 16 -- quedan 15 días comerciales pagables (16 a 30)."""
        employee, contract = self._make_contract('Ingreso', date_start=date(2026, 9, 16))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(payslip._ne_dias_pagables(), 15)

    def test_retiro_a_mitad_de_mes(self):
        """Simétrico: contrato termina el 10 -- quedan 10 días comerciales pagables (1 a 10)."""
        employee, contract = self._make_contract(
            'Retiro', date_start=date(2024, 1, 1), date_end=date(2026, 9, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(payslip._ne_dias_pagables(), 10)

    def test_con_ausencia_no_remunerada_dentro_del_periodo(self):
        """(c): una licencia NO remunerada de 5 días dentro del período resta de los días
        pagables (30 - 5 = 25) -- el mismo mecanismo que ya usaba CO_BASICO antes de este
        refactor (unpaid_types / work_entry_type_id.code), ahora en _ne_dias_pagables().

        AUD-DIAN-34 (2026-10-05): la línea de worked_days_line_ids se construye a mano en
        vez de pasar por hr.leave + compute_sheet() -- la corrida real en staging mostró
        que compute_sheet() por sí solo no genera la línea desde la ausencia validada (hace
        falta además generar los work entries del contrato para el período, algo fuera del
        alcance de esta prueba). _ne_dias_pagables() solo lee worked_days_line_ids filtrando
        por work_entry_type_id.code -- construirla directamente prueba esa lógica igual,
        sin depender del pipeline completo de hr_work_entry_holidays."""
        employee, contract = self._make_contract('ConAusencia')
        work_entry_type = self.env['hr.work.entry.type'].create({
            'name': 'Licencia No Remunerada Prueba',
            'code': 'LNR_PRUEBA_DIAS_TRAB',
            'is_leave': True,
        })
        self.env['hr.leave.type'].create({
            'name': 'Licencia No Remunerada Prueba',
            'work_entry_type_id': work_entry_type.id,
            'requires_allocation': 'no',
            'unpaid': True,
        })
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        # AUD-DIAN-34 (2026-10-05): worked_days_line_ids es un compute stored (readonly=False)
        # -- queda pendiente al crear el payslip. Si se crea la línea manual ANTES de que ese
        # cálculo corra, al leer worked_days_line_ids (_ne_dias_pagables) Odoo ejecuta el
        # cálculo pendiente y SOBRESCRIBE la línea manual con las calculadas (confirmado en el
        # servidor por Tech Lead, con rollback: creando la línea sin forzar antes el cálculo,
        # la línea LNR desaparecía). Se fuerza el cálculo leyendo el campo ANTES de crear la
        # línea manual, para que esta se agregue sobre lo ya calculado y no sea pisada.
        payslip.worked_days_line_ids
        # AUD-DIAN-34 (2026-10-05): modelo real 'hr.payslip.worked_days' (guion bajo), no
        # 'hr.payslip.worked.days' -- confirmado contra enterprise/hr_payroll/models/
        # hr_payslip_worked_days.py en el servidor (Tech Lead). contract_id ahí es un
        # related de payslip_id.contract_id, no se escribe en el create().
        self.env['hr.payslip.worked_days'].create({
            'payslip_id': payslip.id,
            'work_entry_type_id': work_entry_type.id,
            'number_of_days': 5.0,
        })
        self.assertEqual(payslip._ne_dias_pagables(), 25)


class TestNeDiasPagablesLiquidacion(TestDiasTrabajadosCommon):
    """H-009 (2026-10-06, QA Bloque 2): hallazgo real en staging (NE0000000077, contrato desde
    2024-10-05, retiro 2026-11-15) -- el XML mostraba <Basico DiasTrabajados="11"
    SueldoTrabajado="900000.00">, un sueldo de 15 días (15 x 60.000) con un DiasTrabajados de
    11 sin relación con ese sueldo.

    Causa: en Liquidación, date_from es contract.date_start (wizard/hr_liquidacion_wizard.py:
    'date_from': contract.date_start) y el período puede abarcar meses o años -- intersectarlo
    completo contra el contrato (como hacía _ne_dias_pagables() antes) devuelve el total de
    días de TODO el contrato, no el tramo pendiente del último mes que realmente paga
    CO_LIQ_SALARIOS (los meses anteriores ya se pagaron en nóminas mensuales regulares).
    Ahora _ne_dias_pagables() recorta el período al mes calendario de date_to cuando date_from
    y date_to caen en meses distintos; CO_LIQ_SALARIOS (data/hr_payroll_structure_special_
    data.xml) llama a esta misma función en vez de su propio cálculo duplicado (que además
    tenía su propio bug: no aplicaba el caso especial "último día calendario = día comercial
    30" para meses de 28/29 días, dando min(28, 30)=28 en vez de 30 para un retiro en
    febrero)."""

    def test_incidente_real_h009_contrato_2024_retiro_2026_11_15(self):
        """(a) Caso exacto reportado: contrato desde 2024-10-05, retiro 2026-11-15 -> 15 días."""
        employee, contract = self._make_contract(
            'LiqH009', date_start=date(2024, 10, 5), date_end=date(2026, 11, 15),
            wage=1800000.0)
        payslip = self._make_payslip(
            employee, contract, contract.date_start, date(2026, 11, 15))
        self.assertEqual(payslip._ne_dias_pagables(), 15)

    def test_liquidacion_sueldo_coherente_con_dias_via_regla_real(self):
        """(a) extendido: corre CO_LIQ_SALARIOS real (compute_sheet() sobre la estructura de
        Liquidación) -- el sueldo debe salir de EXACTAMENTE los mismos días que
        _ne_dias_pagables(), no de un cálculo propio duplicado. 1.800.000 / 30 x 15 = 900.000,
        el mismo sueldo del incidente real."""
        liquidacion_struct = self.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        employee, contract = self._make_contract(
            'LiqSueldoCoherente', date_start=date(2024, 10, 5), date_end=date(2026, 11, 15),
            wage=1800000.0)
        payslip = self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % employee.name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': liquidacion_struct.id,
            'date_from': contract.date_start,
            'date_to': date(2026, 11, 15),
        })
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'CO_LIQ_SALARIOS')
        self.assertTrue(line, 'CO_LIQ_SALARIOS no generó línea.')
        self.assertEqual(payslip._ne_dias_pagables(), 15)
        self.assertEqual(round(line.total, 2), 900000.0)

    def test_retiro_dia_31_cuenta_como_mes_comercial_completo(self):
        """(b) Retiro el día 31 (mes real de 31 días) -- el último día calendario de
        cualquier mes siempre equivale al día comercial 30, no 31-1+1=31."""
        employee, contract = self._make_contract(
            'LiqRetiro31', date_start=date(2024, 1, 1), date_end=date(2026, 1, 31))
        payslip = self._make_payslip(employee, contract, contract.date_start, date(2026, 1, 31))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_retiro_dia_30_cuenta_como_mes_comercial_completo(self):
        """(b) Retiro el día 30 (mes real de 30 días) -- caso simple, día 30 = día comercial 30."""
        employee, contract = self._make_contract(
            'LiqRetiro30', date_start=date(2024, 1, 1), date_end=date(2026, 4, 30))
        payslip = self._make_payslip(employee, contract, contract.date_start, date(2026, 4, 30))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_retiro_en_febrero_cuenta_como_mes_comercial_completo(self):
        """(b) Retiro el último día de febrero (28, 2026 no es bisiesto) -- antes del arreglo,
        CO_LIQ_SALARIOS calculaba min(28, 30)=28, 2 días comerciales de menos frente a la
        convención real (último día calendario = día comercial 30, igual que CO_BASICO)."""
        employee, contract = self._make_contract(
            'LiqRetiroFeb', date_start=date(2024, 1, 1), date_end=date(2026, 2, 28))
        payslip = self._make_payslip(employee, contract, contract.date_start, date(2026, 2, 28))
        self.assertEqual(payslip._ne_dias_pagables(), 30)

    def test_liquidacion_con_contrato_de_menos_de_un_mes(self):
        """(c) Contrato nace y termina dentro del mismo mes calendario -- date_from y date_to
        ya caen en el mismo mes, así que no aplica el recorte de período multi-mes; el tramo
        pagable es la intersección normal de siempre (día 10 a día 22 = 13 días)."""
        employee, contract = self._make_contract(
            'LiqCorto', date_start=date(2026, 9, 10), date_end=date(2026, 9, 22))
        payslip = self._make_payslip(employee, contract, contract.date_start, date(2026, 9, 22))
        self.assertEqual(payslip._ne_dias_pagables(), 13)


class TestDevBasicoYTransporteGuard(TestDiasTrabajadosCommon):
    """(d) del criterio de aceptación: sin dato válido, UserError -- nunca un 30 inventado."""

    def _make_sueldo_line(self, payslip, employee, contract, total):
        rule = self.env['hr.salary.rule'].search(
            [('code', '=', 'DIAS_TRAB_PRUEBA_SUELDO')], limit=1)
        if not rule:
            category = self.env['hr.salary.rule.category'].search(
                [('code', '=', 'ALW')], limit=1)
            if not category:
                category = self.env['hr.salary.rule.category'].create({
                    'name': 'Allowances', 'code': 'ALW',
                })
            rule = self.env['hr.salary.rule'].create({
                'name': 'Sueldo Prueba DiasTrabajados',
                'code': 'DIAS_TRAB_PRUEBA_SUELDO',
                'l10n_co_ne_dian_concept': 'Sueldo',
                'l10n_co_ne_is_deduction': False,
                'struct_id': self.structure.id,
                'category_id': category.id,
            })
        return self.env['hr.payslip.line'].create({
            'slip_id': payslip.id,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'salary_rule_id': rule.id,
            'code': rule.code,
            'name': rule.name,
            'total': total,
        })

    def test_contrato_no_activo_en_el_periodo_falla_con_usererror(self):
        """Contrato terminado antes del período -> dias_bajo_contrato=0 -- no se inventa 30."""
        employee, contract = self._make_contract(
            'SinContratoActivo', date_start=date(2024, 1, 1), date_end=date(2026, 8, 31))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._make_sueldo_line(payslip, employee, contract, 1800000.0)

        with self.assertRaises(UserError):
            payslip._collect_payslip_data()

    def test_dias_trabajados_coherente_con_dias_pagables(self):
        """El dict que recibe el XML builder debe traer EXACTAMENTE el mismo valor que
        _ne_dias_pagables() -- la coherencia que motivó esta corrección."""
        employee, contract = self._make_contract('Coherente', date_start=date(2026, 9, 16))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._make_sueldo_line(payslip, employee, contract, 900000.0)

        # _map_salary_rules_to_xml() (no _collect_payslip_data(), que devuelve un único dict
        # combinado con todas las secciones del XML, no un par devengados/deducciones) es
        # lo que realmente construye el dict que llega a _dev_basico_y_transporte().
        devengados, _deducciones = payslip._map_salary_rules_to_xml()

        self.assertEqual(payslip._ne_dias_pagables(), 15)
        self.assertEqual(devengados['Basico']['DiasTrabajados'], '15')
