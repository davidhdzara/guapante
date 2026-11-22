# -*- coding: utf-8 -*-
"""Guarda contra un «%» literal sin escapar en un mensaje formateado con ``%`` (N2 «cw» y N1 del 22-nov: «que traen % distinto de 100: %s» % nombre lanzaba TypeError en cada corrida,
porque «% d» es una conversion con la bandera de espacio; el mensaje de un assert se construye SIEMPRE, el assert pase o no). Recorre con AST todo el codigo del modulo: cada
``'cadena' % valor`` y cada ``_('cadena', ...)`` con argumentos se formatea con valores numericos de relleno; si falla, la prueba nombra el archivo y la linea. NO EJECUTADA en Odoo al
escribirla (el barrido equivalente corrio fuera de Odoo sobre todo el modulo)."""

import ast
import os

from odoo.addons import l10n_co_nomina_electronica
from odoo.tests.common import TransactionCase, tagged


def _formato_malo(nodo):
    """Mensaje de error si el formato de ``nodo`` no se puede aplicar, o None."""
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mod) and isinstance(nodo.left, ast.Constant) and isinstance(nodo.left.value, str):
        texto, derecha = nodo.left.value, nodo.right
        if isinstance(derecha, ast.Tuple):
            relleno = tuple(1 for _ in derecha.elts)
        elif isinstance(derecha, ast.Dict):
            relleno = {clave.value: 1 for clave in derecha.keys if isinstance(clave, ast.Constant)}
        else:
            relleno = 1
    elif (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == '_' and nodo.args
          and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str) and (len(nodo.args) > 1 or nodo.keywords)):
        texto = nodo.args[0].value
        relleno = {k.arg: 1 for k in nodo.keywords if k.arg} if nodo.keywords else tuple(1 for _ in nodo.args[1:])
    else:
        return None
    try:
        texto % relleno
    except (TypeError, ValueError, KeyError) as error:
        return '%s: %r' % (error, texto[:90])
    return None


@tagged('post_install', '-at_install')
class TestFormatosDeMensajes(TransactionCase):

    def test_ningun_mensaje_formateado_con_porcentaje_tiene_un_porcentaje_literal_sin_escapar(self):
        raiz = os.path.dirname(l10n_co_nomina_electronica.__file__)
        malos, revisados = [], 0
        for carpeta, _subcarpetas, archivos in os.walk(raiz):
            for archivo in archivos:
                if not archivo.endswith('.py'):
                    continue
                ruta = os.path.join(carpeta, archivo)
                with open(ruta, encoding='utf-8') as f:
                    try:
                        arbol = ast.parse(f.read())
                    except SyntaxError:
                        continue
                revisados += 1
                for nodo in ast.walk(arbol):
                    problema = _formato_malo(nodo)
                    if problema:
                        malos.append('%s:%s %s' % (os.path.relpath(ruta, raiz), nodo.lineno, problema))
        self.assertGreater(revisados, 100, 'Premisa: se recorrió el código del módulo')
        self.assertFalse(malos, 'Mensajes con un «%%» literal sin escapar (escribir «%%%%»):\n%s' % '\n'.join(malos))
