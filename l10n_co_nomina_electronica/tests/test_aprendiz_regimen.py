# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-09 (doc 88; decisiones del TL del 22-nov): el aprendiz tiene un regimen propio que sale de UN metodo, ``HrPayslip._ne_regimen_cotizante``, y de una tabla versionada por fecha (parametro
``l10n_co_aprendiz_etapas``: tipo de cotizante, tipo de contrato, etapa, TipoTrabajador de la DIAN). Esquema PROVISIONAL «mientras el Ministerio de Salud expide el acto administrativo» (Concepto MinSalud
2025310001925691 y Circular MinTrabajo 083 del 18-jul-2025): hasta el 31-jul-2025 el 12 era la lectiva y el 19 la productiva; desde el 1-ago-2025 la lectiva es el tipo 19 y la practica o dual es el tipo 01 con el contrato
«4 - Aprendizaje»; el 12 se restringe."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from . import test_pension_no_exigida as pension
from . import test_validacion_afiliacion as base


@tagged('post_install', '-at_install')
class TestAprendizRegimen(base.TestValidacionAfiliacion):

    def _regimen(self, nombre, tipo, tipo_contrato='2', desde=date(2026, 3, 1), hasta=date(2026, 3, 31)):
        _empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, tipo_contrato=tipo_contrato, desde=desde, hasta=hasta)
        return recibo._ne_regimen_cotizante()

    def test_la_tabla_por_vigencia(self):
        casos = (
            # (nombre, tipo de cotizante, tipo de contrato, desde, hasta, etapa esperada, TipoTrabajador esperado)
            ('12 julio 2025', '12', '2', date(2025, 7, 1), date(2025, 7, 31), 'lectiva', '12'),
            ('19 julio 2025', '19', '2', date(2025, 7, 1), date(2025, 7, 31), 'practica', '19'),
            ('19 agosto 2025', '19', '2', date(2025, 8, 1), date(2025, 8, 31), 'lectiva', '12'),
            ('12 agosto 2025', '12', '2', date(2025, 8, 1), date(2025, 8, 31), False, False),
            ('01 aprendizaje agosto 2025', '01', '4', date(2025, 8, 1), date(2025, 8, 31), 'practica', '19'),
            ('01 aprendizaje julio 2025', '01', '4', date(2025, 7, 1), date(2025, 7, 31), False, False),
            ('01 dependiente 2026', '01', '2', date(2026, 3, 1), date(2026, 3, 31), False, False),
            ('01 aprendizaje 2026', '01', '4', date(2026, 3, 1), date(2026, 3, 31), 'practica', '19'),
            ('19 lectiva 2026', '19', '4', date(2026, 3, 1), date(2026, 3, 31), 'lectiva', '12'),
        )
        for nombre, tipo, tipo_contrato, desde, hasta, etapa, tipo_trabajador in casos:
            regimen = self._regimen(nombre, tipo, tipo_contrato, desde, hasta)
            self.assertEqual((regimen['etapa'], regimen['tipo_trabajador']), (etapa, tipo_trabajador), nombre)

    def test_un_dependiente_normal_no_es_aprendiz(self):
        """Tipo 01 con un contrato que no es de aprendizaje: sin etapa y sin TipoTrabajador derivado (se usa el de la ficha, como siempre)."""
        regimen = self._regimen('Normal', '01', '2')
        self.assertEqual(regimen, {'etapa': False, 'tipo_trabajador': False})

    def test_sin_el_parametro_un_error_que_lo_nombra(self):
        _empleado, recibo = self._empleado_y_recibo('Sin Tabla')
        self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_aprendiz_etapas')]).unlink()
        with self.assertRaisesRegex(UserError, 'l10n_co_aprendiz_etapas'):
            recibo._ne_regimen_cotizante()

    def test_la_tabla_sale_de_los_datos_no_del_codigo(self):
        """Agregar una fila con su fecha cambia el resultado sin tocar codigo: desde el 1-abr-2026 el tipo 01 con contrato «2» tambien es practica (el parametro es la unica fuente)."""
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_aprendiz_etapas')
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parametro.id, 'date_from': date(2026, 4, 1),
            'parameter_value': "[('19', '*', 'lectiva', '12'), ('01', '4', 'practica', '19'), ('01', '2', 'practica', '19')]"})
        self.assertFalse(self._regimen('Marzo', '01', '2', date(2026, 3, 1), date(2026, 3, 31))['etapa'])
        self.assertEqual(self._regimen('Abril', '01', '2', date(2026, 4, 1), date(2026, 4, 30))['etapa'], 'practica')


@tagged('post_install', '-at_install')
class TestAprendizAportes(pension.TestPensionNoExigida):
    """Aportes del aprendiz (decision del TL del 22-nov, H-F1-09): IBC = 1 SMMLV en las dos fases (Decreto 223/2026 art. 2.2.6.3.3.4 par. 2: el piso ya existente es el correcto).
    LECTIVA (tipo 19; «pagado plenamente por la empresa», art. 2.2.6.3.3.6): salud del 12,5 % COMPLETO a cargo de la empresa (sin descuento al aprendiz, sin exoneracion del 114-1) y ARL sobre 1 SMMLV; sin pension, sin FSP y
    sin parafiscales. PRACTICA (tipo 01 con contrato 4): como dependiente, con IBC de 1 SMMLV: salud 4 % + 8,5 %, pension 4 % + 12 %, ARL y parafiscales sobre ese IBC, con la exoneracion del 114-1 de la compania
    (SENA, ICBF y salud patronal) y la CCF siempre al 4 %. Un mes de 30 dias, sueldo del contrato 0 y apoyo como novedad: todo sale del piso. NO VERIFICADO: el 12,5 % de la lectiva y la base de los parafiscales de la practica."""

    def _aprendiz(self, nombre, tipo, tipo_contrato, factor_apoyo, desde=date(2026, 3, 1), hasta=date(2026, 3, 31)):
        empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, tipo_contrato=tipo_contrato, eps=self.eps, afp=self.afp, ccf=self.ccf, desde=desde, hasta=hasta)
        recibo.contract_id.write({'wage': 0.0})
        recibo.contract_id.generate_work_entries(desde, hasta)
        self._config_retefuente(desde.year)
        smmlv = recibo._rule_parameter('l10n_co_smmlv', recibo._ne_fecha_parametros())
        recibo.write({'input_line_ids': [(0, 0, {
            'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_apoyo_sost').id, 'amount': factor_apoyo * smmlv})]})
        recibo.compute_sheet()
        return recibo, smmlv

    def test_lectiva_salud_completa_de_la_empresa_arl_y_nada_mas(self):
        recibo, smmlv = self._aprendiz('Lectiva Aportes', '19', '4', 0.75)
        pct_salud = recibo._rule_parameter('l10n_co_pct_salud_empleador', date(2026, 3, 1)) + recibo._rule_parameter('l10n_co_pct_salud_empleado', date(2026, 3, 1))
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_SP'), smmlv, delta=0.01)                      # IBC = 1 SMMLV (el piso)
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_SALUD_EMP'), 'Sin descuento de salud al aprendiz lectivo')
        self.assertAlmostEqual(pct_salud, 12.5, delta=0.001)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_CIA'), smmlv * 0.125, delta=0.05)           # 12,5 % completo, sin exoneracion
        self._sin_lineas_de_pension(recibo)
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_ARL'), smmlv, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_ARL_CIA'), smmlv * recibo._ne_pct_arl() / 100, delta=0.05)
        for codigo in ('CO_CCF_CIA', 'CO_SENA_CIA', 'CO_ICBF_CIA'):
            self.assertFalse(self._total(recibo, codigo), '%s: la lectiva no paga parafiscales' % codigo)

    def test_lectiva_sin_exoneracion_aunque_la_compania_la_tenga(self):
        self.company.l10n_co_ne_exoneration_1607 = True
        recibo, smmlv = self._aprendiz('Lectiva Exonerada', '19', '4', 0.75)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_CIA'), smmlv * 0.125, delta=0.05)

    def test_practica_como_dependiente_con_ibc_de_un_smmlv(self):
        recibo, smmlv = self._aprendiz('Practica Aportes', '01', '4', 1.0)
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_SP'), smmlv, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), -smmlv * 0.04, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_EMP'), -smmlv * 0.04, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_CIA'), smmlv * 0.12, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_CIA'), smmlv * 0.085, delta=0.05)           # la compania de prueba no tiene la exoneracion
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_ARL'), smmlv, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_PARAF'), smmlv, delta=0.01)                   # parafiscales sobre 1 SMMLV (antes: 0)
        self.assertAlmostEqual(self._total(recibo, 'CO_CCF_CIA'), smmlv * 0.04, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_SENA_CIA'), smmlv * 0.02, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_ICBF_CIA'), smmlv * 0.03, delta=0.05)

    def test_practica_con_la_exoneracion_de_la_compania_paga_solo_la_ccf(self):
        """La exoneracion del 114-1 sale de la logica de la compania que ya existe (``_is_exonerado_parafiscales``): sin SENA, sin ICBF y sin salud patronal; la CCF sigue al 4 %."""
        self.company.l10n_co_ne_exoneration_1607 = True
        recibo, smmlv = self._aprendiz('Practica Exonerada', '01', '4', 1.0)
        for codigo in ('CO_SENA_CIA', 'CO_ICBF_CIA', 'CO_SALUD_CIA'):
            self.assertFalse(self._total(recibo, codigo), codigo)
        self.assertAlmostEqual(self._total(recibo, 'CO_CCF_CIA'), smmlv * 0.04, delta=0.05)

    def test_un_dependiente_normal_no_cambia(self):
        _empleado, recibo = self._calculado('Normal Aportes', eps=self.eps, afp=self.afp, ccf=self.ccf)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), -400000.0, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_CIA'), 850000.0, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_PARAF'), 10000000.0, delta=0.01)

    def test_el_consolidado_mensual_lleva_el_ibc_de_parafiscales_de_la_practica(self):
        """PILA lee ibc_paraf del consolidado: para la practica es 1 SMMLV (antes 0)."""
        recibo, smmlv = self._aprendiz('Practica Consolidado', '01', '4', 1.0)
        recibo.state = 'done'
        consolidado = self.env['l10n.co.ibc.mensual']._refrescar(self.company, recibo.employee_id, date(2026, 3, 1))
        self.assertAlmostEqual(consolidado.ibc_paraf, smmlv, delta=0.01)

    # ── el apoyo de sostenimiento: dos reglas por etapa ──
    def test_lectiva_el_apoyo_es_no_salarial_y_la_regla_de_la_practica_no_sale(self):
        recibo, smmlv = self._aprendiz('Lectiva Apoyo', '19', '4', 0.75)
        self.assertAlmostEqual(self._total(recibo, 'CO_APOYO_SOST'), 0.75 * smmlv, delta=0.01)             # 75 % de 1 SMMLV (Decreto 223/2026 art. 2.2.6.3.3.4)
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_APOYO_SOST_PRAC'))
        self.assertFalse(self._total(recibo, 'CO_IBC_SALARIAL'), 'No salarial: no entra al IBC salarial')
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_PROV_PRIMA' and l.total), 'La lectiva no tiene prestaciones: el apoyo no es base de la provision')

    def test_practica_el_apoyo_es_base_de_prestaciones_y_no_del_ibc(self):
        recibo, smmlv = self._aprendiz('Practica Apoyo', '01', '4', 1.0)
        self.assertAlmostEqual(self._total(recibo, 'CO_APOYO_SOST_PRAC'), smmlv, delta=0.01)               # 100 % de 1 SMMLV
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_APOYO_SOST'))
        self.assertFalse(self._total(recibo, 'CO_IBC_SALARIAL'), 'El IBC del aprendiz es 1 SMMLV (el piso), no el apoyo: no entra al IBC salarial')
        self.assertAlmostEqual(self._total(recibo, 'CO_IBC_SP'), smmlv, delta=0.01)
        self.assertTrue(self._total(recibo, 'CO_PROV_PRIMA') and self._total(recibo, 'CO_PROV_CESANTIAS'), 'El apoyo de la practica es base de las provisiones de prima y cesantias')

    def test_la_regla_de_la_practica_se_siembra_como_naturaleza_para_el_ibc(self):
        """Sin la entrada en el mapa por codigo, ``_ne_ibc_pactados`` lanza el UserError de «sin clasificar» (cuidado del consultor v19). Necesita -u (la siembra del origen es una funcion de datos)."""
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_APOYO_SOST_PRAC'), ('struct_id', '=', self.nomina.id)], limit=1)
        self.assertTrue(regla)
        self.assertEqual(regla.l10n_co_pila_origen_no_salarial, 'naturaleza')
        self.assertTrue(regla.l10n_co_ne_base_prima_cesantias and regla.l10n_co_ne_base_vacaciones)
        self.assertFalse(regla.l10n_co_ne_ajustable or regla.l10n_co_ne_vigilar_habitualidad)

    def test_sin_etapa_el_apoyo_sigue_como_siempre(self):
        """Un contrato que no esta en la tabla (no es de aprendiz) con la novedad: la regla de siempre (no salarial)."""
        _empleado, recibo = self._empleado_y_recibo('Sin Etapa Apoyo', tipo='01', tipo_contrato='2', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2026, 3, 1), hasta=date(2026, 3, 31))
        recibo.contract_id.generate_work_entries(date(2026, 3, 1), date(2026, 3, 31))
        self._config_retefuente(2026)
        recibo.write({'input_line_ids': [(0, 0, {'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_apoyo_sost').id, 'amount': 500000.0})]})
        recibo.compute_sheet()
        self.assertAlmostEqual(self._total(recibo, 'CO_APOYO_SOST'), 500000.0, delta=0.01)
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_APOYO_SOST_PRAC'))
