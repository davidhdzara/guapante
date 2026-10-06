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
        self.env['hr.payslip.worked.days'].create({
            'payslip_id': payslip.id,
            'contract_id': contract.id,
            'work_entry_type_id': work_entry_type.id,
            'number_of_days': 5.0,
        })
        self.assertEqual(payslip._ne_dias_pagables(), 25)


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
