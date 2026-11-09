# -*- coding: utf-8 -*-
"""Toda novedad que una regla salarial lea con ``inputs['CO_XXX']`` debe tener su
``hr.payslip.input.type``: sin él RRHH no puede registrarla en ningún recibo (hallazgo de QA,
Ronda 1 DIAN, 2026-10-05: vacaciones, prima, cesantías, incapacidades y otras no se podían cargar)."""

import re

from odoo.tests.common import TransactionCase

_INPUT_CODE = re.compile(r"""inputs\[['"]([A-Z0-9_]+)['"]\]|inputs\.get\(['"]([A-Z0-9_]+)['"]\)|inputs\.([A-Z][A-Z0-9_]+)\b""")


class TestInputTypes(TransactionCase):
    def _module_rules(self):
        xmlids = self.env['ir.model.data'].search([
            ('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        return self.env['hr.salary.rule'].browse(xmlids.mapped('res_id')).exists()

    def test_cada_codigo_de_entrada_que_leen_las_reglas_tiene_su_tipo(self):
        used = set()
        for rule in self._module_rules():
            for text in (rule.amount_python_compute, rule.condition_python):
                for match in _INPUT_CODE.finditer(text or ''):
                    used.add(next(g for g in match.groups() if g))
        self.assertTrue(used, 'no se encontraron entradas en las reglas del módulo')
        defined = set(self.env['hr.payslip.input.type'].with_context(active_test=False).search([]).mapped('code'))
        self.assertFalse(used - defined, 'faltan hr.payslip.input.type para: %s' % sorted(used - defined))

    def test_las_novedades_de_dias_y_valor_se_pueden_elegir_en_un_recibo(self):
        for code in ('CO_VAC', 'CO_PRIMA', 'CO_CESANTIAS', 'CO_INC_COMUN', 'CO_COMISIONES', 'CO_LIBRANZAS'):
            input_type = self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
            self.assertTrue(input_type, code)
            self.assertEqual(input_type.country_id.code, 'CO', code)
