# -*- coding: utf-8 -*-
"""H-013 (2026-10-08, QA Bloque 4, decisión de David): vacaciones, licencias (remunerada y
no remunerada) e incapacidades entraban como novedades manuales (inputs CO_VAC/CO_LIC_REM/
CO_LIC_NR/CO_INC_COMUN/CO_INC_LABORAL) y el básico (CO_BASICO) no descontaba esos días --
doble pago real (ej. vacaciones 15 días: básico de 30 días completo + vacaciones aparte).

David decidió que estas ausencias deben vivir en el módulo nativo de Ausencias (hr.leave) y
bajar de ahí a la nómina -- una sola fuente: hr.leave validada -> hr.work.entry (mecanismo
nativo hr_work_entry_holidays, confirmado instalado en Guapante) -> worked_days, que ya lee
_ne_dias_pagables() para el básico (vía _NOVEDAD_AUSENCIA_WORK_ENTRY_CODES) y ahora también
las 7 reglas de novedad (data/hr_payroll_structure_data.xml) vía HrPayslip._ne_dias_novedad().

Precondición operativa verificada contra el código fuente real de Odoo 18.0 community
(addons/hr_work_entry_holidays/models/hr_leave.py, addons/hr_work_entry_contract/models/
hr_contract.py), no asumida: hr.leave.action_validate() -> _validate_leave_request() ->
_cancel_work_entry_conflict() SOLO crea los hr.work.entry de la ausencia dentro de la
ventana [contract.date_generated_from, contract.date_generated_to]. En producción, el cron
nativo diario de Odoo (ir_cron_generate_missing_work_entries, parte de
hr_work_entry_contract, instalado y activo por defecto) mantiene esa ventana al día. En una
prueba, sin ese cron corriendo, hay que extender la ventana a mano con
contract.generate_work_entries(date_from, date_to) ANTES de validar la ausencia -- sin ese
paso, la ausencia no genera ningún work entry (esto es justamente lo que se observó en el
hallazgo de la corrección 2/H-009: validar una ausencia sin generar antes los work entries
del contrato no alcanza).

No reproduce números de pesos fijos asumiendo un calendario concreto (duda normativa de
cuántos "días hábiles" cuenta una ausencia según el calendario de cada compañía -- Art. 186
CST, Guapante usa un calendario martes a domingo -- la resuelve David, no se inventa regla
propia aquí, ver ajuste 5). En su lugar lee los días que el mecanismo nativo realmente
produjo (worked_days_line_ids) y verifica la invariante real del bug: básico + novedad debe
dar exactamente el sueldo del período, nunca más (doble pago) ni menos (pago perdido).
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestAusenciasNomina(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py: la
        # build de Odoo.sh corre los tests sobre una COPIA de la BD real de Guapante).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Ausencias',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Ausencias',
            'country_id': co_country.id,
        })
        # Las 7 reglas de novedad viven en la estructura REAL (hr_payroll_structure_
        # co_nomina) -- igual que test_liquidacion_indemnizacion.py usa la estructura real
        # de liquidación en vez de reinventar la fórmula en una estructura de prueba.
        cls.structure = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.leave_type_vac = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        cls.leave_type_lic_rem = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_lic_rem')
        cls.leave_type_lic_nr = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_lic_nr')
        cls.leave_type_inc_comun = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.leave_type_inc_laboral = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_inc_laboral')
        cls.leave_type_lic_mat = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_lic_mat')
        cls.leave_type_lic_pat = cls.env.ref(
            'l10n_co_nomina_electronica.hr_leave_type_co_lic_pat')

    def _make_contract(self, name, wage=1800000.0, date_start=date(2024, 1, 1)):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '80' + str(self.env['hr.employee'].search_count([])),
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

    def _make_validated_leave(self, employee, contract, leave_type, date_from, date_to,
                               work_entries_from=None, work_entries_to=None):
        """Genera primero los work entries del contrato para el período (precondición
        operativa real, ver docstring del módulo) y luego crea y valida la ausencia --
        reproduce lo que el cron nativo diario de Odoo + el flujo normal de RRHH dejarían
        hecho en producción."""
        contract.generate_work_entries(
            work_entries_from or date_from, work_entries_to or date_to)
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })
        leave.action_validate()
        self.assertEqual(leave.state, 'validate')
        return leave

    def _sueldo_basico(self, payslip):
        line = payslip.line_ids.filtered(lambda l: l.code == 'CO_BASICO')
        return line.total if line else 0.0

    def _novedad(self, payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def _dias_worked(self, payslip, work_entry_code):
        wd = payslip.worked_days_line_ids.filtered(
            lambda w: w.work_entry_type_id.code == work_entry_code)
        return wd.number_of_days if wd else 0.0

    def _assert_sin_doble_pago(self, payslip, novedad_code, wage, dias_min=1, dias_max=None):
        """Invariante central del hallazgo: básico + novedad = sueldo del período, ni más
        (doble pago) ni menos (pago perdido) -- sin asumir cuántos días exactos cuenta el
        calendario, solo que el mecanismo nativo produjo AL MENOS uno (si diera 0, la
        prueba pasaría sin probar nada real)."""
        dias = self._dias_worked(payslip, novedad_code)
        self.assertGreaterEqual(
            dias, dias_min,
            'La ausencia validada no generó worked_days para %s (días=%s) -- revisar la '
            'precondición de contract.generate_work_entries() antes de validar, o si el '
            'calendario de la compañía de prueba realmente cubre el rango solicitado.'
            % (novedad_code, dias),
        )
        if dias_max is not None:
            self.assertLessEqual(dias, dias_max)
        basico = self._sueldo_basico(payslip)
        novedad = self._novedad(payslip, novedad_code)
        self.assertEqual(round(basico + novedad, 2), round(wage, 2))
        return dias, basico, novedad

    def test_vacaciones_sin_doble_pago(self):
        """15 días de vacaciones en septiembre -- básico + CO_VAC debe dar el sueldo
        completo del mes, nunca más (antes: básico de 30 días + vacaciones aparte)."""
        wage = 1800000.0
        employee, contract = self._make_contract('Vacaciones', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_vac, date(2026, 9, 16), date(2026, 9, 30))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_VAC', wage)

    def test_licencia_remunerada_sin_doble_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('LicRem', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_rem, date(2026, 9, 1), date(2026, 9, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_LIC_REM', wage)

    def test_licencia_no_remunerada_descuenta_dia_y_paga_cero(self):
        """Licencia no remunerada: el día se descuenta del básico pero no se paga nada --
        ni por el básico ni por CO_LIC_NR. Aquí SÍ se pierde dinero a propósito (por ley),
        así que la invariante es distinta: básico < sueldo completo, novedad = 0."""
        wage = 1800000.0
        employee, contract = self._make_contract('LicNR', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_nr, date(2026, 9, 1), date(2026, 9, 5))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()

        dias = self._dias_worked(payslip, 'CO_LIC_NR')
        self.assertGreaterEqual(
            dias, 1,
            'La ausencia validada no generó worked_days para CO_LIC_NR -- revisar la '
            'precondición de generate_work_entries().',
        )
        basico = self._sueldo_basico(payslip)
        lic_nr = self._novedad(payslip, 'CO_LIC_NR')
        self.assertEqual(lic_nr, 0.0)
        self.assertLess(round(basico, 2), round(wage, 2))

    def test_incapacidad_comun_sin_doble_pago(self):
        """Incapacidad corta (1-2 días) -- se mantiene dentro del tramo "100% a cargo del
        empleador" (Art. 227 CST) sin importar el tramo exacto, para no reproducir aquí la
        fórmula escalonada completa de CO_INC_COMUN."""
        wage = 1800000.0
        employee, contract = self._make_contract('IncComun', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_inc_comun, date(2026, 9, 1), date(2026, 9, 2))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_INC_COMUN', wage, dias_max=2)

    def test_incapacidad_laboral_sin_doble_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('IncLaboral', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_inc_laboral,
            date(2026, 9, 1), date(2026, 9, 3))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_INC_LABORAL', wage)

    def test_licencia_maternidad_sin_doble_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('LicMat', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_mat, date(2026, 9, 1), date(2026, 9, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_LIC_MAT', wage)

    def test_licencia_paternidad_sin_doble_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('LicPat', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_pat, date(2026, 9, 1), date(2026, 9, 5))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_LIC_PAT', wage)

    def test_input_manual_junto_con_ausencia_del_mismo_concepto_falla(self):
        """Si Ausencias YA tiene el dato y además alguien captura el input manual CO_VAC
        para la misma nómina -- nunca sumar ni elegir en silencio, UserError claro."""
        employee, contract = self._make_contract('InputYAusencia', wage=1800000.0)
        self._make_validated_leave(
            employee, contract, self.leave_type_vac, date(2026, 9, 16), date(2026, 9, 30))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self.assertGreater(
            self._dias_worked(payslip, 'CO_VAC'), 0,
            'La ausencia debe generar worked_days antes de poder probar el conflicto con '
            'el input manual.',
        )
        input_type = self.env.ref('l10n_co_nomina_electronica.input_co_vac')
        self.env['hr.payslip.input'].create({
            'payslip_id': payslip.id,
            'input_type_id': input_type.id,
            'code': 'CO_VAC',
            'amount': 15,
        })
        with self.assertRaises(UserError):
            payslip.compute_sheet()

    def test_ausencia_que_cruza_de_mes(self):
        """Vacaciones del 25 de agosto al 5 de septiembre -- solo el tramo de septiembre
        (como máximo 5 días calendario) debe aparecer en worked_days de LA NÓMINA DE
        SEPTIEMBRE; el resto perteneció a la nómina de agosto (no se crea aquí, no hace
        falta para probar el recorte). Básico + vacaciones sigue sin superar el sueldo del
        mes bajo la convención de mes comercial de 30 días (_ne_dias_pagables)."""
        wage = 1800000.0
        employee, contract = self._make_contract(
            'CruceDeMes', wage=wage, date_start=date(2024, 1, 1))
        self._make_validated_leave(
            employee, contract, self.leave_type_vac, date(2026, 8, 25), date(2026, 9, 5),
            work_entries_from=date(2026, 8, 1), work_entries_to=date(2026, 9, 30),
        )
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        self._assert_sin_doble_pago(payslip, 'CO_VAC', wage, dias_max=5)
