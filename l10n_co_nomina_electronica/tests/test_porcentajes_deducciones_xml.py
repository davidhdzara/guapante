# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F3-04 (decision del TL del 22-nov, independiente de la opcion A): los porcentajes de Salud, FondoPension y FondoSP del XML NO son literales (4, 4 y 1): salen de ``rate`` de las lineas del recibo, que cada regla
fija con el MISMO parametro con que calcula (``l10n_co_pct_salud_empleado``, ``l10n_co_pct_pension_empleado`` y el tramo del FSP por el IBC). Sin linea (la regla no se calculo: aprendiz lectivo, pensionado) no hay
nodo y el constructor escribe 0 en Salud y FondoPension, que el XSD v1.0.6 exige (``minOccurs=1``) y cuyo porcentaje es un ``xsd:decimal`` sin minimo; FondoSP es opcional y se omite.

Valores a mano (marzo de 2026, SMMLV 1.750.905): sueldo 10.000.000 (5,7 SMMLV) -> 4 / 4 / FSP total 1,00 = 0,5 solidaridad + 0,5 subsistencia; 30.000.000 (17,1 SMMLV, desde 17) -> total 1,40 = 0,5 + 0,9;
40.000.000 (22,8 SMMLV, desde 20) -> total 2,00 = 0,5 + 1,5 (Ley 797/2003 art. 8: la solidaridad es el 50 % del 1 %; la subsistencia, el otro 50 % mas el adicional del tramo). Cada deduccion es el IBC por su
porcentaje y la suma de las dos es EXACTAMENTE la linea CO_FSP (el centavo de redondeo va a la subsistencia)."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from odoo.addons.l10n_co_nomina_electronica.services import documento_merge, nomina_xml_builder
from odoo.tests.common import BaseCase, tagged

from . import test_aprendiz_regimen as aprendiz

FECHA = date(2026, 3, 1)


@tagged('post_install', '-at_install')
class TestPorcentajesDeduccionesXml(aprendiz.TestAprendizAportes):
    """Hereda los fixtures (compania, EPS/AFP/CCF, recibos, aprendices) pero no vuelve a correr las pruebas del padre."""

    def _con_sueldo(self, nombre, sueldo, tipo='01', subtipo='00', **entidades):
        empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, subtipo=subtipo, desde=FECHA, hasta=date(2026, 3, 31), **entidades)
        recibo.contract_id.write({'wage': sueldo})
        recibo.contract_id.generate_work_entries(FECHA, date(2026, 3, 31))
        self._config_retefuente(2026)
        recibo.compute_sheet()
        return recibo

    def _normal(self, nombre, sueldo=10000000.0):
        return self._con_sueldo(nombre, sueldo, eps=self.eps, afp=self.afp, ccf=self.ccf)

    def _deducciones(self, recibo):
        return recibo._map_salary_rules_to_xml()[1]

    def _nodos(self, recibo):
        """Los nodos como los escribe el constructor del XML, con los porcentajes como numero."""
        nodo = nomina_xml_builder._get_deducciones_node(self._deducciones(recibo))
        return {clave: {atributo: (float(valor) if valor is not None else None) for atributo, valor in nodo[clave].items()} for clave in ('Salud', 'FondoPension', 'FondoSP')}

    # ── normal: los mismos valores de antes, ahora derivados ──
    def test_un_empleado_normal_reporta_4_4_y_el_fsp_en_solidaridad_y_subsistencia(self):
        recibo = self._normal('Normal Porcentajes')
        deducciones = self._deducciones(recibo)
        fsp = deducciones['FondoSP']
        self.assertEqual((deducciones['Salud']['Porcentaje'], deducciones['FondoPension']['Porcentaje'], fsp['Porcentaje'], fsp['PorcentajeSub']), ('4.00', '4.00', '0.50', '0.50'))
        self.assertAlmostEqual(float(deducciones['Salud']['Deduccion']), -self._total(recibo, 'CO_SALUD_EMP'), delta=0.01)
        self.assertAlmostEqual(float(deducciones['FondoPension']['Deduccion']), -self._total(recibo, 'CO_PENSION_EMP'), delta=0.01)
        self.assertEqual((fsp['DeduccionSP'], fsp['DeduccionSub']), ('50000.00', '50000.00'))              # 0,5 % y 0,5 % de 10.000.000

    def test_el_porcentaje_sigue_al_parametro_y_no_a_un_literal(self):
        """Un valor nuevo del parametro con vigencia desde el 1-mar-2026 (5 % de salud y 6 % de pension del trabajador) cambia el porcentaje del XML y la deduccion que lo acompana."""
        for codigo, valor in (('l10n_co_pct_salud_empleado', '5.0'), ('l10n_co_pct_pension_empleado', '6.0')):
            parametro = self.env['hr.rule.parameter'].search([('code', '=', codigo)])
            self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'date_from': FECHA, 'parameter_value': valor})
        recibo = self._normal('Parametro Cambiado')
        deducciones = self._deducciones(recibo)
        self.assertEqual((deducciones['Salud']['Porcentaje'], deducciones['FondoPension']['Porcentaje']), ('5.00', '6.00'))
        self.assertAlmostEqual(float(deducciones['Salud']['Deduccion']), 0.05 * 10000000.0, delta=0.01)
        self.assertAlmostEqual(float(deducciones['FondoPension']['Deduccion']), 0.06 * 10000000.0, delta=0.01)

    # ── FSP segun el IBC: solidaridad y subsistencia ──
    def _fsp(self, recibo):
        """(nodo del XML, linea CO_FSP) de un recibo."""
        return self._deducciones(recibo)['FondoSP'], self.env['hr.payslip.line'].search([('slip_id', '=', recibo.id), ('code', '=', 'CO_FSP')])

    def test_el_fsp_se_divide_en_solidaridad_y_subsistencia_segun_el_tramo_del_ibc(self):
        casos = (
            # (sueldo, % solidaridad, % subsistencia, deduccion solidaridad, deduccion subsistencia)
            (10000000.0, '0.50', '0.50', '50000.00', '50000.00'),
            (30000000.0, '0.50', '0.90', '150000.00', '270000.00'),
            (40000000.0, '0.50', '1.50', '200000.00', '600000.00'))
        for sueldo, pct_sp, pct_sub, ded_sp, ded_sub in casos:
            with self.subTest(sueldo=sueldo):
                fsp, linea = self._fsp(self._normal('Fsp %s' % int(sueldo), sueldo))
                self.assertEqual((fsp['Porcentaje'], fsp['PorcentajeSub'], fsp['DeduccionSP'], fsp['DeduccionSub']), (pct_sp, pct_sub, ded_sp, ded_sub))
                self.assertAlmostEqual(float(pct_sp) + float(pct_sub), linea.rate, places=4)                       # el total del tramo es la rate de la regla
                self.assertEqual(Decimal(fsp['DeduccionSP']) + Decimal(fsp['DeduccionSub']), Decimal('%.2f' % -linea.total), 'La suma es exactamente la linea CO_FSP')

    def test_el_centavo_de_redondeo_del_fsp_va_a_la_subsistencia(self):
        """Sueldo 10.000.333: el 1 % (100.003,33) se reparte en proporcion 0,5 / 0,5: la solidaridad es 50.001,665 -> 50.001,67 (medio arriba) y la subsistencia lo que falta: 50.001,66."""
        fsp, linea = self._fsp(self._normal('Fsp Centavo', 10000333.0))
        total = Decimal('%.2f' % -linea.total)
        solidaridad = (total * Decimal('0.5') / Decimal('1.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual((Decimal(fsp['DeduccionSP']), Decimal(fsp['DeduccionSub'])), (solidaridad, total - solidaridad))
        self.assertEqual(Decimal(fsp['DeduccionSP']) + Decimal(fsp['DeduccionSub']), total)

    def test_la_solidaridad_sigue_al_parametro(self):
        """Un valor nuevo de ``l10n_co_fsp_pct_solidaridad`` (0,4 desde el 1-mar-2026) da 0,40 de solidaridad y 0,60 de subsistencia sobre el mismo 1 % del tramo."""
        parametro = self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_fsp_pct_solidaridad')])
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'date_from': FECHA, 'parameter_value': '0.4'})
        fsp, _linea = self._fsp(self._normal('Fsp Parametro'))
        self.assertEqual((fsp['Porcentaje'], fsp['PorcentajeSub'], fsp['DeduccionSP'], fsp['DeduccionSub']), ('0.40', '0.60', '40000.00', '60000.00'))

    # ── sin linea: 0 en lo obligatorio, sin nodo en lo opcional ──
    def test_el_pensionado_reporta_pension_en_0_con_deduccion_0_y_sin_fsp(self):
        recibo = self._con_sueldo('Pensionado Porcentajes', 10000000.0, tipo='01', subtipo='01', eps=self.eps, ccf=self.ccf)
        deducciones = self._deducciones(recibo)
        self.assertNotIn('FondoPension', deducciones)
        self.assertNotIn('FondoSP', deducciones)
        nodos = self._nodos(recibo)
        self.assertEqual(nodos['Salud']['Porcentaje'], 4.0)                                   # la salud si la paga
        self.assertEqual((nodos['FondoPension']['Porcentaje'], nodos['FondoPension']['Deduccion']), (0.0, 0.0))
        self.assertIsNone(nodos['FondoSP']['Porcentaje'])                                      # FondoSP es opcional: sin nodo

    def test_el_aprendiz_lectivo_reporta_salud_y_pension_en_0_y_el_de_practica_4_y_4(self):
        lectiva, _smmlv = self._aprendiz('Lectiva Porcentajes', '19', '4', 0.75)
        deducciones = self._deducciones(lectiva)
        self.assertNotIn('Salud', deducciones)
        self.assertNotIn('FondoPension', deducciones)
        nodos = self._nodos(lectiva)
        self.assertEqual((nodos['Salud']['Porcentaje'], nodos['Salud']['Deduccion'], nodos['FondoPension']['Porcentaje'], nodos['FondoPension']['Deduccion']), (0.0, 0.0, 0.0, 0.0))
        practica, _smmlv = self._aprendiz('Practica Porcentajes', '01', '4', 1.0)
        deducciones = self._deducciones(practica)
        self.assertEqual((deducciones['Salud']['Porcentaje'], deducciones['FondoPension']['Porcentaje']), ('4.00', '4.00'))

    def test_un_recibo_sin_las_lineas_de_salud_ni_pension_ya_no_reporta_un_4_por_defecto(self):
        nodo = nomina_xml_builder._get_deducciones_node({})
        self.assertEqual((nodo['Salud']['Porcentaje'], nodo['Salud']['Deduccion'], nodo['FondoPension']['Porcentaje'], nodo['FondoPension']['Deduccion']), ('0.00', '0.00', '0.00', '0.00'))


    # ── Cesantias/@Porcentaje: el de los intereses (Ley 52/1975), del parametro ──
    def _recibo_con_intereses(self, nombre, sueldo):
        recibo = self._normal(nombre, sueldo)
        recibo.write({'input_line_ids': [(0, 0, {'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_int_ces').id, 'amount': 150000.0})]})
        recibo.compute_sheet()
        return recibo

    def test_el_porcentaje_de_las_cesantias_es_el_parametro_de_los_intereses_y_no_un_12_fijo(self):
        for sueldo in (10000000.0, 30000000.0, 40000000.0):
            with self.subTest(sueldo=sueldo):
                recibo = self._recibo_con_intereses('Intereses %s' % int(sueldo), sueldo)
                cesantias = recibo._map_salary_rules_to_xml()[0]['Cesantias']
                self.assertEqual(cesantias['Porcentaje'], '12.00')                          # valor de fabrica (Ley 52 de 1975)
                self.assertEqual(cesantias['PagoIntereses'], '150000.00')
        parametro = self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_pct_intereses_cesantias')])
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'date_from': FECHA, 'parameter_value': '13.0'})
        self.assertEqual(self._recibo_con_intereses('Intereses Cambiado', 10000000.0)._map_salary_rules_to_xml()[0]['Cesantias']['Porcentaje'], '13.00')

    def test_sin_cesantias_ni_intereses_en_el_recibo_no_hay_nodo_de_cesantias(self):
        devengados = self._normal('Sin Intereses')._map_salary_rules_to_xml()[0]
        self.assertNotIn('Cesantias', devengados)                                           # sin cesantias ni intereses no hay nodo


@tagged('post_install', '-at_install')
class TestFusionDelFondoSp(BaseCase):
    """La fusion mensual con los porcentajes ya derivados: el tramo del FSP puede cambiar entre recibos del mes (no detiene el documento) y se pondera cada porcentaje por la deduccion de SU pareja; Salud y FondoPension
    siguen exigiendo el mismo porcentaje."""

    @staticmethod
    def _recibo(salud='4.00', fsp=None):
        """``fsp`` = (Porcentaje, DeduccionSP, PorcentajeSub, DeduccionSub)."""
        deducciones = {'Salud': {'Porcentaje': salud, 'Deduccion': '100000.00'}, 'FondoPension': {'Porcentaje': '4.00', 'Deduccion': '100000.00'}}
        if fsp:
            deducciones['FondoSP'] = dict(zip(('Porcentaje', 'DeduccionSP', 'PorcentajeSub', 'DeduccionSub'), fsp))
        return {'deducciones': deducciones}

    def test_el_mismo_tramo_se_conserva_y_las_deducciones_se_suman(self):
        fusion = documento_merge.fusionar_deducciones([self._recibo(fsp=('0.50', '50000.00', '0.50', '50000.00')), self._recibo(fsp=('0.50', '70000.00', '0.50', '70000.00'))])
        self.assertEqual(fusion['FondoSP'], {'Porcentaje': '0.50', 'DeduccionSP': '120000.00', 'PorcentajeSub': '0.50', 'DeduccionSub': '120000.00'})

    def test_tramos_distintos_se_ponderan_cada_uno_por_su_pareja_y_no_detienen_el_documento(self):
        """Subsistencia 0,50 % sobre 50.000 y 0,90 % sobre 180.000 -> (0,5 x 50.000 + 0,9 x 180.000) / 230.000 = 0,81; la solidaridad (0,50 en los dos) se conserva."""
        fusion = documento_merge.fusionar_deducciones([self._recibo(fsp=('0.50', '50000.00', '0.50', '50000.00')), self._recibo(fsp=('0.50', '100000.00', '0.90', '180000.00'))])
        self.assertEqual(fusion['FondoSP'], {'Porcentaje': '0.50', 'DeduccionSP': '150000.00', 'PorcentajeSub': '0.81', 'DeduccionSub': '230000.00'})

    def test_un_recibo_sin_fsp_no_cambia_el_del_otro(self):
        fusion = documento_merge.fusionar_deducciones([self._recibo(), self._recibo(fsp=('0.50', '80000.00', '0.70', '112000.00'))])
        self.assertEqual(fusion['FondoSP'], {'Porcentaje': '0.50', 'DeduccionSP': '80000.00', 'PorcentajeSub': '0.70', 'DeduccionSub': '112000.00'})

    def test_salud_con_porcentaje_distinto_sigue_deteniendo_el_documento(self):
        with self.assertRaises(documento_merge.ErrorFusion):
            documento_merge.fusionar_deducciones([self._recibo(salud='4.00'), self._recibo(salud='5.00')])
