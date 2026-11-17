# -*- coding: utf-8 -*-
"""Frente 4, U3 (doc 57): hoja de conceptos de pago UGPP (formulario 7003): tipo de pago y clasificación con el texto
exacto de las listas de la plantilla, cuenta contable tomada de las cuentas de la regla (una sola fuente) y errores que
nombran las reglas. Nivel de verificación: plantilla y Guía leídas; la aceptación en Storm User solo con Storm real."""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp


@tagged('post_install', '-at_install')
class TestUgppConceptos(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Conceptos UGPP', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id})
        Cuenta = cls.env['account.account'].with_company(cls.company)
        cls.gasto = Cuenta.create({'code': '510506', 'name': 'Sueldos UGPP', 'account_type': 'expense'})
        cls.por_pagar = Cuenta.create({'code': '250505', 'name': 'Salarios por pagar UGPP',
                                       'account_type': 'liability_current'})

    def _regla(self, codigo, tipo, clase=False, nombre=None, debito=None, credito=None):
        regla = self.env['hr.salary.rule'].create({
            'name': nombre or 'Regla %s' % codigo, 'code': codigo,
            'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id,
            'struct_id': self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'amount_select': 'fix', 'amount_fix': 0.0,
            'l10n_co_ugpp_payment_type': tipo, 'l10n_co_ugpp_non_salary_class': clase})
        regla = regla.with_company(self.company)
        if debito:
            regla.account_debit = debito
        if credito:
            regla.account_credit = credito
        return regla

    def test_cuenta_de_la_regla_debito_y_credito_separadas_por_punto_y_coma(self):
        regla = self._regla('U3_CTA_1', 'tp_salarial', debito=self.gasto, credito=self.por_pagar)
        self.assertEqual(self.reporte._ugpp_cuentas_regla(regla), '510506;250505')

    def test_si_debito_y_credito_son_la_misma_cuenta_no_se_repite(self):
        regla = self._regla('U3_CTA_2', 'tp_salarial', debito=self.gasto, credito=self.gasto)
        self.assertEqual(self.reporte._ugpp_cuentas_regla(regla), '510506')

    def test_la_fila_lleva_tipo_de_pago_y_clasificacion_con_el_texto_de_la_plantilla(self):
        salarial = self._regla('U3_FILA_1', 'tp_salarial', debito=self.gasto)
        no_salarial = self._regla('U3_FILA_2', 'tp_no_salarial', clase='contrato', debito=self.gasto)
        filas = self.reporte._ugpp_filas_conceptos(salarial | no_salarial)
        self.assertEqual(filas[0], [1, 'Regla U3_FILA_1', '510506', '1 TP SALARIAL', ''])
        self.assertEqual(filas[1], [2, 'Regla U3_FILA_2', '510506', '2 TP NO SALARIAL', '3 Contrato'])

    def test_clasificacion_solo_se_escribe_si_el_tipo_es_no_salarial(self):
        regla = self._regla('U3_FILA_3', 'tp_salarial', clase='contrato', debito=self.gasto)
        self.assertEqual(self.reporte._ugpp_filas_conceptos(regla)[0][4], '')

    def test_listas_cubren_todas_las_opciones_y_no_cargan_los_tipos_de_independientes(self):
        regla = self.env['hr.salary.rule']
        self.assertEqual(set(ugpp._UGPP_TIPO_PAGO), {k for k, _v in regla._fields['l10n_co_ugpp_payment_type'].selection})
        self.assertEqual(set(ugpp._UGPP_CLASE_NO_SALARIAL),
                         {k for k, _v in regla._fields['l10n_co_ugpp_non_salary_class'].selection})
        numeros = sorted(int(t.split()[0]) for t in ugpp._UGPP_TIPO_PAGO.values())
        self.assertEqual(numeros, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17])   # 12 a 15: independientes

    def test_el_nombre_no_lleva_los_caracteres_que_la_guia_prohibe(self):
        regla = self._regla('U3_NOM', 'tp_salarial', nombre='¡Bono! "A" & B #1 $ 5%', debito=self.gasto)
        self.assertEqual(self.reporte._ugpp_filas_conceptos(regla)[0][1], 'Bono A  B 1  5')

    def test_reglas_sin_cuenta_se_listan_juntas_en_un_solo_error(self):
        a = self._regla('U3_SIN_1', 'tp_salarial')
        b = self._regla('U3_SIN_2', 'tp_prestaciones')
        c = self._regla('U3_CON', 'tp_salarial', debito=self.gasto)
        with self.assertRaises(UserError) as exc:
            self.reporte._ugpp_filas_conceptos(a | b | c)
        mensaje = str(exc.exception)
        self.assertIn('Regla U3_SIN_1', mensaje)
        self.assertIn('Regla U3_SIN_2', mensaje)
        self.assertNotIn('Regla U3_CON', mensaje)
        self.assertIn('Empresa Conceptos UGPP', mensaje)

    def test_una_regla_no_salarial_exige_clasificacion(self):
        with self.assertRaisesRegex(ValidationError, 'clasificación'):
            self._regla('U3_NS', 'tp_no_salarial')

    def test_ya_no_existe_el_campo_de_cuentas_ugpp_aparte(self):
        self.assertNotIn('l10n_co_ugpp_accounts', self.env['hr.salary.rule']._fields)

    # ── U3b: la cuenta solo se exige a las reglas con valor en el periodo ──────────────────────────────
    def _recibo_con_valores(self, *valores):
        """Recibo del mes con una línea por (regla, total)."""
        tipo = self.env['hr.payroll.structure.type'].create({
            'name': 'Tipo U3b', 'country_id': self.env.ref('base.co').id})
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado U3b', 'company_id': self.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato U3b', 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo U3b', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id,
            'struct_id': self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        for regla, total in valores:
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': regla.code, 'name': regla.name,
                'category_id': regla.category_id.id, 'employee_id': empleado.id, 'contract_id': contrato.id,
                'total': total, 'amount': total, 'quantity': 1, 'rate': 100})
        return recibo

    def test_el_reporte_solo_incluye_reglas_con_valor_y_con_tipo_ugpp(self):
        con_valor = self._regla('U3B_VAL', 'tp_salarial', debito=self.gasto)
        en_cero = self._regla('U3B_CERO', 'tp_salarial')
        sin_tipo = self._regla('U3B_SINTIPO', False)
        recibo = self._recibo_con_valores((con_valor, 1000.0), (en_cero, 0.0), (sin_tipo, 500.0))
        self.assertEqual(self.reporte._get_ugpp_salary_rules(recibo), con_valor)

    def test_una_regla_sin_uso_y_sin_cuenta_no_tumba_el_reporte(self):
        con_valor = self._regla('U3B_OK', 'tp_salarial', debito=self.gasto)
        sin_uso = self._regla('U3B_SINUSO', 'tp_prestaciones')          # sin cuenta, pero sin valor en el mes
        recibo = self._recibo_con_valores((con_valor, 1000.0), (sin_uso, 0.0))
        reglas = self.reporte._get_ugpp_salary_rules(recibo)
        self.assertEqual(self.reporte._ugpp_filas_conceptos(reglas)[0][1:3], ['Regla U3B_OK', '510506'])
        self.assertEqual(len(reglas), 1)

    def test_una_regla_con_valor_y_sin_cuenta_si_tumba_el_reporte_y_se_nombra(self):
        con_valor = self._regla('U3B_FALTA', 'tp_salarial')
        sin_uso = self._regla('U3B_NOMBRE_NO', 'tp_salarial')
        recibo = self._recibo_con_valores((con_valor, 1000.0), (sin_uso, 0.0))
        with self.assertRaises(UserError) as exc:
            self.reporte._ugpp_filas_conceptos(self.reporte._get_ugpp_salary_rules(recibo))
        self.assertIn('Regla U3B_FALTA', str(exc.exception))
        self.assertNotIn('Regla U3B_NOMBRE_NO', str(exc.exception))
        self.assertIn('con valor en el periodo', str(exc.exception))

    # ── U5b: aportes y descuentos no son pagos al trabajador ───────────────────────────────────────────
    def test_los_aportes_y_descuentos_de_seguridad_social_no_llevan_tipo_ugpp(self):
        for xmlid in ('salud_emp', 'pension_emp', 'fsp', 'salud_cia', 'pension_cia', 'arl_cia', 'ccf_cia', 'sena_cia',
                      'icbf_cia'):
            regla = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_co_' + xmlid)
            self.assertFalse(regla.l10n_co_ugpp_payment_type, xmlid)

    def test_ninguna_regla_de_descuento_ni_de_aporte_de_la_empresa_tiene_tipo_ugpp(self):
        categorias = self.env['hr.salary.rule.category'].search([
            ('id', 'in', [self.env.ref('l10n_co_nomina_electronica.' + x).id for x in (
                'hr_salary_rule_category_seguridad_social_emp', 'hr_salary_rule_category_seguridad_social_cia')])])
        reglas = self.env['hr.salary.rule'].search([
            ('category_id', 'in', categorias.ids), ('l10n_co_ugpp_payment_type', '!=', False)])
        self.assertFalse(reglas.mapped('code'))

