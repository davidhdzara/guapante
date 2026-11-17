# -*- coding: utf-8 -*-
"""Frente 6, P6-5 (doc 59 5, F6-INE-001): los informes de colilla y comprobante estan en el menu Imprimir de TODO recibo;
para una compania que no es colombiana (Mexico) el modulo no imprime ni envia: error claro que nombra la compania."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInerciaInformes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mx = cls.env['res.company'].create({
            'country_id': cls.env.ref('base.mx').id, 'name': 'Empresa Mexicana Informes'})
        tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Inercia Informes', 'country_id': cls.env.ref('base.mx').id})
        struct = cls.env['hr.payroll.structure'].create({
            'name': 'Estructura MX Informes', 'type_id': tipo.id, 'country_id': cls.env.ref('base.mx').id})
        empleado = cls.env['hr.employee'].create({
            'name': 'Empleado MX Informes', 'company_id': cls.mx.id,
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'})
        contrato = cls.env['hr.contract'].create({
            'name': 'Contrato MX Informes', 'employee_id': empleado.id, 'company_id': cls.mx.id,
            'structure_type_id': tipo.id, 'wage': 1000000.0, 'date_start': date(2026, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        cls.recibo = cls.env['hr.payslip'].create({
            'name': 'Recibo MX Informes', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': cls.mx.id, 'struct_id': struct.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})

    def test_colilla_y_comprobante_no_se_imprimen_para_otra_compania(self):
        for nombre in ('report_payslip_ne', 'report_comprobante_pago'):
            modelo = self.env['report.l10n_co_nomina_electronica.%s' % nombre]
            with self.assertRaisesRegex(UserError, 'Empresa Mexicana Informes'):
                modelo._get_report_values(self.recibo.ids)

    def test_el_correo_del_comprobante_no_se_envia_para_otra_compania(self):
        with self.assertRaisesRegex(UserError, 'Empresa Mexicana Informes'):
            self.recibo.action_send_comprobante_email()
