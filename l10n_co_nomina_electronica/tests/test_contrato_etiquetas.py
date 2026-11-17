# -*- coding: utf-8 -*-
"""H12 (2026-11-09): los 3 campos que agregamos a la pestaña "Detalles" del contrato se veían sin
etiqueta porque se inyectaban directo en el grupo EXTERIOR contract_details (col="2"); Odoo solo
genera la celda de etiqueta dentro de un grupo INTERIOR. Se verifica el arch guardado de la vista
y la vista combinada real: cada campo está dentro de un <group> interior."""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged

_CAMPOS = ('l10n_co_ne_contract_type', 'l10n_co_ne_integral_salary')


@tagged('post_install', '-at_install')
class TestContratoEtiquetas(TransactionCase):
    def test_campos_dentro_de_un_grupo_interior_en_el_arch_guardado(self):
        arch = etree.fromstring(
            self.env.ref('l10n_co_nomina_electronica.view_contract_form_ne').arch_db.encode('utf-8'))
        for campo in _CAMPOS:
            nodo = arch.xpath("//xpath[@expr=\"//group[@name='contract_details']\"]//field[@name='%s']" % campo)
            self.assertEqual(len(nodo), 1, campo)
            self.assertEqual(nodo[0].getparent().tag, 'group', 'Falta el <group> interior de %s' % campo)

    def test_campos_en_la_vista_combinada_dentro_de_contract_details(self):
        combinada = self.env['hr.contract'].get_view(
            self.env.ref('hr_contract.hr_contract_view_form').id, 'form')['arch']
        arch = etree.fromstring(combinada.encode('utf-8'))
        for campo in _CAMPOS:
            nodo = arch.xpath("//group[@name='contract_details']//group//field[@name='%s']" % campo)
            self.assertTrue(nodo, 'El campo %s no quedó en un grupo interior de contract_details.' % campo)
