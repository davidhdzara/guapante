# -*- coding: utf-8 -*-
"""Tope de la renta exenta del 25 %: 790 UVT ANUALES (Art. 206 num. 10 ET, Ley 2277/2022;
Concepto DIAN 15007/2023). Retencion mensual: tope = 790 / 12 = 65,8333 UVT.

UVT 2026 = 52.374 -> tope mensual = 41.375.460 / 12 = 3.447.955 (el 25 % lo alcanza con una
base de 13.791.820). Sin aportes ni dependientes: subtotal = ingreso bruto.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRentaExentaTope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN',
            'name': 'Compañía de Prueba Tope Renta Exenta'})
        cls.config = cls.env['l10n.co.retefuente.uvt'].create({
            'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Tope Renta Exenta', 'company_id': cls.company.id})

    def _rete(self, ingreso):
        return self.config.compute_retefuente(
            self.employee, ingreso, 0.0, 0.0, company=self.company)

    def test_el_parametro_es_anual_790_uvt(self):
        valor = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_co_max_renta_exenta_uvt_anual', '2026-01-01')
        self.assertEqual(valor, 790.0)

    def test_por_debajo_del_tope_aplica_el_25_por_ciento(self):
        """10.000.000: 25 % = 2.500.000 < 3.447.955. Base 7.500.000 / 52.374 = 143,2008 UVT ->
        (143,2008 - 95) x 19 % = 9,1582 UVT x 52.374 = 479.649."""
        res = self._rete(10000000.0)
        self.assertAlmostEqual(res['renta_exenta_25'], 2500000.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 479649.0, delta=1.0)

    def test_por_encima_del_tope_la_renta_exenta_es_790_uvt_entre_12(self):
        """20.000.000: 25 % = 5.000.000 > 3.447.955 -> exenta 3.447.955. Base 16.552.045 /
        52.374 = 316,0355 UVT -> (316,0355 - 150) x 28 % + 10 = 56,4899 UVT x 52.374 =
        2.958.605 (con el tope viejo de 240 UVT = 12.569.760 no aplicaba y daba 2.524.032)."""
        res = self._rete(20000000.0)
        self.assertAlmostEqual(res['renta_exenta_25'], 3447955.0, delta=0.01)
        self.assertAlmostEqual(res['base_gravable'], 16552045.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 2958605.0, delta=1.0)
