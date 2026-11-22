# -*- coding: utf-8 -*-
"""Pieza .301 (doc 76 §2.2, decisión del TL del 22-nov): aviso de HABITUALIDAD de los pagos no salariales. NO EJECUTADAS en Odoo al escribirlas; necesitan ``-u`` para el
campo ``l10n_co_ne_vigilar_habitualidad`` (la siembra del XML) y el parámetro ``l10n_co_no_salarial_meses_habitualidad``: en una N1 sin ``-u`` fallan por diseño las que
leen la siembra o la vista, y las del parámetro lo crean dentro de su transacción.

Qué se prueba:
- Un concepto no salarial VIGILADO (campo plano de la regla, sembrado en True solo en AUX_ALIM, BONIF_NOSAL, BONIF_RET y VIATICOS_NOSAL) avisa cuando se pagó en cada uno de
  los últimos N MESES CALENDARIO, contando el mes del recibo (mes = el de ``date_to``). Cuenta en un mes si está en CUALQUIER recibo de ese mes (quincenal o mensual).
- Los meses anteriores y los otros recibos del mes cuentan solo hechos o pagados; el recibo que se mira cuenta en el estado en que esté. Un hueco corta la racha.
- N sale de un parámetro (3 de fábrica; 0 apaga el aviso); si falta, el aviso lo dice (no se asume un valor).
- Solo es un aviso: ``compute_sheet`` no lo calcula. Solo ``base.group_system`` marca o desmarca el campo (modelo y vista)."""

from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_CODIGO = 'l10n_co_no_salarial_meses_habitualidad'
_G_MANAGER = 'hr_payroll.group_hr_payroll_manager'
_VIGILADOS = {'CO_AUX_ALIM', 'CO_BONIF_NOSAL', 'CO_BONIF_RET', 'CO_VIATICOS_NOSAL'}


@tagged('post_install', '-at_install')
class TestHabitualidadNoSalarial(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Habitualidad'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Habitualidad', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.tipo_bonif = cls.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.n = 0

    def setUp(self):
        super().setUp()
        self._meses(3)

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _meses(self, valor):
        """Fija N (en la N1 sin ``-u`` la base aún no trae el parámetro del XML: se crea dentro de la transacción de la prueba)."""
        Parametro = self.env['hr.rule.parameter']
        parametro = Parametro.search([('code', '=', _CODIGO)], limit=1) or Parametro.create({
            'name': 'Colombia: Meses de Habitualidad de Pagos No Salariales', 'code': _CODIGO, 'country_id': self.env.ref('base.co').id})
        if parametro.parameter_version_ids:
            parametro.parameter_version_ids.write({'parameter_value': str(valor)})
        else:
            self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'parameter_value': str(valor), 'date_from': date(2020, 1, 1)})

    def _empleado(self, nombre=None):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre or 'Empleado Habitualidad %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Habitualidad %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return empleado, contrato

    def _recibo(self, empleado, contrato, desde, hasta, bonificacion=0.0, estado=None):
        """Recibo calculado del periodo; con ``bonificacion`` lleva una novedad de bonificación no salarial (CO_BONIF_NOSAL, vigilada); ``estado`` lo deja hecho."""
        type(self).n += 1
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Habitualidad %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.general.id, 'date_from': desde, 'date_to': hasta})
        if bonificacion:
            self.env['hr.payslip.input'].with_context(ne_sin_recalculo_hoja=True).create({
                'payslip_id': recibo.id, 'input_type_id': self.tipo_bonif.id, 'amount': bonificacion, 'name': 'Bonificación %s' % self.n})
        recibo.compute_sheet()
        if estado:
            recibo.write({'state': estado})
        return recibo

    def _aviso(self, recibo):
        recibo.invalidate_recordset(['l10n_co_ne_aviso_no_salarial'])
        return recibo.l10n_co_ne_aviso_no_salarial

    def _septiembre_octubre(self, empleado, contrato, estado='done', con_bonificacion=(True, True)):
        """Septiembre y octubre de 2026 hechos; ``con_bonificacion`` dice si cada uno trae la bonificación."""
        return (
            self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30), 80000.0 if con_bonificacion[0] else 0.0, estado),
            self._recibo(empleado, contrato, date(2026, 10, 1), date(2026, 10, 31), 80000.0 if con_bonificacion[1] else 0.0, estado))

    # ── el aviso ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_01_pagado_en_los_tres_meses_incluido_el_del_recibo_avisa_con_concepto_empleado_y_meses(self):
        empleado, contrato = self._empleado('Ana Habitual')
        self._septiembre_octubre(empleado, contrato)
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        aviso = self._aviso(noviembre)
        self.assertTrue(aviso, 'Septiembre, octubre y noviembre: tres meses seguidos')
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL')], limit=1)
        self.assertIn(regla.name, aviso)
        self.assertIn('Ana Habitual', aviso)
        self.assertIn('3 meses', aviso)
        self.assertIn('2026', aviso)
        self.assertIn('art. 127 CST', aviso)

    def test_02_con_un_mes_menos_no_avisa(self):
        empleado, contrato = self._empleado()
        self._recibo(empleado, contrato, date(2026, 10, 1), date(2026, 10, 31), 80000.0, 'done')
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.assertFalse(self._aviso(noviembre), 'Solo dos meses: octubre y noviembre')

    def test_03_un_mes_sin_el_concepto_corta_la_racha(self):
        empleado, contrato = self._empleado()
        self._septiembre_octubre(empleado, contrato, con_bonificacion=(True, False))
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.assertFalse(self._aviso(noviembre), 'Octubre sin el concepto: hay hueco')

    def test_04_el_recibo_del_mes_actual_tiene_que_traer_el_concepto(self):
        empleado, contrato = self._empleado()
        self._septiembre_octubre(empleado, contrato)
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30))
        self.assertFalse(self._aviso(noviembre), 'Sin el concepto en este recibo no hay nada que vigilar')

    def test_05_dos_quincenas_de_un_mes_cuentan_como_un_solo_mes(self):
        empleado, contrato = self._empleado()
        self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 15), 80000.0, 'done')
        self._recibo(empleado, contrato, date(2026, 9, 16), date(2026, 9, 30), 80000.0, 'done')
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 15), 80000.0)
        self.assertFalse(self._aviso(noviembre), 'Septiembre (dos quincenas) y noviembre: octubre falta')
        octubre = self._recibo(empleado, contrato, date(2026, 10, 16), date(2026, 10, 31), 80000.0, 'done')
        self.assertTrue(octubre.exists())
        self.assertTrue(self._aviso(noviembre), 'Con una quincena de octubre ya son tres meses: da igual quincenal o mensual')

    def test_06_un_recibo_anterior_en_borrador_no_cuenta_ni_el_de_otro_empleado(self):
        empleado, contrato = self._empleado()
        self._recibo(empleado, contrato, date(2026, 9, 1), date(2026, 9, 30), 80000.0, 'done')
        self._recibo(empleado, contrato, date(2026, 10, 1), date(2026, 10, 31), 80000.0)          # octubre en borrador
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.assertFalse(self._aviso(noviembre), 'El borrador de octubre no cuenta')
        otro, contrato_otro = self._empleado()
        self._septiembre_octubre(otro, contrato_otro)
        self.assertFalse(self._aviso(noviembre), 'Los pagos de otro empleado no cuentan')
        # un mes que ya se pagó pero fuera de la ventana: agosto no completa septiembre-octubre-noviembre
        self._recibo(empleado, contrato, date(2026, 8, 1), date(2026, 8, 31), 80000.0, 'done')
        self.assertFalse(self._aviso(noviembre))

    def test_07_la_ventana_cruza_el_ano(self):
        empleado, contrato = self._empleado()
        self._recibo(empleado, contrato, date(2025, 12, 1), date(2025, 12, 31), 80000.0, 'done')
        self._recibo(empleado, contrato, date(2026, 1, 1), date(2026, 1, 31), 80000.0, 'done')
        febrero = self._recibo(empleado, contrato, date(2026, 2, 1), date(2026, 2, 28), 80000.0)
        aviso = self._aviso(febrero)
        self.assertTrue(aviso, 'Diciembre, enero y febrero')
        self.assertIn('2025', aviso)
        self.assertIn('2026', aviso)

    # ── el parámetro ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_08_n_sale_del_parametro_y_cero_apaga_el_aviso(self):
        empleado, contrato = self._empleado()
        self._recibo(empleado, contrato, date(2026, 10, 1), date(2026, 10, 31), 80000.0, 'done')
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.assertFalse(self._aviso(noviembre), 'Con N = 3 no alcanza')
        self._meses(2)
        aviso = self._aviso(noviembre)
        self.assertTrue(aviso, 'Con N = 2 octubre y noviembre bastan')
        self.assertIn('2 meses', aviso)
        self._meses(0)
        self.assertFalse(self._aviso(noviembre), '0 apaga el aviso')

    def test_09_si_falta_el_parametro_el_aviso_lo_dice_y_no_bloquea(self):
        empleado, contrato = self._empleado()
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.env['hr.rule.parameter'].search([('code', '=', _CODIGO)]).unlink()
        aviso = self._aviso(noviembre)
        self.assertIn(_CODIGO, aviso)
        self.assertIn('Falta el parámetro', aviso)
        noviembre.compute_sheet()                                       # el cálculo no se entera

    def test_10_solo_es_un_aviso_el_calculo_no_lo_toca(self):
        empleado, contrato = self._empleado()
        self._septiembre_octubre(empleado, contrato)
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        neto = noviembre.net_wage
        with patch.object(type(noviembre), '_ne_avisos_habitualidad', side_effect=AssertionError('compute_sheet no debe leer el aviso')):
            noviembre.compute_sheet()
        self.assertEqual(noviembre.net_wage, neto)

    # ── la siembra y quién cambia el campo ───────────────────────────────────────────────────────────────────────────────────
    def test_11_la_siembra_vigila_solo_cuatro_conceptos(self):
        """Decisión del TL: True en AUX_ALIM, BONIF_NOSAL, BONIF_RET y VIATICOS_NOSAL; False en todo lo demás (incluidos AUX_TRANS, APOYO_SOST, INDEMNIZ, DOTACION y
        TELETRABAJO). Las reglas son por estructura: se comparan los códigos."""
        vigiladas = self.env['hr.salary.rule'].search([('l10n_co_ne_vigilar_habitualidad', '=', True)])
        self.assertEqual(set(vigiladas.mapped('code')), _VIGILADOS)
        for codigo in ('CO_AUX_TRANS', 'CO_APOYO_SOST', 'CO_INDEMNIZ', 'CO_DOTACION', 'CO_TELETRABAJO'):
            reglas = self.env['hr.salary.rule'].search([('code', '=', codigo)])
            self.assertTrue(reglas, codigo)
            self.assertFalse(any(reglas.mapped('l10n_co_ne_vigilar_habitualidad')), codigo)

    def test_12_un_concepto_no_vigilado_no_avisa_aunque_se_pague_todos_los_meses(self):
        """El campo es el interruptor: el mismo pago de tres meses seguidos avisa con el campo en True y no avisa con el campo en False (así el auxilio de transporte,
        que se paga todos los meses por ley, no avisa nunca: su campo viene sembrado en False)."""
        empleado, contrato = self._empleado()
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL')])
        self._septiembre_octubre(empleado, contrato)
        noviembre = self._recibo(empleado, contrato, date(2026, 11, 1), date(2026, 11, 30), 80000.0)
        self.assertTrue(self._aviso(noviembre))
        regla.l10n_co_ne_vigilar_habitualidad = False                      # el superusuario de la prueba puede
        self.assertFalse(self._aviso(noviembre), 'El mismo pago, sin vigilar, no avisa')

    def _usuario(self, login, grupos):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    def test_13_solo_el_administrador_del_sistema_cambia_el_campo_modelo_y_vista(self):
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL')], limit=1)
        self.assertTrue(regla.l10n_co_ne_vigilar_habitualidad, 'Premisa: la siembra la vigila')
        gerente = self._usuario('gerente_habitual', (_G_MANAGER, 'base.group_user'))
        administrador = self._usuario('administrador_habitual', (_G_MANAGER, 'base.group_system', 'base.group_user'))
        with self.assertRaisesRegex(AccessError, 'administrador del sistema'):
            regla.with_user(gerente).write({'l10n_co_ne_vigilar_habitualidad': False})
        self.assertTrue(regla.l10n_co_ne_vigilar_habitualidad)
        with self.assertRaisesRegex(AccessError, 'administrador del sistema'):
            self.env['hr.salary.rule'].with_user(gerente).create({
                'name': 'Regla de prueba', 'code': 'CO_PRUEBA_VIGILAR', 'sequence': 999, 'struct_id': regla.struct_id.id,
                'category_id': regla.category_id.id, 'l10n_co_ne_vigilar_habitualidad': True})
        regla.with_user(administrador).write({'l10n_co_ne_vigilar_habitualidad': False})
        self.assertFalse(regla.l10n_co_ne_vigilar_habitualidad, 'El administrador sí')

        def campo_en_la_vista(usuario):
            arch = self.env['hr.salary.rule'].with_user(usuario).get_view(view_type='form')['arch']
            return etree.fromstring(arch.encode('utf-8') if isinstance(arch, str) else arch).xpath("//field[@name='l10n_co_ne_vigilar_habitualidad']")
        self.assertFalse(campo_en_la_vista(gerente), 'El gerente de nómina no ve el campo en el formulario de la regla')
        self.assertTrue(campo_en_la_vista(administrador), 'El administrador del sistema sí')

    def test_14_la_vista_del_recibo_trae_el_aviso_de_solo_lectura_y_sin_estilos_propios(self):
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode('utf-8'))
        campo = arch.xpath("//page[@name='conceptos_de_pago']//field[@name='l10n_co_ne_aviso_no_salarial']")
        self.assertEqual(len(campo), 1)
        self.assertTrue(campo[0].get('readonly'))
        bloque = campo[0].getparent()
        self.assertEqual(bloque.get('invisible'), 'not l10n_co_ne_aviso_no_salarial')
        self.assertIn('alert', bloque.get('class'))
        self.assertFalse(bloque.get('style'))
