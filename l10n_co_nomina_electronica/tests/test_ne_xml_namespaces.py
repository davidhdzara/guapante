"""Regresión ZE02: schemaLocation debe salir como xsi:, con xs declarado antes que xsi."""

import re
import unittest

from lxml import etree

from odoo.addons.l10n_co_nomina_electronica.services import nomina_xml_builder as builder


class TestNeXmlNamespaces(unittest.TestCase):
    """`xs` y `xsi` comparten URI. lxml escribe {URI}schemaLocation con el primer prefijo del
    mapa (`xs:`) pero la DIAN (.NET SignedXml) canoniza con el ULTIMO prefijo declarado
    (`xsi:`); si el texto dice `xs:` el digest del documento no coincide y responde ZE02.
    Estructura aceptada por la DIAN: xmlns:xs ... xmlns:xsi y xsi:schemaLocation."""

    def _serialized(self, ns_root, nsmap):
        root = etree.Element('{%s}NominaIndividual' % ns_root, nsmap=nsmap)
        root.set('SchemaLocation', '')
        root.set('{%s}schemaLocation' % builder.NS_XSD, '%s X.xsd' % ns_root)
        return builder._serialize(root).decode()

    def _assert_estructura_aceptada(self, xml):
        self.assertIn(' xsi:schemaLocation=', xml)
        self.assertNotIn(' xs:schemaLocation=', xml)
        self.assertLess(xml.index('xmlns:xs='), xml.index('xmlns:xsi='))
        self.assertEqual(len(re.findall(r'schemaLocation=', xml)), 1)

    def test_nomina_individual(self):
        self._assert_estructura_aceptada(
            self._serialized(builder.NS_NOMINA, builder._NSMAP_NOMINA))

    def test_nomina_ajuste(self):
        self._assert_estructura_aceptada(
            self._serialized(builder.NS_NOMINA_AJUSTE, builder._NSMAP_AJUSTE))
