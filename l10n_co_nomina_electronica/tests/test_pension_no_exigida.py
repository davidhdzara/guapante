# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-06 (QA sobre el aviso de afiliacion, decidido por el TL el 22-nov): la excepcion de AFP del parametro ``l10n_co_afiliaciones_no_exigidas`` (pensionado, aprendiz en etapa lectiva) hacia desaparecer el aviso
pero CO_PENSION_EMP (-60.000) y CO_PENSION_CIA (180.000) se seguian calculando, y confirmar fallaba con «paga a un tercero y falta AFP»: las reglas solo se omitian con la marca del extranjero. Ahora UNA funcion
(``HrEmployee._ne_entidad_exigida`` / ``HrPayslip._ne_no_cotiza_pension``) decide que la AFP no se exige Y que la pension del empleado, la de la empresa y el FSP no se calculan; quitar la fila del parametro vuelve
a calcularlas sin tocar codigo. El IBC de salud no cambia.

Valores a mano: sueldo 10.000.000 en marzo de 2026 (un mes: IBC 10.000.000; salud 4 % = 400.000, pension 4 % = 400.000, pension de la empresa 12 % = 1.200.000; el FSP aplica desde 4 SMMLV = 7.003.620)."""

from datetime import date

from odoo.tests.common import tagged

from . import test_validacion_afiliacion as base

PARAMETRO = 'l10n_co_nomina_electronica.rule_parameter_afiliaciones_no_exigidas_2025_08'      # el valor vigente desde el 1-ago-2025
REGLAS_DE_PENSION = ('CO_PENSION_EMP', 'CO_PENSION_CIA', 'CO_FSP', 'CO_LIQ_PENSION', 'CO_PRIMA_PENSION', 'CO_BON_PENSION')


@tagged('post_install', '-at_install')
class TestPensionNoExigida(base.TestValidacionAfiliacion):

    def _calculado(self, nombre, tipo='01', subtipo='00', desde=date(2026, 3, 1), hasta=date(2026, 3, 31), **entidades):
        empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, subtipo=subtipo, desde=desde, hasta=hasta, **entidades)
        recibo.contract_id.write({'wage': 10000000.0})
        recibo.contract_id.generate_work_entries(desde, hasta)
        self._config_retefuente(desde.year)
        recibo.compute_sheet()
        return empleado, recibo

    def _config_retefuente(self, anio):
        """CO_RETEFUENTE exige la configuracion de retencion del año de la compañia: sin ella el calculo se detiene (.167)."""
        if not self.env['l10n.co.retefuente.uvt'].search([('year', '=', str(anio)), ('company_id', '=', self.company.id)]):
            self.env['l10n.co.retefuente.uvt'].create({'year': str(anio), 'company_id': self.company.id, 'procedure': '1'})

    def _total(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def _sin_lineas_de_pension(self, recibo, mensaje=''):
        for codigo in ('CO_PENSION_EMP', 'CO_PENSION_CIA', 'CO_FSP'):
            self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == codigo), '%s %s' % (codigo, mensaje))

    # ── la excepcion llega a las reglas ──
    def test_el_pensionado_y_el_aprendiz_lectivo_no_calculan_pension_ni_fsp_pero_si_salud(self):
        # (nombre, tipo, subtipo, salud del empleado): la lectiva desde ago-2025 es el tipo 19, y desde H-F1-09 su salud (12,5 %) es COMPLETA de la empresa: sin descuento al aprendiz (Decreto 223/2026
        # art. 2.2.6.3.3.6 num. 1; doc 88). Los pensionados siguen descontando el 4 %.
        for nombre, tipo, subtipo, salud_empleado in (('Pensionado Dep', '01', '01', -400000.0), ('Pensionado Ind', '03', '02', -400000.0), ('Aprendiz Lectiva', '19', '00', 0.0)):
            _empleado, recibo = self._calculado(nombre, tipo=tipo, subtipo=subtipo, eps=self.eps, ccf=self.ccf)
            self._sin_lineas_de_pension(recibo, nombre)
            self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), salud_empleado, delta=0.01, msg=nombre)       # la EPS se sigue exigiendo; el pensionado paga su 4 % y la lectiva no
            ibc = recibo._rule_parameter('l10n_co_smmlv', recibo._ne_fecha_parametros()) if tipo == '19' else 10000000.0      # H-F1-09: el sueldo del aprendiz es su apoyo y cotiza sobre 1 SMMLV
            self.assertAlmostEqual(self._total(recibo, 'CO_IBC_SP'), ibc, delta=0.01, msg=nombre)         # la excepcion de la AFP no cambia el IBC
            self.assertFalse(recibo.l10n_co_ne_aviso_afiliacion, nombre)
            recibo._ne_validar_afiliaciones()                                                                    # confirma sin AFP

    def test_un_19_en_julio_de_2025_cotiza_pension_y_un_19_en_agosto_de_2025_no(self):
        """Condicion del TL: el 19 era la etapa productiva (con pension) hasta el 31-jul-2025 y es la lectiva (sin pension ni FSP) desde el 1-ago-2025; el IBC de salud no cambia."""
        _e1, julio = self._calculado('Diecinueve Julio', tipo='19', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2025, 7, 1), hasta=date(2025, 7, 31))
        _e2, agosto = self._calculado('Diecinueve Agosto', tipo='19', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2025, 8, 1), hasta=date(2025, 8, 31))
        smmlv = julio._rule_parameter('l10n_co_smmlv', julio._ne_fecha_parametros())      # H-F1-09: en julio de 2025 el 19 es un aprendiz en practica: cotiza sobre 1 SMMLV
        self.assertAlmostEqual(self._total(julio, 'CO_PENSION_EMP'), -smmlv * 0.04, delta=0.05)
        self.assertAlmostEqual(self._total(julio, 'CO_PENSION_CIA'), smmlv * 0.12, delta=0.05)
        self._sin_lineas_de_pension(agosto)
        self.assertAlmostEqual(self._total(julio, 'CO_IBC_SP'), self._total(agosto, 'CO_IBC_SP'), delta=0.01)

    def test_el_pensionado_sin_eps_sigue_sin_poder_confirmar(self):
        _empleado, recibo = self._calculado('Pensionado Sin EPS', tipo='01', subtipo='01', ccf=self.ccf)
        self._sin_lineas_de_pension(recibo)
        texto = self._error(lambda: recibo._ne_validar_afiliaciones())
        self.assertIn('EPS', texto)
        self.assertNotIn('AFP', texto)

    def test_un_empleado_normal_no_cambia(self):
        """Dependiente normal con AFP: pension del empleado -400.000, de la empresa 1.200.000 y FSP (10.000.000 >= 4 SMMLV) con valor."""
        _empleado, recibo = self._calculado('Normal', eps=self.eps, afp=self.afp, ccf=self.ccf)
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_EMP'), -400000.0, delta=0.01)
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_CIA'), 1200000.0, delta=0.01)
        self.assertTrue(self._total(recibo, 'CO_FSP'))
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), -400000.0, delta=0.01)

    def test_quitar_la_fila_del_parametro_vuelve_a_calcular_la_pension(self):
        """Sin la fila (19, *, afp) el aprendiz es un dependiente normal: la pension del empleado y de la empresa y el FSP se calculan y el aviso pide la AFP."""
        self.env.ref(PARAMETRO).parameter_value = "[('*', '01', 'afp'), ('*', '02', 'afp')]"
        _empleado, recibo = self._calculado('Aprendiz Sin Fila', tipo='19', subtipo='00', eps=self.eps, ccf=self.ccf)
        smmlv = recibo._rule_parameter('l10n_co_smmlv', recibo._ne_fecha_parametros())      # H-F1-09: aprendiz: cotiza sobre 1 SMMLV; el FSP empieza en 4 SMMLV
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_EMP'), -smmlv * 0.04, delta=0.05)
        self.assertAlmostEqual(self._total(recibo, 'CO_PENSION_CIA'), smmlv * 0.12, delta=0.05)
        self.assertFalse(self._total(recibo, 'CO_FSP'))
        self.assertIn('AFP', recibo.l10n_co_ne_aviso_afiliacion)

    def test_el_extranjero_no_obligado_sigue_sin_pension_y_ahora_tampoco_fsp(self):
        """La marca de la ficha sigue valiendo (misma funcion). Antes el FSP no miraba la marca: un extranjero no obligado a pension con IBC >= 4 SMMLV pagaba FSP; ahora no."""
        empleado, recibo = self._empleado_y_recibo('Extranjero', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2026, 3, 1), hasta=date(2026, 3, 31))
        empleado.l10n_co_ne_foreigner_no_pension = True
        recibo.contract_id.write({'wage': 10000000.0})
        recibo.contract_id.generate_work_entries(date(2026, 3, 1), date(2026, 3, 31))
        self._config_retefuente(2026)
        recibo.compute_sheet()
        self._sin_lineas_de_pension(recibo)

    def test_las_seis_reglas_llaman_a_la_funcion_y_no_a_una_lista_propia(self):
        """Una sola decision: ninguna condicion repite la lista ni mira la marca del extranjero por su cuenta."""
        reglas = self.env['hr.salary.rule'].with_context(active_test=False).search([('code', 'in', REGLAS_DE_PENSION)])      # CO_PRIMA_PENSION esta archivada desde .164 (la prima no cotiza pension)
        self.assertEqual(set(reglas.mapped('code')), set(REGLAS_DE_PENSION))
        for regla in reglas:
            self.assertIn('_ne_no_cotiza_pension', regla.condition_python, regla.code)
            self.assertNotIn('foreigner', regla.condition_python, regla.code)
