# -*- coding: utf-8 -*-
"""Asiento contable por tercero (commit 4) y regresion del refactor de embargos.

Prueba de concepto de las cuentas: aporte de empresa (ARL: gasto en
account_debit, pasivo en account_credit) y deduccion (libranza: pasivo en
account_debit con monto NEGATIVO, que cae en el CREDITO). Se crean las cuentas
dentro del test para no depender de los scripts de carga de la base.

Nivel de verificacion: _prepare_slip_lines sobre lineas de nomina sinteticas
(totales fijos) y reparto real; el asiento completo (action_payslip_done) se
prueba con compute_sheet real en los tests de nomina real.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAsientoTercero(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Asiento Tercero'})
        cls.env = cls.company.with_company(cls.company).env
        Account = cls.env['account.account']

        def cuenta(code, name, tipo):
            return Account.create({
                'code': code, 'name': name, 'account_type': tipo,
                'company_ids': [(6, 0, [cls.company.id])]})
        cls.gasto = cuenta('510599', 'Gasto ARL prueba', 'expense')
        cls.pasivo_aportes = cuenta('238999', 'Aportes por pagar prueba', 'liability_current')
        cls.pasivo_ded = cuenta('239999', 'Deducciones por pagar prueba', 'liability_current')
        cls.arl = cls.env['res.partner'].create({
            'name': 'ARL Asiento', 'l10n_co_entity_type': 'arl',
            'l10n_co_pila_entity_code': '14-98'})
        cls.banco1 = cls.env['res.partner'].create({'name': 'Banco Asiento Uno'})
        cls.banco2 = cls.env['res.partner'].create({'name': 'Banco Asiento Dos'})
        cls.company.l10n_co_pila_arl_id = cls.arl
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        Rule = cls.env['hr.salary.rule']
        cls.regla_arl = Rule.search([('code', '=', 'CO_ARL_CIA'), ('struct_id', '=', cls.structure.id)])
        cls.regla_lib = Rule.search([('code', '=', 'CO_LIBRANZAS'), ('struct_id', '=', cls.structure.id)])
        cls.regla_arl.write({
            'account_debit': cls.gasto.id, 'account_credit': cls.pasivo_aportes.id,
            'l10n_co_tercero_origen': 'company_arl'})
        cls.regla_lib.write({
            'account_debit': cls.pasivo_ded.id, 'account_credit': False,
            'l10n_co_tercero_origen': 'distribution'})
        employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Asiento', 'company_id': cls.company.id})
        contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Asiento', 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 3000000,
            'date_start': '2026-01-01', 'state': 'draft'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Nomina Asiento', 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': cls.company.id,
            'struct_id': cls.structure.id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31'})

    def _linea(self, regla, total):
        return self.env['hr.payslip.line'].create({
            'slip_id': self.slip.id, 'salary_rule_id': regla.id,
            'code': regla.code, 'name': regla.name,
            'category_id': regla.category_id.id,
            'employee_id': self.slip.employee_id.id,
            'contract_id': self.slip.contract_id.id,
            'total': total, 'amount': total, 'quantity': 1, 'rate': 100})

    def _reparto(self, filas):
        for partner, monto in filas:
            self.env['l10n.co.payslip.tercero'].create({
                'slip_id': self.slip.id, 'rule_code': 'CO_LIBRANZAS',
                'partner_id': partner.id, 'amount': monto})

    def _entradas(self, cuenta):
        lineas = self.slip._prepare_slip_lines(self.slip.date_to, [])
        return [l for l in lineas if l['account_id'] == cuenta.id]

    # ── Prueba de concepto: que campo/columna y en que linea cae el tercero ──
    def test_aporte_empresa_gasto_en_debito_pasivo_en_credito_con_tercero(self):
        self._linea(self.regla_arl, 52200.0)
        gasto = self._entradas(self.gasto)
        pasivo = self._entradas(self.pasivo_aportes)
        self.assertEqual(len(gasto), 1)
        self.assertEqual(len(pasivo), 1)
        self.assertAlmostEqual(gasto[0]['debit'], 52200.0)
        self.assertFalse(gasto[0]['partner_id'])          # el gasto no lleva tercero
        self.assertAlmostEqual(pasivo[0]['credit'], 52200.0)
        self.assertEqual(pasivo[0]['partner_id'], self.arl.id)

    def test_deduccion_con_account_debit_y_monto_negativo_cae_en_credito_con_tercero(self):
        self._linea(self.regla_lib, -300000.0)
        self._reparto([(self.banco1, 300000.0)])
        entradas = self._entradas(self.pasivo_ded)
        self.assertEqual(len(entradas), 1)
        self.assertAlmostEqual(entradas[0]['credit'], 300000.0)
        self.assertAlmostEqual(entradas[0]['debit'], 0.0)
        self.assertEqual(entradas[0]['partner_id'], self.banco1.id)

    def test_reparto_en_varias_lineas_una_por_tercero_y_balancea(self):
        self._linea(self.regla_lib, -1300000.0)
        self._reparto([(self.banco1, 800000.0), (self.banco2, 500000.0)])
        entradas = self._entradas(self.pasivo_ded)
        self.assertEqual(len(entradas), 2)
        por_partner = {e['partner_id']: e for e in entradas}
        self.assertAlmostEqual(por_partner[self.banco1.id]['credit'], 800000.0)
        self.assertAlmostEqual(por_partner[self.banco2.id]['credit'], 500000.0)
        self.assertAlmostEqual(sum(e['credit'] for e in entradas), 1300000.0)

    def test_residuo_de_centavos_va_a_la_ultima_fila_y_suma_exacta(self):
        self._linea(self.regla_lib, -100.0)
        self._reparto([(self.banco1, 33.33), (self.banco2, 66.67)])
        entradas = self._entradas(self.pasivo_ded)
        self.assertAlmostEqual(sum(e['credit'] for e in entradas), 100.0)

    # ── Errores claros ──
    def test_sin_tercero_en_la_compania_da_error_claro(self):
        self.company.l10n_co_pila_arl_id = False
        self._linea(self.regla_arl, 52200.0)
        with self.assertRaises(UserError) as e:
            self.slip._prepare_slip_lines(self.slip.date_to, [])
        self.assertIn('ARL', str(e.exception))

    def test_reparto_que_no_coincide_con_la_linea_da_error(self):
        self._linea(self.regla_lib, -300000.0)
        self._reparto([(self.banco1, 100000.0)])
        with self.assertRaises(UserError):
            self.slip._prepare_slip_lines(self.slip.date_to, [])

    def test_modo_lote_con_tercero_da_error(self):
        self.company.batch_payroll_move_lines = True
        self._linea(self.regla_arl, 52200.0)
        with self.assertRaises(UserError) as e:
            self.slip._prepare_slip_lines(self.slip.date_to, [])
        self.assertIn('lote', str(e.exception))

    def test_regla_sin_origen_no_lleva_tercero(self):
        self.regla_arl.l10n_co_tercero_origen = False
        self._linea(self.regla_arl, 52200.0)
        pasivo = self._entradas(self.pasivo_aportes)
        self.assertFalse(pasivo[0]['partner_id'])

    def test_carga_de_origen_cubre_las_reglas_del_modulo(self):
        Rule = self.env['hr.salary.rule']
        for codigo in ('CO_SALUD_EMP', 'CO_PENSION_EMP', 'CO_FSP', 'CO_RETEFUENTE',
                       'CO_SINDICATO', 'CO_EMBARGO', 'CO_LIBRANZAS', 'CO_SENA_CIA'):
            reglas = Rule.search([('code', '=', codigo)])
            self.assertTrue(reglas, codigo)
            self.assertTrue(all(reglas.mapped('l10n_co_tercero_origen')), codigo)
