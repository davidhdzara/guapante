# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Utilidades puras sobre el XML de nómina electrónica (sin Odoo), compartidas por el ciclo por recibo
(``l10n.co.ne.documento.mixin``) y el documento mensual (``l10n.co.ne.documento``)."""

from lxml import etree


def insertar_cune_y_qr(xml_bytes, cune_value, qr_host):
    """Escribe CUNE/EncripCUNE en ``InformacionGeneral`` y la URL en ``CodigoQR``.

    En las Notas de Ajuste ambos viven dentro de ``<Reemplazar>`` (o ``<Eliminar>``), no como hijos directos de la
    raíz: se buscan en todo el árbol. Si no se encuentran el XML sale con ``CUNE=""`` y la DIAN rechaza (NIAE024)."""
    tree = etree.fromstring(xml_bytes)
    ns = tree.nsmap.get(None, '')
    info_gen = tree.find('.//{%s}InformacionGeneral' % ns)
    if info_gen is not None:
        info_gen.set('CUNE', cune_value)
        info_gen.set('EncripCUNE', 'CUNE-SHA384')
    qr_url = 'https://%s/document/searchqr?documentkey=%s' % (qr_host, cune_value)
    qr_el = tree.find('.//{%s}CodigoQR' % ns)
    if qr_el is None and info_gen is not None:
        parent = info_gen.getparent()
        qr_el = etree.Element('{%s}CodigoQR' % ns)
        parent.insert(list(parent).index(info_gen) + 1, qr_el)
    if qr_el is not None:
        qr_el.text = qr_url
    return etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
