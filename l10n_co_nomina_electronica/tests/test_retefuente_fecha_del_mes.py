# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Cierre del Frente 2 (.334; decision del TL del 27-nov): la tabla del art. 383 y los topes de la retencion se leen con la fecha del mes que se retiene, sin salir del año de la configuracion, y no fijos al
1 de enero. La UVT sigue siendo la anual. Para ver el cambio, la tabla de prueba es plana (10 % de toda la base): la retencion es la base gravable por 10 %."""

from datetime import date
from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

TABLA_PLANA = '[(0, None, 0.10, 0)]'


@tagged('post_install', '-at_install')
class TestRetefuenteFechaDelMes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Retención por Fecha'})
        cls.config = cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.employee = cls.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Retención por Fecha', 'company_id': cls.company.id})

    def _rete(self, ingreso=10000000.0, **extra):
        return self.config.compute_retefuente(self.employee, ingreso, ingreso, ingreso, company=self.company, **extra)

    def _valor_desde(self, parametro, desde, valor):
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': self.env.ref('l10n_co_nomina_electronica.%s' % parametro).id, 'date_from': desde, 'parameter_value': valor})

    def test_la_tabla_de_mitad_de_anio_aplica_desde_su_fecha(self):
        antes = self._rete()
        self.assertGreater(antes['retencion_pesos'], 0.0, 'Premisa')
        self._valor_desde('rule_parameter_tabla_retencion_art383', date(2026, 9, 1), TABLA_PLANA)
        self.assertEqual(self._rete(fecha_mes=date(2026, 8, 31))['retencion_pesos'], antes['retencion_pesos'])
        for fecha in (date(2026, 9, 1), date(2026, 9, 30), date(2026, 12, 31)):
            despues = self._rete(fecha_mes=fecha)
            self.assertAlmostEqual(despues['retencion_pesos'], despues['base_gravable'] * 0.10, delta=1.0, msg=fecha)
        self.assertNotAlmostEqual(despues['retencion_pesos'], antes['retencion_pesos'], delta=1.0)

    def test_un_tope_de_mitad_de_anio_aplica_desde_su_fecha(self):
        """10.000.000: subtotal 9.200.000; renta exenta 25 % = 2.300.000. Con 10 % desde septiembre = 920.000."""
        self._valor_desde('rule_parameter_pct_renta_exenta', date(2026, 9, 1), '10')
        self.assertAlmostEqual(self._rete(fecha_mes=date(2026, 8, 31))['renta_exenta_25'], 2300000.0, delta=0.01)
        self.assertAlmostEqual(self._rete(fecha_mes=date(2026, 9, 30))['renta_exenta_25'], 920000.0, delta=0.01)

    def test_el_recibo_usa_su_hasta_y_sin_recibo_ni_mes_se_lee_el_1_de_enero(self):
        antes = self._rete()
        self._valor_desde('rule_parameter_tabla_retencion_art383', date(2026, 9, 1), TABLA_PLANA)
        recibo = SimpleNamespace(date_from=date(2026, 8, 16), date_to=date(2026, 9, 15), _sum=lambda *args: 0.0)
        con_recibo = self._rete(payslip=recibo)
        self.assertAlmostEqual(con_recibo['retencion_pesos'], con_recibo['base_gravable'] * 0.10, delta=1.0)
        self.assertEqual(self._rete()['retencion_pesos'], antes['retencion_pesos'])

    def test_con_los_valores_del_modulo_ningun_mes_cambia(self):
        al_primero_de_enero = self._rete()
        for mes in range(1, 13):
            self.assertEqual(self._rete(fecha_mes=date(2026, mes, 28)), al_primero_de_enero, mes)

    def test_la_fecha_no_sale_del_anio_de_la_configuracion(self):
        for entrada, esperada in ((None, date(2026, 1, 1)), (date(2025, 12, 16), date(2026, 1, 1)), (date(2026, 7, 15), date(2026, 7, 15)),
                                  (date(2027, 1, 15), date(2026, 12, 31))):
            self.assertEqual(self.config._ne_fecha_de_la_norma(entrada), esperada, entrada)
        antes = self._rete()
        self._valor_desde('rule_parameter_tabla_retencion_art383', date(2027, 1, 1), TABLA_PLANA)
        self.assertEqual(self._rete(fecha_mes=date(2027, 1, 15))['retencion_pesos'], antes['retencion_pesos'])
