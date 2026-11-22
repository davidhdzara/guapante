# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-01 (doc 84, decisiones D-84-1 = B y D-84-3 del TL): la cadena de incapacidades comunes la dan los vinculos EXPLICITOS «Prórroga de», no la contiguidad de las fechas.

Norma: Decreto 1427 de 2022, art. 2.2.3.3.2, par. 1 (antes Decreto 1333 de 2018, art. 3): misma enfermedad o relacionada, con una interrupcion de a lo sumo 30 dias calendario. El modulo no decide
la «misma enfermedad»: lo marca quien registra la ausencia; el parametro ``l10n_co_dias_interrupcion_prorroga`` (30) solo rechaza el vinculo con mas dias libres. Valores a mano con el caso de QA FUN-REG-012:
salario 6.000.000 (valor dia 200.000), tramos 66,67 % (dias 1-90) y 50 % (91 en adelante)."""

import importlib.util
import os
from datetime import date

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from . import test_incapacidad_tramo_prorroga as base

PCT, VALOR_DIA = base.PCT, base.VALOR_DIA
PARAMETRO_2024 = 'l10n_co_nomina_electronica.rule_parameter_dias_interrupcion_prorroga_2024'


@tagged('post_install', '-at_install')
class TestIncapacidadProrrogaVinculo(base.TestIncapacidadTramoProrroga):

    # ── el vinculo, y no las fechas, forma la cadena ──
    def test_contiguas_sin_vinculo_ya_no_se_encadenan(self):
        """1-mar a 31-may y 1-jun a 15-jun, contiguas PERO sin «Prórroga de»: la segunda cuenta desde 1 (antes se encadenaba por fechas): 15 dias a 66,67 % = 2.000.100, no 1.500.000."""
        employee, contract = self._empleado('ContiguaSinVinculo')
        self._incapacidad(employee, date(2026, 3, 1), date(2026, 5, 31))
        self._incapacidad(employee, date(2026, 6, 1), date(2026, 6, 15))
        self.assertAlmostEqual(self._pago(employee, contract, date(2026, 6, 1), date(2026, 6, 15)), 15 * VALOR_DIA * PCT, delta=0.01)

    def test_contiguas_con_vinculo_si_se_encadenan(self):
        """El mismo caso con el vinculo: posiciones 93-107, todas al 50 % = 1.500.000."""
        employee, contract = self._empleado('ContiguaConVinculo')
        primera = self._incapacidad(employee, date(2026, 3, 1), date(2026, 5, 31))
        self._incapacidad(employee, date(2026, 6, 1), date(2026, 6, 15), prorroga_de=primera)
        self.assertAlmostEqual(self._pago(employee, contract, date(2026, 6, 1), date(2026, 6, 15)), 15 * VALOR_DIA * 0.5, delta=0.01)

    def test_cadena_de_tres_cuenta_todos_los_previos(self):
        """A (1-mar a 31-mar, 31 dias) -> B (1-abr a 30-abr, 30) -> C (1-may a 15-jun): en la quincena 1-15 de junio solo hay dias de C; los previos son 31 + 30 + 31 (1 a 31 de mayo) = 92: posiciones 93-107 al 50 %."""
        employee, contract = self._empleado('CadenaDeTres')
        a = self._incapacidad(employee, date(2026, 3, 1), date(2026, 3, 31))
        b = self._incapacidad(employee, date(2026, 4, 1), date(2026, 4, 30), prorroga_de=a)
        self._incapacidad(employee, date(2026, 5, 1), date(2026, 6, 15), prorroga_de=b)
        self.assertAlmostEqual(self._pago(employee, contract, date(2026, 6, 1), date(2026, 6, 15)), 15 * VALOR_DIA * 0.5, delta=0.01)

    def test_los_dias_libres_de_la_interrupcion_no_ocupan_posicion(self):
        """A (1-mar a 20-may, 81 dias) y B (25-may a 15-jun) vinculadas, con 4 dias libres (21 a 24 de mayo). En la quincena 1-15 de junio los previos son 81 + 7 (25 a 31 de mayo) = 88: posiciones 89-103:
        los dias 89 y 90 al 66,67 % y los 13 siguientes al 50 % = 2 x 200.000 x 0,6667 + 13 x 200.000 x 0,5 = 1.566.680. Si los 4 dias libres ocuparan posicion (previos 92) los 15 dias serian al 50 %."""
        employee, contract = self._empleado('DiasLibres')
        a = self._incapacidad(employee, date(2026, 3, 1), date(2026, 5, 20))
        self._incapacidad(employee, date(2026, 5, 25), date(2026, 6, 15), prorroga_de=a)
        self.assertAlmostEqual(
            self._pago(employee, contract, date(2026, 6, 1), date(2026, 6, 15)), 2 * VALOR_DIA * PCT + 13 * VALOR_DIA * 0.5, delta=0.01)

    def test_la_anterior_no_aprobada_da_un_error_claro(self):
        """Una prorroga cuya anterior no esta aprobada no tiene posicion cierta: el recibo se detiene con un mensaje que nombra el estado y dice que hacer."""
        employee, contract = self._empleado('AnteriorNoAprobada')
        anterior = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.tipo.id, 'request_date_from': date(2026, 3, 1), 'request_date_to': date(2026, 3, 10)})
        self.assertNotEqual(anterior.state, 'validate')
        self._incapacidad(employee, date(2026, 3, 11), date(2026, 3, 20), prorroga_de=anterior)
        slip = self.env['hr.payslip'].create({
            'name': 'Quincena', 'employee_id': employee.id, 'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 15)})
        with self.assertRaises(UserError) as exc:
            slip.compute_sheet()
        self.assertIn('no está aprobada', str(exc.exception))
        self.assertIn('Prórroga de', str(exc.exception))

    # ── restricciones del vinculo ──
    def _cruda(self, employee, desde, hasta):
        return self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.tipo.id, 'request_date_from': desde, 'request_date_to': hasta})

    def test_la_interrupcion_no_puede_superar_el_parametro(self):
        """A termina el 10-mar: B desde el 10-abr deja 30 dias libres (admitido, tope 30); C desde el 11-jun, tras B (que termina el 20-abr), deja 51 (rechazado, con el numero y la norma en el mensaje)."""
        employee, _contract = self._empleado('Interrupcion')
        a = self._cruda(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._cruda(employee, date(2026, 4, 10), date(2026, 4, 20))
        b.l10n_co_ne_prorroga_de_id = a                       # 30 dias libres: pasa
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)
        c = self._cruda(employee, date(2026, 6, 11), date(2026, 6, 20))
        with self.assertRaises(ValidationError) as exc:
            c.l10n_co_ne_prorroga_de_id = b                   # 51 dias libres
        self.assertIn('51', str(exc.exception))
        self.assertIn('30', str(exc.exception))
        self.assertIn('2.2.3.3.2', str(exc.exception))

    def test_el_tope_es_el_parametro_y_no_un_numero_en_el_codigo(self):
        """Con el parametro en 3, un vinculo con 4 dias libres se rechaza; con 4, pasa."""
        employee, _contract = self._empleado('TopeParametro')
        a = self._cruda(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._cruda(employee, date(2026, 3, 15), date(2026, 3, 20))              # 4 dias libres
        valor = self.env.ref(PARAMETRO_2024)
        valor.parameter_value = '3'
        with self.assertRaises(ValidationError):
            b.l10n_co_ne_prorroga_de_id = a
        valor.parameter_value = '4'
        b.l10n_co_ne_prorroga_de_id = a
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)

    def test_sin_parametro_un_error_que_lo_nombra(self):
        """Sin valor del parametro a la fecha, no hay tope por defecto: error con el codigo del parametro."""
        valor = self.env.ref(PARAMETRO_2024)
        valor.date_from = date(2099, 1, 1)
        with self.assertRaises(UserError) as exc:
            self.env['hr.leave']._ne_interrupcion_maxima_prorroga(date(2026, 3, 1))
        self.assertIn('l10n_co_dias_interrupcion_prorroga', str(exc.exception))

    def test_una_incapacidad_solo_tiene_una_prorroga_siguiente(self):
        """La cadena es una lista: dos incapacidades no pueden ser prorroga de la misma anterior."""
        employee, _contract = self._empleado('DosSucesoras')
        a = self._cruda(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._cruda(employee, date(2026, 3, 11), date(2026, 3, 20))
        c = self._cruda(employee, date(2026, 3, 21), date(2026, 3, 25))
        b.l10n_co_ne_prorroga_de_id = a
        with self.assertRaises(ValidationError) as exc:
            c.l10n_co_ne_prorroga_de_id = a
        self.assertIn('ya tiene una prórroga', str(exc.exception))

    def test_el_vinculo_se_registra_en_el_chatter(self):
        """El cambio del vinculo queda con rastro: el campo tiene tracking (en TransactionCase el rastreo de mail esta apagado: se comprueba el atributo)."""
        self.assertTrue(self.env['hr.leave']._fields['l10n_co_ne_prorroga_de_id'].tracking)

    # ── aviso «¿Es prórroga de…?» ──
    def test_aviso_cuando_hay_una_anterior_dentro_de_la_interrupcion(self):
        employee, _contract = self._empleado('Aviso')
        a = self._cruda(employee, date(2026, 3, 1), date(2026, 3, 10))
        a.action_validate()
        b = self._cruda(employee, date(2026, 3, 20), date(2026, 3, 25))
        self.assertIn('¿Es prórroga de', b.l10n_co_ne_prorroga_aviso)
        b.l10n_co_ne_prorroga_de_id = a
        self.assertFalse(b.l10n_co_ne_prorroga_aviso)                 # ya vinculada: sin aviso

    def test_sin_aviso_si_la_anterior_queda_fuera_o_es_de_otro_empleado(self):
        employee, _contract = self._empleado('SinAviso')
        otro, _c2 = self._empleado('SinAvisoOtro')
        a = self._cruda(employee, date(2026, 3, 1), date(2026, 3, 10))
        a.action_validate()
        lejos = self._cruda(employee, date(2026, 6, 20), date(2026, 6, 25))          # mas de 30 dias libres
        ajena = self._cruda(otro, date(2026, 3, 20), date(2026, 3, 25))
        self.assertFalse(lejos.l10n_co_ne_prorroga_aviso)
        self.assertFalse(ajena.l10n_co_ne_prorroga_aviso)

    def test_la_vista_trae_el_aviso(self):
        arch = etree.fromstring(self.env['hr.leave'].get_view(view_type='form')['arch'].encode())
        self.assertTrue(arch.xpath("//field[@name='l10n_co_ne_prorroga_aviso']"))

    # ── migracion .305: vincula lo que hoy se encadena por fechas ──
    def _migrar(self):
        """Corre el pre-migrate de .305 sobre la base de la prueba (flush antes, invalidate despues: escribe en SQL)."""
        ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '18.0.3.0.305', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('premigrate_305', ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        self.env.flush_all()
        modulo.migrate(self.env.cr, '18.0.3.0.304')
        self.env.invalidate_all()

    def test_migracion_vincula_los_pares_que_se_encadenaban_con_el_parametro_viejo_en_0(self):
        """Parametro viejo = 0: solo las contiguas. A (1-10 mar) + B (11-20 mar) contiguas -> B se vincula a A; C (23-25 mar, 2 libres) y D (1-jun) quedan sin vinculo."""
        self.env.ref(PARAMETRO_2024).parameter_value = '0'
        employee, _contract = self._empleado('MigraCero')
        a = self._incapacidad(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._incapacidad(employee, date(2026, 3, 11), date(2026, 3, 20))
        c = self._incapacidad(employee, date(2026, 3, 23), date(2026, 3, 25))
        d = self._incapacidad(employee, date(2026, 6, 1), date(2026, 6, 5))
        self._migrar()
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)
        self.assertFalse(c.l10n_co_ne_prorroga_de_id)
        self.assertFalse(d.l10n_co_ne_prorroga_de_id)
        self._migrar()                                                     # idempotente
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)
        self.assertFalse(c.l10n_co_ne_prorroga_de_id)

    def test_migracion_con_el_parametro_viejo_en_4_encadena_tambien_los_de_2_dias_libres(self):
        """Parametro viejo = 4: C (2 libres tras B) tambien se encadenaba: C -> B -> A. Ningun valor calculado cambia."""
        self.env.ref(PARAMETRO_2024).parameter_value = '4'
        employee, _contract = self._empleado('MigraCuatro')
        a = self._incapacidad(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._incapacidad(employee, date(2026, 3, 11), date(2026, 3, 20))
        c = self._incapacidad(employee, date(2026, 3, 23), date(2026, 3, 25))
        self._migrar()
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)
        self.assertEqual(c.l10n_co_ne_prorroga_de_id, b)

    def test_migracion_no_pisa_un_vinculo_puesto_a_mano_ni_viola_el_tope(self):
        """Un vinculo existente se respeta; un par que el parametro viejo (50) encadenaba pero supera el tope nuevo (30 dias libres) NO se vincula (queda en el registro para el TL)."""
        self.env.ref(PARAMETRO_2024).parameter_value = '50'
        employee, _contract = self._empleado('MigraTope')
        a = self._incapacidad(employee, date(2026, 3, 1), date(2026, 3, 10))
        b = self._incapacidad(employee, date(2026, 5, 1), date(2026, 5, 10))      # 51 dias libres tras A
        self._migrar()
        self.assertFalse(b.l10n_co_ne_prorroga_de_id)
        e2, _c2 = self._empleado('MigraManual')
        a2 = self._incapacidad(e2, date(2026, 3, 1), date(2026, 3, 10))
        a3 = self._incapacidad(e2, date(2026, 3, 11), date(2026, 3, 20))
        manual = self._incapacidad(e2, date(2026, 3, 21), date(2026, 3, 25), prorroga_de=a2)   # a mano, saltando a a3 (a2 ya tiene siguiente: a3 no se vincula)
        self._migrar()
        self.assertEqual(manual.l10n_co_ne_prorroga_de_id, a2)
        self.assertFalse(a3.l10n_co_ne_prorroga_de_id)
