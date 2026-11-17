# -*- coding: utf-8 -*-
"""H-QA-011: en Contactos, «Tipo de Entidad (Nómina)» y «Código PILA» salían SIN etiqueta visible porque se insertaban junto a
`vat`, dentro de la fila en línea (div.o_row) de l10n_latam_base. Ahora van en un grupo propio con etiquetas, sin pestañas ni
estilos propios (principio de diseño nativo de David)."""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVistaPartnerEntidadNomina(TransactionCase):

    def _arbol(self):
        arch = self.env['res.partner'].get_view(self.env.ref('base.view_partner_form').id, 'form')['arch']
        return etree.fromstring(arch)

    def test_los_campos_estan_en_un_grupo_con_etiquetas_y_fuera_de_la_fila_en_linea(self):
        arbol = self._arbol()
        for campo in ('l10n_co_entity_type', 'l10n_co_pila_entity_code'):
            nodos = arbol.xpath("//field[@name='%s']" % campo)
            self.assertEqual(len(nodos), 1, campo)
            grupo = nodos[0].getparent()
            self.assertEqual(grupo.tag, 'group', 'El campo %s debe ser hijo directo de un <group> (con etiqueta)' % campo)
            self.assertEqual(grupo.get('string'), 'Entidad de nómina (PILA)')
            ancestros_o_row = [a for a in nodos[0].iterancestors('div') if 'o_row' in (a.get('class') or '')]
            self.assertFalse(ancestros_o_row, 'El campo %s no debe estar en una fila en línea (sin etiqueta)' % campo)

    def test_sin_pestanas_ni_estilos_propios(self):
        vista = self.env.ref('l10n_co_nomina_electronica.view_partner_form_l10n_co_nomina')
        arch = vista.arch_db
        for prohibido in ('style=', 'fa-', '<page', '<notebook', 'text-muted', 'class="o_row"'):
            self.assertNotIn(prohibido, arch, prohibido)
