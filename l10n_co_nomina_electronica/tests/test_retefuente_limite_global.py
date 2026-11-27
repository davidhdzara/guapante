# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-02 (doc 90; decisiones D-02 del TL del 22-nov): limite global de las rentas exentas y deducciones en la retencion en la fuente.

Art. 336 num. 3 E.T. (Ley 2277/2022 art. 7) y Decreto 1625/2016 art. 1.2.4.1.6 par. 3 (Decreto 2231/2023 art. 9): las rentas exentas y deducciones (aqui: aporte voluntario a pension, AFC, dependientes y el
25 %) no pueden superar el 40 % de «ingreso menos ingresos no constitutivos de renta» (salud y pension obligatorias) ni 1.340 UVT ANUALES: en la retencion, que se depura por mes, 1.340 / 12 UVT. Sin
acumulado anual ni prorrateo por quincena. Los 72 UVT por dependiente son de la declaracion anual (D-02-2): no se cargan ni se usan.

UVT 2026 = 52.374; tope mensual del limite = 1.340 / 12 x 52.374 = 5.848.430; tope mensual del 25 % = 790 / 12 x 52.374 = 3.447.955; salud y pension 4 % + 4 % del IBC (= el ingreso). Tabla del art. 383
en UVT. Valores a mano en el doc 90 §5."""

from types import SimpleNamespace

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

LIMITE_MENSUAL = 5848430.0
EXENTA_25_MENSUAL = 3447955.0


@tagged('post_install', '-at_install')
class TestRetefuenteLimiteGlobal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'name': 'Compañía de Prueba Límite Global Retención'})
        cls.config = cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.employee = cls.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Límite Global', 'company_id': cls.company.id})

    def _rete(self, ingreso, vol=0.0, afc=0.0, dependientes=False, procedimiento='1', **extra):
        """Depuracion del mes: IBC = ingreso (salud y pension 4 % + 4 %). El contrato es un simple portador de los dos aportes y del procedimiento (el modelo solo los lee)."""
        self.employee.l10n_co_ne_dependientes = dependientes
        contrato = SimpleNamespace(
            l10n_co_ne_pension_voluntaria=vol, l10n_co_ne_afc=afc, l10n_co_ne_retention_procedure=procedimiento, id=0)
        return self.config.compute_retefuente(self.employee, ingreso, ingreso, ingreso, company=self.company, contract=contrato, **extra)

    # ── los 4 casos del doc 90 §5 ──
    def test_caso_1_sin_voluntarios_ni_dependientes_el_limite_no_muerde(self):
        """8.000.000: base 7.360.000; el 25 % (1.840.000) es menor que el 40 % (2.944.000). Base 5.520.000 = 105,3958 UVT -> (105,3958 - 95) x 19 % = 1,9752 UVT = 103.449."""
        res = self._rete(8000000.0)
        self.assertAlmostEqual(res['base_limite_global'], 7360000.0, delta=0.01)
        self.assertAlmostEqual(res['beneficios_antes_del_limite'], 1840000.0, delta=0.01)
        self.assertAlmostEqual(res['limite_global'], 2944000.0, delta=0.01)
        self.assertEqual(res['exceso_limite_global'], 0.0)
        self.assertAlmostEqual(res['base_gravable'], 5520000.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 103449.0, delta=1.0)

    def test_caso_2_el_40_por_ciento_recorta_voluntarios_dependientes_y_25(self):
        """12.000.000 con pension voluntaria 2.000.000 + AFC 1.600.000 (30 %) y dependientes (10 % = 1.200.000): base 11.040.000; beneficios 3.600.000 + 1.200.000 + 25 % de 6.240.000 (1.560.000) =
        6.360.000; limite 40 % = 4.416.000; exceso 1.944.000; base gravable 11.040.000 - 4.416.000 = 6.624.000 = 126,4750 UVT -> (126,4750 - 95) x 19 % = 5,98 UVT = 313.209. Sin el limite (hoy): base
        4.680.000 = 89,36 UVT (< 95) -> 0."""
        res = self._rete(12000000.0, vol=2000000.0, afc=1600000.0, dependientes=True)
        self.assertAlmostEqual(res['base_limite_global'], 11040000.0, delta=0.01)
        self.assertAlmostEqual(res['beneficios_antes_del_limite'], 6360000.0, delta=0.01)
        self.assertAlmostEqual(res['limite_global'], 4416000.0, delta=0.01)
        self.assertAlmostEqual(res['exceso_limite_global'], 1944000.0, delta=0.01)
        self.assertAlmostEqual(res['base_gravable'], 6624000.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 313209.0, delta=1.0)

    def test_caso_3_el_tope_absoluto_de_1340_uvt_entre_12_recorta(self):
        """30.000.000 con pension voluntaria 3.000.000 + AFC 2.000.000: base 27.600.000; beneficios 5.000.000 + 25 % de 22.600.000 (tope 3.447.955) = 8.447.955; limite = min(40 % = 11.040.000, 1.340/12 UVT =
        5.848.430) = 5.848.430; exceso 2.599.525; base gravable 21.751.570 = 415,3124 UVT -> (415,3124 - 360) x 33 % + 69 = 87,2531 UVT = 4.569.793 (sin el limite: 3.711.950)."""
        res = self._rete(30000000.0, vol=3000000.0, afc=2000000.0)
        self.assertAlmostEqual(res['beneficios_antes_del_limite'], 5000000.0 + EXENTA_25_MENSUAL, delta=0.01)
        self.assertAlmostEqual(res['limite_global'], LIMITE_MENSUAL, delta=0.01)
        self.assertAlmostEqual(res['exceso_limite_global'], 8447955.0 - LIMITE_MENSUAL, delta=0.01)
        self.assertAlmostEqual(res['base_gravable'], 21751570.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 4569793.0, delta=1.0)

    def test_caso_4_el_25_solo_nunca_alcanza_el_limite(self):
        """30.000.000 sin voluntarios: el 25 % (tope 790 UVT anuales = 3.447.955) no llega a 1.340/12 UVT ni al 40 %: no cambia nada. Base 24.152.045 = 461,1457 UVT -> 5.361.950."""
        res = self._rete(30000000.0)
        self.assertAlmostEqual(res['beneficios_antes_del_limite'], EXENTA_25_MENSUAL, delta=0.01)
        self.assertEqual(res['exceso_limite_global'], 0.0)
        self.assertAlmostEqual(res['base_gravable'], 24152045.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 5361950.0, delta=1.0)

    def test_justo_en_el_limite_no_hay_exceso(self):
        """10.000.000 con pension voluntaria 1.840.000: base 9.200.000; beneficios 1.840.000 + 25 % de 7.360.000 (1.840.000) = 3.680.000 = 40 % de 9.200.000: el exceso es 0 y la base 5.520.000."""
        res = self._rete(10000000.0, vol=1840000.0)
        self.assertAlmostEqual(res['beneficios_antes_del_limite'], res['limite_global'], delta=0.01)
        self.assertAlmostEqual(res['exceso_limite_global'], 0.0, delta=0.01)
        self.assertAlmostEqual(res['base_gravable'], 5520000.0, delta=0.01)

    # ── Procedimiento 2 y quincenal ──
    def test_el_procedimiento_2_hereda_el_calculo(self):
        """El % fijo del Procedimiento 2 se deriva con compute_retefuente(force_procedure='1'): hereda el limite. Un contrato en P2 forzado a la tabla da lo del caso 2 (313.209), no el 0 de antes."""
        res = self._rete(12000000.0, vol=2000000.0, afc=1600000.0, dependientes=True, procedimiento='2', force_procedure='1')
        self.assertAlmostEqual(res['exceso_limite_global'], 1944000.0, delta=0.01)
        self.assertAlmostEqual(res['retencion_pesos'], 313209.0, delta=1.0)

    def test_quincenal_el_limite_es_mensual_ni_se_duplica_ni_se_prorratea(self):
        """El limite se calcula sobre la base MENSUAL (R-2 retiene siempre sobre el mes completo y reparte 50 %/50 %): las dos quincenas de un mes ven el mismo limite del mes (4.416.000 en el caso 2), no
        el doble (8.832.000) ni la mitad (2.208.000). El reparto de la retencion entre quincenas es de R-2, no de esta pieza."""
        primera = self._rete(12000000.0, vol=2000000.0, afc=1600000.0, dependientes=True)
        segunda = self._rete(12000000.0, vol=2000000.0, afc=1600000.0, dependientes=True)
        for res in (primera, segunda):
            self.assertAlmostEqual(res['limite_global'], 4416000.0, delta=0.01)
            self.assertAlmostEqual(res['base_gravable'], 6624000.0, delta=0.01)
        self.assertEqual(primera['retencion_pesos'], segunda['retencion_pesos'])

    # ── lo que NO cambia y los parametros ──
    def test_el_acumulador_de_pension_voluntaria_y_afc_no_cambia_con_el_limite(self):
        """D-02-4: CO_EXENTO_PENSION_AFC mide la naturaleza del aporte (tope de 3.800 UVT anuales), no lo que el limite global dejo pasar: en el caso 2 sigue siendo 3.600.000."""
        res = self._rete(12000000.0, vol=2000000.0, afc=1600000.0, dependientes=True)
        self.assertAlmostEqual(res['exento_vol_pension_afc'], 3600000.0, delta=0.01)
        self.assertAlmostEqual(res['aporte_voluntario_pension'] + res['afc'], 3600000.0, delta=0.01)

    def test_los_parametros_son_40_y_1340_con_vigencia_2023_y_no_hay_72_ni_maximo_de_4(self):
        """40 % y 1.340 UVT con vigencia desde 2023-01-01; los 72 UVT por dependiente y el maximo de 4 NO se cargan (D-02-2: nada los usa)."""
        Parametro = self.env['hr.rule.parameter']
        for fecha in ('2023-01-01', '2026-01-01'):
            self.assertEqual(Parametro._get_parameter_from_code('l10n_co_limite_global_pct', fecha), 40.0)
            self.assertEqual(Parametro._get_parameter_from_code('l10n_co_limite_global_uvt_anual', fecha), 1340.0)
        self.assertFalse(Parametro.search([('code', 'in', ('l10n_co_dependiente_adicional_uvt_anual', 'l10n_co_dependientes_adicionales_max'))]))

    def test_sin_el_parametro_un_error_que_lo_nombra(self):
        """Sin valor del 40 % a la fecha, no hay limite por defecto: el error nativo nombra el codigo."""
        self.env.ref('l10n_co_nomina_electronica.rule_parameter_limite_global_pct_2023').date_from = '2099-01-01'
        with self.assertRaises(UserError) as exc:
            self._rete(8000000.0)
        self.assertIn('l10n_co_limite_global_pct', str(exc.exception))
