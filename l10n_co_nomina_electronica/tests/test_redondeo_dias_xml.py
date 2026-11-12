# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-169: el redondeo de los dias del XML es un parametro de la compañia (sin default silencioso).

El XSD v1.0.6 exige enteros en DiasTrabajados y en la Cantidad de vacaciones, primas,
incapacidades, licencias y huelga. Un valor entero pasa tal cual; uno fraccionario se redondea con
el modo nativo de float_round (HALF-UP, UP, DOWN) que configura la compañia; sin configurar es un
error claro (antes se truncaba con int()). Valores a mano:
- 14,4 -> HALF-UP 14, UP 15, DOWN 14; 14,5 -> HALF-UP 15, UP 15, DOWN 14; 14,9 -> HALF-UP 15,
  UP 15, DOWN 14.
- Vacaciones pendientes de una liquidacion con ingreso 2025-01-01 y retiro 2025-12-31 (358 dias de
  servicio, modo de febrero 'real'): 358 x 30 / 720 = 14,9167 dias -> XML Cantidad: HALF-UP 15,
  UP 15, DOWN 14."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRedondeoDiasXml(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'name': 'Compañía de Prueba Redondeo Días'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Redondeo', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Redondeo', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Redondeo', 'employee_id': employee.id,
            'company_id': cls.company.id, 'structure_type_id': cls.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Liquidación Redondeo', 'employee_id': employee.id,
            'contract_id': cls.contract.id, 'company_id': cls.company.id,
            'struct_id': cls.liquidacion.id,
            'date_from': cls.contract.date_start, 'date_to': date(2025, 12, 31)})

    def _dias(self, valor, modo):
        self.company.l10n_co_ne_redondeo_dias = modo
        return self.slip._ne_dias_xml(valor)

    def test_modos_de_redondeo(self):
        for valor, esperado in ((14.4, (14, 15, 14)), (14.5, (15, 15, 14)), (14.9, (15, 15, 14))):
            for modo, dias in zip(('HALF-UP', 'UP', 'DOWN'), esperado):
                self.assertEqual(self._dias(valor, modo), dias, '%s con %s' % (valor, modo))

    def test_un_valor_entero_pasa_sin_parametro(self):
        self.company.l10n_co_ne_redondeo_dias = False
        self.assertEqual(self.slip._ne_dias_xml(15.0), 15)
        self.assertEqual(self.slip._ne_dias_xml(0), 0)

    def test_un_valor_fraccionario_sin_parametro_falla_con_mensaje_claro(self):
        self.company.l10n_co_ne_redondeo_dias = False
        with self.assertRaises(UserError) as exc:
            self.slip._ne_dias_xml(14.9167)
        self.assertIn(self.company.name, str(exc.exception))
        self.assertIn('Redondeo de días del XML', str(exc.exception))

    def _cantidad_vacaciones_compensadas(self):
        self.slip.compute_sheet()
        devengados = {}
        self.slip._dev_prestaciones(self.slip._group_lines_by_concept(), devengados)
        return devengados['Vacaciones']['VacacionesCompensadas'][0]['Cantidad']

    def test_xml_de_vacaciones_pendientes_fraccionarias(self):
        self.company.l10n_co_ne_redondeo_dias = 'HALF-UP'
        self.assertEqual(self._cantidad_vacaciones_compensadas(), '15')
        self.company.l10n_co_ne_redondeo_dias = 'DOWN'
        self.assertEqual(self._cantidad_vacaciones_compensadas(), '14')
        self.company.l10n_co_ne_redondeo_dias = 'UP'
        self.assertEqual(self._cantidad_vacaciones_compensadas(), '15')

    def test_xml_de_vacaciones_pendientes_sin_parametro_falla(self):
        self.company.l10n_co_ne_redondeo_dias = False
        with self.assertRaises(UserError):
            self._cantidad_vacaciones_compensadas()
