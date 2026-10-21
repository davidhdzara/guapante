# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields
from datetime import datetime, date


class TestHrPayslipLeaveIntegration(TransactionCase):
    """Test unitario para la integración de ausencias y novedades de nómina electrónica."""

    def setUp(self):
        super(TestHrPayslipLeaveIntegration, self).setUp()
        self.company = self.env.company
        
        # En Odoo 18, busquemos el país Colombia de forma robusta
        co_country = self.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = self.env.ref('base.co')

        self.employee = self.env['hr.employee'].create({
            'name': 'Juan Pérez Gómez',
            'identification_id': '10203040',
            'l10n_co_ne_document_type': '13',
            'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00',
            'l10n_co_ne_payment_method': '1',  # 1 = Transferencia Bancaria
            'l10n_co_ne_bank_account': '1234567890',
            'l10n_co_ne_bank_name': 'Bancolombia',
            'l10n_co_ne_bank_account_type': 'ahorro',
        })
        self.structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura',
            'country_id': co_country.id,
        })
        self.structure = self.env['hr.payroll.structure'].create({
            'name': 'Nómina Regular',
            'type_id': self.structure_type.id,
        })
        self.contract = self.env['hr.contract'].create({
            'name': 'Contrato Juan Pérez',
            'employee_id': self.employee.id,
            'structure_type_id': self.structure_type.id,
            'wage': 2000000.0,
            'date_start': date(2026, 6, 1),
            'state': 'open',
        })
        # Crear tipos de ausencias
        self.work_entry_type_sick = self.env['hr.work.entry.type'].create({
            'name': 'Incapacidad Común',
            'code': 'INC_COMUN',
            'is_leave': True,
        })
        self.leave_type_sick = self.env['hr.leave.type'].create({
            'name': 'Incapacidad Común',
            'work_entry_type_id': self.work_entry_type_sick.id,
            'requires_allocation': 'no',
        })
        self.work_entry_type_vac = self.env['hr.work.entry.type'].create({
            'name': 'Vacaciones',
            'code': 'VACACIONES',
            'is_leave': True,
        })
        self.leave_type_vac = self.env['hr.leave.type'].create({
            'name': 'Vacaciones',
            'work_entry_type_id': self.work_entry_type_vac.id,
            'requires_allocation': 'no',
        })
        self.rule_category = self.env['hr.salary.rule.category'].search([('code', '=', 'ALW')], limit=1)
        if not self.rule_category:
            self.rule_category = self.env['hr.salary.rule.category'].create({
                'name': 'Allowances',
                'code': 'ALW',
            })

    def test_payslip_leave_autodetection_and_xml_mapping(self):
        """Prueba que el compute_sheet() detecta automáticamente las ausencias y
        que el XML prepara las fechas recortadas de novedades y vacaciones.
        """
        # Crear incapacidad del 5 al 8 de junio de 2026 (4 días)
        inc_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type_sick.id,
            'request_date_from': date(2026, 6, 5),
            'request_date_to': date(2026, 6, 8),
            'date_from': datetime(2026, 6, 5, 8, 0, 0),
            'date_to': datetime(2026, 6, 8, 17, 0, 0),
            'number_of_days': 4.0,
        })
        # Validar la ausencia
        inc_leave.action_validate()
        self.assertEqual(inc_leave.state, 'validate')

        # Crear vacaciones del 15 al 25 de junio de 2026 (11 días)
        vac_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type_vac.id,
            'request_date_from': date(2026, 6, 15),
            'request_date_to': date(2026, 6, 25),
            'date_from': datetime(2026, 6, 15, 8, 0, 0),
            'date_to': datetime(2026, 6, 25, 17, 0, 0),
            'number_of_days': 11.0,
        })
        vac_leave.action_validate()
        self.assertEqual(vac_leave.state, 'validate')

        # Crear payslip del 1 al 30 de junio de 2026
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'name': 'Nómina Junio Juan',
        })

        # Al calcular la nómina, se debe disparar automáticamente action_detect_leaves()
        payslip.compute_sheet()

        # Verificar contadores automáticos
        self.assertEqual(payslip.l10n_co_ne_dias_incapacidad, 4)
        self.assertEqual(payslip.l10n_co_ne_dias_vacaciones, 11)
        self.assertIn('Incapacidad: 4 días (Incapacidad Común)', payslip.l10n_co_ne_leave_summary)
        self.assertIn('Vacaciones: 11 días (Vacaciones)', payslip.l10n_co_ne_leave_summary)

        # Probar la preparación del XML: llamar a _collect_payslip_data()
        # Mockear las lineas de la nomina requeridas para simular los pagos de las reglas
        rule_inc = self.env['hr.salary.rule'].create({
            'name': 'Incapacidad Pago',
            'code': 'INC_PAGO',
            'l10n_co_ne_dian_concept': 'Incapacidad',
            'l10n_co_ne_is_deduction': False,
            'struct_id': self.structure.id,
            'category_id': self.rule_category.id,
        })
        self.env['hr.payslip.line'].create({
            'slip_id': payslip.id,
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'salary_rule_id': rule_inc.id,
            'code': 'INC_PAGO',
            'name': 'Incapacidad Pago',
            'total': 400000.0,
            'quantity': 4,
            'rate': 100,
        })

        rule_vac = self.env['hr.salary.rule'].create({
            'name': 'Vacaciones Comunes Pago',
            'code': 'VAC_PAGO',
            'l10n_co_ne_dian_concept': 'VacacionesComunes',
            'l10n_co_ne_is_deduction': False,
            'struct_id': self.structure.id,
            'category_id': self.rule_category.id,
        })
        self.env['hr.payslip.line'].create({
            'slip_id': payslip.id,
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'salary_rule_id': rule_vac.id,
            'code': 'VAC_PAGO',
            'name': 'Vacaciones Comunes Pago',
            'total': 1100000.0,
            'quantity': 11,
            'rate': 100,
        })

        # Ejecutar recolección de datos XML
        xml_dict = payslip._collect_payslip_data()

        # Verificar incapacidades en el XML
        incapacidades = xml_dict['devengados'].get('Incapacidades', [])
        self.assertEqual(len(incapacidades), 1)
        self.assertEqual(incapacidades[0]['FechaInicio'], '2026-06-05')
        self.assertEqual(incapacidades[0]['FechaFin'], '2026-06-08')
        self.assertEqual(incapacidades[0]['Cantidad'], '4')
        self.assertEqual(incapacidades[0]['Pago'], '400000.00')

        # Verificar vacaciones comunes en el XML
        vacaciones = xml_dict['devengados'].get('Vacaciones', {}).get('VacacionesComunes', [])
        self.assertEqual(len(vacaciones), 1)
        self.assertEqual(vacaciones[0]['FechaInicio'], '2026-06-15')
        self.assertEqual(vacaciones[0]['FechaFin'], '2026-06-25')
        self.assertEqual(vacaciones[0]['Cantidad'], '11')
        self.assertEqual(vacaciones[0]['Pago'], '1100000.00')
