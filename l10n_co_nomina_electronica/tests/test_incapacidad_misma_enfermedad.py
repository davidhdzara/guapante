# -*- coding: utf-8 -*-
"""Vinculo "Prórroga de" entre incapacidades comunes (.183): solo el dato, sin plazo ni cambio de
motor. Validaciones: mismo empleado, ambas incapacidad comun, la anterior termina antes, sin ciclos."""

from datetime import date

from lxml import etree

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIncapacidadMismaEnfermedad(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Prorroga', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U'})
        cls.inc = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.vac = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        cls.emp = cls._empleado('Emp Prorroga A')
        cls.otro = cls._empleado('Emp Prorroga B')

    @classmethod
    def _empleado(cls, nombre):
        return cls.env['hr.employee'].create({
            'name': nombre, 'company_id': cls.company.id,
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'})

    def _ausencia(self, empleado, tipo, desde, hasta):
        return self.env['hr.leave'].with_company(self.company).create({
            'employee_id': empleado.id, 'holiday_status_id': tipo.id,
            'request_date_from': desde, 'request_date_to': hasta})

    def test_vincula_una_incapacidad_con_la_anterior(self):
        a = self._ausencia(self.emp, self.inc, date(2026, 3, 1), date(2026, 3, 10))
        b = self._ausencia(self.emp, self.inc, date(2026, 3, 11), date(2026, 3, 20))
        b.l10n_co_ne_prorroga_de_id = a
        self.assertEqual(b.l10n_co_ne_prorroga_de_id, a)
        self.assertTrue(b.l10n_co_ne_es_incapacidad_comun)

    def test_la_anterior_debe_ser_del_mismo_empleado(self):
        a = self._ausencia(self.otro, self.inc, date(2026, 3, 1), date(2026, 3, 10))
        b = self._ausencia(self.emp, self.inc, date(2026, 3, 11), date(2026, 3, 20))
        with self.assertRaises(ValidationError):
            b.l10n_co_ne_prorroga_de_id = a

    def test_solo_aplica_a_incapacidad_de_origen_comun(self):
        vac = self._ausencia(self.emp, self.vac, date(2026, 2, 1), date(2026, 2, 5))
        b = self._ausencia(self.emp, self.inc, date(2026, 3, 11), date(2026, 3, 20))
        with self.assertRaises(ValidationError) as exc:
            b.l10n_co_ne_prorroga_de_id = vac
        self.assertIn('origen común', str(exc.exception))

    def test_la_anterior_debe_terminar_antes_de_que_empiece_esta(self):
        """No se puede marcar como "anterior" una incapacidad posterior (el mismo empleado no puede
        tener dos ausencias que se crucen, asi que el caso es el orden invertido)."""
        posterior = self._ausencia(self.emp, self.inc, date(2026, 3, 11), date(2026, 3, 20))
        primera = self._ausencia(self.emp, self.inc, date(2026, 3, 1), date(2026, 3, 10))
        with self.assertRaises(ValidationError):
            primera.l10n_co_ne_prorroga_de_id = posterior

    def test_no_se_permiten_ciclos(self):
        a = self._ausencia(self.emp, self.inc, date(2026, 3, 1), date(2026, 3, 10))
        b = self._ausencia(self.emp, self.inc, date(2026, 3, 15), date(2026, 3, 20))
        b.l10n_co_ne_prorroga_de_id = a
        with self.assertRaises(ValidationError):
            a.l10n_co_ne_prorroga_de_id = b

    def test_el_campo_se_oculta_si_no_es_incapacidad_comun_en_la_vista(self):
        arch = etree.fromstring(self.env['hr.leave'].get_view(view_type='form')['arch'].encode())
        nodo = arch.xpath("//field[@name='l10n_co_ne_prorroga_de_id']")
        self.assertTrue(nodo)
        self.assertIn('l10n_co_ne_es_incapacidad_comun', nodo[0].get('invisible'))
