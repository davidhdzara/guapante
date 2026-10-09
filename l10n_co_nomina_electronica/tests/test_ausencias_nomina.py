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

Diagnóstico real en servidor (Tech Lead, staging 39248541): la conversión nativa de
hr.leave a hr.work.entry filtra el resource.calendar.leaves generado por la compañía del
CONTRATO -- si el entorno de la prueba se queda en env.company (la compañía 1 por defecto)
mientras el empleado/contrato son de esta compañía dedicada, el calendar leave se crea con
la compañía equivocada y nunca se ve al generar los work entries. Confirmado que no es un
defecto del diseño ni de los datos de este módulo: el tipo nativo "Unpaid" de Odoo TAMPOCO
convierte bajo el mismo desajuste de compañía, y sí convierte (igual que CO_VAC) cuando
entorno y datos comparten compañía -- exactamente el caso real de producción (una sola
compañía). Por eso setUpClass fija cls.env con with_company(cls.company) antes de crear
ningún dato.
"""

from datetime import date, datetime

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
        # H-013 (2026-10-08, hallazgo de Tech Lead en servidor real): la conversión nativa
        # de hr.leave a hr.work.entry filtra el resource.calendar.leaves por la compañía
        # del CONTRATO -- si el entorno de la prueba sigue en env.company (compañía 1) y
        # el empleado/contrato son de esta compañía dedicada, el calendar leave se crea con
        # company_id=1 y nunca se ve al generar los work entries del contrato. No es un
        # defecto del diseño (confirmado con el tipo nativo "Unpaid": tampoco convierte en
        # ese mismo desajuste) -- es que el entorno de la prueba y los datos deben compartir
        # compañía, igual que en producción (una sola compañía). with_company() hace que
        # TODO lo creado desde cls.env/self.env en este archivo (empleado, contrato,
        # ausencia, nómina) quede en la misma compañía.
        cls.env = cls.company.with_company(cls.company).env
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

    def _make_contract(self, name, wage=1800000.0, date_start=date(2024, 1, 1), calendar=None):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '80' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # l10n_co_ne_payment_method default es '1' (Transferencia Bancaria), que exige
            # l10n_co_ne_bank_account -- sin interés aquí, 'Efectivo' evita datos bancarios falsos.
            'l10n_co_ne_payment_method': '10',
        })
        contract_vals = {
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'date_start': date_start,
            'state': 'open',
        }
        if calendar is not None:
            contract_vals['resource_calendar_id'] = calendar.id
        contract = self.env['hr.contract'].create(contract_vals)
        return employee, contract

    def _make_calendar_martes_a_domingo(self):
        """Calendario Martes a Domingo (H-014, condición 7 de Tech Lead): el mismo patrón
        semanal real de Guapante ('Mar a Dom 42h') -- usado para confirmar que el conteo de
        días CALENDARIO corridos (CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL) no
        depende del patrón semanal del calendario del contrato, a diferencia de CO_VAC/
        CO_LIC_REM/CO_LIC_NR (días hábiles vía worked_days, sí dependientes del calendario)."""
        return self.env['resource.calendar'].create({
            'name': 'Martes a Domingo (prueba)',
            'company_id': self.company.id,
            'attendance_ids': [
                (0, 0, {'name': dia, 'dayofweek': dow, 'hour_from': 8, 'hour_to': 16,
                        'day_period': 'morning'})
                for dow, dia in (
                    ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
                    ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo'),
                )
            ],
        })

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

    # ──────────────────────────────────────────────────────────────────
    # H-014 (2026-10-08, QA Bloque 5): CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
    # cuentan días CALENDARIO corridos (_ne_ausencia_calendario), no worked_days -- por eso
    # estos tests llaman directo a _ne_ausencia_calendario() en vez de _dias_worked() (que
    # mide work entries, un eje distinto que ya no determina el pago de estos 4 conceptos).
    # ──────────────────────────────────────────────────────────────────

    def test_paternidad_14_dias_calendario_lv(self):
        """Paternidad corrida 1-14/12/2026 = 14 días calendario exactos bajo el calendario
        L-V por defecto de la compañía de prueba -- confirma que el conteo cruza los 2 fines
        de semana del rango sin descontarlos (a diferencia de CO_VAC/CO_LIC_REM/CO_LIC_NR)."""
        wage = 1800000.0
        employee, contract = self._make_contract('PatLV', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_pat, date(2026, 12, 1), date(2026, 12, 14))
        payslip = self._make_payslip(employee, contract, date(2026, 12, 1), date(2026, 12, 31))
        payslip.compute_sheet()
        dias, _detalle = payslip._ne_ausencia_calendario('CO_LIC_PAT')
        self.assertEqual(dias, 14)
        basico = self._sueldo_basico(payslip)
        novedad = self._novedad(payslip, 'CO_LIC_PAT')
        self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    def test_paternidad_14_dias_calendario_martes_a_domingo(self):
        """Mismo rango 1-14/12/2026 bajo un calendario Martes a Domingo (patrón real de
        Guapante) -- debe dar el MISMO resultado (14/14) que bajo L-V: el conteo de días
        calendario corridos es independiente del patrón semanal del calendario del contrato,
        justo lo que motivó no usar worked_days para estos 4 conceptos (H-014)."""
        wage = 1800000.0
        calendar = self._make_calendar_martes_a_domingo()
        employee, contract = self._make_contract('PatMarDom', wage=wage, calendar=calendar)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_pat, date(2026, 12, 1), date(2026, 12, 14))
        payslip = self._make_payslip(employee, contract, date(2026, 12, 1), date(2026, 12, 31))
        payslip.compute_sheet()
        dias, _detalle = payslip._ne_ausencia_calendario('CO_LIC_PAT')
        self.assertEqual(dias, 14)
        basico = self._sueldo_basico(payslip)
        novedad = self._novedad(payslip, 'CO_LIC_PAT')
        self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    def _make_calendar_nocturno_bogota(self):
        """Calendario de 7 días (L-D) con jornada hasta las 9pm hora de Bogotá (UTC-5) --
        aísla el bug de huso horario (Tech Lead, revisión .77) del patrón semanal (ya
        cubierto por test_paternidad_14_dias_calendario_martes_a_domingo): todos los días
        de la semana tienen asistencia, así que el único efecto bajo prueba es la
        conversión a UTC del fin de jornada nocturno."""
        return self.env['resource.calendar'].create({
            'name': 'Nocturno Bogotá (prueba)',
            'company_id': self.company.id,
            'tz': 'America/Bogota',
            'attendance_ids': [
                (0, 0, {'name': dia, 'dayofweek': dow, 'hour_from': 13, 'hour_to': 21,
                        'day_period': 'afternoon'})
                for dow, dia in (
                    ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
                    ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo'),
                )
            ],
        })

    def test_paternidad_14_dias_sin_bug_de_huso_horario_nocturno(self):
        """Tech Lead (2026-10-08, revisión .77): hr.leave.date_from/date_to son datetimes
        en UTC -- una ausencia que termina de noche en Colombia (UTC-5, ej. jornada hasta
        las 9pm) cae en la madrugada del día siguiente en UTC, y el fix anterior a este
        (.date() sobre date_from/date_to) contaba 15 días en vez de 14 para 1-14/12/2026.
        _ne_ausencia_calendario() ahora usa request_date_from/request_date_to (fechas
        puras, sin conversión de huso horario) tanto en el dominio del search como en el
        recorte -- esta prueba falla si alguien vuelve a tocar date_from/date_to."""
        wage = 1800000.0
        calendar_nocturno = self._make_calendar_nocturno_bogota()
        employee, contract = self._make_contract(
            'PatNocturno', wage=wage, calendar=calendar_nocturno)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_pat, date(2026, 12, 1), date(2026, 12, 14))
        payslip = self._make_payslip(employee, contract, date(2026, 12, 1), date(2026, 12, 31))
        payslip.compute_sheet()
        dias, _detalle = payslip._ne_ausencia_calendario('CO_LIC_PAT')
        self.assertEqual(dias, 14)
        basico = self._sueldo_basico(payslip)
        novedad = self._novedad(payslip, 'CO_LIC_PAT')
        self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    def test_maternidad_festivo_no_reduce_dias(self):
        """Un festivo (8 dic, Inmaculada Concepción) dentro del rango de licencia de
        maternidad no debe reducir el conteo de días calendario corridos -- estos 4
        conceptos cuentan TODOS los días calendario, festivos incluidos (CST Art. 236 mod.
        Ley 2114/2021), a diferencia de CO_VAC/CO_LIC_REM/CO_LIC_NR (días hábiles vía
        worked_days, que si descuentan festivos del calendario)."""
        wage = 1800000.0
        employee, contract = self._make_contract('MatFestivo', wage=wage)
        self.env['resource.calendar.leaves'].create({
            'name': 'Inmaculada Concepción (prueba)',
            'company_id': self.company.id,
            'calendar_id': False,
            'resource_id': False,
            'date_from': datetime(2026, 12, 8, 0, 0, 0),
            'date_to': datetime(2026, 12, 8, 23, 59, 59),
        })
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_mat, date(2026, 12, 1), date(2026, 12, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 12, 1), date(2026, 12, 31))
        payslip.compute_sheet()
        dias, _detalle = payslip._ne_ausencia_calendario('CO_LIC_MAT')
        self.assertEqual(dias, 10)
        basico = self._sueldo_basico(payslip)
        novedad = self._novedad(payslip, 'CO_LIC_MAT')
        self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    def test_maternidad_cruza_mes_dos_nominas(self):
        """Maternidad del 25 de agosto al 5 de septiembre de 2026 -- cada nómina (agosto y
        septiembre) recibe SOLO su tramo bajo la convención de mes comercial de 30 días
        (_ne_dia_comercial, la MISMA que usa _ne_dias_pagables() para el básico): el 31 de
        agosto, último día real del mes, mapea al día comercial 30. Básico + novedad debe
        dar el sueldo completo en AMBAS nóminas, no solo en una (ningún tramo se paga dos
        veces ni se pierde en el corte de mes)."""
        wage = 1800000.0
        employee, contract = self._make_contract(
            'MatCruzaMes', wage=wage, date_start=date(2024, 1, 1))
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_mat, date(2026, 8, 25), date(2026, 9, 5),
            work_entries_from=date(2026, 8, 1), work_entries_to=date(2026, 9, 30),
        )
        payslip_ago = self._make_payslip(employee, contract, date(2026, 8, 1), date(2026, 8, 31))
        payslip_ago.compute_sheet()
        payslip_sep = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip_sep.compute_sheet()

        dias_ago, _detalle_ago = payslip_ago._ne_ausencia_calendario('CO_LIC_MAT')
        dias_sep, _detalle_sep = payslip_sep._ne_ausencia_calendario('CO_LIC_MAT')
        self.assertEqual(dias_ago, 6)  # 25..31 ago -> comercial 25..30 = 6 días
        self.assertEqual(dias_sep, 5)  # 1..5 sep = 5 días

        for payslip in (payslip_ago, payslip_sep):
            basico = self._sueldo_basico(payslip)
            novedad = self._novedad(payslip, 'CO_LIC_MAT')
            self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    def test_incapacidad_laboral_cruza_fin_de_mes_dos_nominas(self):
        """Incapacidad por accidente de trabajo del 28 de enero al 3 de febrero de 2026 --
        cruza fin de mes bajo la misma convención de mes comercial de 30 días. Se usa
        CO_INC_LABORAL (ARL paga 100% desde el día 1, sin tramos) para poder verificar la
        invariante básico + novedad = sueldo del período en ambas nóminas; CO_INC_COMUN sí
        tiene tramos escalonados (ver test_incapacidad_comun_sin_doble_pago, que se queda
        deliberadamente dentro del tramo "100% empleador" para no reproducir esa fórmula)."""
        wage = 1800000.0
        employee, contract = self._make_contract(
            'IncLaboralCruzaMes', wage=wage, date_start=date(2024, 1, 1))
        self._make_validated_leave(
            employee, contract, self.leave_type_inc_laboral, date(2026, 1, 28), date(2026, 2, 3),
            work_entries_from=date(2026, 1, 1), work_entries_to=date(2026, 2, 28),
        )
        payslip_ene = self._make_payslip(employee, contract, date(2026, 1, 1), date(2026, 1, 31))
        payslip_ene.compute_sheet()
        payslip_feb = self._make_payslip(employee, contract, date(2026, 2, 1), date(2026, 2, 28))
        payslip_feb.compute_sheet()

        dias_ene, _detalle_ene = payslip_ene._ne_ausencia_calendario('CO_INC_LABORAL')
        dias_feb, _detalle_feb = payslip_feb._ne_ausencia_calendario('CO_INC_LABORAL')
        self.assertEqual(dias_ene, 3)  # 28..31 ene -> comercial 28..30 = 3 días
        self.assertEqual(dias_feb, 3)  # 1..3 feb = 3 días

        for payslip in (payslip_ene, payslip_feb):
            basico = self._sueldo_basico(payslip)
            novedad = self._novedad(payslip, 'CO_INC_LABORAL')
            self.assertEqual(round(basico + novedad, 2), round(wage, 2))

    # ──────────────────────────────────────────────────────────────────
    # H-014 (2026-10-08, revisión .78, Tech Lead): nadie probaba el nodo XML de estas 5
    # novedades (_collect_payslip_data()/_dev_novedades()/_dev_prestaciones()) con los
    # tipos REALES de H-013 -- las pruebas de arriba solo verifican las reglas salariales
    # (básico + novedad = sueldo). _LEAVE_CODE_MAP se sincronizó en esta revisión con los
    # 7 códigos CO_ (hr_leave_ne.py); antes de eso, Vacaciones/LicenciaR/LicenciaNR habrían
    # caído en el mismo fallback silencioso de fechas de período completo que expuso Tech
    # Lead para Incapacidad/LicenciaMP.
    # ──────────────────────────────────────────────────────────────────

    def test_xml_vacaciones_fecha_y_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('XmlVac', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_vac, date(2026, 9, 16), date(2026, 9, 30))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        novedad = self._novedad(payslip, 'CO_VAC')
        xml_dict = payslip._collect_payslip_data()
        vacaciones = xml_dict['devengados'].get('Vacaciones', {}).get('VacacionesComunes', [])
        self.assertEqual(len(vacaciones), 1)
        self.assertEqual(vacaciones[0]['FechaInicio'], '2026-09-16')
        self.assertEqual(vacaciones[0]['FechaFin'], '2026-09-30')
        self.assertEqual(vacaciones[0]['Cantidad'], '15')
        self.assertEqual(vacaciones[0]['Pago'], '%.2f' % novedad)

    def test_xml_licencia_remunerada_fecha_y_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('XmlLicRem', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_rem, date(2026, 9, 1), date(2026, 9, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        novedad = self._novedad(payslip, 'CO_LIC_REM')
        xml_dict = payslip._collect_payslip_data()
        licencias = xml_dict['devengados'].get('Licencias', {}).get('LicenciaR', [])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0]['FechaInicio'], '2026-09-01')
        self.assertEqual(licencias[0]['FechaFin'], '2026-09-10')
        self.assertEqual(licencias[0]['Cantidad'], '10')
        self.assertEqual(licencias[0]['Pago'], '%.2f' % novedad)

    def test_xml_licencia_no_remunerada_fecha_y_cantidad(self):
        """CO_LIC_NR nunca paga (0 pesos por diseño, ver amount_python_compute en data/
        hr_payroll_structure_data.xml) -- el nodo XML de LicenciaNR no lleva el campo
        'Pago' en absoluto (ver _dev_novedades()), no es que valga '0.00'."""
        wage = 1800000.0
        employee, contract = self._make_contract('XmlLicNR', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_nr, date(2026, 9, 1), date(2026, 9, 5))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        xml_dict = payslip._collect_payslip_data()
        licencias = xml_dict['devengados'].get('Licencias', {}).get('LicenciaNR', [])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0]['FechaInicio'], '2026-09-01')
        self.assertEqual(licencias[0]['FechaFin'], '2026-09-05')
        self.assertEqual(licencias[0]['Cantidad'], '5')
        self.assertNotIn('Pago', licencias[0])

    def test_xml_incapacidad_fecha_y_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('XmlInc', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_inc_comun, date(2026, 9, 1), date(2026, 9, 2))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        novedad = self._novedad(payslip, 'CO_INC_COMUN')
        xml_dict = payslip._collect_payslip_data()
        incapacidades = xml_dict['devengados'].get('Incapacidades', [])
        self.assertEqual(len(incapacidades), 1)
        self.assertEqual(incapacidades[0]['FechaInicio'], '2026-09-01')
        self.assertEqual(incapacidades[0]['FechaFin'], '2026-09-02')
        self.assertEqual(incapacidades[0]['Cantidad'], '2')
        self.assertEqual(incapacidades[0]['Pago'], '%.2f' % novedad)

    def test_xml_licencia_maternidad_fecha_y_pago(self):
        wage = 1800000.0
        employee, contract = self._make_contract('XmlLicMat', wage=wage)
        self._make_validated_leave(
            employee, contract, self.leave_type_lic_mat, date(2026, 9, 1), date(2026, 9, 10))
        payslip = self._make_payslip(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        payslip.compute_sheet()
        novedad = self._novedad(payslip, 'CO_LIC_MAT')
        xml_dict = payslip._collect_payslip_data()
        licencias = xml_dict['devengados'].get('Licencias', {}).get('LicenciaMP', [])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0]['FechaInicio'], '2026-09-01')
        self.assertEqual(licencias[0]['FechaFin'], '2026-09-10')
        self.assertEqual(licencias[0]['Cantidad'], '10')
        self.assertEqual(licencias[0]['Pago'], '%.2f' % novedad)
