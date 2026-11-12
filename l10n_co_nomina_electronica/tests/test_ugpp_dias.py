# -*- coding: utf-8 -*-
"""UGPP días: las columnas de días del reporte salen del consolidado mensual (misma fuente
que PILA) y de las mismas funciones de ausencias de nómina; solo en la primera fila del
empleado-mes (igual que el IBC). Nivel de verificación: hoja 'nomina' real con recibos
calculados con compute_sheet; el Excel completo se prueba en servidor."""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill
except ImportError:  # pragma: no cover
    openpyxl = None

_PAYSLIP = 'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.HrPayslip'
# Posición (0-based) de cada columna de días en la fila de la hoja.
_COL = {'trabajados': 18, 'incapacidad': 19, 'lic_mat': 20, 'lic_rem': 21,
        'suspension': 22, 'vacaciones': 23, 'huelga': 24, 'total': 25}


@tagged('post_install', '-at_install')
class TestUgppDias(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba UGPP Días'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura UGPP', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.Ugpp = cls.env['l10n_co_nomina.ugpp']

    def _empleado(self):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Ana Gómez', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato UGPP', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return employee, contract

    def _recibo(self, employee, contract, ini, fin):
        slip = self.env['hr.payslip'].create({
            'name': 'Nómina UGPP', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.structure.id,
            'date_from': ini, 'date_to': fin})
        slip.compute_sheet()
        return slip

    def _confirmar(self, *slips):
        for s in slips:
            s.state = 'done'
        slips[0]._ne_refrescar_ibc_mensual()

    def _filas(self, slips):
        wb = openpyxl.Workbook()
        ws = wb.active
        report = self.Ugpp.create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30), 'company_id': self.company.id})
        report._generate_sheet_nomina(
            ws, slips, Font(bold=True), PatternFill(), Alignment(), Border())
        return [[c.value for c in fila] for fila in ws.iter_rows(min_row=2)]

    def test_un_recibo_sin_novedades_total_30_y_trabajados_30(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        fila = self._filas(slip)[0]
        self.assertEqual(fila[_COL['total']], 30)
        self.assertEqual(fila[_COL['trabajados']], 30)
        self.assertEqual(fila[_COL['suspension']], 0)

    def test_total_igual_a_dias_de_pila(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        consolidado = self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', employee.id)])
        self.assertEqual(self._filas(slip)[0][_COL['total']], consolidado.dias_sp)

    def test_dos_recibos_del_mes_los_dias_van_solo_en_la_primera_fila(self):
        employee, contract = self._empleado()
        s1 = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 15))
        s2 = self._recibo(employee, contract, date(2026, 9, 16), date(2026, 9, 30))
        self._confirmar(s1, s2)
        filas = self._filas(s1 | s2)
        self.assertEqual(sum(f[_COL['total']] for f in filas), 30)
        self.assertEqual(filas[1][_COL['total']], 0)
        self.assertEqual(filas[1][_COL['trabajados']], 0)

    def test_novedades_salen_de_las_funciones_de_nomina(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        consolidado = self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', employee.id)])

        def ausencia(_self, codigo):
            return ({'CO_INC_COMUN': 3, 'CO_LIC_MAT': 5}.get(codigo, 0), [])
        with patch(_PAYSLIP + '._ne_ausencia_calendario', ausencia), \
                patch(_PAYSLIP + '._ne_dias_sln', lambda _self: 2):
            dias = self.Ugpp._dias_ugpp(consolidado)
        self.assertEqual(dias['incapacidad'], 3)
        self.assertEqual(dias['lic_mat'], 5)
        self.assertEqual(dias['suspension'], 2)
        self.assertEqual(dias['total'], 30)
        self.assertEqual(dias['trabajados'], 30 - 3 - 5 - 2)

    def test_trabajados_nunca_es_negativo(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        consolidado = self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', employee.id)])
        with patch(_PAYSLIP + '._ne_dias_sln', lambda _self: 40):
            self.assertEqual(self.Ugpp._dias_ugpp(consolidado)['trabajados'], 0)

    def test_sin_consolidado_es_error_y_no_asume_30(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        slip.state = 'done'  # sin refrescar el consolidado ni líneas de IBC
        slip.line_ids.filtered(lambda l: l.code.startswith('CO_IBC')).unlink()
        with self.assertRaises(UserError):
            self._filas(slip)
