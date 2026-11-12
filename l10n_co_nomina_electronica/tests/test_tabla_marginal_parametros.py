# -*- coding: utf-8 -*-
"""La tabla marginal del Art. 383 ET vive en el parametro versionado l10n_co_tabla_retencion_art383
(no en el codigo). Equivalencia con la tabla legal vigente (que antes era una constante de codigo) y
versionado por fecha. Valores en UVT a mano."""

from odoo.tests.common import TransactionCase, tagged

# Tabla legal (Art. 383 ET), copiada aqui como valor esperado.
TABLA_LEGAL = [
    (0, 95, 0.0, 0), (95, 150, 0.19, 0), (150, 360, 0.28, 10), (360, 640, 0.33, 69),
    (640, 945, 0.35, 162), (945, 2300, 0.37, 268), (2300, None, 0.39, 770)]


@tagged('post_install', '-at_install')
class TestTablaMarginalParametros(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['l10n.co.retefuente.uvt']
        cls.parametro = cls.env['hr.rule.parameter'].search(
            [('code', '=', 'l10n_co_tabla_retencion_art383')])

    def test_el_parametro_trae_la_tabla_legal_y_el_ultimo_tramo_abierto(self):
        valor = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_co_tabla_retencion_art383', '2026-06-01')
        self.assertEqual([tuple(t) for t in valor], TABLA_LEGAL)

    def test_equivalencia_con_el_calculo_de_la_constante_anterior(self):
        """(base UVT, retencion UVT a mano)"""
        casos = [
            (0, 0.0), (95, 0.0), (143.2008, 9.158152),
            (150, 10.45), (316.0355, 56.48994), (360, 68.8), (700, 183.0),
            (945, 162 + (945 - 640) * 0.35),
            (1000, 288.35), (2300, 268 + (2300 - 945) * 0.37), (2500, 848.0),
        ]
        for base, esperado in casos:
            self.assertAlmostEqual(
                self.Config._apply_marginal_table(base, '2026-06-01'), esperado, delta=0.001,
                msg='base %s UVT' % base)

    def test_una_tabla_nueva_con_fecha_rige_desde_esa_fecha_sin_tocar_codigo(self):
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': self.parametro.id,
            'parameter_value': '[(0, 50, 0.0, 0), (50, None, 0.5, 0)]',
            'date_from': '2030-01-01'})
        # antes de 2030: la tabla vigente -> (100 - 95) x 19 % = 0,95
        self.assertAlmostEqual(self.Config._apply_marginal_table(100, '2029-12-31'), 0.95, delta=1e-6)
        # desde 2030: la nueva -> (100 - 50) x 50 % = 25
        self.assertAlmostEqual(self.Config._apply_marginal_table(100, '2030-01-01'), 25.0, delta=1e-6)
