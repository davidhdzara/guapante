# -*- coding: utf-8 -*-
"""UGPP días: las columnas de días del reporte salen del consolidado mensual (misma fuente
que PILA) y de las mismas funciones de ausencias de nómina; solo en la primera fila del
empleado-mes (igual que el IBC). Nivel de verificación: hoja 'nomina' real con recibos
calculados con compute_sheet; el Excel completo se prueba en servidor."""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill
except ImportError:  # pragma: no cover
    openpyxl = None

_PAYSLIP = 'odoo.addons.l10n_co_nomina_electronica.models.hr_payslip.HrPayslip'
# Posición (0-based) de cada columna de días en la fila de la hoja (los datos empiezan en la columna C: A y B llevan el
# número de fila, marco de la plantilla Storm User, U1).
_COL = {'trabajados': 20, 'incapacidad': 21, 'lic_mat': 22, 'lic_rem': 23,
        'suspension': 24, 'vacaciones': 25, 'huelga': 26, 'total': 27}


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
            'name': 'Ana Gómez', 'company_id': self.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_payment_method': '10'})
        cedula = self.env['l10n_latam.identification.type'].search(
            [('l10n_co_ne_dian_document_code', '=', '13')], limit=1)
        employee.work_contact_id.l10n_latam_identification_type_id = cedula   # U5: el documento sale del contacto
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
        return [[c.value for c in fila] for fila in ws.iter_rows(min_row=11)]

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

    def test_dos_recibos_del_mes_son_una_sola_fila_con_los_dias_del_consolidado(self):
        # U4 (doc 57): una fila por empleado y mes; los días salen del consolidado del mes, no de cada recibo.
        employee, contract = self._empleado()
        s1 = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 15))
        s1.state = 'done'      # R-2: el segundo cierra el mes y exige el primero confirmado
        s2 = self._recibo(employee, contract, date(2026, 9, 16), date(2026, 9, 30))
        self._confirmar(s1, s2)
        filas = self._filas(s1 | s2)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0][_COL['total']], 30)
        self.assertEqual(filas[0][_COL['trabajados']], 30)

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

    # ── U5 (doc 57): hoja nómina con las listas y columnas de la plantilla ─────────────────────────────
    def test_la_fila_lleva_tipo_y_subtipo_de_cotizante_ugpp_y_la_nota_de_360_sin_columnas_de_ibc(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        fila = self._filas(slip)[0]
        self.assertEqual(fila[2:4], [1, 0])                           # PILA 01/00 -> UGPP 1/0 (columna C en adelante)
        self.assertEqual(fila[8:10], ['CC', '1020304050'])
        self.assertEqual(fila[2 + 35], ugpp._UGPP_NOTA_360)           # observaciones
        # ``_filas`` ya creó el reporte de septiembre de la compañía (único por compañía y mes): se reutiliza.
        reporte = self.Ugpp.search([('company_id', '=', self.company.id), ('year', '=', 2026), ('month', '=', '9')])
        reglas = reporte._get_ugpp_salary_rules(slip)
        self.assertEqual(len(fila), 2 + 36 + len(reglas))             # A, B, 36 fijas y conceptos: sin IBC

    def test_tipo_de_cotizante_pila_21_es_20_en_la_ugpp_y_sin_equivalente_es_error_con_nombre(self):
        # Contratos virtuales (``new``): un contrato abierto no admite quedarse sin tipo de cotizante (validación nativa).
        employee, _contract = self._empleado()
        reporte = self.Ugpp.new({})
        contrato = self.env['hr.contract'].new({
            'l10n_co_pila_tipo_cotizante': '21', 'l10n_co_pila_subtipo_cotizante': '00'})
        self.assertEqual(reporte._ugpp_cotizante(employee, contrato), (20, 0))
        sin_tipo = self.env['hr.contract'].new({'l10n_co_pila_subtipo_cotizante': '00'})
        with self.assertRaisesRegex(UserError, 'Ana Gómez'):
            reporte._ugpp_cotizante(employee, sin_tipo)

    def test_documento_del_trabajador_sin_equivalente_o_con_numero_invalido_es_error(self):
        employee, _contract = self._empleado()
        reporte = self.Ugpp.new({})
        self.assertEqual(reporte._ugpp_documento_trabajador(employee), ('CC', '1020304050'))
        employee.identification_id = '12345678901'                    # 11 dígitos: la cédula admite hasta 10
        with self.assertRaisesRegex(UserError, 'Ana Gómez'):
            reporte._ugpp_documento_trabajador(employee)
        employee.work_contact_id.l10n_latam_identification_type_id = False
        with self.assertRaisesRegex(UserError, 'equivalente'):
            reporte._ugpp_documento_trabajador(employee)

    def test_mas_de_133_conceptos_es_error_claro(self):
        employee, contract = self._empleado()
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        reglas = self.env['hr.salary.rule'].search([('l10n_co_ugpp_payment_type', '!=', False)], limit=2)
        with patch.object(ugpp, '_UGPP_MAX_CONCEPTOS', 1), \
                patch.object(type(self.Ugpp), '_get_ugpp_salary_rules', lambda _s, _p: reglas):
            with self.assertRaisesRegex(UserError, 'admite 1 conceptos'):
                self._filas(slip)

    def test_las_fechas_de_novedades_sin_ausencias_van_vacias_y_suspension_incluye_lic_nr(self):
        employee, _contract = self._empleado()
        reporte = self.Ugpp.create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': self.company.id})
        self.assertEqual(reporte._ugpp_fechas_ausencia(employee, ('CO_VAC',), recortar=False), ('', ''))
        self.assertIn('CO_LIC_NR', reporte._ugpp_codigos_suspension())
        self.assertNotIn('CO_VAC', reporte._ugpp_codigos_suspension())
        self.assertNotIn('CO_LIC_REM', reporte._ugpp_codigos_suspension())

    def _ausencia(self, employee, xmlid, desde, hasta):
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.env.ref('l10n_co_nomina_electronica.' + xmlid).id,
            'request_date_from': desde, 'request_date_to': hasta})
        leave.action_validate()
        self.assertEqual(leave.state, 'validate')
        return leave

    def _reporte_septiembre(self):
        return self.Ugpp.create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': self.company.id})

    def test_fechas_de_novedades_con_ausencias_reales_de_los_tipos_del_modulo(self):
        # Tipos de ausencia REALES del módulo (data/l10n_co_ausencias_data.xml), no tipos inventados.
        employee, _contract = self._empleado()
        self._ausencia(employee, 'hr_leave_type_co_vac', date(2026, 9, 28), date(2026, 10, 2))      # cruza de mes
        self._ausencia(employee, 'hr_leave_type_co_lic_rem', date(2026, 9, 7), date(2026, 9, 8))
        otro, _contrato = self._empleado()      # dos ausencias del mismo empleado no pueden solaparse
        self._ausencia(otro, 'hr_leave_type_co_lic_nr', date(2026, 9, 29), date(2026, 10, 1))        # cruza de mes
        reporte = self._reporte_septiembre()
        # vacaciones: fechas reales de la ausencia (la plantilla no impone el mes)
        self.assertEqual(reporte._ugpp_fechas_ausencia(employee, ('CO_VAC',), recortar=False),
                         ('28/09/2026', '02/10/2026'))
        # permiso y suspensión: recortadas al mes que se reporta
        self.assertEqual(reporte._ugpp_fechas_ausencia(employee, ('CO_LIC_REM',)), ('07/09/2026', '08/09/2026'))
        self.assertEqual(reporte._ugpp_fechas_ausencia(otro, reporte._ugpp_codigos_suspension()),
                         ('29/09/2026', '30/09/2026'))

    def test_una_ausencia_de_otro_mes_no_aparece_en_las_fechas_del_reporte(self):
        employee, _contract = self._empleado()
        self._ausencia(employee, 'hr_leave_type_co_lic_rem', date(2026, 8, 3), date(2026, 8, 4))
        self.assertEqual(self._reporte_septiembre()._ugpp_fechas_ausencia(employee, ('CO_LIC_REM',)), ('', ''))

    def test_los_conceptos_son_enteros_y_un_valor_negativo_es_error(self):
        employee, _contract = self._empleado()
        regla = self.env['hr.salary.rule'].search([('l10n_co_ugpp_payment_type', '!=', False)], limit=1)
        reporte = self.Ugpp.new({})
        self.assertEqual(reporte._ugpp_entero(1000.5, employee, regla), 1001)
        self.assertEqual(reporte._ugpp_entero(1000.49, employee, regla), 1000)
        self.assertIsInstance(reporte._ugpp_entero(12.3, employee, regla), int)
        self.assertEqual(reporte._ugpp_entero(0.0, employee, regla), 0)
        with self.assertRaisesRegex(UserError, 'Ana Gómez'):
            reporte._ugpp_entero(-5.0, employee, regla)

