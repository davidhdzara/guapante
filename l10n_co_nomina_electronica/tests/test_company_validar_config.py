# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""``res.company._l10n_co_ne_validar_config()`` (doc 53 §23.13, etapa 4 commit 3).

La validación de la configuración de nómina electrónica pasó del mixin del recibo
(``_validate_company_ne_config(company)``) a la compañía. Mismos chequeos, mismo orden, mismos
mensajes: el envoltorio del mixin llama al método de la compañía y el recibo se comporta igual.
Las pruebas existentes de la validación por el recibo (``test_dian_pais_moneda``) siguen intactas.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


class _Certificado:
    """Doble mínimo del certificado: verdadero y con ``date_end`` configurable."""

    def __init__(self, date_end=False):
        self.date_end = date_end

    def __bool__(self):
        return True


@tagged('post_install', '-at_install')
class TestCompanyValidarConfig(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cop = cls.env['res.currency'].search([('name', '=', 'COP')], limit=1)
        cls.usd = cls.env['res.currency'].search([('name', '=', 'USD')], limit=1) or cls.env.ref('base.USD')
        cls.co = cls.env['res.country'].search([('code', '=', 'CO')], limit=1) or cls.env.ref('base.co')
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía Validación Config', 'country_id': cls.co.id, 'currency_id': cop.id})
        cls.modo = cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SW-ID-TEST', 'software_pin': 'PIN-TEST'})

    def _con_certificado(self, certificado):
        patcher = patch(
            'odoo.addons.l10n_co_nomina_electronica.models.res_company.ResCompany._get_ne_certificate',
            lambda s: certificado)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_configuracion_completa_no_lanza(self):
        self._con_certificado(_Certificado())
        self.company._l10n_co_ne_validar_config()

    # ``software_id`` y ``software_pin`` son ``required=True``, pero en Odoo eso es solo NOT NULL en la base: la cadena
    # vacía pasa (código, API, importación; solo la interfaz la impide). Por eso "falta solo el ID" o "falta solo el PIN"
    # SÍ se puede provocar con '' y el validador lo bloquea (doc 53 §23.15 corregido). NO simplificar a ``not mode``.
    def test_falta_solo_el_certificado(self):
        self._con_certificado(False)
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('Certificado Digital', mensaje)
        self.assertNotIn('ID Software Nómina', mensaje)
        self.assertNotIn('PIN Software Nómina', mensaje)
        self.assertIn(self.company.name, mensaje)

    def test_modo_con_software_id_vacio_falta_solo_el_id(self):
        """'' pasa el NOT NULL: sin la condición ``not mode.software_id`` este caso dejaría de bloquear."""
        self._con_certificado(_Certificado())
        self.modo.software_id = ''
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('ID Software Nómina', mensaje)
        self.assertNotIn('PIN Software Nómina', mensaje)
        self.assertNotIn('Certificado Digital', mensaje)
        self.assertIn(self.company.name, mensaje)

    def test_modo_con_software_pin_vacio_falta_solo_el_pin(self):
        self._con_certificado(_Certificado())
        self.modo.software_pin = ''
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('PIN Software Nómina', mensaje)
        self.assertNotIn('ID Software Nómina', mensaje)
        self.assertNotIn('Certificado Digital', mensaje)
        self.assertIn(self.company.name, mensaje)

    def test_sin_modo_y_sin_certificado_se_listan_juntos(self):
        self._con_certificado(False)
        self.modo.unlink()
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('ID Software Nómina', mensaje)
        self.assertIn('PIN Software Nómina', mensaje)
        self.assertIn('Certificado Digital', mensaje)

    def test_sin_modo_de_operacion_faltan_id_y_pin(self):
        self._con_certificado(_Certificado())
        self.modo.unlink()
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('ID Software Nómina', mensaje)
        self.assertIn('PIN Software Nómina', mensaje)

    def test_certificado_vencido(self):
        ayer = fields.Datetime.now() - timedelta(days=1)
        self._con_certificado(_Certificado(date_end=ayer))
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        self.assertIn('vencido', str(exc.exception))
        self.assertIn(self.company.name, str(exc.exception))

    def test_certificado_vigente_no_lanza(self):
        manana = fields.Datetime.now() + timedelta(days=1)
        self._con_certificado(_Certificado(date_end=manana))
        self.company._l10n_co_ne_validar_config()

    def test_moneda_distinta_de_cop(self):
        self._con_certificado(_Certificado())
        self.company.currency_id = self.usd.id
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        mensaje = str(exc.exception)
        self.assertIn('moneda', mensaje.lower())
        self.assertIn('COP', mensaje)
        self.assertIn(self.company.name, mensaje)

    def test_el_orden_de_los_chequeos_faltantes_antes_que_vencido_antes_que_moneda(self):
        """Faltan datos Y la moneda es USD: gana el chequeo de datos faltantes (orden de siempre)."""
        self._con_certificado(False)
        self.company.currency_id = self.usd.id
        with self.assertRaises(UserError) as exc:
            self.company._l10n_co_ne_validar_config()
        self.assertIn('Faltan los siguientes datos', str(exc.exception))

    def test_el_envoltorio_del_recibo_da_el_mismo_resultado(self):
        """``HrPayslip._validate_company_ne_config(company)`` llama a la compañía: mismo mensaje."""
        self._con_certificado(False)
        with self.assertRaises(UserError) as directo:
            self.company._l10n_co_ne_validar_config()
        with self.assertRaises(UserError) as por_recibo:
            self.env['hr.payslip']._validate_company_ne_config(self.company)
        self.assertEqual(str(directo.exception), str(por_recibo.exception))

    def test_el_envoltorio_del_recibo_no_lanza_con_configuracion_completa(self):
        self._con_certificado(_Certificado())
        self.env['hr.payslip']._validate_company_ne_config(self.company)
