# -*- coding: utf-8 -*-
"""Pieza .302 (doc 76 §2.3, decisión del TL del 22-nov): PACTO escrito de desalarización del EMPLEADO (``l10n.co.employee.pacto``). NO EJECUTADAS en Odoo al escribirlas;
necesitan ``-u`` (modelo, permisos, regla de compañía, vistas y el parámetro ``l10n_co_exigir_pacto_no_salarial``): en una N1 sin ``-u`` fallan por diseño todas.

Qué se prueba:
- Un pago no salarial POR PACTO (origen «pacto»: CO_AUX_ALIM, CO_BONIF_NOSAL) necesita un pacto del empleado; el de naturaleza no. Un pacto cubre los recibos cuyo ``date_to``
  cae entre la firma y el fin (fin vacía = vigente), por el ``code`` del concepto y sin depender del contrato (renovarlo no lo pierde). Con el documento firmado: sin
  documento se guarda pero NO cubre («pacto sin soporte», SU 25185: la carga de la prueba es del empleador).
- Sin pacto el recibo AVISA siempre; al CONFIRMAR es un error solo si el interruptor ``l10n_co_exigir_pacto_no_salarial`` vale 1 (0 de fábrica); el parámetro es obligatorio
  y solo se lee si hay un pago por pacto sin cubrir.
- Aislamiento por la compañía del empleado; la lista vive en la pestaña Nómina del empleado."""

import re
from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_CODIGO = 'l10n_co_exigir_pacto_no_salarial'
_G_MANAGER = 'hr_payroll.group_hr_payroll_manager'
_G_USER = 'hr_payroll.group_hr_payroll_user'


@tagged('post_install', '-at_install')
class TestPactoDesalarizacion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Pactos A'))
        cls.company_b = cls.env['res.company'].create(dict(valores, name='Compañía Pactos B'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Pactos', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.tipo_bonif = cls.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.Pacto = cls.env['l10n.co.employee.pacto']
        cls.regla_bonif = cls.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL')], limit=1)
        cls.regla_alim = cls.env['hr.salary.rule'].search([('code', '=', 'CO_AUX_ALIM')], limit=1)
        cls.n = 0

    def setUp(self):
        super().setUp()
        self._exigir(0)

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _exigir(self, valor):
        """Fija el interruptor (en la N1 sin ``-u`` la base aún no trae el parámetro del XML: se crea dentro de la transacción de la prueba)."""
        Parametro = self.env['hr.rule.parameter']
        parametro = Parametro.search([('code', '=', _CODIGO)], limit=1) or Parametro.create({
            'name': 'Colombia: Exigir el Pacto de los Pagos No Salariales', 'code': _CODIGO, 'country_id': self.env.ref('base.co').id})
        if parametro.parameter_version_ids:
            parametro.parameter_version_ids.write({'parameter_value': str(valor)})
        else:
            self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'parameter_value': str(valor), 'date_from': date(2020, 1, 1)})

    def _empleado(self, compania=None):
        type(self).n += 1
        compania = compania or self.company
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Pacto %s' % self.n,
            'company_id': compania.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Pacto %s' % self.n, 'employee_id': empleado.id, 'company_id': compania.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return empleado, contrato

    def _recibo(self, empleado, contrato, bonificacion=80000.0, desde=date(2026, 9, 1), hasta=date(2026, 9, 30)):
        """Recibo calculado; con ``bonificacion`` lleva una novedad de bonificación no salarial (CO_BONIF_NOSAL, origen «pacto»)."""
        type(self).n += 1
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Pacto %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': empleado.company_id.id,
            'struct_id': self.general.id, 'date_from': desde, 'date_to': hasta})
        if bonificacion:
            self.env['hr.payslip.input'].with_context(ne_sin_recalculo_hoja=True).create({
                'payslip_id': recibo.id, 'input_type_id': self.tipo_bonif.id, 'amount': bonificacion, 'name': 'Bonificación %s' % self.n})
        recibo.compute_sheet()
        return recibo

    def _documento(self):
        return self.env['ir.attachment'].create({'name': 'Pacto firmado.pdf', 'raw': b'%PDF-1.4 pacto de prueba', 'mimetype': 'application/pdf'})

    def _pacto(self, empleado, regla=None, firma=date(2026, 1, 1), fin=False, con_documento=True):
        """Pacto del empleado; por defecto CON el documento firmado (decisión del TL, 22-nov: un pacto sin documento no cubre)."""
        valores = {'employee_id': empleado.id, 'salary_rule_id': (regla or self.regla_bonif).id, 'fecha_firma': firma, 'fecha_fin': fin}
        if con_documento:
            valores['attachment_ids'] = [(4, self._documento().id)]
        return self.Pacto.create(valores)

    def _aviso(self, recibo):
        recibo.invalidate_recordset(['l10n_co_ne_aviso_pacto'])
        return recibo.l10n_co_ne_aviso_pacto

    # ── el aviso y la cobertura ──────────────────────────────────────────────────────────────────────────────────────────────
    def test_01_sin_pacto_el_recibo_avisa_con_concepto_empleado_y_donde_completarlo(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        aviso = self._aviso(recibo)
        self.assertTrue(aviso)
        self.assertIn(self.regla_bonif.name, aviso)
        self.assertIn(empleado.name, aviso)
        self.assertIn('art. 128 CST', aviso)
        self.assertIn('Pactos de desalarización', aviso)

    def test_02_con_pacto_vigente_no_avisa_y_el_aviso_no_depende_del_interruptor(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        self.assertTrue(self._aviso(recibo), 'Con el interruptor en 0 también avisa')
        self._exigir(1)
        self.assertTrue(self._aviso(recibo), 'Con el interruptor en 1 también avisa')
        self._pacto(empleado)
        self.assertFalse(self._aviso(recibo))

    def test_03_el_pacto_de_otro_concepto_no_cubre(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        self._pacto(empleado, regla=self.regla_alim)
        self.assertTrue(self._aviso(recibo), 'El pacto del auxilio de alimentación no cubre la bonificación')

    def test_04_la_vigencia_va_de_la_firma_al_fin_del_periodo_del_recibo(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)                       # date_to = 30-sep-2026
        posterior = self._pacto(empleado, firma=date(2026, 10, 1))
        self.assertTrue(self._aviso(recibo), 'Firmado después del periodo: no cubre')
        posterior.fecha_firma = date(2026, 9, 30)
        self.assertFalse(self._aviso(recibo), 'Firmado el último día del periodo: cubre')
        posterior.write({'fecha_firma': date(2026, 1, 1), 'fecha_fin': date(2026, 9, 29)})
        self.assertTrue(self._aviso(recibo), 'Terminó antes del fin del periodo: no cubre')
        posterior.fecha_fin = date(2026, 9, 30)
        self.assertFalse(self._aviso(recibo), 'Terminó el último día del periodo: cubre')

    def test_05_renovar_el_contrato_no_pierde_el_pacto(self):
        empleado, contrato = self._empleado()
        self._pacto(empleado)
        contrato.write({'state': 'close', 'date_end': date(2026, 8, 31)})
        nuevo = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato renovado', 'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2026, 9, 1), 'state': 'open'})
        recibo = self._recibo(empleado, nuevo)
        self.assertFalse(self._aviso(recibo), 'El pacto es del empleado: el contrato nuevo queda cubierto')

    def test_05b_un_pacto_sin_documento_se_guarda_pero_no_cubre_y_dice_pacto_sin_soporte(self):
        """Decisión del TL (22-nov): se puede guardar sin adjunto (para cargarlo y escanear después), pero sin el documento firmado el pacto NO cubre: el aviso dice «pacto
        sin soporte» (no «no tiene registrado el pacto») y, con el interruptor en 1, confirmar da error igual que sin pacto. Al adjuntar el documento, cubre."""
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        sin_pacto = self._aviso(recibo)
        self.assertIn('no tiene registrado el pacto', sin_pacto)
        self.assertNotIn('pacto sin soporte', sin_pacto)
        pacto = self._pacto(empleado, con_documento=False)              # se guarda sin documento
        self.assertTrue(pacto.exists())
        aviso = self._aviso(recibo)
        self.assertIn('pacto sin soporte', aviso)
        self.assertNotIn('no tiene registrado el pacto', aviso)
        self.assertIn(self.regla_bonif.name, aviso)
        self.assertIn(empleado.name, aviso)
        self.assertIn('SU 25185', aviso)
        recibo._ne_validar_pacto_no_salarial()                          # interruptor en 0: solo avisa
        self._exigir(1)
        with self.assertRaisesRegex(UserError, 'pacto sin soporte'):
            recibo._ne_validar_pacto_no_salarial()
        pacto.attachment_ids = [(4, self._documento().id)]
        self.assertFalse(self._aviso(recibo), 'Con el documento adjunto cubre')
        recibo._ne_validar_pacto_no_salarial()

    def test_05c_basta_un_pacto_vigente_con_documento_aunque_otro_no_lo_tenga(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        self._pacto(empleado, firma=date(2026, 1, 1), fin=date(2026, 12, 31), con_documento=False)
        self.assertIn('pacto sin soporte', self._aviso(recibo))
        self._pacto(empleado, firma=date(2026, 3, 1))                   # otro pacto vigente, este con documento
        self.assertFalse(self._aviso(recibo))

    def test_06_el_pacto_de_otro_empleado_no_cubre(self):
        empleado, contrato = self._empleado()
        otro, _contrato_otro = self._empleado()
        self._pacto(otro)
        self.assertTrue(self._aviso(self._recibo(empleado, contrato)))

    def test_07_un_pago_no_salarial_por_naturaleza_no_exige_pacto(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        self.assertTrue(self._aviso(recibo))
        self.regla_bonif.l10n_co_pila_origen_no_salarial = 'naturaleza'
        self.assertFalse(self._aviso(recibo), 'Por naturaleza no necesita pacto')

    def test_08_un_recibo_sin_pagos_por_pacto_no_avisa_ni_lee_el_interruptor(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato, bonificacion=0.0)
        self.assertFalse(self._aviso(recibo))
        self._exigir(1)
        self.env['hr.rule.parameter'].search([('code', '=', _CODIGO)]).unlink()
        recibo._ne_validar_pacto_no_salarial()                         # sin pagos por pacto no depende del parámetro: no falla

    # ── al confirmar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_09_con_el_interruptor_en_1_sin_pacto_no_se_confirma_y_con_pacto_o_en_0_si(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        recibo._ne_validar_pacto_no_salarial()                         # interruptor en 0: solo avisa
        self._exigir(1)
        with self.assertRaisesRegex(UserError, 'no tiene registrado el pacto'):
            recibo._ne_validar_pacto_no_salarial()
        with self.assertRaisesRegex(UserError, re.escape(self.regla_bonif.name)):
            recibo._ne_validar_pacto_no_salarial()
        self._pacto(empleado)
        recibo._ne_validar_pacto_no_salarial()                         # con el pacto confirma

    def test_10_si_falta_el_interruptor_y_hay_un_pago_por_pacto_sin_cubrir_el_error_lo_dice(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        self.env['hr.rule.parameter'].search([('code', '=', _CODIGO)]).unlink()
        with self.assertRaisesRegex(UserError, _CODIGO):
            recibo._ne_validar_pacto_no_salarial()

    def test_11_confirmar_el_recibo_llama_a_la_validacion_del_pacto(self):
        empleado, contrato = self._empleado()
        recibo = self._recibo(empleado, contrato)
        tipo = type(recibo)
        with patch.object(tipo, '_ne_validar_duracion_periodo'), patch.object(tipo, '_ne_validar_sin_solape'), patch.object(tipo, '_ne_validar_cuenta_neto'), \
                patch.object(tipo, '_ne_validar_pacto_no_salarial', side_effect=UserError('Falta el pacto de prueba')):
            with self.assertRaisesRegex(UserError, 'Falta el pacto de prueba'):
                recibo.action_payslip_done()

    # ── el modelo ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_12_el_pacto_valida_fechas_y_solo_admite_conceptos_por_pacto(self):
        empleado, _contrato = self._empleado()
        with self.assertRaises(ValidationError):
            self._pacto(empleado, firma=date(2026, 5, 1), fin=date(2026, 4, 30))
        naturaleza = self.env['hr.salary.rule'].search([('l10n_co_pila_origen_no_salarial', '=', 'naturaleza')], limit=1)
        self.assertTrue(naturaleza, 'Premisa: hay reglas por naturaleza')
        with self.assertRaises(ValidationError):
            self._pacto(empleado, regla=naturaleza)

    def _usuario(self, login, grupos, companias):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': companias[0].id,
            'company_ids': [(6, 0, companias.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    def test_13_los_pactos_de_la_compania_a_son_invisibles_desde_la_compania_b(self):
        empleado, _contrato = self._empleado()
        pacto = self._pacto(empleado)
        usuario_b = self._usuario('gerente_pactos_b', (_G_MANAGER, 'base.group_user'), self.company_b)
        usuario_ab = self._usuario('gerente_pactos_ab', (_G_MANAGER, 'base.group_user'), self.company | self.company_b)
        self.assertFalse(self.Pacto.with_user(usuario_b).search([('id', '=', pacto.id)]))
        con_ambas = self.Pacto.with_user(usuario_ab).with_context(allowed_company_ids=[self.company.id, self.company_b.id])
        self.assertTrue(con_ambas.search([('id', '=', pacto.id)]))
        solo_b = self.Pacto.with_user(usuario_ab).with_context(allowed_company_ids=[self.company_b.id])
        self.assertFalse(solo_b.search([('id', '=', pacto.id)]))

    def test_14_el_usuario_de_nomina_carga_pactos_y_solo_el_gerente_los_borra(self):
        empleado, _contrato = self._empleado()
        oficial = self._usuario('oficial_pactos', (_G_USER, 'base.group_user'), self.company)
        gerente = self._usuario('gerente_pactos', (_G_MANAGER, 'base.group_user'), self.company)
        pacto = self.Pacto.with_user(oficial).create({'employee_id': empleado.id, 'salary_rule_id': self.regla_bonif.id, 'fecha_firma': date(2026, 1, 1)})
        pacto.with_user(oficial).write({'fecha_fin': date(2026, 12, 31)})
        with self.assertRaises(UserError):                              # AccessError es un UserError en Odoo 18
            pacto.with_user(oficial).unlink()
        pacto.with_user(gerente).unlink()
        self.assertFalse(pacto.exists())

    # ── las vistas y los datos ──────────────────────────────────────────────────────────────────────────────────────────────
    def test_15_la_pestana_nomina_del_empleado_trae_los_pactos_y_el_recibo_el_aviso(self):
        arch = etree.fromstring(self.env['hr.employee'].get_view(view_type='form')['arch'].encode('utf-8'))
        grupo = arch.xpath("//page[@name='hr_payroll']//group[@name='pactos_desalarizacion']")
        self.assertEqual(len(grupo), 1, 'Los pactos van dentro de la pestaña nativa Nómina, sin pestaña nueva')
        campo = grupo[0].xpath(".//field[@name='l10n_co_pacto_ids']")
        self.assertEqual(len(campo), 1)
        self.assertTrue(campo[0].xpath(".//form//field[@name='attachment_ids'][@widget='many2many_binary']"), 'El documento se adjunta con el widget nativo')
        self.assertFalse(grupo[0].xpath(".//*[@style]"), 'Sin estilos propios')
        recibo = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode('utf-8'))
        aviso = recibo.xpath("//page[@name='conceptos_de_pago']//field[@name='l10n_co_ne_aviso_pacto']")
        self.assertEqual(len(aviso), 1)
        self.assertEqual(aviso[0].getparent().get('invisible'), 'not l10n_co_ne_aviso_pacto')


@tagged('post_install', '-at_install')
class TestPactoDesalarizacionSiembra(TransactionCase):
    """Aparte de la clase anterior: su ``setUp`` fija el interruptor y taparía el valor sembrado."""

    def test_el_interruptor_de_fabrica_es_0(self):
        valor = self.env.ref('l10n_co_nomina_electronica.rule_parameter_exigir_pacto_no_salarial_v')
        self.assertEqual(valor.parameter_value, '0', 'Se despliega en 0: hasta que el usuario cargue los pactos solo avisa')
        self.assertEqual(valor.rule_parameter_id.code, _CODIGO)
