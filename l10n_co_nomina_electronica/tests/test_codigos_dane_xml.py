# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F3-06: en una dirección colombiana el XML exige el código DANE del departamento y de una ciudad de ese departamento: sin ellos se detiene y nombra qué completar; no cae al código postal."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCodigosDaneXml(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.colombia = cls.env.ref('base.co')
        cls.depto = cls._departamento('Departamento DANE', 83)          # 83 y 84: números que el DANE no asigna
        cls.otro = cls._departamento('Departamento Vecino', 84)
        cls.sin_codigo = cls.env['res.country.state'].create({'name': 'Departamento Sin Código', 'code': 'ZQS', 'country_id': cls.colombia.id})
        cls.ciudad = cls._ciudad('Ciudad DANE', cls.depto, l10n_co_edi_code=83360)

    @classmethod
    def _departamento(cls, nombre, numero):
        """Con el campo DANE del departamento si la base lo tiene; si no, con el código numérico."""
        Estado = cls.env['res.country.state']
        valores = {'name': nombre, 'country_id': cls.colombia.id, 'code': str(numero)}
        if 'l10n_co_edi_code' in Estado._fields:
            valores.update(code='ZQ%s' % numero, l10n_co_edi_code=numero)
        return Estado.create(valores)

    @classmethod
    def _ciudad(cls, nombre, estado, **extra):
        return cls.env['res.city'].create(dict({'name': nombre, 'state_id': estado.id, 'country_id': estado.country_id.id}, **extra))

    def _contacto(self, estado, ciudad, pais=None):
        return self.env['res.partner'].create({
            'name': 'Dirección de Prueba DANE', 'country_id': (pais or self.colombia).id, 'state_id': estado.id if estado else False, 'city_id': ciudad.id if ciudad else False})

    def _codigos(self, contacto):
        return self.env['hr.payslip']._ne_codigos_ubicacion(contacto, 'la prueba')

    def _falla(self, contacto, texto):
        with self.assertRaises(UserError) as error:
            self._codigos(contacto)
        mensaje = str(error.exception)
        self.assertIn(texto, mensaje)
        self.assertIn(contacto.display_name, mensaje)

    def test_con_los_codigos_sale_el_dane(self):
        self.assertEqual(self._codigos(self._contacto(self.depto, self.ciudad)), ('83', '83360'))

    def test_una_ciudad_sin_codigo_dane_no_cae_al_codigo_postal(self):
        ciudad = self._ciudad('Ciudad Solo Postal', self.depto, zipcode='05001')
        self._falla(self._contacto(self.depto, ciudad), ciudad.name)

    def test_un_departamento_sin_codigo_dane_no_cae_a_su_codigo(self):
        ciudad = self._ciudad('Ciudad de Departamento sin Código', self.sin_codigo, l10n_co_edi_code=83001)
        self._falla(self._contacto(self.sin_codigo, ciudad), self.sin_codigo.name)

    def test_la_ciudad_debe_ser_del_departamento(self):
        self._falla(self._contacto(self.otro, self.ciudad), self.otro.name)

    def test_sin_departamento_o_sin_ciudad(self):
        self._falla(self._contacto(None, self.ciudad), 'departamento')
        self._falla(self._contacto(self.depto, None), 'ciudad')

    def test_fuera_de_colombia_no_cambia(self):
        pais = self.env.ref('base.mx')
        estado = self.env['res.country.state'].create({'name': 'Estado Extranjero', 'code': 'ZQX', 'country_id': pais.id})
        ciudad = self._ciudad('Ciudad Extranjera', estado, zipcode='99999')
        self.assertEqual(self._codigos(self._contacto(estado, ciudad, pais=pais)), ('ZQX', '99999'))
