# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-09 (doc 88; decisiones del TL del 22-nov): el aprendiz tiene un regimen propio que sale de UN metodo, ``HrPayslip._ne_regimen_cotizante``, y de una tabla versionada por fecha (parametro
``l10n_co_aprendiz_etapas``: tipo de cotizante, tipo de contrato, etapa, TipoTrabajador de la DIAN y si paga auxilio de transporte). Esquema PROVISIONAL «mientras el Ministerio de Salud expide el acto administrativo» (Concepto MinSalud
2025310001925691 y Circular MinTrabajo 083 del 18-jul-2025): hasta el 31-jul-2025 el 12 era la lectiva y el 19 la productiva; desde el 1-ago-2025 la lectiva es el tipo 19 y la practica o dual es el tipo 01 con el contrato
«4 - Aprendizaje»; el 12 se restringe."""

from datetime import date, timedelta

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
        self.assertEqual(regimen, {'etapa': False, 'tipo_trabajador': False, 'paga_auxilio_transporte': True})      # la regla general del auxilio (con su tope) decide

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
            'parameter_value': "[('19', '*', 'lectiva', '12', False), ('01', '4', 'practica', '19', True), ('01', '2', 'practica', '19', True)]"})
        self.assertFalse(self._regimen('Marzo', '01', '2', date(2026, 3, 1), date(2026, 3, 31))['etapa'])
        self.assertEqual(self._regimen('Abril', '01', '2', date(2026, 4, 1), date(2026, 4, 30))['etapa'], 'practica')

    def test_la_tabla_dice_si_la_etapa_paga_auxilio_de_transporte(self):
        """Circular MinTrabajo 083 de 2025, num. 4, Cuadro 1 (decision A del TL, 23-nov): la lectiva no paga auxilio de transporte; la practica y la formacion dual (tipo 01 con contrato «4») si; el que no es
        aprendiz sigue con la regla general (con su tope). Tambien en el esquema anterior al 1-ago-2025 (tipos 12 y 19)."""
        casos = (
            ('19 lectiva 2026', '19', '4', date(2026, 3, 1), date(2026, 3, 31), False),
            ('01 practica o dual 2026', '01', '4', date(2026, 3, 1), date(2026, 3, 31), True),
            ('01 dependiente 2026', '01', '2', date(2026, 3, 1), date(2026, 3, 31), True),
            ('12 lectiva julio 2025', '12', '2', date(2025, 7, 1), date(2025, 7, 31), False),
            ('19 productiva julio 2025', '19', '2', date(2025, 7, 1), date(2025, 7, 31), True),
        )
        for nombre, tipo, tipo_contrato, desde, hasta, paga in casos:
            self.assertIs(self._regimen(nombre, tipo, tipo_contrato, desde, hasta)['paga_auxilio_transporte'], paga, nombre)

    def test_el_auxilio_de_la_lectiva_se_cambia_con_un_valor_nuevo_sin_tocar_codigo(self):
        """Un caso que necesite otra cosa (por ejemplo, una formacion dual reportada con el tipo 19) cambia la columna con un valor nuevo y su fecha: el codigo no mira el tipo de cotizante."""
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_aprendiz_etapas')
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parametro.id, 'date_from': date(2026, 4, 1), 'parameter_value': "[('19', '*', 'lectiva', '12', True), ('01', '4', 'practica', '19', True)]"})
        self.assertFalse(self._regimen('Lectiva marzo', '19', '4', date(2026, 3, 1), date(2026, 3, 31))['paga_auxilio_transporte'])
        self.assertTrue(self._regimen('Lectiva abril', '19', '4', date(2026, 4, 1), date(2026, 4, 30))['paga_auxilio_transporte'])

    def test_una_fila_sin_la_columna_del_auxilio_da_un_error_que_nombra_el_parametro(self):
        """Sin valor por defecto: una fila de cuatro columnas (el formato anterior) no se interpreta como «sin auxilio»."""
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_aprendiz_etapas')
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parametro.id, 'date_from': date(2026, 4, 1), 'parameter_value': "[('19', '*', 'lectiva', '12'), ('01', '4', 'practica', '19')]"})
        with self.assertRaisesRegex(UserError, 'l10n_co_aprendiz_etapas'):
            self._regimen('Fila vieja', '19', '4', date(2026, 4, 1), date(2026, 4, 30))


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

    # ── el consolidado del mes con dos etapas (consultor v19 §11.13 punto 3; decision del TL del 22-nov, opcion a) ──
    def _segundo_recibo(self, primero, tipo, factor_apoyo, desde, hasta):
        """Otrosi de cambio de etapa dentro del mes: el contrato del primer recibo termina el dia anterior y empieza otro del MISMO empleado, de aprendizaje, con otro tipo de cotizante, y su recibo."""
        primero.contract_id.write({'date_end': desde - timedelta(days=1)})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato 2 %s' % primero.employee_id.name, 'employee_id': primero.employee_id.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'l10n_co_ne_contract_type': '4', 'l10n_co_pila_tipo_cotizante': tipo, 'l10n_co_pila_subtipo_cotizante': '00', 'wage': 0.0, 'date_start': desde, 'state': 'open'})
        contrato.generate_work_entries(desde, hasta)
        smmlv = primero._rule_parameter('l10n_co_smmlv', primero._ne_fecha_parametros())
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo 2 %s' % primero.employee_id.name, 'employee_id': primero.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': desde, 'date_to': hasta,
            'input_line_ids': [(0, 0, {'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_apoyo_sost').id, 'amount': factor_apoyo * smmlv})]})
        recibo.compute_sheet()
        return recibo

    def test_un_mes_con_lectiva_y_practica_aplica_el_piso_solo_a_los_dias_del_recibo_de_la_practica(self):
        """Un recibo de lectiva (1 al 15 de marzo) y otro de practica (16 al 31), en los dos ordenes. Antes el piso de la practica salia de ``slips[-1]`` y de la SUMA de los dias del mes: con la practica
        ultima daba 1 SMMLV (los 30 dias, aunque la lectiva no paga parafiscales) y con la lectiva ultima daba 0: el consolidado no cuadraba con la suma de las lineas CO_IBC_PARAF de los recibos.
        Ahora es recibo por recibo: 15 dias de practica = medio SMMLV, igual a la suma de las lineas, con diferencia 0."""
        for nombre, primero, segundo in (
                ('Lectiva y Practica', ('19', 0.75), ('01', 1.0)),
                ('Practica y Lectiva', ('01', 1.0), ('19', 0.75))):
            with self.subTest(nombre):
                uno, smmlv = self._aprendiz(nombre, primero[0], '4', primero[1], desde=date(2026, 3, 1), hasta=date(2026, 3, 15))
                dos = self._segundo_recibo(uno, segundo[0], segundo[1], date(2026, 3, 16), date(2026, 3, 31))
                (uno | dos).write({'state': 'done'})
                practica = dos if segundo[0] == '01' else uno
                lectiva = uno if segundo[0] == '01' else dos
                self.assertAlmostEqual(self._total(practica, 'CO_IBC_PARAF'), smmlv / 2, delta=0.01)
                self.assertFalse(self._total(lectiva, 'CO_IBC_PARAF'), 'La lectiva no paga parafiscales: sin piso')
                consolidado = self.env['l10n.co.ibc.mensual']._refrescar(self.company, uno.employee_id, date(2026, 3, 1))
                self.assertAlmostEqual(consolidado.ibc_recibos_paraf, smmlv / 2, delta=0.01)
                self.assertAlmostEqual(consolidado.ibc_paraf, smmlv / 2, delta=0.01)
                self.assertAlmostEqual(consolidado.diferencia_paraf, 0.0, delta=0.01)
                self.assertEqual(consolidado.dias_paraf, 30)

    def test_el_consolidado_de_un_empleado_normal_con_dos_recibos_no_cambia(self):
        """Sin aprendiz no hay piso en parafiscales: la base del mes es la suma de lo salarial de los recibos, como siempre."""
        empleado, uno = self._empleado_y_recibo('Normal Dos Recibos', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2026, 3, 1), hasta=date(2026, 3, 15))
        uno.contract_id.write({'wage': 10000000.0})
        uno.contract_id.generate_work_entries(date(2026, 3, 1), date(2026, 3, 31))
        self._config_retefuente(2026)
        uno.compute_sheet()
        dos = self.env['hr.payslip'].create({
            'name': 'Recibo 2 Normal', 'employee_id': empleado.id, 'contract_id': uno.contract_id.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2026, 3, 16), 'date_to': date(2026, 3, 31)})
        dos.compute_sheet()
        (uno | dos).write({'state': 'done'})
        salarial = self._total(uno, 'CO_IBC_SALARIAL') + self._total(dos, 'CO_IBC_SALARIAL')
        self.assertTrue(salarial)
        consolidado = self.env['l10n.co.ibc.mensual']._refrescar(self.company, empleado, date(2026, 3, 1))
        self.assertAlmostEqual(consolidado.ibc_paraf, salarial, delta=0.01)
        self.assertAlmostEqual(consolidado.diferencia_paraf, 0.0, delta=0.01)

    # ── el apoyo de sostenimiento: dos reglas por etapa ──
    def test_lectiva_el_apoyo_es_no_salarial_y_la_regla_de_la_practica_no_sale(self):
        recibo, smmlv = self._aprendiz('Lectiva Apoyo', '19', '4', 0.75)
        self.assertAlmostEqual(self._total(recibo, 'CO_APOYO_SOST'), 0.75 * smmlv, delta=0.01)             # 75 % de 1 SMMLV (Decreto 223/2026 art. 2.2.6.3.3.4)
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_APOYO_SOST_PRAC'))
        self.assertFalse(self._total(recibo, 'CO_IBC_SALARIAL'), 'No salarial: no entra al IBC salarial')
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_PROV_PRIMA' and l.total), 'La lectiva no tiene prestaciones: el apoyo no es base de la provision')

    def test_el_auxilio_de_transporte_sale_en_la_practica_y_no_en_la_lectiva(self):
        """Decision A del TL (23-nov; Circular MinTrabajo 083 de 2025, num. 4, Cuadro 1). El aprendiz se modela con sueldo de contrato 0 (queda bajo el tope), asi que antes recibia el auxilio tambien en la lectiva
        y la provision de prima y cesantias lo sumaba (N2 «db»: ``CO_PROV_PRIMA`` con total en la lectiva). Ahora la lectiva no tiene la linea ni las provisiones; la practica si, con el valor de siempre."""
        lectiva, _smmlv = self._aprendiz('Lectiva Auxilio', '19', '4', 0.75)
        self.assertFalse(lectiva.line_ids.filtered(lambda l: l.code == 'CO_AUX_TRANS' and l.total), 'La lectiva no paga auxilio de transporte')
        for codigo in ('CO_PROV_PRIMA', 'CO_PROV_CESANTIAS'):
            self.assertFalse(self._total(lectiva, codigo), '%s: sin auxilio ni sueldo no hay base de provision en la lectiva' % codigo)
        practica, _smmlv = self._aprendiz('Practica Auxilio', '01', '4', 1.0)
        linea = practica.line_ids.filtered(lambda l: l.code == 'CO_AUX_TRANS')
        self.assertTrue(linea.total, 'La practica y la formacion dual si reciben el auxilio')
        auxilio = practica._rule_parameter('l10n_co_aux_transporte', practica._ne_fecha_parametros())
        dias_mes = practica._rule_parameter('l10n_co_dias_mes_comercial', practica._ne_fecha_parametros())
        self.assertAlmostEqual(linea.total, auxilio / dias_mes * linea.quantity, delta=0.05)

    def test_el_dependiente_normal_sigue_recibiendo_el_auxilio_de_transporte(self):
        _empleado, recibo = self._empleado_y_recibo('Normal Auxilio', tipo='01', tipo_contrato='2', eps=self.eps, afp=self.afp, ccf=self.ccf, desde=date(2026, 3, 1), hasta=date(2026, 3, 31))
        recibo.contract_id.write({'wage': 1800000.0})
        recibo.contract_id.generate_work_entries(date(2026, 3, 1), date(2026, 3, 31))
        self._config_retefuente(2026)
        recibo.compute_sheet()
        self.assertTrue(self._total(recibo, 'CO_AUX_TRANS'), 'Un dependiente normal bajo el tope sigue con su auxilio')

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

    # ── TipoTrabajador del XML y la fusion mensual ──
    def _lugar_de_trabajo_completo(self):
        """``_ne_trabajador()`` exige pais, departamento y municipio en la Direccion de Trabajo del empleado (H-018; por defecto la de la compañia): sin ellos da un UserError que no es lo que se prueba aqui
        (N2 «db» del 23-nov). Mismo arreglo que ``test_tipo_documento_dian`` y ``test_ausencias_nomina``."""
        pais = self.env.ref('base.co')
        departamento = self.env['res.country.state'].search([('country_id', '=', pais.id)], limit=1) or self.env['res.country.state'].create({
            'name': 'Departamento Prueba Aprendiz', 'code': 'PA', 'country_id': pais.id})
        ciudad = self.env['res.city'].create({'name': 'Ciudad Prueba Aprendiz', 'state_id': departamento.id, 'country_id': pais.id})
        self.company.partner_id.write({'country_id': pais.id, 'state_id': departamento.id, 'city_id': ciudad.id, 'street': 'Calle Prueba Aprendiz # 1-1'})

    def test_el_tipo_de_trabajador_del_aprendiz_sale_del_contrato_y_el_de_los_demas_de_la_ficha(self):
        self._lugar_de_trabajo_completo()
        empleado_1, lectiva = self._empleado_y_recibo('TT Lectiva', tipo='19', tipo_contrato='4', eps=self.eps, ccf=self.ccf)
        empleado_2, practica = self._empleado_y_recibo('TT Practica', tipo='01', tipo_contrato='4', eps=self.eps, afp=self.afp, ccf=self.ccf)
        empleado_3, normal = self._empleado_y_recibo('TT Normal', tipo='01', tipo_contrato='2', eps=self.eps, afp=self.afp, ccf=self.ccf)
        for empleado in (empleado_1, empleado_2, empleado_3):
            empleado.l10n_co_ne_identification_type_id = self.env.ref('l10n_co.national_citizen_id')      # _ne_tipo_documento() exige un tipo con equivalente DIAN
        self.assertEqual(lectiva._ne_trabajador()['TipoTrabajador'], '12')                    # la ficha dice 01
        self.assertEqual(practica._ne_trabajador()['TipoTrabajador'], '19')
        self.assertEqual(normal._ne_trabajador()['TipoTrabajador'], '01')                     # la ficha, como siempre

    def test_aviso_si_la_ficha_del_aprendiz_dice_otro_tipo_y_nada_si_coincide(self):
        empleado, recibo = self._empleado_y_recibo('Aviso TT', tipo='19', tipo_contrato='4', eps=self.eps, ccf=self.ccf)
        self.assertIn('Aviso TT', recibo.l10n_co_ne_aviso_tipo_trabajador)
        self.assertIn('12 - Aprendiz del SENA en Etapa Lectiva', recibo.l10n_co_ne_aviso_tipo_trabajador)
        self.assertIn('01 - Trabajador Dependiente', recibo.l10n_co_ne_aviso_tipo_trabajador)
        empleado.l10n_co_ne_worker_type = '12'
        self.assertFalse(recibo.l10n_co_ne_aviso_tipo_trabajador)
        _e, normal = self._empleado_y_recibo('Normal TT', tipo='01', tipo_contrato='2', eps=self.eps, afp=self.afp, ccf=self.ccf)
        self.assertFalse(normal.l10n_co_ne_aviso_tipo_trabajador)

    def test_la_fusion_del_mes_con_cambio_de_etapa_da_un_error_que_nombra_al_empleado_y_los_dos_tipos(self):
        """Un aprendiz que pasa de la lectiva (12) a la practica (19) dentro del mes: el documento mensual exige un solo TipoTrabajador. Prueba obligatoria del TL (cuidado 3 del consultor)."""
        from odoo.addons.l10n_co_nomina_electronica.services import documento_merge as fusion
        from .test_documento_merge import PERIODO, _recibo as recibo_base

        def recibo(tipo):
            datos = recibo_base()
            datos['trabajador'] = dict(datos['trabajador'], TipoTrabajador=tipo, PrimerNombre='Ana', PrimerApellido='Aprendiz')
            return datos
        fechas = ['2026-03-15', '2026-03-31']
        with self.assertRaises(fusion.ErrorFusion) as exc:
            fusion.fusionar_documento([recibo('12'), recibo('19')], fechas, PERIODO)
        texto = str(exc.exception)
        for esperado in ('Ana Aprendiz', '1020304050', '12', '19', 'TipoTrabajador'):
            self.assertIn(esperado, texto)
        fusion.fusionar_documento([recibo('12'), recibo('12')], fechas, PERIODO)           # el mismo tipo si se fusiona
