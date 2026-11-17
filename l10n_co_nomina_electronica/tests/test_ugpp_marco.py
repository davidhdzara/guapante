# -*- coding: utf-8 -*-
"""Frente 4, U1 (doc 57): el libro UGPP lleva el marco de la plantilla oficial ``Anexo_1.xlsx`` (Guía V-20.1 §1.3):
preámbulo, título, fila de códigos, encabezados en la fila 10 y datos desde la 11. Nivel de verificación: estructura
leída de la plantilla; que Storm User acepte el libro generado solo se prueba con Storm real (piloto)."""
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill
except ImportError:  # pragma: no cover
    openpyxl = None

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp


@tagged('post_install', '-at_install')
class TestUgppMarco(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Marco UGPP', 'country_id': cls.env.ref('base.co').id, 'vat': '900123456-8',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})
        cls.company.partner_id.l10n_latam_identification_type_id = cls.env.ref('l10n_co.rut')
        cls.company.write({'l10n_co_ugpp_legal_nature': 'privada', 'l10n_co_ugpp_contributor_type': 'empleador'})
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id})

    def _reglas_de_prueba(self, *_args):
        """Tres reglas con tipo UGPP: el marco no depende de los valores de los recibos."""
        return self.env['hr.salary.rule'].search(
            [('l10n_co_ugpp_payment_type', '!=', False)], order='sequence, code', limit=3)

    def _hoja(self, metodo, *args):
        ws = openpyxl.Workbook().active
        getattr(self.reporte, metodo)(ws, *args, Font(bold=True), PatternFill(), Alignment(), Border())
        return ws

    def _preambulo(self, ws, formulario, descripcion):
        self.assertEqual([ws.cell(row=f, column=2).value for f in range(1, 7)],
                         ['Tipo Modalidad', 'Formulario', 'Moneda Informe', 'Entidad', 'Fecha', 'Periodicidad'])
        self.assertEqual(ws['C1'].value, 7000)
        self.assertEqual(ws['D1'].value, 'Informe Nomina - UGPP')
        self.assertEqual(ws['C2'].value, formulario)
        self.assertEqual(ws['D2'].value, descripcion)
        self.assertEqual(ws['C3'].value, 1)                       # moneda
        self.assertEqual(ws['C4'].value, 900123456)               # NIT sin dígito de verificación
        self.assertEqual(ws['C5'].value, date(2026, 9, 30))   # fecha de corte = último día del periodo
        self.assertEqual((ws['C6'].value, ws['D6'].value), (0, 'Ocasional'))
        self.assertEqual(ws['A8'].value, '[1]')

    def test_hoja_aportante_lleva_el_marco_de_la_plantilla(self):
        ws = self._hoja('_generate_sheet_aportante')
        self._preambulo(ws, 7001, 'Formulario Nómina - Aportante')
        self.assertEqual(ws['B8'].value, '0 Formulario Nómina - Aportante')
        codigos = {c.column_letter: c.value for c in ws[9] if c.value is not None}
        self.assertEqual(codigos, {'C': 4, 'D': 8, 'E': 12, 'F': 16, 'G': 20, 'H': 28})
        self.assertEqual(ws['C10'].value, 'TIPO DOCUMENTO APORTANTE')
        self.assertEqual((ws['A11'].value, ws['B11'].value), (1, 'FILA_1'))
        self.assertEqual(ws['E11'].value, 'Empresa Marco UGPP')   # los datos empiezan en la columna C
        self.assertIsNone(ws['A12'].value)

    def test_hoja_conceptos_lleva_el_marco_y_un_concepto_por_fila(self):
        # Las cuentas de las reglas se prueban en test_ugpp_conceptos: aquí solo el marco de la hoja.
        with patch.object(type(self.reporte), '_ugpp_cuentas_regla', lambda _self, _regla: '510506'), \
                patch.object(type(self.reporte), '_get_ugpp_salary_rules', self._reglas_de_prueba):
            ws = self._hoja('_generate_sheet_conceptos', self.env['hr.payslip'])
        self._preambulo(ws, 7003, 'Formulario Nómina - Concepto Pago Aportante ')
        self.assertEqual(ws['B8'].value, '0 Formulario Nómina - Concepto Pago Aportante')
        self.assertEqual([c.value for c in ws[9] if c.value is not None], [4, 8, 12, 19, 20])
        self.assertEqual([c.value for c in ws[10] if c.value is not None],
                         ['Concepto', 'Nombre concepto', 'Cuenta contable', 'Tipo pago', 'Clasificación TP NO SALARIAL'])
        reglas = self._reglas_de_prueba(self.reporte, self.env['hr.payslip'])
        self.assertTrue(reglas)
        self.assertEqual(ws.max_row, 10 + len(reglas))
        self.assertEqual((ws['A11'].value, ws['B11'].value, ws['C11'].value), (1, 'FILA_1', 1))
        self.assertEqual(ws.cell(row=10 + len(reglas), column=1).value, len(reglas))

    def test_hoja_nomina_lleva_los_codigos_de_columna_de_la_plantilla(self):
        with patch.object(type(self.reporte), '_get_ugpp_salary_rules', self._reglas_de_prueba):
            ws = self._hoja('_generate_sheet_nomina', self.env['hr.payslip'])   # sin recibos: solo marco
        self._preambulo(ws, 7002, 'Formulario Nómina')
        self.assertEqual(ws['B8'].value, '0 Formulario Nómina')
        codigos = [c.value for c in ws[9] if c.value is not None]
        self.assertEqual(codigos[:3], [8, 12, 16])
        self.assertEqual(codigos[31:37], [144, 148, 152, 156, 184, 276])   # fechas nuevas, observaciones, concepto 1
        self.assertEqual(len(set(codigos)), len(codigos))          # sin repetidos
        self.assertEqual(codigos, sorted(codigos))
        n_conceptos = len(self._reglas_de_prueba(self.reporte, self.env['hr.payslip']))
        self.assertEqual(codigos[36:], [276 + 4 * i for i in range(n_conceptos)])
        self.assertEqual(ws['C10'].value, 'Tipo cotizante')
        self.assertFalse(ws['C11'].value)                          # sin recibos no hay filas de datos

    def test_nombres_de_hoja_son_los_de_la_plantilla(self):
        self.assertEqual(
            [h[0] for h in ugpp._UGPP_HOJAS.values()],
            ['Formulario Nómina - Aportante', 'Formulario Nómina - Concepto...', 'Formulario Nómina'])
        self.assertTrue(all(len(h[0]) <= 31 for h in ugpp._UGPP_HOJAS.values()))   # límite de Excel
