# -*- coding: utf-8 -*-
"""Las novedades guardadas DESDE EL FORMULARIO del recibo recalculan la hoja (.286; corrige .283, doc 68 §14; hallazgo de QA en staging_dev).

Defecto (QA, recibo «En espera» con la hoja calculada): al crear, editar o borrar una novedad en la pestaña del recibo y guardar, la hoja NO se
recalculaba (el neto seguía igual, sin línea nueva ni nota; al borrar, la línea de una novedad inexistente seguía en la hoja). Solo «Calcular hoja»
la corregía. Causa: el cliente web guarda con ``web_save`` -> ``hr.payslip.write({'input_line_ids': [...]})`` (``addons/web/models/models.py:68-70``);
``input_line_ids`` es un One2many calculado, almacenado y no de solo lectura (``hr_payroll/models/hr_payslip.py:93-96``) y ``BaseModel.write`` lo
PROTEGE mientras escribe (``odoo/models.py:4774-4785`` y ``:4798``); el guardián de .283 (``_ne_recalcular_hoja_por_novedad``, ``not
env.is_protected(input_line_ids)``, ``odoo/api.py:866-870``) veía el campo protegido y se saltaba el recálculo. Las pruebas de .283 creaban las
novedades con el ORM directo (``hr.payslip.input.create``), fuera de ese ``write``, y por eso no lo veían.

Estas pruebas usan ``odoo.tests.Form`` (el mismo camino ``web_save`` que el cliente web, ``odoo/tests/form.py:428-445``) y, en CADA paso, comparan el
neto y la línea contra un «Calcular hoja» manual.

.290 (corrección de la N2 «co» de .289): desde la pieza 3 (.289, doc 71c §5) las estructuras con el interruptor ``l10n_co_ne_conceptos_de_pago`` (hoy
la general) OCULTAN la página nativa de novedades (``views/hr_payslip_conceptos_views.xml:13-15``) y las novedades se agregan, editan y borran como
FILAS de «Conceptos de pago» (``l10n_co_concepto_ids``); ``odoo.tests.Form`` no deja operar un campo invisible (``odoo/tests/form.py:855``). Por eso:

- la prueba de crear/editar/borrar maneja las filas de la pestaña nueva (lo que ve el usuario de la estructura general); el recálculo único lo hace
  ``HrPayslip.write`` en la rama de ``l10n_co_concepto_ids`` (``models/hr_payslip.py:771``);
- el camino de ``input_line_ids`` del .286 se prueba con el interruptor de la estructura APAGADO (es configuración por estructura: sin él la página
  nativa queda visible y el recibo no genera filas), con ``Form`` y con ``write({'input_line_ids': [...]})`` (lo que envía ``web_save``), que también
  usan el ORM y los asistentes. Así la prueba no depende del diario de otra estructura (``journal_id`` es un ``related`` de la estructura y la copia de
  la base solo lo trae en la general: ``Form`` exige el campo requerido al guardar)."""

from datetime import date
from unittest.mock import patch

from odoo import Command
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNovedadesDesdeElFormulario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Novedades Formulario'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Novedades Formulario', 'country_id': cls.env.ref('base.co').id})
        cls.est_general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.tipo_bonificacion = cls.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.n = 0

    def _recibo(self):
        """Recibo en espera con la hoja ya calculada (como el de QA) y sin novedades."""
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Formulario %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Formulario %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Formulario %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.est_general.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})
        recibo.compute_sheet()
        self.assertEqual(recibo.state, 'verify', 'Premisa: recibo «En espera»')
        return recibo

    def _linea(self, recibo):
        return recibo.line_ids.filtered(lambda l: l.code == 'CO_BONIF_NOSAL')

    def _fila(self, recibo):
        fila = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.salary_rule_id.code == 'CO_BONIF_NOSAL')
        self.assertEqual(len(fila), 1, 'Debe haber una fila de «Conceptos de pago» para CO_BONIF_NOSAL')
        return fila

    def _indice(self, recibo, fila):
        return recibo.l10n_co_concepto_ids.ids.index(fila.id)

    def _como_el_boton(self, recibo):
        """(neto, total de la línea) que da «Calcular hoja» sobre el estado actual del recibo; deja la hoja en ese estado."""
        recibo.compute_sheet()
        return recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))

    def _contando_calculos(self, recibo):
        original = type(recibo).compute_sheet
        llamadas = []

        def espia(slip):
            llamadas.append(slip.ids)
            return original(slip)

        return patch.object(type(recibo), 'compute_sheet', espia), llamadas

    def test_crear_editar_y_borrar_la_novedad_desde_la_pestana_conceptos_de_pago_recalcula_la_hoja(self):
        """Estructura general (con «Conceptos de pago»): la novedad se agrega, edita y borra como FILA de la pestaña nueva."""
        recibo = self._recibo()
        self.assertTrue(recibo.l10n_co_ne_usa_conceptos, 'Premisa: la estructura general usa «Conceptos de pago»')
        neto_inicial = recibo._ne_pdf_neto()
        self.assertFalse(self._linea(recibo), 'Premisa: sin la novedad no hay línea')

        # 1. Crear: «Agregar concepto» Bonificación No Salarial 300.000, guardar.
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.new() as fila:
                    fila.input_type_id = self.tipo_bonificacion
                    fila.amount = 300000.0
        neto_formulario, linea_formulario = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual(llamadas, [recibo.ids], 'Crear: UN recálculo por guardado, no cero ni dos')
        self.assertEqual(linea_formulario, 300000.0, 'Crear: la línea de la novedad debe existir con su valor')
        self.assertEqual(len(recibo.input_line_ids), 1, 'Crear: la fila creó UNA novedad del recibo')
        self.assertEqual(self._fila(recibo).origen, 'novedad', 'Crear: la fila regenerada es de novedad')
        self.assertNotAlmostEqual(neto_formulario, neto_inicial, places=2, msg='Crear: el neto debe cambiar')
        self.assertEqual((neto_formulario, linea_formulario), self._como_el_boton(recibo), 'Crear: igual que «Calcular hoja»')

        # 2. Editar: 250.000.
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.edit(self._indice(recibo, self._fila(recibo))) as fila:
                    fila.amount = 250000.0
        neto_formulario, linea_formulario = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual(llamadas, [recibo.ids], 'Editar: UN recálculo por guardado')
        self.assertEqual(linea_formulario, 250000.0, 'Editar: la línea debe valer el monto nuevo')
        self.assertEqual(recibo.input_line_ids.amount, 250000.0, 'Editar: se cambió la novedad, no se creó un ajuste')
        self.assertFalse(recibo.l10n_co_ajuste_ids, 'Editar una novedad no crea un ajuste de la empresa')
        self.assertEqual((neto_formulario, linea_formulario), self._como_el_boton(recibo), 'Editar: igual que «Calcular hoja»')

        # 3. Borrar: la hoja vuelve a la de antes de la novedad (no se paga una novedad que ya no existe).
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                formulario.l10n_co_concepto_ids.remove(self._indice(recibo, self._fila(recibo)))
        self.assertFalse(recibo.input_line_ids, 'Premisa: la novedad se borró')
        neto_formulario, linea_formulario = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual(llamadas, [recibo.ids], 'Borrar: UN recálculo por guardado')
        self.assertFalse(self._linea(recibo), 'Borrar: la línea de la novedad borrada no puede quedar en la hoja')
        self.assertFalse(recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id.code == 'CO_BONIF_NOSAL'), 'Borrar: la fila ya no existe')
        self.assertAlmostEqual(neto_formulario, neto_inicial, places=2, msg='Borrar: el neto vuelve al de antes de la novedad')
        self.assertEqual((neto_formulario, linea_formulario), self._como_el_boton(recibo), 'Borrar: igual que «Calcular hoja»')

    def test_con_el_interruptor_apagado_la_pagina_nativa_recalcula_al_crear_editar_y_borrar_por_el_formulario_y_por_write(self):
        """Camino de .286 (``web_save`` -> ``write({'input_line_ids': [...]})``): con el interruptor de la estructura apagado la página nativa de
        novedades queda visible y el recibo no genera filas de «Conceptos de pago». El interruptor se apaga dentro de la transacción de la prueba."""
        self.est_general.l10n_co_ne_conceptos_de_pago = False
        recibo = self._recibo()
        self.assertFalse(recibo.l10n_co_ne_usa_conceptos, 'Premisa: sin interruptor, página nativa visible')
        self.assertFalse(recibo.l10n_co_concepto_ids, 'Premisa: sin interruptor no hay filas de «Conceptos de pago»')
        neto_inicial = recibo._ne_pdf_neto()

        # 1. Formulario nativo: crear Bonificación No Salarial 300.000, editarla a 250.000 y borrarla (un recálculo por guardado, igual al botón).
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.input_line_ids.new() as novedad:
                    novedad.input_type_id = self.tipo_bonificacion
                    novedad.amount = 300000.0
        self.assertEqual(llamadas, [recibo.ids], 'Crear: UN recálculo por guardado')
        self.assertEqual(sum(self._linea(recibo).mapped('total')), 300000.0, 'Crear: la línea de la novedad debe existir con su valor')
        self.assertNotAlmostEqual(recibo._ne_pdf_neto(), neto_inicial, places=2, msg='Crear: el neto debe cambiar')
        neto_formulario, linea_formulario = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual((neto_formulario, linea_formulario), self._como_el_boton(recibo), 'Crear: igual que «Calcular hoja»')

        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.input_line_ids.edit(0) as novedad:
                    novedad.amount = 250000.0
        self.assertEqual(llamadas, [recibo.ids], 'Editar: UN recálculo por guardado')
        neto_formulario, linea_formulario = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual(linea_formulario, 250000.0, 'Editar: la línea debe valer el monto nuevo')
        self.assertEqual((neto_formulario, linea_formulario), self._como_el_boton(recibo), 'Editar: igual que «Calcular hoja»')

        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                formulario.input_line_ids.remove(0)
        self.assertEqual(llamadas, [recibo.ids], 'Borrar: UN recálculo por guardado')
        self.assertFalse(recibo.input_line_ids, 'Premisa: la novedad se borró')
        self.assertFalse(self._linea(recibo), 'Borrar: la línea de la novedad borrada no puede quedar en la hoja')
        self.assertAlmostEqual(recibo._ne_pdf_neto(), neto_inicial, places=2, msg='Borrar: el neto vuelve al de antes de la novedad')

        # 2. write con comandos (lo que envía web_save y lo que usan el ORM y los asistentes): el campo está protegido durante el write.
        recibo.write({'input_line_ids': [Command.create({'input_type_id': self.tipo_bonificacion.id, 'code': 'CO_BONIF_NOSAL', 'amount': 120000.0})]})
        self.assertEqual(sum(self._linea(recibo).mapped('total')), 120000.0, 'write(create): la línea debe existir con su valor')
        novedad = recibo.input_line_ids
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            recibo.write({'input_line_ids': [Command.update(novedad.id, {'amount': 700000.0})]})
        self.assertEqual(llamadas, [recibo.ids], 'write(update): UN recálculo')
        neto_write, linea_write = recibo._ne_pdf_neto(), sum(self._linea(recibo).mapped('total'))
        self.assertEqual(linea_write, 700000.0, 'write(update): la línea debe valer el monto nuevo')
        self.assertEqual((neto_write, linea_write), self._como_el_boton(recibo), 'write(update): igual que «Calcular hoja»')
        recibo.write({'input_line_ids': [Command.delete(novedad.id)]})
        self.assertFalse(recibo.input_line_ids, 'Premisa: la novedad se borró')
        self.assertFalse(self._linea(recibo), 'write(delete): la línea de la novedad borrada no puede quedar en la hoja')

    def test_guardar_el_formulario_sin_tocar_las_novedades_no_recalcula(self):
        """Solo cambian el cálculo las altas, bajas y cambios de monto o tipo de novedades: otro campo del formulario no dispara el recálculo."""
        recibo = self._recibo()
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                formulario.note = 'Observación de prueba'
        self.assertEqual(llamadas, [], 'Cambiar una nota no recalcula la hoja')
        self.assertEqual(recibo.note, 'Observación de prueba')

    def test_un_recibo_hecho_no_se_recalcula_al_editar_la_novedad_por_orm(self):
        """El camino por ORM directo de .283 sigue igual: crear la novedad fuera del ``write`` del recibo recalcula (una vez)."""
        recibo = self._recibo()
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            self.env['hr.payslip.input'].create({
                'payslip_id': recibo.id, 'input_type_id': self.tipo_bonificacion.id, 'code': 'CO_BONIF_NOSAL', 'amount': 120000.0})
        self.assertEqual(llamadas, [recibo.ids])
        self.assertEqual(sum(self._linea(recibo).mapped('total')), 120000.0)
