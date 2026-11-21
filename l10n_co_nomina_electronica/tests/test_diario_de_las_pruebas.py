# -*- coding: utf-8 -*-
"""Pieza .296 (solo pruebas): las pruebas con ``odoo.tests.Form`` ya no dependen del «Diario de salarios» que traiga la base donde corren.

``journal_id`` del recibo es un ``related`` de la estructura (``hr_payslip.py:16``) y ``required`` en la vista (``hr_payslip_views.xml:36``); ``Form``
lo exige al guardar (``odoo/tests/form.py:506``). Estas pruebas simulan una base SIN el diario en la estructura y comprueban que ``tests/common_diario.py``
basta. NO EJECUTADAS en Odoo al escribirlas."""

from datetime import date

from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

from .common_diario import fijar_diario_de_salarios


@tagged('post_install', '-at_install')
class TestDiarioDeLasPruebas(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Diario de Pruebas'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Diario', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.bonificacion = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')

    def _recibo(self, estructura):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Diario de Pruebas',
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Diario de Pruebas', 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Recibo Diario de Pruebas', 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': estructura.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})

    def test_01_el_diario_es_general_de_la_compania_del_entorno_y_lo_lee_cada_estructura(self):
        diario = fijar_diario_de_salarios(self.env, self.general, self.bonificacion)
        self.assertEqual((diario.type, diario.company_id), ('general', self.env.company))
        for estructura in (self.general, self.bonificacion):
            self.assertEqual(estructura.with_company(self.env.company).journal_id, diario, estructura.name)

    def test_02_el_formulario_del_recibo_guarda_aunque_la_base_no_traiga_el_diario(self):
        for estructura in (self.general, self.bonificacion):
            estructura.with_company(self.env.company).journal_id = False        # una base sin el diario de salarios en la estructura
            self.assertFalse(estructura.with_company(self.env.company).journal_id, 'Premisa: la estructura no trae diario')
        diario = fijar_diario_de_salarios(self.env, self.general, self.bonificacion)
        for estructura in (self.general, self.bonificacion):
            recibo = self._recibo(estructura)
            self.assertEqual(recibo.journal_id, diario, 'El recibo lo lee de su estructura: %s' % estructura.name)
            with Form(recibo) as formulario:
                formulario.note = 'Guardado sin depender del diario de la base'
            self.assertEqual(recibo.note, 'Guardado sin depender del diario de la base', estructura.name)
