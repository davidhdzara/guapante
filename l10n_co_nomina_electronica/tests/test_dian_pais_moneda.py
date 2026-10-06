# -*- coding: utf-8 -*-
"""Corrección 5 (AUD-DIAN-34, 2026-10-05): TipoMoneda e Idioma son constantes del Anexo
Técnico ("Para Colombia se debe colocar 'COP'"/"'es'", NIE030/LugarGeneracionXML) -- no se
parametrizan, pero una compañía en otra moneda debe fallar explícito en vez de enviar "COP"
sobre montos que no están en pesos. Pais/LugarTrabajoPais SÍ admiten cualquier código alfa-2
(el Anexo no los fija a Colombia, NIE013/NIE035/NIE050) -- se derivan del país real de la
compañía/trabajador, nunca un 'CO' inventado.

(a) mismo valor de siempre para una compañía colombiana (cero cambio para Guapante).
(b) compañía con moneda distinta de COP -> UserError claro, no un XML con "COP" mentido.
"""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class _FakeCertificate:
    """Doble mínimo: solo necesita ser verdadero y no estar vencido (mismo doble que
    test_dian_matching.py/test_dian_status_recheck.py)."""
    date_end = False

    def __bool__(self):
        return True


class TestDianPaisMoneda(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not cls.co_country:
            cls.co_country = cls.env.ref('base.co')
        cls.mx_country = cls.env['res.country'].search([('code', '=', 'MX')], limit=1)
        cop_currency = cls.env['res.currency'].search([('name', '=', 'COP')], limit=1)
        usd_currency = cls.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        if not usd_currency:
            usd_currency = cls.env.ref('base.USD')
        cls.cop_currency = cop_currency
        cls.usd_currency = usd_currency

        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba País/Moneda',
            'currency_id': cls.cop_currency.id,
        })
        cls.company.partner_id.country_id = cls.co_country.id
        # Resto de la configuración de nómina electrónica completa, para que la única
        # causa posible de UserError en _validate_company_ne_config() sea la moneda --
        # si no, "Faltan los siguientes datos..." (software ID/certificado) la enmascararía.
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id,
            'software_id': 'SOFTWARE-TEST-ID',
            'software_pin': 'PIN-TEST',
        })

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura País/Moneda',
            'country_id': cls.co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba País/Moneda',
            'type_id': cls.structure_type.id,
        })

    def setUp(self):
        super().setUp()
        self.cert_patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.res_company.'
            'ResCompany._get_ne_certificate',
            return_value=_FakeCertificate(),
        )
        self.cert_patcher.start()
        self.addCleanup(self.cert_patcher.stop)

    def _make_payslip(self, employee_country=None):
        employee_vals = {
            'name': 'Empleado Prueba',
            'identification_id': '60' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        }
        employee = self.env['hr.employee'].create(employee_vals)
        if employee_country:
            work_contact = self.env['res.partner'].create({
                'name': 'Lugar de Trabajo Prueba',
                'country_id': employee_country.id,
            })
            employee.work_contact_id = work_contact.id
        contract = self.env['hr.contract'].create({
            'name': 'Contrato Prueba',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        return self.env['hr.payslip'].create({
            'name': 'Nómina Prueba',
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })

    def test_pais_idioma_moneda_sin_cambio_para_compania_colombiana(self):
        """(a) Cero cambio para Guapante: mismos valores de siempre."""
        payslip = self._make_payslip()
        data = payslip._collect_payslip_data()
        self.assertEqual(data['informacion_general']['TipoMoneda'], 'COP')
        self.assertEqual(data['lugar_generacion']['Pais'], 'CO')
        self.assertEqual(data['lugar_generacion']['Idioma'], 'es')
        self.assertEqual(data['empleador']['Pais'], 'CO')
        self.assertEqual(data['trabajador']['LugarTrabajoPais'], 'CO')

    def test_lugar_trabajo_pais_usa_el_dato_real_del_trabajador_si_existe(self):
        """LugarTrabajoPais NO está fijo a 'CO' -- si el trabajador tiene un lugar de
        trabajo real en otro país, el XML debe reflejarlo."""
        if not self.mx_country:
            self.skipTest('res.country MX no disponible en esta base')
        payslip = self._make_payslip(employee_country=self.mx_country)
        data = payslip._collect_payslip_data()
        self.assertEqual(data['trabajador']['LugarTrabajoPais'], 'MX')
        # El resto (compañía) sigue siendo Colombia -- solo cambia el dato del trabajador.
        self.assertEqual(data['empleador']['Pais'], 'CO')

    def test_compania_con_moneda_distinta_de_cop_falla_explicito(self):
        """(b) El Anexo Técnico fija TipoMoneda="COP" para Colombia (NIE030) -- una
        compañía en otra moneda debe fallar antes de generar el XML, no enviar "COP" sobre
        montos que no están en pesos. Resto de la config completa (certificado/software
        mockeados arriba): la única causa posible de error aquí es la moneda."""
        self.company.currency_id = self.usd_currency.id
        with self.assertRaises(UserError) as exc:
            self.env['hr.payslip']._validate_company_ne_config(self.company)
        self.assertIn('moneda', str(exc.exception).lower())
        self.assertIn('COP', str(exc.exception))

    def test_compania_con_cop_no_falla_por_moneda(self):
        """Control: con la misma config completa, una compañía en COP no debe lanzar
        ningún UserError -- confirma que el chequeo nuevo no afecta el caso normal."""
        self.company.currency_id = self.cop_currency.id
        self.env['hr.payslip']._validate_company_ne_config(self.company)
