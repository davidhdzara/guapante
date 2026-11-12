# -*- coding: utf-8 -*-
"""Regresion del refactor de embargos: hr.payslip._ne_embargos_calcular debe
dar el MISMO monto que el calculo inline anterior de la regla CO_EMBARGO
(topes Art. 155/156 CST, prelacion y piso de minimo vital). `_legacy` es la
transcripcion fiel del bloque anterior de la regla, conservada solo aqui."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmbargosRefactor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Embargos Refactor'})
        cls.env = cls.company.with_company(cls.company).env
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Embargos', 'company_id': cls.company.id})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Embargos', 'employee_id': cls.employee.id,
            'company_id': cls.company.id, 'wage': 5000000,
            'date_start': '2026-01-01', 'state': 'draft'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Nomina Embargos', 'employee_id': cls.employee.id,
            'contract_id': cls.contract.id, 'company_id': cls.company.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31'})
        cls.juzgado = cls.env['res.partner'].create({'name': 'Juzgado Refactor'})
        cls.smmlv = cls.slip._rule_parameter('l10n_co_smmlv', cls.slip.date_from)

    def _embargo(self, xmlid, monto=0.0, porcentaje=0.0):
        tipo = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
        return self.env['hr.salary.attachment'].create({
            'description': 'Embargo %s' % xmlid,
            'employee_ids': [(6, 0, [self.employee.id])],
            'company_id': self.company.id, 'other_input_type_id': tipo.id,
            'monthly_amount': monto or 1.0, 'l10n_co_embargo_porcentaje': porcentaje,
            'date_start': '2026-01-01', 'no_end_date': True,
            'l10n_co_partner_id': self.juzgado.id})

    def _legacy(self, neto, smmlv, manual=0.0):
        prioridad = {'L10N_CO_EMBARGO_ALIMENTOS': 0, 'L10N_CO_EMBARGO_COOPERATIVA': 1,
                     'L10N_CO_EMBARGO_CIVIL': 2}
        slip = self.slip
        activos = slip.employee_id.salary_attachment_ids.filtered(
            lambda a: a.state == 'open' and a.other_input_type_id.code in prioridad)
        ordenados = activos.sorted(key=lambda a: prioridad.get(a.other_input_type_id.code, 99))
        total = 0.0
        for e in ordenados:
            individual = e._l10n_co_compute_embargo_amount(
                neto, smmlv, slip.date_from,
                factor_embargo_civil=slip._rule_parameter('l10n_co_factor_embargo_civil', slip.date_from),
                pct_tope_embargo_alimentos=slip._rule_parameter('l10n_co_pct_tope_embargo_alimentos', slip.date_from))
            espacio = max(0.0, (neto - total) - smmlv)
            total += min(individual, espacio)
        if manual and manual > 0:
            total = max(total, min(manual, max(0.0, neto - smmlv)))
        return total

    def _comparar(self, neto, manual=0.0):
        esperado = self._legacy(neto, self.smmlv, manual)
        self.assertAlmostEqual(
            self.slip._ne_embargos_calcular(neto, self.smmlv, manual), esperado, places=2)

    def test_un_embargo_civil(self):
        self._embargo('input_l10n_co_embargo_civil', monto=500000.0)
        self._comparar(4600000.0)

    def test_alimentos_por_porcentaje(self):
        self._embargo('input_l10n_co_embargo_alimentos', porcentaje=30.0)
        self._comparar(4600000.0)

    def test_concurrentes_alimentos_cooperativa_y_civil(self):
        self._embargo('input_l10n_co_embargo_civil', monto=900000.0)
        self._embargo('input_l10n_co_embargo_alimentos', porcentaje=40.0)
        self._embargo('input_l10n_co_embargo_cooperativa', monto=800000.0)
        self._comparar(4600000.0)

    def test_piso_de_minimo_vital_con_salario_bajo(self):
        self._embargo('input_l10n_co_embargo_alimentos', porcentaje=50.0)
        self._embargo('input_l10n_co_embargo_civil', monto=700000.0)
        self._comparar(self.smmlv + 300000.0)

    def test_manual_menor_o_igual_al_reparto_da_el_mismo_total(self):
        self._embargo('input_l10n_co_embargo_civil', monto=500000.0)
        self._comparar(4600000.0, manual=200000.0)

    def test_manual_que_excede_las_asignaciones_es_error_claro(self):
        self._embargo('input_l10n_co_embargo_civil', monto=500000.0)
        with self.assertRaises(UserError) as e:
            self.slip._ne_embargos_calcular(4600000.0, self.smmlv, 2000000.0)
        self.assertIn('Juzgado / Entidad', str(e.exception))

    def test_reparto_suma_el_total(self):
        self._embargo('input_l10n_co_embargo_civil', monto=500000.0)
        self._embargo('input_l10n_co_embargo_alimentos', porcentaje=20.0)
        total = self.slip._ne_embargos_calcular(4600000.0, self.smmlv)
        filas = self.env['l10n.co.payslip.tercero'].search(
            [('slip_id', '=', self.slip.id), ('rule_code', '=', 'CO_EMBARGO')])
        self.assertEqual(len(filas), 2)
        self.assertAlmostEqual(sum(filas.mapped('amount')), total, places=2)
