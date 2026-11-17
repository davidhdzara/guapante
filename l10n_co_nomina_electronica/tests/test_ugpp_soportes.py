# -*- coding: utf-8 -*-
"""Frente 4, U6b (doc 57 §11.4): paquete de PDF por trabajador (art. 3 de la Res. 858; Guía V-20.1 §2.3). Solo con los
adjuntos PDF que existen (contrato, empleado, contacto de trabajo, planillas PILA); lo que falta se lista y NO es un
error."""
import io
import zipfile
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp

PDF = b'%PDF-1.4 prueba'


@tagged('post_install', '-at_install')
class TestUgppSoportes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Soportes UGPP', 'country_id': cls.env.ref('base.co').id, 'vat': '900123456-8',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Soportes', 'country_id': cls.env.ref('base.co').id})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Soportes', 'company_id': cls.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato Soportes', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        cls.recibo = cls.env['hr.payslip'].create({
            'name': 'Recibo Soportes', 'employee_id': cls.empleado.id, 'contract_id': cls.contrato.id,
            'company_id': cls.company.id, 'struct_id': cls.estructura.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        cls.recibo.state = 'done'
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id})

    def _adjunto(self, modelo, res_id, nombre='doc', mimetype='application/pdf', raw=PDF):
        return self.env['ir.attachment'].create({
            'name': nombre, 'res_model': modelo, 'res_id': res_id, 'mimetype': mimetype, 'raw': raw})

    def _soporte(self):
        soportes = self.reporte._ugpp_soportes(self.recibo)
        self.assertEqual(len(soportes), 1)
        return soportes[0]

    def test_sin_adjuntos_se_listan_faltantes_y_no_es_error(self):
        item = self._soporte()
        self.assertFalse(item['adjuntos'])
        self.assertEqual(len(item['faltan']), 2)
        self.assertIn('falta el contrato laboral', item['faltan'][0])
        self.assertIn('planilla PILA', item['faltan'][1])

    def test_los_pdf_del_contrato_del_empleado_y_del_contacto_se_incluyen_y_otros_tipos_no(self):
        self._adjunto('hr.contract', self.contrato.id, 'contrato')
        self._adjunto('hr.employee', self.empleado.id, 'cedula')
        self._adjunto('res.partner', self.empleado.work_contact_id.id, 'rut')
        self._adjunto('hr.employee', self.empleado.id, 'foto', mimetype='image/png', raw=b'x')
        item = self._soporte()
        self.assertEqual(sorted(tipo for tipo, _a in item['adjuntos']), ['contacto', 'contrato', 'empleado'])
        self.assertEqual(len(item['faltan']), 1)                         # solo falta la planilla PILA
        self.assertNotIn('contrato laboral', item['faltan'][0])

    def test_la_planilla_pila_del_trabajador_en_el_mes_y_su_pdf(self):
        planilla = self.env['l10n.co.pila.planilla'].create({
            'company_id': self.company.id, 'period': date(2026, 9, 1), 'tipo_planilla': 'E', 'operador_code': 'X'})
        self.env['l10n.co.ibc.mensual'].create({
            'company_id': self.company.id, 'employee_id': self.empleado.id, 'period': date(2026, 9, 1),
            'planilla_id': planilla.id})
        self._adjunto('l10n.co.pila.planilla', planilla.id, 'planilla')
        item = self._soporte()
        self.assertEqual([tipo for tipo, _a in item['adjuntos']], ['planilla'])
        self.assertTrue(all('planilla PILA' not in f for f in item['faltan']))

    def test_nombre_con_la_identificacion_sin_caracteres_especiales_y_maximo_50(self):
        nombre = self.reporte._ugpp_nombre_soporte(self.empleado, 'contrato', 1)
        self.assertEqual(nombre, '1020304050_contrato.pdf')
        self.assertEqual(self.reporte._ugpp_nombre_soporte(self.empleado, 'contacto', 2), '1020304050_contacto_2.pdf')
        virtual = self.env['hr.employee'].new({'identification_id': 'AB-12.34 #' + '9' * 60})   # sin tocar el contacto
        largo = self.reporte._ugpp_nombre_soporte(virtual, 'contrato', 1)
        self.assertLessEqual(len(largo), 50)
        self.assertTrue(largo.endswith('.pdf'))
        self.assertNotRegex(largo[:-4], r'[^A-Za-z0-9_]')

    def test_el_boton_arma_el_zip_y_el_resumen(self):
        self._adjunto('hr.contract', self.contrato.id, 'contrato')
        self._adjunto('res.partner', self.empleado.work_contact_id.id, 'rut')
        accion = self.reporte.action_generar_soportes()
        self.assertEqual(accion['type'], 'ir.actions.act_url')
        import base64
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(self.reporte.soportes_file))) as zf:
            self.assertEqual(sorted(zf.namelist()), ['1020304050_contacto.pdf', '1020304050_contrato.pdf'])
        self.assertIn('Empleado Soportes', self.reporte.soportes_resumen)
        self.assertIn('no es un error del módulo', self.reporte.soportes_resumen)

    def test_aviso_si_los_soportes_pasan_de_100_mb(self):
        self._adjunto('hr.contract', self.contrato.id, 'contrato')
        with patch.object(ugpp, '_UGPP_MAX_BYTES_SOPORTES', 1):
            self.reporte.action_generar_soportes()
        self.assertIn('100 MB', self.reporte.soportes_resumen)
