# -*- coding: utf-8 -*-
"""Al agregar, editar o borrar una novedad (``hr.payslip.input``) la hoja del recibo se recalcula sola (.283, doc 68 §14; orden de David).

Defecto (producción, SLIP/087): una novedad guardada (``CO_BONIF_NOSAL`` 200.000) no generaba su línea hasta pulsar «Calcular hoja». La regla
``CO_BONIF_NOSAL`` paga ``inputs['CO_BONIF_NOSAL'].amount`` (``data/hr_payroll_structure_data.xml:373-380``): el valor de la línea es el monto.

Qué se prueba: crear/editar/borrar recalculan (sin llamar ``compute_sheet`` desde la prueba); no se tocan recibos hechos ni editados; un recibo
sin hoja calculada no se calcula (sin número, sigue en borrador) y las novedades que nacen en el ``create`` del recibo no disparan; una
llamada de ``compute_sheet`` por recibo aunque se creen 2 novedades; contextos de bypass (carga masiva e importación); los días no se
recalculan; el resultado es el del botón; y un error del cálculo NO impide guardar la novedad (savepoint + nota en el recibo).
NO EJECUTADAS en Odoo."""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNovedadesRecalculanHoja(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Novedades Recalculan'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Novedades Recalculan', 'country_id': cls.env.ref('base.co').id})
        cls.est_general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.tipo_bonificacion = cls.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _recibo(self, calculado=True, novedades=()):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Novedades %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Novedades %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        vals = {
            'name': 'Recibo Novedades %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.est_general.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)}
        if novedades:
            vals['input_line_ids'] = [(0, 0, self._vals_novedad(None, monto)) for monto in novedades]
        recibo = self.env['hr.payslip'].create(vals)
        if calculado:
            recibo.compute_sheet()
        return recibo

    def _vals_novedad(self, recibo, monto):
        vals = {'input_type_id': self.tipo_bonificacion.id, 'code': 'CO_BONIF_NOSAL', 'amount': monto}
        if recibo:
            vals['payslip_id'] = recibo.id
        return vals

    def _novedad(self, recibo, monto, **contexto):
        return self.env['hr.payslip.input'].with_context(**contexto).create(self._vals_novedad(recibo, monto))

    def _lineas(self, recibo, codigo='CO_BONIF_NOSAL'):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _totales(self, recibo):
        return {l.code: l.total for l in recibo.line_ids}

    # ── crear, editar, borrar ─────────────────────────────────────────
    def test_una_novedad_nueva_genera_su_linea_sin_calcular_la_hoja(self):
        recibo = self._recibo()
        self.assertFalse(self._lineas(recibo), 'Premisa: el recibo calculado no tiene bonificación')
        self._novedad(recibo, 200000.0)
        self.assertEqual(self._lineas(recibo).total, 200000.0)
        self.assertEqual(recibo.state, 'verify')

    def test_editar_el_monto_actualiza_la_linea(self):
        recibo = self._recibo()
        novedad = self._novedad(recibo, 200000.0)
        novedad.amount = 350000.0
        self.assertEqual(self._lineas(recibo).total, 350000.0)

    def test_borrar_la_novedad_quita_la_linea(self):
        recibo = self._recibo()
        novedad = self._novedad(recibo, 200000.0)
        self.assertTrue(self._lineas(recibo))
        novedad.unlink()
        self.assertFalse(self._lineas(recibo))

    # ── qué recibos no se tocan ───────────────────────────────────────
    def test_un_recibo_hecho_no_se_recalcula(self):
        recibo = self._recibo()
        recibo.state = 'done'
        antes = self._totales(recibo)
        self._novedad(recibo, 200000.0)
        self.assertEqual(self._totales(recibo), antes)
        self.assertFalse(self._lineas(recibo))

    def test_un_recibo_editado_a_mano_no_se_recalcula(self):
        recibo = self._recibo()
        recibo.edited = True
        antes = self._totales(recibo)
        self._novedad(recibo, 200000.0)
        self.assertEqual(self._totales(recibo), antes)

    def test_un_recibo_sin_hoja_calculada_no_se_calcula(self):
        """Nada viejo que actualizar: sin líneas, sin número y en borrador; calcularlo gastaría un número de la secuencia."""
        recibo = self._recibo(calculado=False)
        self.assertFalse(recibo.line_ids)
        self._novedad(recibo, 200000.0)
        self.assertFalse(recibo.line_ids)
        self.assertEqual(recibo.state, 'draft')
        self.assertFalse(recibo.number)

    def test_las_novedades_que_nacen_con_el_recibo_no_disparan_el_calculo(self):
        recibo = self._recibo(calculado=False, novedades=(200000.0,))
        self.assertEqual(len(recibo.input_line_ids), 1)
        self.assertFalse(recibo.line_ids)
        self.assertEqual(recibo.state, 'draft')

    # ── una pasada, bypass, días y resultado ──────────────────────────
    def test_dos_novedades_del_mismo_codigo_se_suman_y_hay_una_llamada_por_recibo(self):
        recibo = self._recibo()
        original = type(recibo).compute_sheet
        llamadas = []

        def espia(slip):
            llamadas.append(slip.ids)
            return original(slip)

        with patch.object(type(recibo), 'compute_sheet', espia):
            self.env['hr.payslip.input'].create([self._vals_novedad(recibo, 100000.0), self._vals_novedad(recibo, 50000.0)])
        self.assertEqual(llamadas, [recibo.ids], 'Una llamada por recibo aunque se creen 2 novedades')
        self.assertEqual(sum(self._lineas(recibo).mapped('total')), 150000.0)

    def test_los_contextos_de_carga_masiva_e_importacion_no_recalculan(self):
        recibo = self._recibo()
        self._novedad(recibo, 200000.0, ne_sin_recalculo_hoja=True)
        self.assertFalse(self._lineas(recibo), 'ne_sin_recalculo_hoja: la hoja queda vieja')
        self._novedad(recibo, 30000.0, import_file=True)
        self.assertFalse(self._lineas(recibo), 'import_file: la hoja queda vieja')
        recibo.compute_sheet()
        self.assertEqual(sum(self._lineas(recibo).mapped('total')), 230000.0, 'El botón las recoge')

    def test_los_dias_no_se_recalculan(self):
        recibo = self._recibo()
        dias = recibo.worked_days_line_ids.ids
        self.assertTrue(dias)
        self._novedad(recibo, 200000.0)
        self.assertEqual(recibo.worked_days_line_ids.ids, dias)

    def test_el_resultado_es_el_del_boton_calcular_hoja(self):
        recibo = self._recibo()
        self._novedad(recibo, 200000.0)
        automatico = self._totales(recibo)
        neto = recibo.net_wage
        recibo.compute_sheet()
        self.assertEqual(self._totales(recibo), automatico)
        self.assertAlmostEqual(recibo.net_wage, neto, places=2)

    # ── error del cálculo ─────────────────────────────────────────────
    def test_un_error_del_calculo_no_impide_guardar_la_novedad_y_deja_una_nota(self):
        """Decisión de TL: savepoint; el recálculo se revierte, la novedad SE GUARDA y el recibo recibe una nota con el error y la instrucción
        de pulsar «Calcular hoja» (p. ej. un reparto por tercero que no cuadra tras cambiar el monto de un embargo)."""
        recibo = self._recibo()
        antes = self._totales(recibo)
        with patch.object(type(recibo), 'compute_sheet', side_effect=UserError('Error de prueba del cálculo')):
            novedad = self._novedad(recibo, 200000.0)
        self.assertTrue(novedad.exists(), 'La novedad se conserva')
        self.assertEqual(novedad.amount, 200000.0)
        self.assertEqual(self._totales(recibo), antes, 'La hoja quedó como estaba')
        mensaje = recibo.message_ids[:1]
        self.assertIn('Error de prueba del cálculo', mensaje.body)
        self.assertIn('Calcular hoja', mensaje.body)
