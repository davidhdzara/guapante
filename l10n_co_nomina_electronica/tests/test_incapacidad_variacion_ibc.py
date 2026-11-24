# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-08 P2 (doc 106): limite del 40 % de la base de la incapacidad comun (Decreto 780 de 2016, art. 2.2.3.4.5, Decreto 2126 de 2023): «las variaciones en el Ingreso Base de Cotizacion [...] del
mes anterior al inicio de la incapacidad que excedan el cuarenta por ciento (40%) respecto del promedio de los doce (12) meses inmediatamente anteriores, o su fraccion de meses cuando este tiempo
fuere menor, no seran tomadas en consideracion, en la parte que exceda de dicho porcentaje».

Valores a mano: sueldo 6.000.000, tramo del empleador y EPS (dias 1-90) al 66,67 %, 10 dias corridos (lun 3 a mie 12 de agosto de 2026). El IBC de julio (el mes anterior a la inicial) y el de los meses
previos se fijan con recibos confirmados de solo CO_SS_BASE_IBC y CO_DIAS_SP (tests/ibc_previo.py). Con promedio previo 6.000.000 el tope es 6.000.000 x 1,4 = 8.400.000 (valor dia 280.000)."""

import calendar
from datetime import date

from odoo.tests.common import tagged

from . import test_incapacidad_tramo_prorroga as base
from .ibc_previo import crear_recibo_previo

PCT = base.PCT
PROMEDIO = 6000000.0
TOPE = PROMEDIO * 1.4          # 8.400.000


@tagged('post_install', '-at_install')
class TestIncapacidadVariacionIbc(base.TestIncapacidadTramoProrroga):

    def _mes(self, empleado, contrato, anio, mes, ibc):
        """Recibo confirmado de TODO un mes con ese IBC."""
        ultimo = calendar.monthrange(anio, mes)[1]
        return crear_recibo_previo(self.env, empleado, contrato, self.nomina, date(anio, mes, 1), date(anio, mes, ultimo), ibc)

    def _meses_previos(self, empleado, contrato, desde, hasta, ibc=PROMEDIO):
        """Un recibo por mes, de ``desde`` a ``hasta`` (ambos (anio, mes), inclusive)."""
        anio, mes = desde
        while (anio, mes) <= hasta:
            self._mes(empleado, contrato, anio, mes, ibc)
            mes += 1
            if mes == 13:
                anio, mes = anio + 1, 1

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

    def _agosto(self, nombre, ibc_julio, previos=((2026, 1), (2026, 6))):
        """Incapacidad del 3 al 12 de agosto; ``previos`` = (desde, hasta) de los meses previos a julio con IBC de 6.000.000 (None: sin meses previos)."""
        empleado, contrato = self._empleado(nombre)
        if previos:
            self._meses_previos(empleado, contrato, previos[0], previos[1])
        self._mes(empleado, contrato, 2026, 7, ibc_julio)
        self._incapacidad(empleado, date(2026, 8, 3), date(2026, 8, 12))
        return empleado, contrato, self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))

    def test_dentro_del_limite_paga_con_el_ibc_completo_y_sin_aviso(self):
        """IBC de julio 7.000.000 (16,7 % sobre el promedio de 6.000.000): no excede el 40 %. 10 x (7.000.000 / 30) x 0,6667."""
        _e, _c, recibo = self._agosto('VarDentro', 7000000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 7000000.0 / 30 * PCT, delta=0.01)
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_si_excede_el_40_por_ciento_se_paga_sobre_el_tope_y_se_avisa(self):
        """IBC de julio 12.000.000 contra promedio 6.000.000 (6 meses): tope 8.400.000. 10 x 280.000 x 0,6667 = 1.866.760 (sin tope serian 2.666.800). El aviso dice el articulo y el mes."""
        _e, _c, recibo = self._agosto('VarExcede', 12000000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * TOPE / 30 * PCT, delta=0.01)
        aviso = recibo.l10n_co_ne_aviso_ibc_anterior
        self.assertIn('2.2.3.4.5', aviso)
        self.assertIn('2026-07', aviso)
        self.assertIn('40', aviso)

    def test_con_un_solo_mes_previo_el_promedio_es_ese_mes(self):
        """«O su fraccion de meses cuando este tiempo fuere menor»: solo junio (6.000.000) como mes previo: el mismo tope de 8.400.000."""
        _e, _c, recibo = self._agosto('VarUnMes', 12000000.0, previos=((2026, 6), (2026, 6)))
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * TOPE / 30 * PCT, delta=0.01)

    def test_sin_meses_previos_no_hay_con_que_comparar_y_no_se_limita(self):
        """Primer mes con IBC (julio): no hay promedio previo. 10 x (12.000.000 / 30) x 0,6667 = 2.666.800, sin aviso de tope."""
        _e, _c, recibo = self._agosto('VarSinPrevios', 12000000.0, previos=None)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 12000000.0 / 30 * PCT, delta=0.01)
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_un_mes_fuera_de_la_ventana_de_12_no_entra_al_promedio(self):
        """Julio de 2026 = 9.000.000; de julio de 2025 a junio de 2026 (12 meses) 6.000.000; enero de 2025 = 60.000.000 queda FUERA de los 12 meses. Si entrara, el promedio seria 10.500.000 y no
        habria tope; fuera, el promedio es 6.000.000 y el tope 8.400.000 (9.000.000 lo excede)."""
        empleado, contrato = self._empleado('VarVentana')
        contrato.write({'date_start': date(2024, 1, 1)})
        self._mes(empleado, contrato, 2025, 1, 60000000.0)
        self._meses_previos(empleado, contrato, (2025, 7), (2026, 6))
        self._mes(empleado, contrato, 2026, 7, 9000000.0)
        self._incapacidad(empleado, date(2026, 8, 3), date(2026, 8, 12))
        recibo = self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * TOPE / 30 * PCT, delta=0.01)

    def test_el_porcentaje_es_un_parametro_por_fecha(self):
        """Con el parametro en 100 % el tope es 12.000.000: el IBC de julio (12.000.000) no se limita. Una fila nueva del parametro (fecha 2026-01-01), sin tocar la de 2024."""
        parametro = self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_incapacidad_variacion_pct')], limit=1)
        self.assertTrue(parametro, 'El parametro l10n_co_incapacidad_variacion_pct debe existir.')
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'parameter_value': '100', 'date_from': date(2026, 1, 1)})
        _e, _c, recibo = self._agosto('VarParametro', 12000000.0)
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 12000000.0 / 30 * PCT, delta=0.01)
        self.assertFalse(recibo.l10n_co_ne_aviso_ibc_anterior)

    def test_el_tope_es_el_mismo_en_toda_la_cadena(self):
        """A (1 a 31 de agosto) y su prorroga B (1 a 15 de septiembre, vinculada): la quincena 1-15 de septiembre paga las posiciones 32-46 con el tope calculado sobre el mes anterior a la INICIAL
        (julio): 15 x 280.000 x 0,6667 = 2.800.140. El recibo confirmado de agosto (con un IBC de 20.000.000 que NO debe usarse) va DESPUES de validar las ausencias."""
        empleado, contrato = self._empleado('VarCadena')
        self._meses_previos(empleado, contrato, (2026, 1), (2026, 6))
        self._mes(empleado, contrato, 2026, 7, 12000000.0)
        a = self._incapacidad(empleado, date(2026, 8, 1), date(2026, 8, 31))
        self._incapacidad(empleado, date(2026, 9, 1), date(2026, 9, 15), prorroga_de=a)
        self._mes(empleado, contrato, 2026, 8, 20000000.0)
        recibo = self._recibo_inc(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15))
        self.assertAlmostEqual(self._pago_inc(recibo), 15 * TOPE / 30 * PCT, delta=0.01)

    def test_vacaciones_licencia_y_sln_no_llevan_el_tope(self):
        """El tope es de la prestacion economica de la incapacidad: ``_ne_ibc_mes_anterior`` (vacaciones, licencia remunerada, SLN) sigue devolviendo el IBC completo de julio (12.000.000), y la base
        de la incapacidad el tope (8.400.000)."""
        empleado, contrato, recibo = self._agosto('VarOtrosUsos', 12000000.0)
        self.assertAlmostEqual(recibo._ne_ibc_mes_anterior(contrato, antes_de=date(2026, 8, 3)), 12000000.0, delta=0.01)
        ibc, mes, con_base, tope = recibo._ne_ibc_incapacidad_datos(contrato, antes_de=date(2026, 8, 3))
        self.assertAlmostEqual(ibc, TOPE, delta=0.01)
        self.assertEqual(mes, date(2026, 7, 1))
        self.assertTrue(con_base)
        self.assertEqual(tope['meses'], 6)
        self.assertAlmostEqual(tope['promedio'], PROMEDIO, delta=0.01)
        self.assertAlmostEqual(tope['base'], 12000000.0, delta=0.01)

    def test_sin_ibc_del_mes_anterior_no_hay_tope_y_sigue_el_aviso_del_sueldo(self):
        """Sin recibos de julio: la base es el sueldo de la ficha (6.000.000) con el aviso de siempre; el tope no interviene aunque haya meses previos."""
        empleado, contrato = self._empleado('VarSinJulio')
        self._meses_previos(empleado, contrato, (2026, 1), (2026, 5), ibc=3000000.0)
        self._incapacidad(empleado, date(2026, 8, 3), date(2026, 8, 12))
        recibo = self._recibo_inc(empleado, contrato, date(2026, 8, 1), date(2026, 8, 15))
        self.assertAlmostEqual(self._pago_inc(recibo), 10 * 6000000.0 / 30 * PCT, delta=0.01)
        self.assertIn('No hay IBC del mes anterior (2026-07)', recibo.l10n_co_ne_aviso_ibc_anterior)
        self.assertNotIn('2.2.3.4.5', recibo.l10n_co_ne_aviso_ibc_anterior)
