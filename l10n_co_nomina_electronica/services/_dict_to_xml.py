# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Helper para renderizar un dict Python como nodo XML -- vendorizado.

Copia local de ``odoo.addons.account.tools.dict_to_xml`` (Odoo 18,
verificado contra el código real del framework ``account_edi_ubl_cii``,
doc 24). Se vendoriza en vez de importarla directo de Odoo porque
``nomina_xml_builder.py`` documenta explícitamente "Sin dependencias de
Odoo" -- es Python puro, testeable sin un entorno Odoo completo.

``_remove_control_characters`` (abajo) es una copia literal, confirmada
contra el código real de ``odoo.tools.xml_utils.remove_control_characters``
en el servidor (2026-09-12) -- la primera versión de este archivo la
había reimplementado de memoria (sin acceso al servidor en ese momento)
y difería en 2 puntos importantes, ya corregidos:
1. La real opera sobre BYTES (``str(text).encode()``), no sobre el
   ``str`` directo -- ``dict_to_xml`` real hace
   ``remove_control_characters(str(text).encode()).decode()``, no
   ``remove_control_characters(str(text))``.
2. La real es una lista BLANCA (``[^...]``, quita todo lo que NO esté
   en los rangos permitidos por la especificacion XML 1.0 -- tab, LF,
   CR, U+0020-U+D7FF, U+E000-U+FFFD, U+10000-U+10FFFF), no una lista
   negra de los controles C0 (\\x00-\\x1f) como tenía antes -- la
   version vieja dejaba pasar U+007F (DEL) y no cubría sustitutos
   (U+D800-U+DFFF) ni el resto de rangos no-Char de la especificacion.

La lógica de ``dict_to_xml`` en sí (el resto de esta función) SÍ está
copiada literal del código real leído completo en la investigación de
doc 24, no reescrita de memoria.
"""

import re

from lxml import etree

# Copia literal de odoo.tools.xml_utils.remove_control_characters (Odoo 18):
# especificacion XML 1.0 de "Char" valido -- todo lo que NO esta en estos
# rangos se elimina. https://www.w3.org/TR/xml/
_INVALID_XML_CHARS_RE = re.compile(
    (
        '[^'
        '\u0009'
        '\u000A'
        '\u000D'
        '\u0020-\uD7FF'
        '\uE000-\uFFFD'
        '\U00010000-\U0010FFFF'
        ']'
    ).encode()
)


def _remove_control_characters(byte_node: bytes) -> bytes:
    """Quita caracteres invalidos para XML 1.0 (copia literal del original de Odoo,
    opera sobre bytes UTF-8, no sobre str -- ver llamada en dict_to_xml abajo).

    NOTA (verificado empiricamente, no solo leido): el patron real de Odoo, al operar
    sobre BYTES UTF-8 con rangos '\\uXXXX-\\uYYYY' definidos como texto y luego
    codificados, no filtra correctamente ningun caracter cuya codificacion UTF-8 use
    bytes >= 0x20 (DEL \\x7f, sustitutos \\ud800-\\udfff, no-caracteres \\ufffe/\\uffff,
    etc. pasan intactos) -- un rango de clase de caracteres con limites multi-byte no
    equivale a un rango de codepoints Unicode una vez codificado a bytes. SI elimina
    correctamente los controles C0 reales (\\x00-\\x1f salvo tab/LF/CR), que es el caso
    practico real (texto corrupto/basura de BD) para el que se usa aqui. Se mantiene
    esta implementacion tal cual porque el objetivo de esta vendorizacion es igualar el
    comportamiento REAL de Odoo, no corregirlo -- documentado para que quien lo lea
    despues no asuma que filtra mas de lo que realmente filtra."""
    return _INVALID_XML_CHARS_RE.sub(b'', byte_node)


def dict_to_xml(node, *, nsmap={}, template=None, render_empty_nodes=False, tag=None, path=None):
    """ Helper to render a Python dict as an XML node.

    The dict is expected to be of the form:
    {
        # Special keys:
        '_tag': 'tag_name',  # '_tag' is rendered as the node's tag
        '_text': 'content',  # '_text' is rendered as the node's text content
        '_dummy': 'dummy_value',  # Keys starting with '_' are not rendered

        # Simple values are rendered as attributes
        'attribute_name': 'attribute_value',

        # Dicts are rendered as child nodes
        'child_tag': {
            '_text': 'content',
            'attribute_name': 'attribute_value',
        },

        # Lists of dicts are also rendered as child nodes
        'child_tag': [
            {
                '_text': 'content',
                'attribute_name': 'attribute_value',
            },
        ],
    }

    :param node: The Python dict to render.
    :param nsmap: (optional) A dict of namespaces to be used for rendering the node.
    :param template: (optional) A Python dict providing default values and an order of keys for rendering the node.
    :param render_empty_nodes: (optional) If True, empty nodes will be rendered in the XML tree.
    :param tag: (optional) The tag of the node to render (needed only for recursive calls).
    :param path: (optional) The path of the currently rendered node in the XML tree (needed only for recursive calls).
    :return: The rendered XML node as an lxml.Element.
    """
    def convert_tag_to_lxml_convention(tag):
        if ':' in tag:
            namespace, local_name = tag.split(':')
            if namespace in nsmap:
                return etree.QName(nsmap[namespace], local_name).text
        return tag

    def convert_element_tag_to_lxml_convention(tag):
        # ADAPTACION LOCAL, no esta en el dict_to_xml original de Odoo:
        # UBL (el unico consumidor real de dict_to_xml en Odoo) SIEMPRE
        # usa tags con prefijo (cac:/cbc:/ext:), nunca namespace por
        # defecto sin prefijo -- por eso el original nunca necesito
        # resolver un tag "pelado" contra nsmap[None]. Nuestro XSD (DIAN
        # Nomina Electronica) SI usa namespace por defecto sin prefijo
        # para sus propios elementos (<Periodo>, <Trabajador>, etc.,
        # sin cac:/cbc:). Verificado empiricamente ANTES de agregar esto
        # que sin este fallback, etree.Element('Periodo', nsmap={None:
        # NS}) crea un elemento en el namespace VACIO (QName(...).
        # namespace == None), no en NS -- aunque el string serializado
        # se vea igual a simple vista, XSD validation lo rechazaria.
        # Los ATRIBUTOS (convert_tag_to_lxml_convention de arriba, sin
        # tocar) NO llevan este fallback -- nuestro XSD, igual que UBL,
        # espera atributos SIN calificar (attributeFormDefault
        # implicito "unqualified"), mismo comportamiento que ya tenia
        # _attr()/_el() en el builder viejo (nunca namespace-calificaban
        # atributos).
        if ':' not in tag and nsmap.get(None):
            return etree.QName(nsmap[None], tag).text
        return convert_tag_to_lxml_convention(tag)

    if template is not None:
        # Ensure order of keys
        node = dict.fromkeys(template) | node

    tag = node.get('_tag') or (template or {}).get('_tag', tag)

    if tag is None:
        raise ValueError(f"No tag was specified for node: {str(node)[:20]}")

    if path is None:
        path = tag

    element = etree.Element(convert_element_tag_to_lxml_convention(tag), nsmap=nsmap)

    # Add attributes
    for attr_name, attr_value in node.items():
        if not attr_name.startswith('_') and not isinstance(attr_value, (dict, list)) and attr_value is not None and attr_value is not False:
            element.set(convert_tag_to_lxml_convention(attr_name), str(attr_value))

    # Add text content if present
    text = node.get('_text')
    if text is not None and text is not False:
        element.text = _remove_control_characters(str(text).encode()).decode()

    # Add child nodes
    for child_tag, child in node.items():
        if not child_tag.startswith('_') and isinstance(child, (dict, list)):
            child_template = (template or {}).get(child_tag)
            child_is_empty = True
            if isinstance(child, dict):
                child = [child]

            # child is a list (of dicts)
            for sub_child in child:
                if sub_child is not None:
                    child_element = dict_to_xml(
                        sub_child,
                        nsmap=nsmap,
                        template=child_template,
                        render_empty_nodes=render_empty_nodes,
                        tag=child_tag,
                        path=f'{path}/{child_tag}',
                    )
                    if child_element is not None:
                        element.append(child_element)
                        child_is_empty = False

            # Check that all non-empty child nodes are defined in the template
            if template is not None and child_tag not in template and not child_is_empty:
                raise ValueError(f"The following child node is not defined in the template: {path}/{child_tag}")

    if not render_empty_nodes and not element.attrib and not element.text and len(element) == 0:
        return None

    return element
