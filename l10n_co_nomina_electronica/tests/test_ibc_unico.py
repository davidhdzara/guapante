# -*- coding: utf-8 -*-
"""IBC unico del recibo (H-017b, commit 1): regla del 40% (Ley 1393/2010 Art. 30,
SU 25185/2021), techo de 25 SMMLV sin prorratear, piso de 1 SMMLV prorrateado por
dias, salario integral, y exclusion del auxilio de transporte.

Nivel de verificacion: funcion de limites (pura) + compute_sheet real sobre la
estructura general. La consolidacion mensual, los dias por novedad y PILA/UGPP
llegan en commits siguientes."""

from collections import defaultdict
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class IbcBase(TransactionCase):
    """Fixtures comunes (sin tests propios)."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba IBC'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura IBC', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _payslip(self, name, wage, integral=False):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_integral_salary': integral})
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})

    def _linea(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def _smmlv(self, slip):
        return slip._rule_parameter('l10n_co_smmlv', slip.date_from)


@tagged('post_install', '-at_install')
class TestIbcUnico(IbcBase):

    # ── funcion de limites (pura) ──
    def test_40_por_ciento_excedente_suma_al_ibc(self):
        slip = self._payslip('Lim1', 3000000.0)
        # salarial 3.000.000 + pactado 3.000.000: tope 40% de 6.000.000 = 2.400.000 -> excedente 600.000
        ibc = slip._ne_ibc_limites(3000000.0, 0.0, 3000000.0, 3000000.0, 30)
        self.assertAlmostEqual(ibc, 3600000.0, delta=0.01)

    def test_pactados_bajo_el_40_no_suman(self):
        slip = self._payslip('Lim2', 3000000.0)
        ibc = slip._ne_ibc_limites(3000000.0, 0.0, 3000000.0, 500000.0, 30)
        self.assertAlmostEqual(ibc, 3000000.0, delta=0.01)

    def test_integral_70_mas_excedente_sobre_integral_completo(self):
        slip = self._payslip('Lim3', 20000000.0, integral=True)
        # integral 20.000.000 -> IBC salarial 14.000.000; pactado 10.000.000 sobre
        # remuneracion (20.000.000 + 10.000.000)=30.000.000 -> tope 12.000.000 -> excedente 0
        self.assertAlmostEqual(
            slip._ne_ibc_limites(14000000.0, 0.0, 20000000.0, 10000000.0, 30), 14000000.0, delta=0.01)
        # pactado 15.000.000: tope 40% de 35.000.000 = 14.000.000 -> excedente 1.000.000
        self.assertAlmostEqual(
            slip._ne_ibc_limites(14000000.0, 0.0, 20000000.0, 15000000.0, 30), 15000000.0, delta=0.01)

    def test_techo_25_smmlv_no_se_prorratea(self):
        slip = self._payslip('Lim4', 3000000.0)
        smmlv = self._smmlv(slip)
        self.assertAlmostEqual(
            slip._ne_ibc_limites(100 * smmlv, 0.0, 100 * smmlv, 0.0, 10), 25 * smmlv, delta=0.01)

    def test_piso_se_prorratea_por_dias(self):
        slip = self._payslip('Lim5', 3000000.0)
        smmlv = self._smmlv(slip)
        self.assertAlmostEqual(
            slip._ne_ibc_limites(100000.0, 0.0, 100000.0, 0.0, 15), smmlv / 2, delta=0.01)

    # ── clasificacion de no salariales ──
    def _rr(self, **totales):
        rr = defaultdict(lambda: {'total': 0.0})
        for k, v in totales.items():
            rr[k] = {'total': v}
        return rr

    def test_pactados_cuenta_pacto_y_excluye_naturaleza(self):
        slip = self._payslip('Pac1', 3000000.0)
        rr = self._rr(CO_AUX_TRANS=200000.0, CO_AUX_ALIM=150000.0)
        self.assertAlmostEqual(slip._ne_ibc_pactados(rr), 150000.0, delta=0.01)

    def test_no_salarial_sin_clasificar_es_error_claro(self):
        slip = self._payslip('Pac2', 3000000.0)
        regla = self.structure.rule_ids.filtered(lambda r: r.code == 'CO_AUX_ALIM')
        regla.l10n_co_pila_origen_no_salarial = False
        with self.assertRaises(UserError) as e:
            slip._ne_ibc_pactados(self._rr(CO_AUX_ALIM=100000.0))
        self.assertIn('Origen del Pago No Salarial', str(e.exception))

    def test_clasificacion_cargada_para_las_reglas_del_modulo(self):
        mapa = {r.code: r.l10n_co_pila_origen_no_salarial for r in self.structure.rule_ids}
        self.assertEqual(mapa['CO_AUX_TRANS'], 'naturaleza')
        self.assertEqual(mapa['CO_AUX_ALIM'], 'pacto')

    # ── compute_sheet real ──
    def test_ibc_no_incluye_auxilio_de_transporte_y_alimenta_la_deduccion(self):
        slip = self._payslip('Real1', 1800000.0)
        slip.compute_sheet()
        ibc = self._linea(slip, 'CO_IBC_SP')
        self.assertTrue(ibc)
        self.assertAlmostEqual(ibc.total, 1800000.0, delta=0.01)
        self.assertTrue(self._linea(slip, 'CO_AUX_TRANS'))   # el auxilio existe...
        self.assertGreater(self._linea(slip, 'CO_BRUTO').total, ibc.total)  # ...y no entra
        pct = slip._rule_parameter('l10n_co_pct_salud_empleado', slip.date_from)
        self.assertAlmostEqual(-self._linea(slip, 'CO_SALUD_EMP').total, ibc.total * pct / 100, delta=1.0)

    def test_techo_en_nomina_real(self):
        slip = self._payslip('Real2', 60000000.0)
        slip.compute_sheet()
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, 25 * self._smmlv(slip), delta=0.01)

    def test_piso_en_nomina_real(self):
        slip = self._payslip('Real3', 1000000.0)
        slip.compute_sheet()
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, self._smmlv(slip), delta=0.01)

    def test_integral_en_nomina_real_es_70_por_ciento(self):
        slip = self._payslip('Real4', 20000000.0, integral=True)
        slip.compute_sheet()
        factor = slip._rule_parameter('l10n_co_factor_integral_salary', slip.date_from)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SP').total, 20000000.0 * factor, delta=0.01)


@tagged('post_install', '-at_install')
class TestIbcUnicoCiaYLiquidacion(IbcBase):
    """Commit 3a: los aportes patronales y la liquidacion leen el IBC unico."""

    def test_aportes_patronales_usan_el_ibc_unico_no_el_bruto(self):
        slip = self._payslip('Cia1', 1800000.0)   # con auxilio de transporte
        slip.compute_sheet()
        ibc = self._linea(slip, 'CO_IBC_SP').total
        self.assertAlmostEqual(ibc, 1800000.0, delta=0.01)
        pension = self._linea(slip, 'CO_PENSION_CIA')
        pct = slip._rule_parameter('l10n_co_pct_pension_empleador', slip.date_from)
        self.assertAlmostEqual(pension.total, ibc * pct / 100, delta=1.0)
        arl = self._linea(slip, 'CO_ARL_CIA')
        self.assertAlmostEqual(arl.total, self._linea(slip, 'CO_IBC_ARL').total * slip._ne_pct_arl() / 100, delta=1.0)
        ccf = self._linea(slip, 'CO_CCF_CIA')
        pct_ccf = slip._rule_parameter('l10n_co_pct_ccf', slip.date_from)
        self.assertAlmostEqual(ccf.total, self._linea(slip, 'CO_IBC_PARAF').total * pct_ccf / 100, delta=1.0)

    def test_aportes_patronales_con_piso_y_techo(self):
        alto = self._payslip('Cia2', 60000000.0)
        alto.compute_sheet()
        self.assertAlmostEqual(
            self._linea(alto, 'CO_PENSION_CIA').total,
            25 * self._smmlv(alto) * alto._rule_parameter('l10n_co_pct_pension_empleador', alto.date_from) / 100,
            delta=1.0)


@tagged('post_install', '-at_install')
class TestIbcParafiscales(IbcBase):
    """.299-1 (decisión del TL, 22-nov; Ley 21/1982 art. 17, Ley 344/1996 art. 17, Ley 1393/2010 art. 30, SU 25185/2021): el IBC de CCF, SENA e ICBF es SOLO lo
    salarial (sin el excedente del 40 %, sin piso y sin techo); el de salud, pensión y ARL conserva el 40 %, el piso y el techo."""

    def _limites_anterior(self, slip, salarial, incap, remuneracion, pactados, dias):
        """ORÁCULO: copia literal de ``_ne_ibc_limites`` de .298 (con el excedente escrito en línea). Si la extracción de .299 cambiara algún resultado, falla."""
        smmlv = slip._rule_parameter('l10n_co_smmlv', slip._ne_fecha_parametros())
        pct = slip._rule_parameter('l10n_co_pct_tope_no_salarial', slip._ne_fecha_parametros())
        minimo = slip._rule_parameter('l10n_co_ibc_min_smmlv', slip._ne_fecha_parametros())
        maximo = slip._rule_parameter('l10n_co_ibc_max_smmlv', slip._ne_fecha_parametros())
        dias_mes = slip._rule_parameter('l10n_co_dias_mes_comercial', slip._ne_fecha_parametros())
        excedente = max(0.0, pactados - pct / 100.0 * (remuneracion + pactados))
        ibc = min(salarial + incap + excedente, maximo * smmlv)
        if dias > 0:
            ibc = max(ibc, minimo * smmlv / dias_mes * dias)
        return ibc

    def _con_pactados(self, nombre, wage, pactados, integral=False):
        """Recibo de septiembre de la estructura general con un pago no salarial POR PACTO (CO_BONIF_NOSAL) de ``pactados``, ya calculado."""
        slip = self._payslip(nombre, wage, integral=integral)
        if pactados:
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal').id,
                'code': 'CO_BONIF_NOSAL', 'amount': pactados})
        slip.compute_sheet()
        return slip

    # ── la extracción no cambia el IBC de salud, pensión y ARL (prueba de equivalencia) ──
    def test_01_extraer_el_exceso_no_cambia_el_resultado_de_la_funcion_de_limites(self):
        slip = self._payslip('Equiv1', 3000000.0)
        smmlv = self._smmlv(slip)
        casos = 0
        for salarial in (100000.0, 1000000.0, 3000000.0, 14000000.0, 100 * smmlv):
            for pactados in (0.0, 500000.0, 3000000.0, 15000000.0):
                for incap in (0.0, 200000.0):
                    for dias in (0, 7, 15, 30):
                        esperado = self._limites_anterior(slip, salarial, incap, salarial, pactados, dias)
                        self.assertAlmostEqual(slip._ne_ibc_limites(salarial, incap, salarial, pactados, dias), esperado, places=6,
                                               msg=(salarial, pactados, incap, dias))
                        casos += 1
        self.assertEqual(casos, 160)
        pct = slip._rule_parameter('l10n_co_pct_tope_no_salarial', slip.date_from)
        self.assertAlmostEqual(slip._ne_exceso_no_salarial(3000000.0, 3000000.0), 3000000.0 - pct / 100.0 * 6000000.0, places=6)
        self.assertEqual(slip._ne_exceso_no_salarial(3000000.0, 500000.0), 0.0)

    # ── la base de parafiscales: solo lo salarial ──
    def test_02_parafiscales_es_solo_salarial_sin_el_40_sin_piso_y_sin_techo(self):
        slip = self._payslip('Paraf1', 3000000.0)
        smmlv = self._smmlv(slip)
        for salarial in (100000.0, 3000000.0, 100 * smmlv):
            self.assertEqual(slip._ne_ibc_parafiscales(salarial), salarial)
        # con pactados sobre el 40 % la base de salud, pensión y ARL sube y la de parafiscales NO
        con_exceso = slip._ne_ibc_limites(3000000.0, 0.0, 3000000.0, 3000000.0, 30)
        self.assertAlmostEqual(con_exceso, 3600000.0, delta=0.01)
        self.assertEqual(slip._ne_ibc_parafiscales(3000000.0), 3000000.0)
        # ni el techo de 25 SMMLV ni el piso (prorrateado) aplican a parafiscales
        self.assertAlmostEqual(slip._ne_ibc_limites(100 * smmlv, 0.0, 100 * smmlv, 0.0, 30), 25 * smmlv, delta=0.01)
        self.assertAlmostEqual(slip._ne_ibc_limites(100000.0, 0.0, 100000.0, 0.0, 30), smmlv, delta=0.01)
        self.assertEqual(slip._ne_ibc_parafiscales(100000.0), 100000.0)

    # ── antes y después en una nómina real (necesita -u: la fórmula de CO_IBC_PARAF es dato) ──
    def test_03_con_pactados_sobre_el_40_solo_cambia_el_ibc_de_parafiscales_y_su_aporte(self):
        """Salario 3.000.000 + 3.000.000 de pactados no salariales: 40 % de 6.000.000 = 2.400.000, exceso 600.000. ANTES de .299 los tres IBC eran 3.600.000;
        AHORA salud, pensión y ARL siguen en 3.600.000 y parafiscales baja a 3.000.000 (CCF, SENA e ICBF sobre lo salarial)."""
        slip = self._con_pactados('Antes1', 3000000.0, 3000000.0)
        antes = self._limites_anterior(slip, 3000000.0, 0.0, 3000000.0, 3000000.0, 30)
        self.assertAlmostEqual(antes, 3600000.0, delta=0.01)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_SALARIAL').total, 3000000.0, delta=0.01)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_PACTADOS').total, 3000000.0, delta=0.01)
        for codigo in ('CO_IBC_SP', 'CO_IBC_ARL'):
            self.assertAlmostEqual(self._linea(slip, codigo).total, 3600000.0, delta=0.01, msg=codigo)
        paraf = self._linea(slip, 'CO_IBC_PARAF').total
        self.assertAlmostEqual(paraf, 3000000.0, delta=0.01)
        self.assertAlmostEqual(antes - paraf, 600000.0, delta=0.01, msg='El recibo deja de pagar parafiscales sobre el exceso')
        pct_ccf = slip._rule_parameter('l10n_co_pct_ccf', slip.date_from)
        self.assertAlmostEqual(self._linea(slip, 'CO_CCF_CIA').total, 3000000.0 * pct_ccf / 100.0, delta=1.0)
        pct_pension = slip._rule_parameter('l10n_co_pct_pension_empleador', slip.date_from)
        self.assertAlmostEqual(self._linea(slip, 'CO_PENSION_CIA').total, 3600000.0 * pct_pension / 100.0, delta=1.0)

    def test_04_sin_pactados_los_tres_ibc_son_iguales_y_no_cambia_nada(self):
        slip = self._con_pactados('Antes2', 3000000.0, 0.0)
        ibcs = [self._linea(slip, c).total for c in ('CO_IBC_SP', 'CO_IBC_ARL', 'CO_IBC_PARAF')]
        self.assertEqual(ibcs, [ibcs[0]] * 3)
        self.assertAlmostEqual(ibcs[0], 3000000.0, delta=0.01)

    def test_05_con_pactados_bajo_el_40_tampoco_cambia_nada(self):
        slip = self._con_pactados('Antes3', 3000000.0, 500000.0)
        for codigo in ('CO_IBC_SP', 'CO_IBC_ARL', 'CO_IBC_PARAF'):
            self.assertAlmostEqual(self._linea(slip, codigo).total, 3000000.0, delta=0.01, msg=codigo)

    def test_06_parafiscales_no_tiene_techo_ni_piso_en_una_nomina_real(self):
        alto = self._payslip('Paraf2', 60000000.0)
        alto.compute_sheet()
        self.assertAlmostEqual(self._linea(alto, 'CO_IBC_SP').total, 25 * self._smmlv(alto), delta=0.01, msg='Salud y pensión: techo de 25 SMMLV')
        self.assertAlmostEqual(self._linea(alto, 'CO_IBC_PARAF').total, 60000000.0, delta=0.01, msg='Parafiscales: sin techo')
        pct_ccf = alto._rule_parameter('l10n_co_pct_ccf', alto.date_from)
        self.assertAlmostEqual(self._linea(alto, 'CO_CCF_CIA').total, 60000000.0 * pct_ccf / 100.0, delta=1.0)
        bajo = self._payslip('Paraf3', 500000.0)
        bajo.compute_sheet()
        self.assertAlmostEqual(self._linea(bajo, 'CO_IBC_SP').total, self._smmlv(bajo), delta=0.01, msg='Salud y pensión: piso de 1 SMMLV')
        self.assertAlmostEqual(self._linea(bajo, 'CO_IBC_PARAF').total, 500000.0, delta=0.01, msg='Parafiscales: sin piso')

    def test_07_el_salario_integral_en_parafiscales_se_queda_en_el_70_por_ciento(self):
        slip = self._payslip('Paraf4', 20000000.0, integral=True)
        slip.compute_sheet()
        factor = slip._rule_parameter('l10n_co_factor_integral_salary', slip.date_from)
        self.assertAlmostEqual(self._linea(slip, 'CO_IBC_PARAF').total, 20000000.0 * factor, delta=0.01)

    def test_08_el_apoyo_de_sostenimiento_no_cuenta_en_el_40_ni_lanza_el_error_de_sin_clasificar(self):
        """.299 (TL, 22-nov): CO_APOYO_SOST se siembra con origen «naturaleza» (régimen propio del aprendiz): el 40 % no lo cuenta y ``_ne_ibc_pactados`` no
        lanza el UserError. Necesita -u (la siembra del origen es una función de datos)."""
        slip = self._payslip('Apoyo1', 3000000.0)
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_APOYO_SOST'), ('struct_id', '=', self.structure.id)], limit=1)
        self.assertEqual(regla.l10n_co_pila_origen_no_salarial, 'naturaleza')
        rr = defaultdict(lambda: {'total': 0.0})
        rr['CO_APOYO_SOST'] = {'total': 900000.0}
        self.assertEqual(slip._ne_ibc_pactados(rr), 0.0)

