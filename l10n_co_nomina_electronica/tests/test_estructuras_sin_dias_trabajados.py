# -*- coding: utf-8 -*-
"""Prima y bonificacion no usan dias trabajados nativos (use_worked_day_lines=False).

La pestana "Dias trabajados" de un recibo de prima mostraba horas del calendario de todo el
semestre (119 dias / 952 h "Asistencia", 10 "Festivo") con un importe nativo que ninguna regla
usa. Ninguna regla de estas estructuras lee worked_days: el neto no depende de ellos."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEstructurasSinDiasTrabajados(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Sin Días'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Sin Días', 'country_id': cls.env.ref('base.co').id})
        cls.est_prima = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.est_bonificacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')

    def _recibo(self, estructura, name, date_from, date_to):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date_from, 'date_to': date_to})

    def _neto(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def test_las_estructuras_declaran_no_usar_dias_trabajados(self):
        self.assertFalse(self.est_prima.use_worked_day_lines)
        self.assertFalse(self.est_bonificacion.use_worked_day_lines)

    def test_prima_no_genera_lineas_de_dias_y_el_neto_no_cambia(self):
        slip = self._recibo(self.est_prima, 'PrimaSinDias', date(2026, 7, 1), date(2026, 12, 31))
        slip.compute_sheet()
        self.assertFalse(slip.worked_days_line_ids)
        neto_sin = self._neto(slip, 'CO_PRIMA_NETO')
        self.assertGreater(neto_sin, 0)
        # Con las lineas de dias activadas (comportamiento nativo) el neto es el mismo.
        self.est_prima.use_worked_day_lines = True
        slip.compute_sheet()
        self.assertAlmostEqual(self._neto(slip, 'CO_PRIMA_NETO'), neto_sin, places=2)

    def test_bonificacion_no_genera_lineas_de_dias_y_el_neto_no_cambia(self):
        slip = self._recibo(
            self.est_bonificacion, 'BonSinDias', date(2026, 9, 1), date(2026, 9, 30))
        self.env['hr.payslip.input'].create({
            'payslip_id': slip.id, 'input_type_id': self.env.ref(
                'l10n_co_nomina_electronica.input_co_bon_valor').id,
            'code': 'CO_BON_VALOR', 'amount': 500000.0})
        slip.compute_sheet()
        self.assertFalse(slip.worked_days_line_ids)
        neto_sin = self._neto(slip, 'CO_BON_NETO')
        self.assertGreater(neto_sin, 0)
        self.est_bonificacion.use_worked_day_lines = True
        slip.compute_sheet()
        self.assertAlmostEqual(self._neto(slip, 'CO_BON_NETO'), neto_sin, places=2)
