# -*- coding: utf-8 -*-
"""H-F1-06 (doc 87, aprobado por el TL el 22-nov): la afiliacion (EPS, AFP, Caja de Compensacion y ARL) del empleado se valida de forma EXPLICITA, sin depender de que las reglas tengan cuenta
contable: aviso en el recibo al calcular y ERROR al confirmar, con el empleado, TODOS los campos que faltan y donde completarlos. Las excepciones (pensionado y aprendiz en etapa lectiva: sin AFP)
salen del tipo y subtipo de cotizante del CONTRATO y de un parametro versionado (``l10n_co_afiliaciones_no_exigidas``), no de una lista en el codigo.
Antes (QA, ficticios GZ0-GZ3): un empleado sin afiliacion se confirmaba sin error si la regla no tenia cuenta, y el mensaje del asiento nombraba un solo campo y decia «Employee»."""

from datetime import date
from types import SimpleNamespace

from odoo.addons.l10n_co_nomina_electronica.models.hr_employee import (
    NE_EMPLEADO_GRUPO_AFILIACION, NE_EMPLEADO_PAGINA, NE_EMPLEADO_PESTANA)
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from lxml import etree


@tagged('post_install', '-at_install')
class TestValidacionAfiliacion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.eps = Partner.create({'name': 'EPS Afiliacion', 'l10n_co_entity_type': 'eps', 'l10n_co_pila_entity_code': 'EPS777'})
        cls.afp = Partner.create({'name': 'AFP Afiliacion', 'l10n_co_entity_type': 'afp', 'l10n_co_pila_entity_code': 'AFP777'})
        cls.ccf = Partner.create({'name': 'CCF Afiliacion', 'l10n_co_entity_type': 'ccf', 'l10n_co_pila_entity_code': 'CCF777'})
        cls.arl = Partner.create({'name': 'ARL Afiliacion', 'l10n_co_entity_type': 'arl', 'l10n_co_pila_entity_code': '14-77'})
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Afiliación',
            'l10n_co_pila_ccf_por_empleado': True, 'l10n_co_pila_arl_id': cls.arl.id})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Afiliación', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _empleado_y_recibo(self, nombre, tipo='01', subtipo='00', eps=None, afp=None, ccf=None, desde=date(2026, 3, 1), hasta=date(2026, 3, 15), tipo_contrato='2'):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10',
            'l10n_co_pila_eps_id': eps.id if eps else False, 'l10n_co_pila_afp_id': afp.id if afp else False, 'l10n_co_pila_ccf_id': ccf.id if ccf else False})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': tipo_contrato, 'l10n_co_pila_tipo_cotizante': tipo, 'l10n_co_pila_subtipo_cotizante': subtipo, 'name': 'Contrato %s' % nombre,
            'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % nombre, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': desde, 'date_to': hasta})
        return empleado, recibo

    # ── el aviso y el error nombran al empleado y TODO lo que falta, y dicen donde completarlo ─────────────────────────────────────────────
    def test_sin_eps_afp_ni_caja_el_aviso_y_el_error_nombran_todo_y_dicen_donde_completar(self):
        _empleado, recibo = self._empleado_y_recibo('Sin Afiliacion Uno')
        for texto in (recibo.l10n_co_ne_aviso_afiliacion, self._error(lambda: recibo._ne_validar_afiliaciones())):
            for esperado in ('Sin Afiliacion Uno', 'EPS', 'AFP', 'Caja de Compensación', 'pestaña %s' % NE_EMPLEADO_PESTANA, str(NE_EMPLEADO_GRUPO_AFILIACION)):
                self.assertIn(esperado, texto)
            self.assertNotIn('Employee', texto)

    def test_el_caso_de_qa_sin_cuenta_en_la_regla_y_sin_afiliacion_ahora_no_se_confirma(self):
        """Antes se confirmaba sin error cuando la regla no tenia cuenta contable (la exigencia era un efecto colateral del asiento)."""
        _empleado, recibo = self._empleado_y_recibo('Sin Afiliacion Dos')
        self.assertFalse(recibo.struct_id.rule_ids.filtered(lambda r: r.account_debit or r.account_credit), 'Premisa: las reglas de la estructura no tienen cuenta')
        with self.assertRaisesRegex(UserError, 'Afiliación incompleta'):
            recibo.action_payslip_done()

    def test_el_empleado_completo_no_tiene_aviso_ni_error(self):
        _empleado, recibo = self._empleado_y_recibo('Completo', eps=self.eps, afp=self.afp, ccf=self.ccf)
        self.assertFalse(recibo.l10n_co_ne_aviso_afiliacion)
        recibo._ne_validar_afiliaciones()

    # ── excepciones desde los datos del contrato y el parametro ───────────────────────────────────────────────────────────────────────────
    def test_el_pensionado_y_el_aprendiz_en_etapa_lectiva_no_exigen_afp_pero_si_eps(self):
        for nombre, tipo, subtipo in (('Pensionado', '01', '01'), ('Pensionado Independiente', '03', '02'), ('Aprendiz Lectiva', '19', '00')):      # desde el 1-ago-2025 la lectiva se reporta con el tipo 19 (Concepto MinSalud 2025310001925691)
            _empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, subtipo=subtipo, ccf=self.ccf)
            texto = recibo.l10n_co_ne_aviso_afiliacion
            self.assertIn('EPS', texto, nombre)
            self.assertNotIn('AFP', texto, nombre)

    def test_el_aprendiz_en_etapa_practica_si_exige_afp(self):
        """Ley 2466/2025 art. 21: en la fase practica el aprendiz esta afiliado a pensiones y salud como dependiente. Desde el 1-ago-2025 se reporta con el tipo 01 (dependiente) y el contrato «4 - Aprendizaje»."""
        _empleado, recibo = self._empleado_y_recibo('Aprendiz Practica', tipo='01', tipo_contrato='4', ccf=self.ccf)
        self.assertIn('AFP', recibo.l10n_co_ne_aviso_afiliacion)

    def test_el_tipo_19_exige_afp_en_julio_de_2025_y_no_desde_agosto_de_2025(self):
        """El tipo 19 era la etapa PRODUCTIVA (con pension) hasta el 31-jul-2025 y es la LECTIVA (sin pension) desde el 1-ago-2025; el 12, al reves: exceptuado hasta jul-2025 y restringido despues
        (Concepto MinSalud 2025310001925691 del 22-jul-2025). Todo por la vigencia del parametro."""
        casos = (('Tipo 19 julio', '19', date(2025, 7, 1), date(2025, 7, 31), True), ('Tipo 19 agosto', '19', date(2025, 8, 1), date(2025, 8, 31), False),
                 ('Tipo 12 julio', '12', date(2025, 7, 1), date(2025, 7, 31), False), ('Tipo 12 agosto', '12', date(2025, 8, 1), date(2025, 8, 31), True))
        for nombre, tipo, desde, hasta, exige in casos:
            _empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, eps=self.eps, ccf=self.ccf, desde=desde, hasta=hasta)
            self.assertEqual('AFP' in recibo.l10n_co_ne_aviso_afiliacion, exige, nombre)

    def test_cambiar_la_vigencia_del_parametro_cambia_el_resultado_sin_tocar_codigo(self):
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_afiliaciones_no_exigidas')
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'parameter_value': '[]', 'date_from': date(2026, 4, 1)})
        _e1, antes = self._empleado_y_recibo('Pensionado Marzo', subtipo='01', eps=self.eps, ccf=self.ccf, desde=date(2026, 3, 1), hasta=date(2026, 3, 15))
        _e2, despues = self._empleado_y_recibo('Pensionado Abril', subtipo='01', eps=self.eps, ccf=self.ccf, desde=date(2026, 4, 1), hasta=date(2026, 4, 15))
        self.assertFalse(antes.l10n_co_ne_aviso_afiliacion, 'Hasta el 31-mar el pensionado sigue exceptuado de la AFP')
        self.assertIn('AFP', despues.l10n_co_ne_aviso_afiliacion, 'Desde el 1-abr (parametro vacio) la AFP se exige')

    def test_sin_el_parametro_el_error_dice_cual_falta(self):
        self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_afiliaciones_no_exigidas')]).unlink()
        _empleado, recibo = self._empleado_y_recibo('Sin Parametro')
        self.assertIn('l10n_co_afiliaciones_no_exigidas', recibo.l10n_co_ne_aviso_afiliacion)
        with self.assertRaisesRegex(UserError, 'l10n_co_afiliaciones_no_exigidas'):
            recibo._ne_validar_afiliaciones()

    # ── la Caja: del empleado o general ───────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_con_caja_general_se_exige_la_de_la_compania_y_el_mensaje_dice_donde(self):
        self.company.l10n_co_pila_ccf_por_empleado = False
        self.company.l10n_co_pila_ccf_id = False
        _empleado, recibo = self._empleado_y_recibo('Caja General', eps=self.eps, afp=self.afp)
        texto = recibo.l10n_co_ne_aviso_afiliacion
        self.assertIn('Caja de Compensación general de la empresa', texto)
        self.assertIn('Nómina > Configuración > Ajustes, bloque PILA', texto)
        self.company.l10n_co_pila_ccf_id = self.ccf
        recibo.invalidate_recordset()
        self.assertFalse(recibo.l10n_co_ne_aviso_afiliacion)

    def test_sin_arl_de_la_compania_falta_la_arl(self):
        self.company.l10n_co_pila_arl_id = False
        _empleado, recibo = self._empleado_y_recibo('Sin ARL', eps=self.eps, afp=self.afp, ccf=self.ccf)
        self.assertIn('ARL', recibo.l10n_co_ne_aviso_afiliacion)
        self.company.l10n_co_pila_arl_id = self.arl

    # ── lotes, habilitacion y otros paises ───────────────────────────────────────────────────────────────────────────────────────────────────
    def test_un_lote_da_un_solo_error_con_una_linea_por_empleado(self):
        _e1, uno = self._empleado_y_recibo('Lote Uno')
        _e2, dos = self._empleado_y_recibo('Lote Dos', eps=self.eps)
        texto = self._error(lambda: (uno | dos)._ne_validar_afiliaciones())
        self.assertIn('Lote Uno: falta', texto)
        self.assertIn('Lote Dos: falta', texto)
        self.assertEqual(texto.count('Afiliación incompleta'), 1)
        self.assertNotIn('EPS', [linea for linea in texto.split('\n') if linea.startswith('Lote Dos')][0])

    def test_los_empleados_de_prueba_de_la_habilitacion_y_las_companias_de_otro_pais_no_se_validan(self):
        empleado, recibo = self._empleado_y_recibo('Sintetico')
        empleado.l10n_co_ne_is_habilitacion_test = True
        self.assertFalse(empleado._ne_afiliaciones_faltantes(recibo.contract_id, recibo.date_from))
        self.assertFalse(recibo.l10n_co_ne_aviso_afiliacion)
        recibo._ne_validar_afiliaciones()
        mx = self.env['res.company'].create({'country_id': self.env.ref('base.mx').id, 'name': 'Empresa MX Afiliación'})
        recibo_mx = self.env['hr.payslip'].new({'company_id': mx.id, 'employee_id': empleado.id, 'contract_id': recibo.contract_id.id})
        self.assertFalse(recibo_mx._ne_solo_colombia())

    # ── el mensaje del asiento ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_el_asiento_dice_empleado_y_todos_los_campos_no_employee(self):
        _empleado, recibo = self._empleado_y_recibo('Asiento Sin Afiliacion')
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_SALUD_EMP'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        self.assertEqual(regla.l10n_co_tercero_origen, 'employee_eps', 'Premisa: la salud del empleado paga a la EPS')
        linea = SimpleNamespace(salary_rule_id=regla, code='CO_SALUD_EMP', name='Salud')
        texto = self._error(lambda: recibo._ne_repartos_tercero(linea))
        for esperado in ('Asiento Sin Afiliacion', 'EPS', 'AFP', 'Caja de Compensación', str(NE_EMPLEADO_GRUPO_AFILIACION)):
            self.assertIn(esperado, texto)
        self.assertNotIn('Employee', texto)

    def test_el_mensaje_de_los_terceros_del_contrato_dice_empleado_y_su_nombre(self):
        _empleado, recibo = self._empleado_y_recibo('Tercero Contrato', eps=self.eps, afp=self.afp, ccf=self.ccf)
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_SINDICATO'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        self.assertEqual(regla.l10n_co_tercero_origen, 'contract_sindicato', 'Premisa: el sindicato paga a un tercero del contrato')
        texto = self._error(lambda: recibo._ne_repartos_tercero(SimpleNamespace(salary_rule_id=regla, code='CO_SINDICATO', name='Cuota Sindical')))
        self.assertIn('el contrato del empleado "Tercero Contrato"', texto)
        self.assertNotIn('Contract', texto)

    # ── rastro y ubicacion de los campos ────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_las_tres_afiliaciones_del_empleado_tienen_rastro(self):
        """``tracking=True`` en EPS, AFP y Caja: el chatter NATIVO del empleado deja quien cambio cual y cuando. Se prueba el atributo del campo (el motor de rastro es de Odoo; el caso de
        pruebas lo apaga por defecto y la nota se escribe al cierre de la transaccion)."""
        for campo in ('l10n_co_pila_eps_id', 'l10n_co_pila_afp_id', 'l10n_co_pila_ccf_id'):
            self.assertTrue(self.env['hr.employee']._fields[campo].tracking, campo)

    def test_la_vista_del_empleado_usa_las_mismas_constantes_que_el_mensaje(self):
        """Una sola fuente del lugar: la pagina del xpath y el grupo de la vista son los de las constantes del mensaje."""
        arch = etree.fromstring(self.env['hr.employee'].get_view(view_type='form')['arch'].encode('utf-8'))
        self.assertTrue(arch.xpath("//page[@name='%s']" % NE_EMPLEADO_PAGINA), 'La pagina nativa de Nómina existe con el nombre de la constante')
        grupo = arch.xpath("//page[@name='%s']//group[@name='pila_administradoras']" % NE_EMPLEADO_PAGINA)
        self.assertEqual(len(grupo), 1)
        self.assertEqual(grupo[0].get('string'), str(NE_EMPLEADO_GRUPO_AFILIACION))
        self.assertTrue(grupo[0].xpath(".//field[@name='l10n_co_pila_eps_id']"))

    def _error(self, funcion):
        with self.assertRaises(UserError) as contexto:
            funcion()
        return str(contexto.exception)
