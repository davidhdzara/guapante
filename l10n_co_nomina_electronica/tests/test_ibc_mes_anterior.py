# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-11 (doc 89 + decision del TL del 22-nov): la base «IBC del mes anterior» de las vacaciones, la licencia remunerada y los dias de suspension (SLN) es la SUMA de CO_SS_BASE_IBC de los recibos
confirmados del mes calendario anterior, escalada a 30 dias: ibc = suma x 30 / dias, donde dias = CO_DIAS_SP - SLN - incapacidad comun y laboral (que no entran a CO_SS_BASE_IBC). Antes
(``_ne_ultimo_ibc_anterior``) era la de UN solo recibo: con nomina quincenal, medio mes. No es ``ibc_sp`` del consolidado: ese suma el valor pagado de la incapacidad (66,67 %). Se conserva la
decision de David del 10-nov: la incapacidad no es salario (CST art. 192).

Valores a mano: sueldo 6.000.000 (valor dia 200.000, mes comercial de 30). Agosto-2026 en dos quincenas (1-15 y 16-30), cada una con CO_SS_BASE_IBC 3.000.000 y 15 dias -> 6.000.000.
Vacaciones lun 21 a vie 25 de septiembre. En la quincena 16-30 de septiembre el basico paga (15 - d) dias y el IBC de los d dias de vacacion es base / 30 x d: con la base del mes (6.000.000) el IBC
salarial del recibo es el sueldo de la quincena, 3.000.000; con la base de UNA quincena (3.000.000, antes de H-F1-11) eran 2.500.000 en el caso de 5 dias. Con 10 dias de incapacidad en agosto:
base 4.000.000 en 20 dias -> 4.000.000 x 30 / 20 = 6.000.000 (con ibc_sp serian 5.333.400)."""

from datetime import date
from unittest import mock

from odoo.tests.common import tagged

from . import test_incapacidad_tramo_prorroga as base
from .ibc_previo import crear_recibo_previo

SUELDO = 6000000.0


@tagged('post_install', '-at_install')
class TestIbcMesAnterior(base.TestIncapacidadTramoProrroga):

    def _recibo(self, empleado, contrato, desde, hasta, confirmar=False):
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        if confirmar:
            recibo.write({'state': 'done'})                  # la confirmacion real exige afiliacion y cuentas: aqui solo importa el estado
        return recibo

    def _linea(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def _previo(self, empleado, contrato, base, dias=30.0, mes=date(2026, 8, 1)):
        """Recibo confirmado del mes con SOLO CO_SS_BASE_IBC y CO_DIAS_SP (ver tests/ibc_previo.py)."""
        return crear_recibo_previo(self.env, empleado, contrato, self.nomina, mes, date(mes.year, mes.month, 28), base, dias)

    def _vacaciones(self, empleado, contrato, desde, hasta):
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        tipo = self.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        leave = self.env['hr.leave'].create({
            'employee_id': empleado.id, 'holiday_status_id': tipo.id, 'request_date_from': desde, 'request_date_to': hasta})
        leave.action_validate()
        return leave

    def _con_agosto_en_dos_quincenas(self, nombre):
        empleado, contrato = self._empleado(nombre)
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        for desde, hasta in ((date(2026, 8, 1), date(2026, 8, 15)), (date(2026, 8, 16), date(2026, 8, 30))):
            self._recibo(empleado, contrato, desde, hasta, confirmar=True)
        return empleado, contrato

    # ── el defecto: un solo recibo ──
    def test_quincenal_la_base_es_el_mes_completo_y_no_la_quincena(self):
        empleado, contrato = self._con_agosto_en_dos_quincenas('QuincenalMes')
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 16), date(2026, 9, 30))
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)             # antes: 3.000.000 (la ultima quincena)
        self.assertAlmostEqual(self._linea(recibo, 'CO_IBC_SALARIAL'), SUELDO / 2, delta=0.01)        # el sueldo de la quincena; antes 2.500.000

    def test_mensual_da_lo_mismo_que_antes(self):
        empleado, contrato = self._empleado('MensualMes')
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        self._recibo(empleado, contrato, date(2026, 8, 1), date(2026, 8, 31), confirmar=True)
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)
        self.assertAlmostEqual(self._linea(recibo, 'CO_IBC_SALARIAL'), SUELDO, delta=0.01)

    def test_el_primer_recibo_del_mes_y_el_segundo_usan_el_mismo_mes_anterior(self):
        empleado, contrato = self._con_agosto_en_dos_quincenas('MismoMes')
        primero = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        segundo = self._recibo(empleado, contrato, date(2026, 9, 16), date(2026, 9, 30))
        self.assertAlmostEqual(primero._ne_ibc_mes_anterior(contrato), segundo._ne_ibc_mes_anterior(contrato), delta=0.01)

    # ── casos de la base ──
    def test_mes_anterior_incompleto_se_normaliza_a_mes_completo(self):
        """Ingreso a mitad de mes: base 4.000.000 en 20 dias -> 4.000.000 x 30 / 20 = 6.000.000."""
        empleado, contrato = self._empleado('MesIncompleto')
        self._previo(empleado, contrato, 4000000.0, dias=20.0)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)

    def test_los_recibos_de_otro_empleado_no_se_usan(self):
        empleado, contrato = self._empleado('ConBase')
        otro, contrato_otro = self._empleado('SinBase')
        self._previo(empleado, contrato, 9000000.0)
        recibo = self._recibo(otro, contrato_otro, date(2026, 9, 1), date(2026, 9, 15))
        ibc, mes, con_base = recibo._ne_ibc_mes_anterior_datos(contrato_otro)
        self.assertFalse(con_base)
        self.assertEqual(mes, date(2026, 8, 1))
        self.assertAlmostEqual(ibc, SUELDO, delta=0.01)

    def test_una_base_en_cero_cuenta_como_sin_base(self):
        empleado, contrato = self._empleado('BaseCero')
        self._previo(empleado, contrato, 0.0, dias=0.0)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertFalse(recibo._ne_ibc_mes_anterior_datos(contrato)[2])

    def _agosto_con_ausencia(self, nombre, tipo, desde, hasta, **extra):
        """Un recibo mensual de agosto con una ausencia validada, confirmado; devuelve el recibo de septiembre para consultar la base."""
        empleado, contrato = self._empleado(nombre)
        if extra:
            contrato.write(extra)
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        leave = self.env['hr.leave'].create({
            'employee_id': empleado.id, 'holiday_status_id': self.env.ref(tipo).id, 'request_date_from': desde, 'request_date_to': hasta})
        leave.action_validate()
        self._recibo(empleado, contrato, date(2026, 8, 1), date(2026, 8, 31), confirmar=True)
        return empleado, contrato, self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))

    def test_un_mes_anterior_con_incapacidad_da_el_equivalente_al_salario(self):
        """Decision del TL: la incapacidad no es salario. Agosto con 10 dias de incapacidad comun (10 a 19): CO_SS_BASE_IBC = 20 dias x 200.000 = 4.000.000, CO_DIAS_SP = 30, dias de incapacidad 10:
        dias que sustentan la base = 20 -> 4.000.000 x 30 / 20 = 6.000.000 (el sueldo), no el 66,67 % de esos 10 dias (con ibc_sp: 4.000.000 + 10 x 200.000 x 0,6667 = 5.333.400)."""
        _empleado, contrato, septiembre = self._agosto_con_ausencia(
            'MesConIncapacidad', 'l10n_co_nomina_electronica.hr_leave_type_co_inc_comun', date(2026, 8, 10), date(2026, 8, 19))
        self.assertAlmostEqual(septiembre._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)

    def test_un_mes_anterior_con_suspension_da_el_equivalente_al_salario(self):
        """Agosto con 5 dias de licencia no remunerada (SLN, lun 10 a vie 14): CO_SS_BASE_IBC = 25 dias x 200.000 = 5.000.000, dias que sustentan la base 30 - 5 = 25 -> 5.000.000 x 30 / 25 = 6.000.000."""
        _empleado, contrato, septiembre = self._agosto_con_ausencia(
            'MesConSln', 'l10n_co_nomina_electronica.hr_leave_type_co_lic_nr', date(2026, 8, 10), date(2026, 8, 14))
        self.assertAlmostEqual(septiembre._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)

    def test_el_salario_integral_no_resta_los_dias_de_incapacidad(self):
        """El integral cotiza 70 % del sueldo completo aunque haya incapacidad (CO_SS_BASE_IBC no la excluye): con 10 dias de incapacidad la base sigue siendo 25.000.000 x 70 % = 17.500.000, sin escalar por 20 dias."""
        _empleado, contrato, septiembre = self._agosto_con_ausencia(
            'MesIntegralConIncapacidad', 'l10n_co_nomina_electronica.hr_leave_type_co_inc_comun', date(2026, 8, 10), date(2026, 8, 19),
            wage=25000000.0, l10n_co_ne_integral_salary=True)
        self.assertAlmostEqual(septiembre._ne_ibc_mes_anterior(contrato), 17500000.0, delta=0.01)

    def _anular_despues_de_confirmar(self, nombre, tipo, desde, hasta):
        """Confirma agosto con la ausencia, lee la base de septiembre, anula la ausencia y vuelve a leerla: devuelve (antes, despues)."""
        empleado, contrato = self._empleado(nombre)
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        ausencia = self.env['hr.leave'].create({
            'employee_id': empleado.id, 'holiday_status_id': self.env.ref(tipo).id, 'request_date_from': desde, 'request_date_to': hasta})
        ausencia.action_validate()
        self._recibo(empleado, contrato, date(2026, 8, 1), date(2026, 8, 31), confirmar=True)
        septiembre = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        antes = septiembre._ne_ibc_mes_anterior(contrato)
        ausencia.action_refuse()
        self.assertEqual(ausencia.state, 'refuse')
        return antes, septiembre._ne_ibc_mes_anterior(contrato)

    def test_anular_la_incapacidad_despues_de_confirmar_no_cambia_la_base(self):
        """Los dias de incapacidad del divisor son los del recibo CONFIRMADO (la cantidad de su linea CO_INC_COMUN), no los de las ausencias de hoy: si la ausencia se anula despues de confirmar, la base
        sigue siendo 4.000.000 x 30 / 20 = 6.000.000 (recalculando en vivo daria 4.000.000 x 30 / 30 = 4.000.000, que no corresponde a lo que se pago)."""
        antes, despues = self._anular_despues_de_confirmar(
            'AnulaIncapacidad', 'l10n_co_nomina_electronica.hr_leave_type_co_inc_comun', date(2026, 8, 10), date(2026, 8, 19))
        self.assertAlmostEqual(antes, SUELDO, delta=0.01)
        self.assertAlmostEqual(despues, antes, delta=0.01)

    def test_anular_la_suspension_despues_de_confirmar_no_cambia_la_base(self):
        """Igual con SLN: sus dias salen de las worked_days guardadas del recibo confirmado."""
        antes, despues = self._anular_despues_de_confirmar(
            'AnulaSln', 'l10n_co_nomina_electronica.hr_leave_type_co_lic_nr', date(2026, 8, 10), date(2026, 8, 14))
        self.assertAlmostEqual(antes, SUELDO, delta=0.01)
        self.assertAlmostEqual(despues, antes, delta=0.01)

    def test_el_aviso_no_repite_el_error_de_una_liquidacion_mal_fechada(self):
        """Una liquidacion cuyo date_from no es el inicio del contrato da su error al calcular; el aviso (campo calculado de la vista) no lo repite ni se rompe: queda vacio."""
        empleado, contrato = self._empleado('LiquidacionMalFechada')
        liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        recibo = self.env['hr.payslip'].create({
            'name': 'Liquidacion mal fechada', 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': liquidacion.id, 'date_from': date(2026, 1, 11), 'date_to': date(2026, 8, 15)})
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_LIQ_VAC_DISFRUTADAS'), ('struct_id', '=', liquidacion.id)], limit=1)
        self.assertTrue(regla)
        self.env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': 'CO_LIQ_VAC_DISFRUTADAS', 'name': 'Vacaciones', 'contract_id': contrato.id, 'employee_id': empleado.id,
            'quantity': 1.0, 'rate': 100.0, 'amount': 100.0, 'total': 100.0})
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_el_sueldo_de_respaldo_en_v18_ignora_la_fecha(self):
        """UNA funcion (consultor v19): en v18 la fecha no cambia el resultado; en v19 sera el sueldo de la version vigente en ella."""
        empleado, contrato = self._empleado('Respaldo')
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertEqual(recibo._ne_sueldo_de_respaldo(contrato), SUELDO)
        self.assertEqual(recibo._ne_sueldo_de_respaldo(contrato, date(2026, 1, 1)), recibo._ne_sueldo_de_respaldo(contrato, date(2030, 1, 1)))

    def test_el_sueldo_de_respaldo_integral_es_el_factor_del_sueldo(self):
        empleado, contrato = self._empleado('RespaldoIntegral')
        contrato.write({'wage': 25000000.0, 'l10n_co_ne_integral_salary': True})                      # piso integral 2026: 13 SMMLV = 22.761.765
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertAlmostEqual(recibo._ne_sueldo_de_respaldo(contrato), 17500000.0, delta=0.01)       # 70 %

    def test_sln_usa_la_misma_base(self):
        """Los 5 dias SLN con la base de agosto de 6.000.000: 6.000.000 / 30 x 5 = 1.000.000."""
        empleado, contrato = self._empleado('SlnMes')
        self._previo(empleado, contrato, SUELDO)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        with mock.patch.object(type(recibo), '_ne_dias_sln', return_value=5):
            self.assertAlmostEqual(recibo._ne_ibc_sln(contrato), 1000000.0, delta=0.01)

    # ── el aviso ──
    def test_sin_base_con_vacaciones_avisa_con_empleado_y_ficha_del_empleado(self):
        empleado, contrato = self._empleado('AvisoSinBase')
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        aviso = recibo.l10n_co_ne_aviso_ibc_anterior
        self.assertIn('No hay IBC del mes anterior (2026-08)', aviso)
        self.assertIn('AvisoSinBase', aviso)
        self.assertIn('ficha del empleado', aviso)
        self.assertNotIn('contrato', aviso)                               # una sola redaccion para v18 y v19 (el sueldo vive en la version, no en el contrato)

    def test_con_base_no_avisa(self):
        empleado, contrato = self._empleado('AvisoConBase')
        self._previo(empleado, contrato, SUELDO)
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_sin_vacaciones_ni_licencias_ni_sln_no_avisa(self):
        empleado, contrato = self._empleado('AvisoSinNovedad')
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_la_vista_trae_el_aviso(self):
        from lxml import etree
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        self.assertTrue(arch.xpath("//field[@name='l10n_co_ne_aviso_ibc_anterior']"))

    def test_no_queda_ninguna_llamada_al_ultimo_ibc_anterior(self):
        """La funcion vieja ya no existe: ningun consumidor puede volver a leer un solo recibo."""
        self.assertFalse(hasattr(self.env['hr.payslip'], '_ne_ultimo_ibc_anterior'))
