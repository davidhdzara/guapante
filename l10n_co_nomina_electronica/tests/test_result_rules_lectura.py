# -*- coding: utf-8 -*-
"""Pieza .275: leer ``result_rules`` SIN mutarlo (causa raíz del KeyError: 'total' de la regresión bv).

Hecho nativo (lectura del servidor, no ejecutada aquí): ``result_rules`` es un ``DefaultDictPayroll``
(``hr_payroll/models/hr_payslip.py:23-27``, instanciado en ``:833`` con ``lambda: dict(total=0, amount=0, quantity=0, rate=0)``);
su ``get(clave, default)`` INSERTA el default si la clave falta y el default no es ``None``. ``_ne_ibc_incap`` hacía
``result_rules.get(codigo, {}).get('total', 0.0)`` y dejaba ``{}`` (sin ``total``) para cada ausencia no evaluada; el ayudante del
neto (E-8) veía ``codigo in result_rules`` y fallaba en ``['total']``. Las pruebas usan la CLASE REAL del motor.
Valores a mano."""

import copy
from datetime import date
from types import SimpleNamespace

from odoo.addons.hr_payroll.models.hr_payslip import DefaultDictPayroll
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

CODIGOS_AUSENCIA = ('CO_INC_COMUN', 'CO_INC_LABORAL', 'CO_LIC_MAT', 'CO_LIC_PAT')


def _result_rules(**totales):
    """Un ``result_rules`` como el del motor (clase real y fábrica real) con las reglas ``totales`` ya evaluadas."""
    reglas = DefaultDictPayroll(lambda: dict(total=0, amount=0, quantity=0, rate=0))
    for codigo, total in totales.items():
        reglas[codigo] = {'total': total, 'amount': total, 'quantity': 1, 'rate': 100}
    return reglas


def _formula_anterior(result_rules, codigos=CODIGOS_AUSENCIA):
    """La fórmula de antes de .275 (sirve de referencia numérica y de prueba del defecto)."""
    return sum(result_rules.get(codigo, {}).get('total', 0.0) for codigo in sorted(codigos))


@tagged('post_install', '-at_install')
class TestResultRulesLectura(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Lectura Result Rules'})
        tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Lectura RR', 'country_id': cls.env.ref('base.co').id})
        empleado = cls.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Lectura RR',
            'company_id': cls.company.id, 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Lectura RR', 'employee_id': empleado.id, 'company_id': cls.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        cls.recibo = cls.env['hr.payslip'].create({
            'name': 'Recibo Lectura RR', 'employee_id': empleado.id, 'contract_id': cls.contrato.id,
            'company_id': cls.company.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})

    # ── el defecto, con la clase real del motor ──────────────────────
    def test_la_formula_anterior_dejaba_entradas_vacias(self):
        reglas = _result_rules(CO_BASICO=1000.0)
        self.assertEqual(_formula_anterior(reglas), 0.0)
        self.assertEqual(sorted(reglas), sorted(('CO_BASICO',) + CODIGOS_AUSENCIA))   # insertó 4 claves
        for codigo in CODIGOS_AUSENCIA:
            self.assertEqual(reglas[codigo], {})                                      # sin 'total'

    # ── equivalencia numérica y no mutación ──────────────────────────
    def test_sin_ausencias_evaluadas_da_cero_y_no_inserta_claves(self):
        reglas = _result_rules(CO_BASICO=1000.0)
        referencia = _formula_anterior(copy.deepcopy(reglas))
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas), referencia)
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas), 0.0)
        self.assertEqual(list(reglas), ['CO_BASICO'])                                  # no mutó

    def test_con_ausencias_evaluadas_suma_igual_que_antes(self):
        reglas = _result_rules(CO_BASICO=1000.0, CO_INC_COMUN=100000.5, CO_LIC_MAT=40000.0)
        referencia = _formula_anterior(copy.deepcopy(reglas))
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas), referencia)
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas), 140000.5)   # 100000.5 + 40000
        self.assertEqual(sorted(reglas), ['CO_BASICO', 'CO_INC_COMUN', 'CO_LIC_MAT'])

    def test_codigos_acotados_como_en_ibc_seguridad_social(self):
        reglas = _result_rules(CO_INC_COMUN=100000.5, CO_LIC_MAT=40000.0, CO_LIC_PAT=2500.0)
        acotados = ('CO_LIC_MAT', 'CO_LIC_PAT')
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas, codigos=acotados), 42500.0)
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas, codigos=acotados),
                         _formula_anterior(copy.deepcopy(reglas), acotados))

    def test_una_entrada_creada_por_el_motor_con_total_cero_suma_cero(self):
        reglas = _result_rules()
        reglas['CO_INC_COMUN']          # __missing__ del motor: dict(total=0, amount=0, quantity=0, rate=0)
        self.assertEqual(self.recibo._ne_ibc_incap(self.contrato, reglas), 0.0)

    def test_integral_es_cero_aunque_haya_ausencias(self):
        integral = SimpleNamespace(l10n_co_ne_integral_salary=True)   # solo se lee esa marca; evita el piso de 13 SMMLV
        reglas = _result_rules(CO_INC_COMUN=100000.5)
        self.assertEqual(self.recibo._ne_ibc_incap(integral, reglas), 0.0)

    # ── el recorrido que falló en bv: ibc_incap y luego el neto ───────
    def test_despues_de_ibc_incap_el_neto_ya_no_falla(self):
        reglas = _result_rules(CO_BASICO=1000.0, CO_SALUD_EMP=-40.0, CO_PENSION_EMP=-40.0)
        self.recibo._ne_ibc_incap(self.contrato, reglas)           # CO_IBC_INCAP (seq 91) corre antes que CO_NETO (200)
        self.assertEqual(self.recibo._ne_neto_redondeado(reglas, 'DEV'), 920.0)

    # ── entrada presente sin 'total': error claro ────────────────────
    def test_entrada_sin_total_da_error_con_regla_tipo_y_claves(self):
        reglas = _result_rules(CO_BASICO=1000.0)
        reglas['CO_INC_COMUN'] = {}
        with self.assertRaises(UserError) as error:
            self.recibo._ne_neto_redondeado(reglas, 'DEV')
        mensaje = str(error.exception)
        self.assertIn('CO_INC_COMUN', mensaje)
        self.assertIn('dict', mensaje)
        self.assertIn('claves []', mensaje)
        reglas['CO_INC_COMUN'] = {'amount': 5}
        with self.assertRaisesRegex(UserError, r"claves \['amount'\]"):
            self.recibo._ne_ibc_incap(self.contrato, reglas)

    def test_entrada_que_no_es_dict_da_error(self):
        reglas = _result_rules()
        reglas['CO_LIC_MAT'] = 12.0
        with self.assertRaisesRegex(UserError, 'tipo float'):
            self.recibo._ne_ibc_incap(self.contrato, reglas)
