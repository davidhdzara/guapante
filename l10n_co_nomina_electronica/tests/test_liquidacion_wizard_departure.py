# -*- coding: utf-8 -*-
"""H-011 (2026-10-06): el wizard de liquidación (l10n.co.hr.liquidacion.wizard) proponía
siempre fecha de hoy y causal vacía, incluso cuando el retiro del empleado ya se había
registrado en RRHH. David confirmó el flujo real: 1) se registra el retiro
(hr.departure.wizard, nativo de Odoo), 2) se liquida -- "de ahí en adelante se baja todo".

Los campos reales que deja ese wizard nativo (hr.employee.departure_date/
departure_reason_id, hr.contract.date_end) están verificados contra el código fuente real de
Odoo 18.0 community, no supuestos:
  - addons/hr/wizard/hr_departure_wizard.py -- action_register_departure() escribe
    employee.departure_reason_id/departure_date.
  - addons/hr_contract/wizard/hr_departure_wizard.py -- con "Set Contract End Date" marcado
    (default para un contract manager), también escribe contract.date_end = departure_date y
    cierra el contrato (state='close').
  - addons/hr/data/hr_data.xml -- xmlids de los 3 motivos de retiro por defecto:
    hr.departure_fired / hr.departure_resigned / hr.departure_retired.

Pruebas sobre el onchange directamente (self.env[...].new({}) + llamada directa al método,
patrón estándar de Odoo para probar un @api.onchange sin pasar por una vista/Form real).
"""

from datetime import date

from odoo import fields
from odoo.tests.common import TransactionCase


class TestLiquidacionWizardDeparture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py: la build
        # de Odoo.sh corre los tests sobre una COPIA de la BD real de Guapante).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Retiro RRHH',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Retiro RRHH',
            'country_id': co_country.id,
        })

    def _make_employee_con_contrato(self, name, date_start=date(2024, 1, 1)):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '70' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date_start,
            'state': 'open',
        })
        employee.contract_id = contract.id
        return employee, contract

    def _registrar_retiro(self, employee, contract, departure_date, reason_xmlid=None):
        """Simula lo que deja hr.departure.wizard con 'Set Contract End Date' marcado
        (ver docstring del módulo) -- no se instancia ese wizard porque no pertenece a este
        módulo; se escriben directamente los campos reales que él mismo escribiría."""
        contract.write({'date_end': departure_date, 'state': 'close'})
        employee.departure_date = departure_date
        if reason_xmlid:
            employee.departure_reason_id = self.env.ref(reason_xmlid)

    def _new_wizard(self):
        return self.env['l10n.co.hr.liquidacion.wizard'].new({})

    def test_con_retiro_registrado_prellena_fecha_desde_contract_date_end(self):
        """(a) Fecha prellenada desde contract.date_end, y el contrato correcto."""
        employee, contract = self._make_employee_con_contrato('ConRetiro')
        self._registrar_retiro(employee, contract, date(2026, 11, 15))

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertEqual(wizard.contract_id.id, contract.id)
        self.assertEqual(wizard.date_end, date(2026, 11, 15))

    def test_con_retiro_registrado_sin_set_date_end_usa_departure_date_del_empleado(self):
        """Respaldo: si en hr.departure.wizard 'Set Contract End Date' quedó desmarcado,
        contract.date_end sigue vacío pero employee.departure_date ya tiene el dato."""
        employee, contract = self._make_employee_con_contrato('SinSetDateEnd')
        employee.departure_date = date(2026, 11, 20)

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertFalse(contract.date_end)
        self.assertEqual(wizard.date_end, date(2026, 11, 20))

    def test_motivo_resigned_prellena_causal_renuncia(self):
        """(b) 'Resigned' es inequívoco -- siempre renuncia voluntaria."""
        employee, contract = self._make_employee_con_contrato('Renuncio')
        self._registrar_retiro(employee, contract, date(2026, 11, 15), 'hr.departure_resigned')

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertEqual(wizard.cause, 'renuncia')

    def test_motivo_fired_deja_causal_vacia(self):
        """(b) 'Fired' no distingue con/sin justa causa en RRHH nativo -- de eso depende la
        indemnización (Art. 64 CST), así que la causal queda vacía y obligatoria, nunca un
        default silencioso que generaría una indemnización incorrecta."""
        employee, contract = self._make_employee_con_contrato('Despedido')
        self._registrar_retiro(employee, contract, date(2026, 11, 15), 'hr.departure_fired')

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertFalse(wizard.cause)

    def test_motivo_retired_deja_causal_vacia(self):
        """'Retired' tampoco tiene causal equivalente entre las 6 que maneja esta
        liquidación (no es ninguna de justa_causa/sin_justa_causa/renuncia/mutuo_acuerdo/
        fin_obra/muerte) -- queda fuera del mapeo a propósito."""
        employee, contract = self._make_employee_con_contrato('Jubilado')
        self._registrar_retiro(employee, contract, date(2026, 11, 15), 'hr.departure_retired')

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertFalse(wizard.cause)

    def test_sin_retiro_registrado_no_cambia_comportamiento(self):
        """(c) Sin retiro registrado -- misma fecha de hoy y causal vacía que antes de esta
        corrección."""
        employee, _contract = self._make_employee_con_contrato('SinRetiro')

        wizard = self._new_wizard()
        wizard.employee_id = employee
        wizard._onchange_employee_id()

        self.assertEqual(wizard.date_end, fields.Date.context_today(wizard))
        self.assertFalse(wizard.cause)

    def test_cambiar_de_empleado_no_arrastra_datos_del_anterior(self):
        """Si el usuario cambia de empleado dentro del mismo wizard, la fecha/causal
        prellenadas para el primer empleado no deben quedar pegadas al segundo."""
        con_retiro, contract_con_retiro = self._make_employee_con_contrato('ConRetiroPrevio')
        self._registrar_retiro(
            con_retiro, contract_con_retiro, date(2026, 11, 15), 'hr.departure_resigned')
        sin_retiro, _contract_sin_retiro = self._make_employee_con_contrato('SinRetiroPrevio')

        wizard = self._new_wizard()
        wizard.employee_id = con_retiro
        wizard._onchange_employee_id()
        self.assertEqual(wizard.cause, 'renuncia')

        wizard.employee_id = sin_retiro
        wizard._onchange_employee_id()
        self.assertFalse(wizard.cause)
        self.assertEqual(wizard.date_end, fields.Date.context_today(wizard))

    def test_regresion_misma_liquidacion_con_o_sin_prellenado(self):
        """(d) Regresión: la liquidación resultante (CO_LIQ_SALARIOS/CO_LIQ_INDEMNIZACION)
        es idéntica si date_end/cause se obtienen a mano (comportamiento anterior a esta
        corrección) o vía el prellenado nuevo -- esta corrección solo toca el onchange del
        wizard, nunca las fórmulas de hr_payroll_structure_special_data.xml. No reproduce
        los valores exactos del caso real NE0000000079 (no tengo los días restantes exactos
        de ese contrato, y no quiero inventarlos) -- compara los dos caminos con el MISMO
        contrato/causa/días restantes, que es lo que realmente puede romper este cambio."""
        employee, contract = self._make_employee_con_contrato(
            'Regresion', date_start=date(2024, 10, 5))
        contract.l10n_co_ne_contract_type = '1'
        self._registrar_retiro(
            employee, contract, date(2026, 11, 15), 'hr.departure_resigned')

        wizard_manual = self.env['l10n.co.hr.liquidacion.wizard'].create({
            'employee_id': employee.id,
            'contract_id': contract.id,
            'date_end': date(2026, 11, 15),
            'cause': 'sin_justa_causa',
            'dias_restantes_contrato': 100,
        })
        payslip_manual = self.env['hr.payslip'].browse(
            wizard_manual.action_create_liquidacion()['res_id'])
        payslip_manual.compute_sheet()

        wizard_prellenado = self._new_wizard()
        wizard_prellenado.employee_id = employee
        wizard_prellenado._onchange_employee_id()
        wizard_prellenado.cause = 'sin_justa_causa'
        wizard_prellenado.dias_restantes_contrato = 100
        payslip_prellenado = self.env['hr.payslip'].browse(
            wizard_prellenado.action_create_liquidacion()['res_id'])
        payslip_prellenado.compute_sheet()

        self.assertEqual(wizard_prellenado.date_end, date(2026, 11, 15))

        sueldo_manual = payslip_manual.line_ids.filtered(
            lambda l: l.code == 'CO_LIQ_SALARIOS').total
        sueldo_prellenado = payslip_prellenado.line_ids.filtered(
            lambda l: l.code == 'CO_LIQ_SALARIOS').total
        indemniz_manual = payslip_manual.line_ids.filtered(
            lambda l: l.code == 'CO_LIQ_INDEMNIZACION').total
        indemniz_prellenado = payslip_prellenado.line_ids.filtered(
            lambda l: l.code == 'CO_LIQ_INDEMNIZACION').total

        self.assertEqual(round(sueldo_manual, 2), round(sueldo_prellenado, 2))
        self.assertEqual(round(indemniz_manual, 2), round(indemniz_prellenado, 2))
