# -*- coding: utf-8 -*-
"""Volver a borrador un LOTE (.333): el nativo escribe el estado de los recibos sin cancelarlos, asi que el asiento seguiria ligado y la libranza aplicada. En compania colombiana se detiene y pide cancelar
recibo por recibo."""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestLoteVolverABorrador(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Lote a Borrador')

    def _lote(self):
        """Lote cerrado con las dos quincenas del fixture en estado Hecho, sin asiento ni libranza."""
        recibos = self._documento(date(2024, 3, 1)).payslip_ids.sorted('date_to')
        recibos.write({'state': 'done', 'paid_date': False})
        recibos[0].name = 'Primera quincena sin nada'
        recibos[1].name = 'Segunda quincena afectada'
        lote = self.env['hr.payslip.run'].create({'name': 'Lote a borrador %s' % self.n, 'state': 'close', 'company_id': self.company.id})
        recibos.write({'payslip_run_id': lote.id})
        return lote, recibos[0], recibos[1]

    def _asiento(self):
        diario = self.env['account.journal'].with_company(self.company).create({'name': 'Salarios lote', 'code': 'SLLO', 'type': 'general', 'company_id': self.company.id})
        return self.env['account.move'].with_company(self.company).create({'move_type': 'entry', 'journal_id': diario.id, 'date': date(2026, 3, 31)})

    def _libranza_aplicada(self, recibo):
        asignacion = self.env['hr.salary.attachment'].create({
            'description': 'Libranza lote', 'employee_ids': [(6, 0, recibo.employee_id.ids)], 'company_id': self.company.id,
            'other_input_type_id': self.env.ref('l10n_co_nomina_electronica.input_l10n_co_libranza').id, 'monthly_amount': 500000.0,
            'date_start': date(2026, 1, 1), 'no_end_date': True, 'l10n_co_saldo_pendiente': 1000000.0,
            'l10n_co_partner_id': self.env['res.partner'].create({'name': 'Banco Lote'}).id})
        fila = self.env['l10n.co.payslip.tercero'].create({'slip_id': recibo.id, 'rule_code': 'CO_LIBRANZAS', 'attachment_id': asignacion.id, 'amount': 500000.0})
        recibo._ne_aplicar_libranzas()
        self.assertEqual((fila.applied, asignacion.paid_amount), (True, 500000.0), 'Premisa')
        return asignacion, fila

    def test_un_recibo_con_asiento_detiene_el_lote_y_nada_cambia(self):
        lote, limpio, afectado = self._lote()
        asiento = self._asiento()
        afectado.move_id = asiento
        with self.assertRaises(UserError) as error:
            lote.action_draft()
        mensaje = error.exception.args[0]
        self.assertIn(afectado.display_name, mensaje)
        self.assertNotIn(limpio.display_name, mensaje)
        self.assertIn('Cancelar', mensaje)
        self.assertEqual((set(lote.slip_ids.mapped('state')), lote.state, afectado.move_id), ({'done'}, 'close', asiento))

    def test_una_cuota_de_libranza_aplicada_detiene_el_lote(self):
        lote, _limpio, afectado = self._lote()
        asignacion, fila = self._libranza_aplicada(afectado)
        with self.assertRaises(UserError) as error:
            lote.action_draft()
        self.assertIn(afectado.display_name, error.exception.args[0])
        self.assertEqual((set(lote.slip_ids.mapped('state')), fila.applied, asignacion.paid_amount), ({'done'}, True, 500000.0))

    def test_cancelando_el_recibo_se_reversa_y_el_lote_vuelve_a_borrador(self):
        lote, _limpio, afectado = self._lote()
        asignacion, fila = self._libranza_aplicada(afectado)
        afectado.move_id = self._asiento()
        afectado.action_payslip_cancel()
        self.assertEqual((fila.applied, asignacion.paid_amount, bool(afectado.move_id)), (False, 0.0, False))
        lote.action_draft()
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'draft'})

    def test_el_borrador_del_lote_borra_la_fecha_de_pago_registrada(self):
        """CC-08 (.334): el lote no pasa por el borrador del recibo y cancelar tampoco la borra; la fecha de un neto 0 se registra de nuevo."""
        lote, _limpio, afectado = self._lote()
        afectado.l10n_co_ne_fecha_pago_registrada = date(2026, 3, 31)
        afectado.move_id = self._asiento()
        afectado.action_payslip_cancel()
        self.assertEqual(afectado.l10n_co_ne_fecha_pago_registrada, date(2026, 3, 31), 'Premisa: cancelar no la borra')
        lote.action_draft()
        self.assertEqual((afectado.state, afectado.l10n_co_ne_fecha_pago_registrada), ('draft', False))

    def test_sin_asiento_ni_libranza_vuelve_a_borrador_como_el_nativo(self):
        lote, _limpio, _afectado = self._lote()
        lote.action_draft()
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'draft'})

    def test_con_recibos_pagados_responde_el_mensaje_nativo(self):
        lote, _limpio, afectado = self._lote()
        afectado.move_id = self._asiento()
        lote.slip_ids.write({'state': 'paid'})
        with self.assertRaises(ValidationError):
            lote.action_draft()

    def test_una_compania_no_colombiana_conserva_el_nativo(self):
        lote, _limpio, afectado = self._lote()
        afectado.move_id = self._asiento()
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            lote.action_draft()
        self.assertEqual(set(lote.slip_ids.mapped('state')), {'draft'})
