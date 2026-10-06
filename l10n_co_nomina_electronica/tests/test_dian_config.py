# -*- coding: utf-8 -*-
"""Corrección 4 (AUD-DIAN-34, 2026-10-05): un solo punto para las URL de la DIAN por
ambiente ('1' producción, '2' habilitación) y para los 3 tiempos fijos (SOAP_TIMEOUT,
tick/timeout del motor de habilitación), ahora configurables vía ir.config_parameter sin
cambiar ningún valor por defecto -- antes las URL estaban repetidas en 3 sitios
(services/dian_utils.py, services/soap_client.py, models/hr_payslip.py) y los tiempos
hardcodeados en 2 archivos distintos.

Dos niveles de prueba:
- TestDianUtilsUrlsPure (unittest.TestCase, sin DB): dian_utils.get_soap_endpoint()/
  get_qr_catalog_host()/parse_positive_int() son funciones puras -- se prueban solas.
- TestResCompanyDianConfig (TransactionCase): ResCompany._ne_dian_endpoint()/
  _ne_dian_qr_host()/_ne_config_int_param() leyendo ir.config_parameter de verdad.
"""

import unittest

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils
from odoo.tests.common import TransactionCase


class TestDianUtilsUrlsPure(unittest.TestCase):
    """(a)/(b) del criterio de aceptación, a nivel de la función pura."""

    def test_soap_endpoint_defaults_unchanged(self):
        """Mismos valores que estaban hardcodeados antes -- esta corrección no cambia ninguno."""
        self.assertEqual(
            dian_utils.get_soap_endpoint('1'),
            'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc')
        self.assertEqual(
            dian_utils.get_soap_endpoint('2'),
            'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc')

    def test_qr_catalog_host_defaults_unchanged(self):
        self.assertEqual(dian_utils.get_qr_catalog_host('1'), 'catalogo-vpfe.dian.gov.co')
        self.assertEqual(dian_utils.get_qr_catalog_host('2'), 'catalogo-vpfe-hab.dian.gov.co')

    def test_soap_endpoint_override_wins(self):
        self.assertEqual(
            dian_utils.get_soap_endpoint('1', override='https://otro.example.com'),
            'https://otro.example.com')

    def test_qr_catalog_host_override_wins(self):
        self.assertEqual(
            dian_utils.get_qr_catalog_host('2', override='otro-host.example.com'),
            'otro-host.example.com')

    def test_parse_positive_int_valid_value(self):
        self.assertEqual(dian_utils.parse_positive_int('30', 45, 'x'), 30)

    def test_parse_positive_int_none_uses_default(self):
        self.assertEqual(dian_utils.parse_positive_int(None, 45, 'x'), 45)

    def test_parse_positive_int_non_numeric_uses_default(self):
        """Parámetro inválido -> defecto (nunca revienta un envío por una config mal escrita)."""
        self.assertEqual(dian_utils.parse_positive_int('abc', 45, 'x'), 45)

    def test_parse_positive_int_zero_or_negative_uses_default(self):
        self.assertEqual(dian_utils.parse_positive_int('0', 45, 'x'), 45)
        self.assertEqual(dian_utils.parse_positive_int('-5', 45, 'x'), 45)


class TestResCompanyDianConfig(TransactionCase):
    """(b)/(c) del criterio de aceptación: ResCompany lee de verdad ir.config_parameter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Config DIAN',
        })

    def _set_param(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param(key, value)

    def test_endpoint_default_matches_environment_when_no_override(self):
        self.company.l10n_co_ne_environment = '1'
        self.assertEqual(
            self.company._ne_dian_endpoint(),
            'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc')
        self.company.l10n_co_ne_environment = '2'
        self.assertEqual(
            self.company._ne_dian_endpoint(),
            'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc')

    def test_endpoint_explicit_environment_overrides_company_setting(self):
        """action_send_test_set() siempre apunta a habilitación, sin importar el ambiente
        configurado en la compañía (ver models/hr_payslip.py)."""
        self.company.l10n_co_ne_environment = '1'
        self.assertEqual(
            self.company._ne_dian_endpoint(environment='2'),
            'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc')

    def test_endpoint_overridden_by_config_parameter(self):
        self.company.l10n_co_ne_environment = '2'
        self._set_param(
            'l10n_co_nomina_electronica.dian_soap_endpoint_2',
            'https://otro-endpoint.example.com')
        self.assertEqual(
            self.company._ne_dian_endpoint(), 'https://otro-endpoint.example.com')

    def test_qr_host_overridden_by_config_parameter(self):
        self.company.l10n_co_ne_environment = '1'
        self._set_param(
            'l10n_co_nomina_electronica.dian_qr_host_1', 'otro-catalogo.example.com')
        self.assertEqual(self.company._ne_dian_qr_host(), 'otro-catalogo.example.com')

    def test_int_param_default_when_unset(self):
        self._set_param('l10n_co_nomina_electronica.soap_timeout_seconds', '')
        self.assertEqual(
            self.company._ne_config_int_param(
                'l10n_co_nomina_electronica.soap_timeout_seconds', 45), 45)

    def test_int_param_overridden_by_config_parameter(self):
        self._set_param('l10n_co_nomina_electronica.habilitacion_tick_seconds', '5')
        self.assertEqual(
            self.company._ne_config_int_param(
                'l10n_co_nomina_electronica.habilitacion_tick_seconds', 20), 5)

    def test_int_param_invalid_falls_back_to_default(self):
        self._set_param(
            'l10n_co_nomina_electronica.habilitacion_timeout_minutes', 'no-es-un-numero')
        self.assertEqual(
            self.company._ne_config_int_param(
                'l10n_co_nomina_electronica.habilitacion_timeout_minutes', 45), 45)
