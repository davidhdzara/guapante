# -*- coding: utf-8 -*-
"""UX-02 (2026-10-11, decisión de David + Tech Lead), parte (a): el atributo
TipoDocumento del nodo <Trabajador> ya no sale de un Selection propio
(l10n_co_ne_document_type, retirado) -- sale del tipo de identificación nativo
de Contactos (employee.work_contact_id.l10n_latam_identification_type_id), vía
el código DIAN que l10n_latam.identification.type.l10n_co_ne_dian_document_code
guarda como dato (data/l10n_latam_identification_type_dian_code_data.xml).

Cálculo a mano (tabla 5.1 del Anexo Técnico, confirmada contra los datos reales
de l10n_co.l10n_latam.identification.type.csv): civil_registration=11,
id_card=12, national_citizen_id=13, foreign_colombian_card=21,
foreign_resident_card=22, rut=31, l10n_latam_base.it_pass=41,
residence_document=47, l10n_co.48 (PPT)=48, external_id=50, niup_id=91.
foreign_id_card (l10n_latam_base.it_fid, "Cédula Extranjera" genérico LATAM) y
l10n_latam_base.it_vat ("VAT" genérico) quedan sin código DIAN a propósito.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestTipoDocumentoDian(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Tipo Documento',
        })
        cls.co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not cls.co_country:
            cls.co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Tipo Documento',
            'country_id': cls.co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Tipo Documento',
            'type_id': cls.structure_type.id,
        })

    def _make_payslip(self, name):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '90' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })

    def test_tipo_documento_cedula_ciudadania_codigo_13(self):
        payslip = self._make_payslip('CedulaCiudadania')
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.national_citizen_id').id
        self.assertEqual(payslip._ne_tipo_documento(), '13')

    def test_tipo_documento_nit_codigo_31(self):
        payslip = self._make_payslip('Nit')
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.rut').id
        self.assertEqual(payslip._ne_tipo_documento(), '31')

    def test_tipo_documento_pasaporte_codigo_41(self):
        payslip = self._make_payslip('Pasaporte')
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_latam_base.it_pass').id
        self.assertEqual(payslip._ne_tipo_documento(), '41')

    def test_tipo_documento_ppt_codigo_48(self):
        payslip = self._make_payslip('Ppt')
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.48').id
        self.assertEqual(payslip._ne_tipo_documento(), '48')

    def test_tipo_documento_sin_tipo_levanta_usererror(self):
        """Sin tipo de documento configurado en work_contact_id: UserError que nombra
        al empleado, nunca un '13' inventado como hacía el default silencioso anterior."""
        payslip = self._make_payslip('SinTipo')
        self.assertFalse(payslip.employee_id.l10n_co_ne_identification_type_id)
        with self.assertRaises(UserError) as exc:
            payslip._ne_tipo_documento()
        self.assertIn('SinTipo', str(exc.exception))

    def test_tipo_documento_sin_equivalente_dian_levanta_usererror(self):
        """foreign_id_card ("Cédula Extranjera", tipo genérico de l10n_latam_base para
        otros países LATAM) no tiene código DIAN -- debe fallar igual que sin tipo,
        nunca inventar un código."""
        payslip = self._make_payslip('SinEquivalente')
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_latam_base.it_fid').id
        with self.assertRaises(UserError) as exc:
            payslip._ne_tipo_documento()
        self.assertIn('SinEquivalente', str(exc.exception))

    def test_identification_type_id_escribe_en_work_contact_id(self):
        """El related editable debe escribir de verdad en work_contact_id (inverse con
        sudo, ver _inverse_l10n_co_ne_identification_type_id) -- no solo quedarse en el
        empleado."""
        payslip = self._make_payslip('Sincroniza')
        employee = payslip.employee_id
        self.assertTrue(
            employee.work_contact_id,
            'hr nativo debe haber creado work_contact_id al crear el empleado.',
        )
        employee.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.id_card').id
        self.assertEqual(
            employee.work_contact_id.l10n_latam_identification_type_id,
            self.env.ref('l10n_co.id_card'),
        )

    def test_identification_type_id_lee_de_work_contact_id(self):
        """En el otro sentido: si el tipo se cambia directo en Contactos (ej. desde la
        ficha del partner), el related del empleado debe reflejarlo sin tocar nada más."""
        payslip = self._make_payslip('LeeDeContactos')
        employee = payslip.employee_id
        employee.work_contact_id.l10n_latam_identification_type_id = self.env.ref(
            'l10n_co.foreign_resident_card').id
        self.assertEqual(
            employee.l10n_co_ne_identification_type_id,
            self.env.ref('l10n_co.foreign_resident_card'),
        )

    def test_tipo_documento_en_xml_trabajador_end_to_end(self):
        """Prueba end-to-end: _collect_payslip_data()['trabajador']['TipoDocumento']
        debe traer el mismo código que _ne_tipo_documento() -- confirma que
        _ne_trabajador() de verdad usa esta fuente."""
        payslip = self._make_payslip('EndToEnd')
        co_state = self.env['res.country.state'].search(
            [('country_id', '=', self.co_country.id)], limit=1)
        if not co_state:
            co_state = self.env['res.country.state'].create({
                'name': 'Departamento Prueba TipoDocumento',
                'code': 'PD',
                'country_id': self.co_country.id,
            })
        co_city = self.env['res.city'].create({
            'name': 'Ciudad Prueba TipoDocumento',
            'state_id': co_state.id,
            'country_id': self.co_country.id,
        })
        # H-018: _ne_lugar_trabajo_partner() exige la Dirección de Trabajo completa
        # (aquí, la de la compañía, que hereda el empleado por defecto) antes de
        # llegar a TipoDocumento dentro de la misma _ne_trabajador().
        self.company.partner_id.write({
            'country_id': self.co_country.id,
            'state_id': co_state.id,
            'city_id': co_city.id,
            'street': 'Calle Prueba TipoDocumento # 1-1',
        })
        payslip.employee_id.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.national_citizen_id').id
        data = payslip._collect_payslip_data()
        self.assertEqual(data['trabajador']['TipoDocumento'], '13')
        self.assertEqual(data['trabajador']['TipoDocumento'], payslip._ne_tipo_documento())
