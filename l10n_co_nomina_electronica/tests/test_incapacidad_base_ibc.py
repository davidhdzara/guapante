# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-08 (doc 84/89): el valor del dia de la incapacidad comun sale del IBC del MES ANTERIOR al inicio de la incapacidad INICIAL de la cadena (Decreto 1427 de 2022, art. 2.2.3.3.1), el mismo en
todas sus prorrogas, no del sueldo actual en cada recibo. Sin IBC de ese mes, el sueldo con aviso. Misma funcion que las vacaciones (H-F1-11): ``_ne_ibc_mes_anterior``.

Valores a mano: sueldo 6.000.000 (valor dia 200.000), tramo del empleador y EPS (dias 1-90) al 66,67 %, piso diario 2026 = 1.750.905 / 30 = 58.363,5. Incapacidad lun 3 a mie 12 de agosto
(10 dias corridos). El «IBC del mes anterior» (julio) se fija con un recibo confirmado de solo CO_SS_BASE_IBC y CO_DIAS_SP (tests/ibc_previo.py)."""

from datetime import date

from odoo.tests.common import tagged

from . import test_incapacidad_tramo_prorroga as base
from .ibc_previo import crear_recibo_previo

PCT, SUELDO = base.PCT, 6000000.0
PISO_DIA = 1750905.0 / 30


@tagged('post_install', '-at_install')
class TestIncapacidadBaseIbc(base.TestIncapacidadTramoProrroga):

    def _julio(self, empleado, contrato, ibc):
        return crear_recibo_previo(self.env, empleado, contrato, self.nomina, date(2026, 7, 1), date(2026, 7, 31), ibc)

    def _recibo_inc(self, empleado, contrato, desde, hasta):
        contrato.generate_work_entries(date(2026, 1, 1), date(2026, 9, 30))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        return recibo

    def _pago_inc(self, recibo):
        linea = recibo.line_ids.filtered(lambda l: l.code == 'CO_INC_COMUN')
        self.assertTrue(linea, 'El recibo debe pagar incapacidad.')
        return linea.total

    def _agosto(self, nombre, ibc_julio=None):
        empleado, contrato = self._empleado(nombre)
        if ibc_julio is not None:
            self._julio(empleado, contrato, ibc_julio)
        self._incapacidad(empleado, date(2026, 8, 3), date(2026, 8, 12))
        return empleado, contrato, self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))

    # ── la base ──
    def test_sin_ibc_del_mes_anterior_paga_con_el_sueldo_y_avisa(self):
        """Sin recibos de julio: 10 x 200.000 x 0,6667 = 1.333.400 (lo de siempre) y el aviso dice que se uso el sueldo de la ficha del empleado."""
        _empleado, _contrato, recibo = self._agosto('IncSinBase')
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 200000.0 * PCT, delta=0.01)
        self.assertIn('No hay IBC del mes anterior (2026-07)', recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_con_ibc_menor_al_sueldo_paga_con_ese_ibc(self):
        """IBC de julio 4.500.000 (valor dia 150.000): 10 x 150.000 x 0,6667 = 1.000.050, sin aviso. Antes: 1.333.400 (el sueldo actual)."""
        _empleado, _contrato, recibo = self._agosto('IncIbcMenor', ibc_julio=4500000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 150000.0 * PCT, delta=0.01)
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_con_ibc_mayor_al_sueldo_por_variables_paga_con_ese_ibc(self):
        """IBC de julio 7.500.000 por horas extras (valor dia 250.000): 10 x 250.000 x 0,6667 = 1.666.750."""
        _empleado, _contrato, recibo = self._agosto('IncIbcMayor', ibc_julio=7500000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 250000.0 * PCT, delta=0.01)

    def test_el_piso_de_un_smmlv_por_dia_sigue_aplicando(self):
        """IBC de julio 1.000.000: 33.333 x 0,6667 = 22.222 por dia, por debajo del piso de 1 SMMLV por dia (58.363,5, CST art. 227): 10 x 58.363,5 = 583.635."""
        _empleado, _contrato, recibo = self._agosto('IncPiso', ibc_julio=1000000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * PISO_DIA, delta=0.01)

    def test_un_aumento_de_sueldo_despues_de_la_inicial_no_cambia_el_pago(self):
        """El sueldo sube a 8.000.000 despues del inicio: la incapacidad sigue pagandose con el IBC de julio (6.000.000): 1.333.400 (con el sueldo actual serian 1.777.867)."""
        empleado, contrato = self._empleado('IncAumento')
        self._julio(empleado, contrato, SUELDO)
        self._incapacidad(empleado, date(2026, 8, 3), date(2026, 8, 12))
        contrato.write({'wage': 8000000.0})
        recibo = self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 200000.0 * PCT, delta=0.01)

    # ── la cadena ──
    def test_la_prorroga_usa_el_mes_anterior_a_la_inicial_no_al_del_recibo(self):
        """A (1 a 31 de agosto) y su prorroga B (1 a 15 de septiembre, vinculada). IBC de julio 4.500.000 (mes anterior a A) y de agosto 6.000.000 (mes anterior al recibo de septiembre): en la quincena
        1-15 de septiembre las posiciones 32-46 se pagan con el IBC de la INICIAL: 15 x 150.000 x 0,6667 = 1.500.075 (con el de agosto serian 2.000.100). Y no hay aviso: el mes anterior a la inicial SI tiene base."""
        empleado, contrato = self._empleado('IncCadena')
        self._julio(empleado, contrato, 4500000.0)
        a = self._incapacidad(empleado, date(2026, 8, 1), date(2026, 8, 31))
        self._incapacidad(empleado, date(2026, 9, 1), date(2026, 9, 15), prorroga_de=a)
        # el recibo confirmado de agosto va DESPUES de validar las ausencias: hr_payroll_holidays marca «blocked» (a diferir) una ausencia que se valida sobre un recibo ya confirmado y bloquea el calculo
        crear_recibo_previo(self.env, empleado, contrato, self.nomina, date(2026, 8, 1), date(2026, 8, 31), SUELDO)
        recibo = self._recibo_inc(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertAlmostEqual(self._pago_inc(recibo), 15 * 150000.0 * PCT, delta=0.01)
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_el_aviso_mira_el_mes_de_la_inicial_y_no_el_del_recibo(self):
        """Solo hay base en julio (mes anterior a la inicial): el recibo de septiembre, cuyo mes anterior (agosto) no tiene base, NO avisa. Si faltara julio, avisaria de julio."""
        empleado, contrato = self._empleado('IncAvisoInicial')
        self._julio(empleado, contrato, SUELDO)
        a = self._incapacidad(empleado, date(2026, 8, 1), date(2026, 8, 31))
        self._incapacidad(empleado, date(2026, 9, 1), date(2026, 9, 15), prorroga_de=a)
        self.assertFalse(self._recibo_inc(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15)).l10n_co_ne_aviso_ibc_anterior)
        otro, contrato_otro = self._empleado('IncAvisoSinJulio')
        b = self._incapacidad(otro, date(2026, 8, 1), date(2026, 8, 31))
        self._incapacidad(otro, date(2026, 9, 1), date(2026, 9, 15), prorroga_de=b)
        crear_recibo_previo(self.env, otro, contrato_otro, self.nomina, date(2026, 8, 1), date(2026, 8, 31), SUELDO)       # agosto SI tiene base, julio no
        aviso = self._recibo_inc(otro, contrato_otro, date(2026, 9, 1), date(2026, 9, 15)).l10n_co_ne_aviso_ibc_anterior
        self.assertIn('2026-07', aviso)
        self.assertNotIn('2026-08', aviso)

    def test_otros_codigos_de_ausencia_no_cambian(self):
        """Licencia de maternidad (100 % del sueldo) y incapacidad laboral siguen con el sueldo del contrato: H-F1-08 es solo de la incapacidad comun."""
        empleado, contrato = self._empleado('OtrosCodigos')
        self._julio(empleado, contrato, 4500000.0)
        recibo = self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))
        self.assertAlmostEqual(recibo._ne_pago_ausencia_calendario('CO_INC_LABORAL', 5), 5 * 200000.0, delta=0.01)
        self.assertAlmostEqual(recibo._ne_pago_ausencia_calendario('CO_LIC_MAT', 10), 10 * 200000.0, delta=0.01)
