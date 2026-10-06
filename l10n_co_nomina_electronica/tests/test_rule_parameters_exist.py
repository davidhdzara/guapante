# -*- coding: utf-8 -*-
"""Todo código que una regla salarial lea con ``payslip._rule_parameter('código', ...)`` debe
tener su ``hr.rule.parameter`` con al menos un ``hr.rule.parameter.value``: sin eso, el lookup
nativo (``hr.rule.parameter._get_parameter_from_code``) no encuentra nada y el payslip revienta
o calcula con un valor equivocado. Mismo hallazgo que motivó tests/test_input_types.py
(novedades/inputs), aplicado aquí a parámetros normativos -- Corrección 3 (AUD-DIAN-34,
2026-10-05): 7 parámetros nuevos para la indemnización por despido (Art. 64 CST) y el umbral
de 90 días de incapacidad común, que antes vivían como literales sueltos en las fórmulas."""

import re
from datetime import date

from odoo.tests.common import TransactionCase

_RULE_PARAMETER_CODE = re.compile(r"""_rule_parameter\(\s*['"]([a-z0-9_]+)['"]""")

_NUEVOS_PARAMETROS_INDEMNIZACION = (
    'l10n_co_dias_indemniz_primer_anio_menor10',
    'l10n_co_dias_indemniz_anio_adicional_menor10',
    'l10n_co_dias_indemniz_primer_anio_mayor10',
    'l10n_co_dias_indemniz_anio_adicional_mayor10',
    'l10n_co_tope_indemniz_smmlv',
    'l10n_co_dias_piso_indemniz_obra_labor',
)


class TestRuleParametersExist(TransactionCase):
    def _module_rules(self):
        xmlids = self.env['ir.model.data'].search([
            ('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        return self.env['hr.salary.rule'].browse(xmlids.mapped('res_id')).exists()

    def test_cada_codigo_de_parametro_que_leen_las_reglas_tiene_valor(self):
        """Barrido dinámico sobre TODAS las reglas del módulo -- no solo los 7 nuevos de
        esta corrección, cualquier _rule_parameter() futuro sin su valor queda atrapado aquí."""
        used = set()
        for rule in self._module_rules():
            for text in (rule.amount_python_compute, rule.condition_python):
                for match in _RULE_PARAMETER_CODE.finditer(text or ''):
                    used.add(match.group(1))
        self.assertTrue(used, 'no se encontraron parámetros en las reglas del módulo')
        defined = set(
            self.env['hr.rule.parameter.value'].search([]).mapped('rule_parameter_id.code'))
        self.assertFalse(
            used - defined, 'faltan hr.rule.parameter.value para: %s' % sorted(used - defined))

    def test_los_6_parametros_nuevos_de_indemnizacion_tienen_valor(self):
        for code in _NUEVOS_PARAMETROS_INDEMNIZACION:
            param = self.env['hr.rule.parameter'].search([('code', '=', code)], limit=1)
            self.assertTrue(param, code)
            self.assertEqual(param.country_id.code, 'CO', code)
            value = self.env['hr.rule.parameter.value'].search(
                [('rule_parameter_id', '=', param.id)], limit=1)
            self.assertTrue(value, code)

    def test_umbral_90_dias_incapacidad_tiene_valor_correcto(self):
        param = self.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_dias_incapacidad_limite_3_90')], limit=1)
        self.assertTrue(param)
        self.assertEqual(param.country_id.code, 'CO')
        # hr.rule.parameter.value.parameter_value es Text (guarda el literal Python como
        # string, no el valor evaluado) -- se compara con la API nativa de lookup, igual
        # que payslip._rule_parameter(), no con el campo crudo.
        valor = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_co_dias_incapacidad_limite_3_90', date(2026, 1, 1))
        self.assertEqual(valor, 90)

    def test_indemnizacion_no_reutiliza_parametros_de_otro_concepto_legal(self):
        """El umbral de 10 SMMLV del Art. 64 (indemnización) y el de exoneración de
        parafiscales (Art. 114-1 ET) son conceptos distintos -- deben ser 2 parámetros."""
        indemniz = self.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_tope_indemniz_smmlv')], limit=1)
        exoneracion = self.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_tope_exoneracion_smmlv')], limit=1)
        self.assertTrue(indemniz)
        self.assertTrue(exoneracion)
        self.assertNotEqual(indemniz.id, exoneracion.id)
