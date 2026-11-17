# -*- coding: utf-8 -*-
"""Frente 4, U6 (doc 57 §11): oficio de respuesta a la UGPP (código 9006). Datos de Contactos, de la compañía y del
reporte; sin valores por defecto. El módulo no firma ni radica. Nivel de verificación: datos y errores; el PDF se mira en
pantalla (UAT F4)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp


@tagged('post_install', '-at_install')
class TestUgppOficio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Oficio UGPP', 'country_id': cls.env.ref('base.co').id, 'vat': '900123456-8',
            'email': 'notificaciones@oficio.example.com', 'street': 'Calle 1 # 2-3', 'city': 'Bogotá',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        cls.representante = cls.env['res.partner'].create({
            'name': 'Representante Legal Prueba', 'vat': '1020304050',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_co.national_citizen_id').id})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Oficio', 'country_id': cls.env.ref('base.co').id,
            'default_schedule_pay': 'bi-weekly'})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Oficio', 'company_id': cls.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato Oficio', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        cls.recibo = cls.env['hr.payslip'].create({
            'name': 'Recibo Oficio', 'employee_id': cls.empleado.id, 'contract_id': cls.contrato.id,
            'company_id': cls.company.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        cls.recibo.write({'state': 'done', 'paid_date': date(2026, 9, 30)})
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id, 'requerimiento_radicado': '2026-RAD-123',
            'requerimiento_fecha': date(2026, 10, 6)})
        cls.company.l10n_co_ne_representante_legal_id = cls.representante

    def test_datos_completos_del_oficio(self):
        datos = self.reporte._ugpp_datos_oficio()
        self.assertEqual(datos['nit'], '9001234568')
        self.assertEqual(datos['representante'], self.representante)
        self.assertIn('1020304050', datos['representante_documento'])
        self.assertEqual(datos['periodo'], 'Septiembre de 2026')
        self.assertEqual(datos['correo'], 'notificaciones@oficio.example.com')
        self.assertIn('Bogotá', datos['direccion'])
        self.assertEqual(len(datos['calendarios']), 1)                 # la periodicidad sale del contrato (nativo)
        self.assertEqual(datos['nota_360'], ugpp._UGPP_NOTA_360)

    def test_sin_representante_legal_el_oficio_falla_nombrando_la_compania(self):
        self.company.l10n_co_ne_representante_legal_id = False
        with self.assertRaises(UserError) as exc:
            self.reporte._ugpp_datos_oficio()
        self.assertIn('Empresa Oficio UGPP', str(exc.exception))
        self.assertIn('representante legal', str(exc.exception))

    def test_representante_sin_identificacion_falla(self):
        sin_id = self.env['res.partner'].create({'name': 'Sin Identificación'})
        self.company.l10n_co_ne_representante_legal_id = sin_id
        with self.assertRaisesRegex(UserError, 'Sin Identificación'):
            self.reporte._ugpp_datos_oficio()

    def test_sin_radicado_o_fecha_del_requerimiento_falla(self):
        self.reporte.requerimiento_radicado = False
        with self.assertRaisesRegex(UserError, 'radicado y la fecha'):
            self.reporte._ugpp_datos_oficio()

    def test_sin_recibos_del_periodo_falla(self):
        self.recibo.state = 'draft'
        with self.assertRaisesRegex(UserError, 'recibos confirmados'):
            self.reporte._ugpp_datos_oficio()

    def test_el_texto_de_ajustes_es_borrador_y_la_certificacion_no_se_genera(self):
        self.assertIn('Ajustes', self.env.ref('l10n_co_nomina_electronica.report_ugpp_oficio').arch)
        self.assertFalse(self.env['ir.actions.report'].search([('name', 'ilike', 'Certificación de información')]))

    def test_el_boton_devuelve_el_pdf_del_oficio(self):
        accion = self.reporte.action_imprimir_oficio()
        self.assertEqual(accion['report_name'], 'l10n_co_nomina_electronica.report_ugpp_oficio')
        self.assertEqual(accion['type'], 'ir.actions.report')

    def test_el_oficio_lista_las_fechas_de_pago_reales_de_los_recibos(self):
        # Pagos los 5 y 20 (no caben en la periodicidad nativa): se leen de los recibos, sin campo nuevo.
        segundo = self.env['hr.payslip'].create({
            'name': 'Recibo Oficio 2', 'employee_id': self.empleado.id, 'contract_id': self.contrato.id,
            'company_id': self.company.id, 'struct_id': self.recibo.struct_id.id,
            'date_from': date(2026, 9, 6), 'date_to': date(2026, 9, 20)})
        segundo.write({'state': 'done', 'paid_date': date(2026, 9, 20)})
        self.recibo.paid_date = date(2026, 9, 5)
        self.assertEqual(self.reporte._ugpp_datos_oficio()['fechas_pago'], ['05/09/2026', '20/09/2026'])

    def test_un_recibo_sin_fecha_de_pago_hace_fallar_el_oficio_nombrandolo(self):
        self.recibo.paid_date = False
        with self.assertRaisesRegex(UserError, 'Recibo Oficio'):
            self.reporte._ugpp_datos_oficio()

