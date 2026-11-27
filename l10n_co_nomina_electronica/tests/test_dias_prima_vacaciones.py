# -*- coding: utf-8 -*-
"""Q-19 (doc 116, .332): la nómina electrónica informa los días de la prima y de las vacaciones compensadas pagadas como novedad en pesos (antes salía ``Cantidad="1"``).

Los días van en una novedad aparte, sin regla: se registran con «Días de prima y vacaciones» en un recibo en borrador o confirmado sin reportar, sin cambiar valores."""

import base64
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

NATIVO = 'odoo.addons.hr_payroll.models.hr_payslip.HrPayslip.action_payslip_done'


@tagged('post_install', '-at_install')
class TestDiasDePrimaYVacacionesCompensadas(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Días de Prima'})
        cls.env = cls.company.with_company(cls.company).env
        cls.tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Tipo Días de Prima', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _recibo(self, novedades=(('input_co_prima', 500000.0), ('input_co_vac_comp', 300000.0))):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Dias %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Dias %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.tipo.id,
            'wage': 3000000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        contrato.generate_work_entries(date(2026, 9, 1), date(2026, 9, 30))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Dias %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.general.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15),
            'input_line_ids': [(0, 0, {'input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id, 'amount': monto}) for xmlid, monto in novedades]})
        recibo.compute_sheet()
        return recibo

    def _registrar(self, recibo, prima=180.0, vacaciones=5.0):
        return self.env['hr.payslip.dias.prestaciones'].create({'payslip_id': recibo.id, 'dias_prima': prima, 'dias_vacaciones': vacaciones}).action_registrar_dias()

    def _confirmar(self, recibo):
        """Confirma con las demás comprobaciones, el nativo y el asiento parchados; devuelve el parche del nativo (llamado = pasó)."""
        parches = [patch.object(type(recibo), nombre) for nombre in (
            '_ne_validar_duracion_periodo', '_ne_validar_sin_solape', '_ne_validar_cuenta_neto', '_ne_validar_pacto_no_salarial', '_ne_validar_afiliaciones',
            '_ne_aplicar_libranzas', '_ne_refrescar_ibc_mensual', '_action_create_account_move')]
        for parche in parches:
            parche.start()
        try:
            with patch(NATIVO, return_value=True) as nativo:
                recibo.action_payslip_done()
        finally:
            for parche in parches:
                parche.stop()
        return nativo

    def _cantidades_del_xml(self, recibo):
        devengados = {}
        recibo._dev_prestaciones(recibo._group_lines_by_concept(), devengados)
        return devengados['Primas']['Cantidad'], devengados['Vacaciones']['VacacionesCompensadas'][0]['Cantidad']

    def _asiento(self, recibo):
        cuentas = self.env['account.account']
        for codigo, tipo in (('510599', 'expense'), ('250599', 'liability_current')):
            cuentas |= self.env['account.account'].create({'code': codigo, 'name': 'Cuenta %s' % codigo, 'account_type': tipo, 'company_ids': [(6, 0, self.company.ids)]})
        diario = self.env['account.journal'].create({'name': 'Salarios dias', 'code': 'SLDI', 'type': 'general', 'company_id': self.company.id})
        asiento = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': diario.id, 'date': date(2026, 9, 15), 'line_ids': [
                (0, 0, {'account_id': cuentas[0].id, 'debit': 800000.0, 'credit': 0.0, 'name': 'Gasto'}),
                (0, 0, {'account_id': cuentas[1].id, 'debit': 0.0, 'credit': 800000.0, 'name': 'Por pagar'})]})
        asiento.action_post()
        recibo.move_id = asiento
        return asiento

    def _foto(self, recibo):
        """Líneas (con su id), neto, estado y asiento: lo que registrar días en un confirmado no puede tocar."""
        return (sorted((l.id, l.code, l.quantity, l.amount, l.total) for l in recibo.line_ids), recibo.net_wage, recibo.state,
                recibo.move_id.id, recibo.move_id.state, sorted((a.id, a.account_id.id, a.debit, a.credit) for a in recibo.move_id.line_ids))

    # ── borrador: no se confirma sin días ────────────────────────────
    def test_en_borrador_no_se_confirma_sin_dias_y_con_ellos_si_sin_cambiar_valores(self):
        recibo = self._recibo()
        self.assertTrue(recibo.l10n_co_ne_puede_registrar_dias)
        with self.assertRaises(UserError) as error:
            self._confirmar(recibo)
        for texto in (recibo.name, recibo.employee_id.name, 'Prima de Servicios'):
            self.assertIn(texto, error.exception.args[0])
        valores = sorted((l.code, l.total) for l in recibo.line_ids)
        self._registrar(recibo)
        self.assertEqual(sorted((l.code, l.total) for l in recibo.line_ids), valores)
        self.assertEqual(self._cantidades_del_xml(recibo), ('180', '5'))
        self.assertTrue(self._confirmar(recibo).called)

    def test_un_reembolso_no_exige_dias(self):
        recibo = self._recibo()
        recibo.credit_note = True
        recibo._ne_validar_dias_de_prestaciones()
        self.assertFalse(recibo.l10n_co_ne_puede_registrar_dias)

    # ── confirmado sin reportar: solo la novedad de días ─────────────
    def test_confirmado_sin_dias_el_xml_falla_y_registrarlos_no_toca_lineas_neto_ni_asiento(self):
        recibo = self._recibo()
        recibo.state = 'done'                                   # como quedó antes de la .332
        self._asiento(recibo)
        with self.assertRaises(UserError) as error:
            self._cantidades_del_xml(recibo)
        for texto in (recibo.name, recibo.employee_id.name, 'Días de prima y vacaciones'):
            self.assertIn(texto, error.exception.args[0])
        documento = self.env['l10n.co.ne.documento'].create({
            'company_id': self.company.id, 'employee_id': recibo.employee_id.id, 'contract_id': recibo.contract_id.id, 'period': date(2026, 9, 1)})
        recibo.l10n_co_ne_documento_id = documento
        adjunto = self.env['ir.attachment'].create({'name': 'ne.xml', 'datas': base64.b64encode(b'<x/>'), 'res_model': documento._name, 'res_id': documento.id})
        documento.write({'xml_attachment_id': adjunto.id, 'cune': 'a' * 96, 'etapa': 'ready'})
        foto = self._foto(recibo)
        self._registrar(recibo)
        self.assertEqual(self._foto(recibo), foto)
        self.assertEqual(self._cantidades_del_xml(recibo), ('180', '5'))
        self.assertFalse(documento.xml_attachment_id)           # el XML generado con la cantidad vieja no se puede enviar
        self.assertEqual(documento.etapa, 'draft')
        nota = [m.body for m in recibo.message_ids if '180' in (m.body or '')]
        self.assertEqual(len(nota), 1)
        for texto in ('no se recalculó la hoja ni cambió el asiento', 'genérelo de nuevo'):
            self.assertIn(texto, nota[0])
        mensajes = len(recibo.message_ids)
        self._registrar(recibo)                                 # los mismos días: nada que anotar
        self.assertEqual(len(recibo.message_ids), mensajes)

    def test_reportado_o_sin_prima_no_se_registra(self):
        recibo = self._recibo()
        recibo.state = 'done'
        recibo.l10n_co_ne_state = 'accepted'
        self.assertFalse(recibo.l10n_co_ne_puede_registrar_dias)
        with self.assertRaisesRegex(UserError, 'aún no se haya reportado'):
            self._registrar(recibo)
        self.assertFalse(self._recibo(novedades=(('input_co_bonif_nosal', 100000.0),)).l10n_co_ne_puede_registrar_dias)

    def _intento(self, documento, estado):
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': documento.id, 'state': estado, 'identifier': documento.cune, 'numero': documento.consecutive, 'datetime': datetime(2026, 10, 2)})

    def _documento_aceptado(self, recibo):
        documento = self.env['l10n.co.ne.documento'].create({
            'company_id': self.company.id, 'employee_id': recibo.employee_id.id, 'contract_id': recibo.contract_id.id, 'period': date(2026, 9, 1)})
        recibo.l10n_co_ne_documento_id = documento
        documento.write({'cune': 'a' * 96, 'consecutive': 'NE%08d' % recibo.id})
        self._intento(documento, 'invoice_accepted')
        self.assertEqual(documento.state, 'invoice_accepted', 'Premisa')
        return documento

    def test_reportado_con_nota_reemplazar_sin_enviar_se_registran_y_se_descarta_su_xml(self):
        """.335: el documento aceptado se corrige con una nota «Reemplazar»; mientras no se haya enviado se registran los días que faltaban."""
        recibo = self._recibo()
        recibo.state = 'done'
        documento = self._documento_aceptado(recibo)
        self.assertFalse(recibo.l10n_co_ne_puede_registrar_dias)
        nota = documento.action_crear_ajuste('1')
        adjunto = self.env['ir.attachment'].create({'name': 'na.xml', 'datas': base64.b64encode(b'<x/>'), 'res_model': nota._name, 'res_id': nota.id})
        nota.write({'xml_attachment_id': adjunto.id, 'cune': 'b' * 96, 'consecutive': 'NA%08d' % recibo.id, 'etapa': 'ready'})
        recibo.invalidate_recordset(['l10n_co_ne_puede_registrar_dias'])
        self.assertTrue(recibo.l10n_co_ne_puede_registrar_dias)
        self._registrar(recibo)
        self.assertEqual(self._cantidades_del_xml(recibo), ('180', '5'))
        self.assertEqual((bool(nota.xml_attachment_id), nota.etapa, documento.state), (False, 'draft', 'invoice_accepted'))
        self.assertTrue(any('nota de ajuste se descartó' in (m.body or '') for m in recibo.message_ids))
        nota.cune = 'b' * 96
        self._intento(nota, 'invoice_pending')                      # ya viajó: no se registran más
        recibo.invalidate_recordset(['l10n_co_ne_puede_registrar_dias'])
        self.assertFalse(recibo.l10n_co_ne_puede_registrar_dias)
        with self.assertRaisesRegex(UserError, 'Reemplazar'):
            self._registrar(recibo, prima=90.0)

    def test_reportado_con_nota_eliminar_no_se_registra(self):
        recibo = self._recibo()
        recibo.state = 'done'
        self._documento_aceptado(recibo).action_crear_ajuste('2')
        recibo.invalidate_recordset(['l10n_co_ne_puede_registrar_dias'])
        self.assertFalse(recibo.l10n_co_ne_puede_registrar_dias)

    def test_los_dias_deben_ser_mayores_que_cero(self):
        recibo = self._recibo()
        with self.assertRaisesRegex(UserError, 'mayores que cero, de "Vacaciones Compensadas: días"'):
            self._registrar(recibo, vacaciones=0.0)

    def test_las_lineas_que_ya_traen_dias_conservan_su_cantidad(self):
        """Liquidación y estructura Prima: la cantidad de la línea ya son días y no se pide nada."""
        recibo = self._recibo(novedades=())
        regla = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima').rule_ids.filtered(lambda r: r.code == 'CO_PRIMA_VALOR')
        linea = self.env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': regla.code, 'name': regla.name, 'contract_id': recibo.contract_id.id,
            'employee_id': recibo.employee_id.id, 'quantity': 180.0, 'rate': 100.0, 'amount': 1000.0, 'total': 180000.0})
        self.assertEqual(recibo._ne_cantidad_en_dias([linea]), 180.0)
