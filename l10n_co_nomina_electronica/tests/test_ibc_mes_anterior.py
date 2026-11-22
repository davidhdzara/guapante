# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-11 (doc 89, aprobado por el TL): la base «IBC del mes anterior» de las vacaciones, la licencia remunerada y los dias de suspension (SLN) sale del IBC CONSOLIDADO del empleado y el
mes (``l10n.co.ibc.mensual``), no de UN solo recibo (``_ne_ultimo_ibc_anterior``, que con nomina quincenal era medio mes y con semanal una semana).

Valores a mano: sueldo 6.000.000 (valor dia 200.000, mes comercial de 30). Agosto-2026 en dos quincenas (1-15 y 16-30), cada una con IBC 3.000.000 -> consolidado 6.000.000 y 30 dias.
Vacaciones lun 21 a vie 25 de septiembre. En la quincena 16-30 de septiembre el basico paga (15 - d) dias y el IBC de los d dias de vacacion es base / 30 x d: con la base del mes
(6.000.000) el IBC salarial del recibo es el sueldo de la quincena, 3.000.000; con la base de UNA quincena (3.000.000, antes de H-F1-11) eran 2.500.000 en el caso de 5 dias. El caso semanal lo
cubre el escalado de test_periodos_ibc_semanal (el consolidado ya suma las semanas del mes)."""

from datetime import date
from unittest import mock

from odoo.tests.common import tagged

from . import test_incapacidad_tramo_prorroga as base

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

    def _consolidado(self, empleado, mes, ibc_sp, dias_sp):
        return self.env['l10n.co.ibc.mensual'].create({
            'company_id': self.company.id, 'employee_id': empleado.id, 'period': mes, 'ibc_sp': ibc_sp, 'dias_sp': dias_sp})

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
        self.env['l10n.co.ibc.mensual']._refrescar(self.company, empleado, date(2026, 8, 1))
        return empleado, contrato

    # ── el defecto: un solo recibo ──
    def test_quincenal_la_base_es_el_mes_completo_y_no_la_quincena(self):
        empleado, contrato = self._con_agosto_en_dos_quincenas('QuincenalMes')
        consolidado = self.env['l10n.co.ibc.mensual'].search([('employee_id', '=', empleado.id), ('period', '=', date(2026, 8, 1))])
        self.assertAlmostEqual(consolidado.ibc_sp, SUELDO, delta=0.01)
        self.assertEqual(consolidado.dias_sp, 30)
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 16), date(2026, 9, 30))
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)             # antes: 3.000.000 (la ultima quincena)
        self.assertAlmostEqual(self._linea(recibo, 'CO_IBC_SALARIAL'), SUELDO / 2, delta=0.01)        # el sueldo de la quincena; antes 2.500.000

    def test_mensual_da_lo_mismo_que_antes(self):
        empleado, contrato = self._empleado('MensualMes')
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        self._recibo(empleado, contrato, date(2026, 8, 1), date(2026, 8, 31), confirmar=True)
        self.env['l10n.co.ibc.mensual']._refrescar(self.company, empleado, date(2026, 8, 1))
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
        """Ingreso a mitad de mes: IBC 4.000.000 en 20 dias -> 4.000.000 x 30 / 20 = 6.000.000."""
        empleado, contrato = self._empleado('MesIncompleto')
        self._consolidado(empleado, date(2026, 8, 1), 4000000.0, 20)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato), SUELDO, delta=0.01)

    def test_el_consolidado_de_otro_empleado_no_se_usa(self):
        empleado, contrato = self._empleado('ConConsolidado')
        otro, contrato_otro = self._empleado('SinConsolidado')
        self._consolidado(empleado, date(2026, 8, 1), 9000000.0, 30)
        recibo = self._recibo(otro, contrato_otro, date(2026, 9, 1), date(2026, 9, 15))
        ibc, mes, con_consolidado = recibo._ne_ibc_mes_anterior_datos(contrato_otro)
        self.assertFalse(con_consolidado)
        self.assertEqual(mes, date(2026, 8, 1))
        self.assertAlmostEqual(ibc, SUELDO, delta=0.01)

    def test_un_consolidado_en_cero_cuenta_como_sin_consolidado(self):
        empleado, contrato = self._empleado('ConsolidadoCero')
        self._consolidado(empleado, date(2026, 8, 1), 0.0, 0)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertFalse(recibo._ne_ibc_mes_anterior_datos(contrato)[2])

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
        """Los 5 dias SLN con el consolidado de agosto de 6.000.000: 6.000.000 / 30 x 5 = 1.000.000."""
        empleado, contrato = self._empleado('SlnMes')
        self._consolidado(empleado, date(2026, 8, 1), SUELDO, 30)
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        with mock.patch.object(type(recibo), '_ne_dias_sln', return_value=5):
            self.assertAlmostEqual(recibo._ne_ibc_sln(contrato), 1000000.0, delta=0.01)

    # ── el aviso ──
    def test_sin_consolidado_con_vacaciones_avisa_con_empleado_y_ficha_del_empleado(self):
        empleado, contrato = self._empleado('AvisoSinBase')
        self._vacaciones(empleado, contrato, date(2026, 9, 21), date(2026, 9, 25))
        recibo = self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30))
        aviso = recibo.l10n_co_ne_aviso_ibc_anterior
        self.assertIn('No hay IBC consolidado de 2026-08', aviso)
        self.assertIn('AvisoSinBase', aviso)
        self.assertIn('ficha del empleado', aviso)
        self.assertNotIn('contrato', aviso)                               # una sola redaccion para v18 y v19 (el sueldo vive en la version, no en el contrato)

    def test_con_consolidado_no_avisa(self):
        empleado, contrato = self._empleado('AvisoConBase')
        self._consolidado(empleado, date(2026, 8, 1), SUELDO, 30)
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
