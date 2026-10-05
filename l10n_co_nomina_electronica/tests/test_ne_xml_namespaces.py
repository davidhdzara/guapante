"""Regresión ZE02: el atributo schemaLocation debe serializarse como xsi:."""

import unittest

from lxml import etree

from odoo.addons.l10n_co_nomina_electronica.services import nomina_xml_builder as builder


class TestNeXmlNamespaces(unittest.TestCase):
    """`xs` y `xsi` comparten URI; lxml usa el primero del mapa para {URI}schemaLocation y la
    DIAN (.NET SignedXml) canoniza el atributo como `xsi:schemaLocation`. Si sale `xs:` el
    digest del documento firmado no coincide y la DIAN rechaza con ZE02."""

    def _root_xml(self, ns_root, nsmap):
        root = etree.Element('{%s}NominaIndividual' % ns_root, nsmap=nsmap)
        root.set('SchemaLocation', '')
        root.set('{%s}schemaLocation' % builder.NS_XSD, '%s X.xsd' % ns_root)
        return etree.tostring(root).decode()

    def test_schema_location_usa_prefijo_xsi_en_nomina(self):
        xml = self._root_xml(builder.NS_NOMINA, builder._NSMAP_NOMINA)
        self.assertIn('xsi:schemaLocation=', xml)
        self.assertNotIn('xs:schemaLocation=', xml)

    def test_schema_location_usa_prefijo_xsi_en_ajuste(self):
        xml = self._root_xml(builder.NS_NOMINA_AJUSTE, builder._NSMAP_AJUSTE)
        self.assertIn('xsi:schemaLocation=', xml)
        self.assertNotIn('xs:schemaLocation=', xml)

    def test_se_siguen_declarando_xs_y_xsi(self):
        for nsmap in (builder._NSMAP_NOMINA, builder._NSMAP_AJUSTE):
            self.assertEqual(nsmap['xs'], nsmap['xsi'])
