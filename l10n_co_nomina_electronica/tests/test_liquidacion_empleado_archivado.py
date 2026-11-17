# -*- coding: utf-8 -*-
"""E-6 (H-QA-023, ALTA): el asistente «Generar Liquidacion de Contrato» no encontraba empleados ARCHIVADOS. El flujo real, confirmado por David,
es «primero se registra el retiro (hr.departure.wizard, que por defecto archiva al empleado), despues se liquida»: con el empleado archivado
el campo Empleado del asistente (many2one nativo, `active_test` por defecto) no lo ofrecia y la liquidacion final no se podia completar por
la UI. La lista ahora incluye archivados (`context active_test=False`); el flujo completo con empleado archivado se prueba aqui."""

import ast
from datetime import date

from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestLiquidacionEmpleadoArchivado(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Liquidación Archivado')
        cls.Wizard = cls.env['l10n.co.hr.liquidacion.wizard']

    def _retirado(self, archivar=True):
        """Empleado con contrato cerrado por la fecha de retiro (como deja el asistente de retiro de RRHH) y, por defecto, archivado."""
        documento = self._documento(date(2024, 3, 1))
        empleado, contrato = documento.employee_id, documento.contract_id
        contrato.write({'date_end': date(2026, 3, 31), 'state': 'close'})
        if archivar:
            empleado.write({'active': False})
        return empleado, contrato

    # ── la lista de empleados ────────────────────────────────────────
    def test_el_campo_empleado_del_asistente_incluye_archivados(self):
        arch = self.Wizard.get_view(self.env.ref(
            'l10n_co_nomina_electronica.view_l10n_co_hr_liquidacion_wizard_form').id, 'form')['arch']
        campo = etree.fromstring(arch).xpath("//field[@name='employee_id']")[0]
        contexto = ast.literal_eval(campo.get('context') or '{}')
        self.assertIs(contexto.get('active_test'), False)

    def test_un_empleado_archivado_es_ofrecido_con_ese_contexto(self):
        empleado, _contrato = self._retirado()
        self.assertFalse(empleado.active)
        ofrecidos = self.env['hr.employee'].with_context(active_test=False).name_search(empleado.name, operator='=')
        self.assertIn(empleado.id, [i for i, _n in ofrecidos])

    # ── el flujo completo con empleado archivado ─────────────────────
    def test_el_asistente_encuentra_el_contrato_cerrado_del_empleado_archivado(self):
        empleado, contrato = self._retirado()
        asistente = self.Wizard.new({'employee_id': empleado.id})
        asistente._onchange_employee_id()
        self.assertEqual(asistente.contract_id, contrato)
        self.assertEqual(asistente.date_end, date(2026, 3, 31))      # la fecha de retiro sale del contrato

    def test_la_liquidacion_de_un_empleado_archivado_genera_el_recibo(self):
        empleado, contrato = self._retirado()
        asistente = self.Wizard.create({
            'employee_id': empleado.id, 'contract_id': contrato.id, 'date_end': date(2026, 3, 31), 'cause': 'renuncia'})
        accion = asistente.action_create_liquidacion()
        recibo = self.env['hr.payslip'].browse(accion['res_id'])
        self.assertEqual(recibo.employee_id, empleado)
        self.assertEqual(recibo.struct_id, self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion'))
        self.assertEqual((recibo.date_from, recibo.date_to), (contrato.date_start, date(2026, 3, 31)))
        self.assertEqual(recibo.l10n_co_ne_liquidacion_cause, 'renuncia')
        self.assertFalse(recibo.employee_id.active)

    def test_el_recibo_de_liquidacion_de_un_empleado_archivado_se_calcula(self):
        """Pregunta de TL: ¿falla el calculo con empleado archivado? Si esta prueba falla en la regresion, ese es el defecto real."""
        empleado, contrato = self._retirado()
        asistente = self.Wizard.create({
            'employee_id': empleado.id, 'contract_id': contrato.id, 'date_end': date(2026, 3, 31), 'cause': 'renuncia'})
        recibo = self.env['hr.payslip'].browse(asistente.action_create_liquidacion()['res_id'])
        recibo.compute_sheet()
        self.assertTrue(recibo.line_ids.filtered(lambda l: l.code == 'CO_LIQ_NETO'))

    def test_un_empleado_activo_sigue_funcionando_igual(self):
        empleado, contrato = self._retirado(archivar=False)
        asistente = self.Wizard.create({
            'employee_id': empleado.id, 'contract_id': contrato.id, 'date_end': date(2026, 3, 31), 'cause': 'mutuo_acuerdo'})
        recibo = self.env['hr.payslip'].browse(asistente.action_create_liquidacion()['res_id'])
        self.assertEqual(recibo.employee_id, empleado)
        self.assertTrue(recibo.employee_id.active)

    # ── el mismo patron en otro punto: el contacto de un empleado archivado ──
    def test_el_cambio_de_nit_del_contacto_sincroniza_tambien_al_empleado_archivado(self):
        empleado, _contrato = self._retirado()
        empleado.work_contact_id.sudo().vat = '1020304099'
        self.assertEqual(empleado.identification_id, '1020304099')
