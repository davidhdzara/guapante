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

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils


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
        cls.co_state = cls.env['res.country.state'].search(
            [('country_id', '=', cls.co_country.id)], limit=1)
        if not cls.co_state:
            cls.co_state = cls.env['res.country.state'].create({
                'name': 'Departamento Prueba',
                'code': 'PT',
                'country_id': cls.co_country.id,
            })
        cls.co_city = cls.env['res.city'].create({
            'name': 'Ciudad Prueba Compañía',
            'state_id': cls.co_state.id,
            'country_id': cls.co_country.id,
        })
        # H-018 (2026-10-11): la "Dirección de Trabajo" de un empleado por defecto es la
        # de la compañía (hr.employee.address_id, compute nativo) -- país, departamento y
        # municipio deben estar completos aquí para que _ne_lugar_trabajo_partner() no
        # levante UserError en los tests que no tocan explícitamente el lugar de trabajo.
        cls.company.partner_id.write({
            'country_id': cls.co_country.id,
            'state_id': cls.co_state.id,
            'city_id': cls.co_city.id,
            'street': 'Calle Prueba Compañía # 1-1',
        })
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

    def _make_payslip(self, work_address=None):
        """H-018 (2026-10-11): el lugar de trabajo sale de employee.address_id (Dirección
        de Trabajo nativa), no de work_contact_id (ficha de contacto) -- `work_address`,
        si se pasa, es el partner que se asigna ahí, simulando un teletrabajador."""
        employee_vals = {
            'name': 'Empleado Prueba',
            'identification_id': '60' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        }
        employee = self.env['hr.employee'].create(employee_vals)
        # UX-02 (2026-10-11): _ne_tipo_documento() exige un tipo de documento con
        # equivalente DIAN en work_contact_id.
        employee.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_co.national_citizen_id').id
        if work_address is not None:
            employee.address_id = work_address.id
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
        """(a) Cero cambio para Guapante: mismos valores de siempre -- el empleado sin
        Dirección de Trabajo propia hereda la de la compañía (address_id, compute
        nativo), igual que antes de H-018."""
        payslip = self._make_payslip()
        data = payslip._collect_payslip_data()
        self.assertEqual(data['informacion_general']['TipoMoneda'], 'COP')
        self.assertEqual(data['lugar_generacion']['Pais'], 'CO')
        self.assertEqual(data['lugar_generacion']['Idioma'], 'es')
        self.assertEqual(data['empleador']['Pais'], 'CO')
        self.assertEqual(data['trabajador']['LugarTrabajoPais'], 'CO')

    def test_lugar_trabajo_default_usa_los_4_de_la_compania(self):
        """H-018 (2026-10-11), punto (a): un empleado sin Dirección de Trabajo propia
        hereda la de la compañía (address_id, compute nativo) -- los 4 atributos
        LugarTrabajo* deben coincidir con los 4 del partner de la compañía."""
        payslip = self._make_payslip()
        data = payslip._collect_payslip_data()
        self.assertEqual(data['trabajador']['LugarTrabajoPais'], self.co_country.code)
        self.assertEqual(
            data['trabajador']['LugarTrabajoDepartamentoEstado'],
            dian_utils.get_department_code(self.co_state))
        self.assertEqual(
            data['trabajador']['LugarTrabajoMunicipioCiudad'],
            dian_utils.get_city_code(self.co_city))
        self.assertEqual(
            data['trabajador']['LugarTrabajoDireccion'], self.company.partner_id.street)

    def test_lugar_trabajo_teletrabajador_usa_los_4_del_mismo_contacto(self):
        """H-018 (2026-10-11): un teletrabajador con su propia Dirección de Trabajo
        (employee.address_id distinto del de la compañía) debe mostrar los 4 atributos
        LugarTrabajo* de ESE contacto, nunca mezclados con los de la compañía."""
        otro_state = self.env['res.country.state'].search(
            [('country_id', '=', self.co_country.id), ('id', '!=', self.co_state.id)],
            limit=1) or self.co_state
        otra_ciudad = self.env['res.city'].create({
            'name': 'Ciudad Prueba Teletrabajador',
            'state_id': otro_state.id,
            'country_id': self.co_country.id,
        })
        work_address = self.env['res.partner'].create({
            'name': 'Dirección de Trabajo Teletrabajador',
            'country_id': self.co_country.id,
            'state_id': otro_state.id,
            'city_id': otra_ciudad.id,
            'street': 'Calle Teletrabajador # 2-2',
        })
        payslip = self._make_payslip(work_address=work_address)
        data = payslip._collect_payslip_data()
        self.assertEqual(data['trabajador']['LugarTrabajoPais'], 'CO')
        self.assertEqual(
            data['trabajador']['LugarTrabajoDepartamentoEstado'],
            dian_utils.get_department_code(otro_state))
        self.assertEqual(
            data['trabajador']['LugarTrabajoMunicipioCiudad'],
            dian_utils.get_city_code(otra_ciudad))
        self.assertEqual(data['trabajador']['LugarTrabajoDireccion'], 'Calle Teletrabajador # 2-2')
        # El resto (compañía) sigue intacto -- solo cambia el dato del trabajador.
        self.assertEqual(data['empleador']['Pais'], 'CO')

    def test_lugar_trabajo_sin_municipio_levanta_usererror(self):
        """H-018 (2026-10-11): antes, un lugar de trabajo en el exterior (sin municipio/
        departamento DANE, ej. México) caía en silencio al municipio de la COMPAÑÍA --
        el mismo defecto que esta corrección cierra. Ahora, sin departamento/municipio en
        el partner de la Dirección de Trabajo, el XML falla explícito en vez de inventar
        un dato."""
        if not self.mx_country:
            self.skipTest('res.country MX no disponible en esta base')
        work_address = self.env['res.partner'].create({
            'name': 'Lugar de Trabajo Exterior Prueba',
            'country_id': self.mx_country.id,
        })
        payslip = self._make_payslip(work_address=work_address)
        with self.assertRaises(UserError) as exc:
            payslip._collect_payslip_data()
        mensaje = str(exc.exception).lower()
        self.assertIn('departamento', mensaje)
        self.assertIn('municipio', mensaje)
        self.assertIn('empleado prueba', mensaje)

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
