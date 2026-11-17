# -*- coding: utf-8 -*-
"""Registro de planillas PILA y planilla tipo N (H-017b, commit 4): la correccion exige la
planilla original completa y el MISMO operador; E no lleva original; al generar se deja
constancia y el IBC consolidado queda ligado ('requiere planilla N' si cambia despues).

Nivel de verificacion: validaciones del wizard y registro/consolidado con recibos reales;
el archivo TXT generado no se valida aqui."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPilaPlanilla(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía Prueba Planilla', 'l10n_co_pila_operador_code': '89'})
        cls.env = cls.company.with_company(cls.company).env
        cls.Planilla = cls.env['l10n.co.pila.planilla']
        cls.Wizard = cls.env['l10n.co.hr.pila.wizard.v2']

    def _wizard(self, tipo='E', original=None):
        return self.Wizard.create({
            'year': '2026', 'month': '09', 'tipo_planilla': tipo,
            'company_id': self.company.id,
            'planilla_original_id': original.id if original else False})

    def _planilla(self, **kw):
        vals = {'company_id': self.company.id, 'period': date(2026, 9, 1),
                'tipo_planilla': 'E', 'operador_code': '89',
                'numero_planilla': '123456', 'fecha_pago': date(2026, 10, 5)}
        vals.update(kw)
        return self.Planilla.create(vals)

    def test_e_con_planilla_original_es_error(self):
        with self.assertRaises(UserError):
            self._wizard('E', self._planilla())._validar_planilla_correccion()

    def test_n_sin_original_es_error(self):
        with self.assertRaises(UserError):
            self._wizard('N')._validar_planilla_correccion()

    def test_n_con_original_sin_numero_o_fecha_es_error(self):
        original = self._planilla(numero_planilla=False)
        with self.assertRaises(UserError) as e:
            self._wizard('N', original)._validar_planilla_correccion()
        self.assertIn('número de planilla', str(e.exception))

    def test_n_con_planilla_de_otro_mes_es_error(self):
        original = self._planilla(period=date(2026, 8, 1))
        with self.assertRaises(UserError) as e:
            self._wizard('N', original)._validar_planilla_correccion()
        self.assertIn('ESE mes', str(e.exception))

    def test_dominio_filtra_por_el_periodo_del_wizard(self):
        wizard = self._wizard('N')
        self.assertEqual(wizard.periodo_date, date(2026, 9, 1))

    def test_n_con_operador_distinto_es_error(self):
        original = self._planilla(operador_code='90')
        with self.assertRaises(UserError) as e:
            self._wizard('N', original)._validar_planilla_correccion()
        self.assertIn('MISMO operador', str(e.exception))

    def test_n_correcta_pasa_y_hereda_numero_y_fecha(self):
        original = self._planilla()
        wizard = self._wizard('N', original)
        wizard._validar_planilla_correccion()
        self.assertEqual(wizard.numero_planilla_asociada, '123456')
        self.assertEqual(wizard.fecha_pago_asociada, date(2026, 10, 5))

    def test_registro_liga_el_consolidado_y_marca_si_cambia_despues(self):
        structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Planilla', 'country_id': self.env.ref('base.co').id})
        structure = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Planilla', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Planilla', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        slip = self.env['hr.payslip'].create({
            'name': 'Nómina Planilla', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        slip.compute_sheet()
        slip.state = 'done'
        slip._ne_refrescar_ibc_mensual()
        wizard = self._wizard('E')
        planilla = wizard._registrar_planilla(slip)
        consolidado = self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', employee.id)])
        self.assertEqual(consolidado.planilla_id, planilla)
        self.assertEqual(planilla.operador_code, '89')
        self.assertFalse(consolidado.requiere_planilla_n)
        # un documento tardio cambia el IBC del mes ya reportado
        consolidado.ibc_sp = consolidado.ibc_sp + 100000.0
        self.assertTrue(consolidado.requiere_planilla_n)
        self.assertTrue(planilla.requiere_correccion)
