# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Herramienta de UN SOLO USO (no la ejecuta Odoo): convierte la tabla oficial del Decreto 768 de
2022 (CSV con columnas code,risk_class,ciiu_4d,adicional_2d,name) en data/l10n_co_pila_ciiu.xml.

    python3 generar_ciiu_xml.py <entrada.csv> <salida.xml>

Valida antes de escribir y se detiene con un mensaje claro si algo no cuadra: códigos de 7 dígitos
sin repetir, primer dígito del código = clase de riesgo, código = clase + CIIU(4) + adicional(2),
nombre no vacío. Escribe con noupdate="1": una corrección hecha por el usuario en el catálogo (que
es editable a propósito) NO se pisa en una actualización del módulo, pero las filas nuevas de una
versión futura sí se crean. No se inventa vigencia: date_start/date_end quedan vacíos.
"""

import csv
import sys
from xml.sax.saxutils import escape


def main(entrada, salida):
    filas = list(csv.DictReader(open(entrada, encoding='utf-8')))
    vistos = set()
    for f in filas:
        codigo = f['code']
        if not (len(codigo) == 7 and codigo.isdigit()):
            sys.exit('Código inválido: %r' % codigo)
        if codigo in vistos:
            sys.exit('Código repetido: %s' % codigo)
        vistos.add(codigo)
        if codigo[0] != f['risk_class'] or f['risk_class'] not in '12345':
            sys.exit('Clase de riesgo no coincide con el código %s' % codigo)
        if codigo != f['risk_class'] + f['ciiu_4d'].zfill(4) + f['adicional_2d'].zfill(2):
            sys.exit('El código %s no es clase + CIIU + adicional' % codigo)
        if not f['name'].strip():
            sys.exit('Nombre vacío en %s' % codigo)
    with open(salida, 'w', encoding='utf-8') as out:
        out.write('<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n    <data noupdate="1">\n')
        for f in filas:
            out.write(
                '        <record id="ciiu_%s" model="l10n.co.pila.ciiu">\n'
                '            <field name="code">%s</field>\n'
                '            <field name="name">%s</field>\n'
                '            <field name="risk_class">%s</field>\n'
                '        </record>\n' % (
                    f['code'], f['code'], escape(' '.join(f['name'].split())), f['risk_class']))
        out.write('    </data>\n</odoo>\n')
    print('OK: %d actividades escritas en %s' % (len(filas), salida))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
