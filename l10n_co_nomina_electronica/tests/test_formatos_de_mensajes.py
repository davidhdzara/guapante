# -*- coding: utf-8 -*-
"""Guarda contra un «%» literal sin escapar en un mensaje formateado con ``%`` (N2 «cw» y N1 del 22-nov: «que traen % distinto de 100: %s» % nombre lanzaba TypeError en cada corrida,
porque «% d» es una conversion con la bandera de espacio; el mensaje de un assert se construye SIEMPRE, el assert pase o no). Recorre con AST todo el codigo del modulo: cada
``'cadena' % valor`` y cada ``_('cadena', ...)`` con argumentos se formatea con valores numericos de relleno; si falla, la prueba nombra el archivo y la linea. NO EJECUTADA en Odoo al
escribirla (el barrido equivalente corrio fuera de Odoo sobre todo el modulo).

``**dict``: en ``_('...%(x)s...', **datos)`` el AST no ve las claves del dict expandido, asi que esas llamadas se formatean con un relleno que devuelve 1 para CUALQUIER clave (``_ClavesLibres``): se
detecta un «%» literal sin escapar, pero NO una clave que falte en el dict. LIMITE CONOCIDO: eso lo cubren las pruebas Odoo que EJECUTAN el mensaje con el dict real; para los UserError de la ubicacion
laboral de H-F4-08 (cuatro mensajes con ``**datos``, hr_payslip.py ``_ne_ubicacion_laboral_pila``) son ``TestPilaUbicacionLaboral.test_una_direccion_de_trabajo_incompleta_o_incoherente_es_un_error_que_nombra_al_empleado``
(departamento sin codigo, ciudad sin codigo DANE, ciudad de otro departamento y codigo DANE no valido) y ``test_la_ciudad_sin_codigo_dane_nombra_la_ciudad_y_no_cae_al_codigo_postal``."""

import ast
import os

from odoo.addons import l10n_co_nomina_electronica
from odoo.tests.common import BaseCase, TransactionCase, tagged


class _ClavesLibres(dict):
    """Relleno de un ``**dict`` expandido: las claves explicitas valen 1 y cualquier otra tambien (no se puede saber cuales trae el dict)."""

    def __missing__(self, clave):
        return 1


def _formato_malo(nodo):
    """Mensaje de error si el formato de ``nodo`` no se puede aplicar, o None."""
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mod) and isinstance(nodo.left, ast.Constant) and isinstance(nodo.left.value, str):
        texto, derecha = nodo.left.value, nodo.right
        if isinstance(derecha, ast.Tuple):
            relleno = tuple(1 for _ in derecha.elts)
        elif isinstance(derecha, ast.Dict):
            relleno = {clave.value: 1 for clave in derecha.keys if isinstance(clave, ast.Constant)}
            if any(clave is None for clave in derecha.keys):            # {**datos, ...}
                relleno = _ClavesLibres(relleno)
        else:
            relleno = 1
    elif (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == '_' and nodo.args
          and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str) and (len(nodo.args) > 1 or nodo.keywords)):
        texto = nodo.args[0].value
        if nodo.keywords:
            relleno = {k.arg: 1 for k in nodo.keywords if k.arg}
            if any(k.arg is None for k in nodo.keywords):               # **datos: no se ven sus claves (limite conocido, ver el docstring del modulo)
                relleno = _ClavesLibres(relleno)
        else:
            relleno = tuple(1 for _ in nodo.args[1:])
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


def _llamada(codigo):
    """El nodo de una expresion de una linea."""
    return ast.parse(codigo).body[0].value


@tagged('post_install', '-at_install')
class TestFormatoMalo(BaseCase):
    """La logica de ``_formato_malo`` es Python puro: se prueba sin base de datos, con nodos construidos a mano y con los mensajes reales del modulo."""

    def test_un_mensaje_con_datos_expandido_y_claves_completas_pasa(self):
        self.assertIsNone(_formato_malo(_llamada("_('La ciudad \"%(ciudad)s\" de %(employee)s', **datos)")))
        self.assertIsNone(_formato_malo(_llamada("_('La ciudad %(ciudad)s de %(employee)s %(longitud)s', longitud=5, **datos)")))
        self.assertIsNone(_formato_malo(_llamada("'%(a)s y %(b)s' % {**datos, 'b': 1}")))

    def test_un_porcentaje_suelto_se_detecta_con_o_sin_datos_expandido(self):
        """«40 % del» es la conversion «% d» (bandera de espacio): es el defecto que la guarda existe para cazar, tambien cuando el mensaje trae ``**datos``."""
        for codigo in ("_('Excede el 40 % del valor %(a)s', a=1)",
                       "_('Excede el 40 % del valor %(a)s', **datos)",
                       "_('Excede el 40 % del valor %(a)s', a=1, **datos)",
                       "'Excede el 40 % del valor %(a)s' % {**datos}"):
            with self.subTest(codigo):
                self.assertTrue(_formato_malo(_llamada(codigo)), 'Debia marcar el «%» suelto.')

    def test_el_porcentaje_escapado_pasa(self):
        self.assertIsNone(_formato_malo(_llamada("_('Excede el 40 %% del valor %(a)s', **datos)")))

    def test_sin_datos_expandido_una_clave_ausente_se_detecta(self):
        problema = _formato_malo(_llamada("_('Hola %(a)s y %(b)s', a=1)"))
        self.assertTrue(problema, 'Sin **datos las claves del mensaje deben estar todas en los argumentos con nombre.')
        self.assertIn("'b'", problema)           # el KeyError nombra la clave ausente

    def test_limite_conocido_con_datos_expandido_una_clave_ausente_del_dict_no_se_detecta(self):
        """No se puede saber que claves trae ``**datos``: ese caso lo cubren las pruebas Odoo que ejecutan el mensaje (ver el docstring del modulo)."""
        self.assertIsNone(_formato_malo(_llamada("_('Hola %(a)s y %(no_esta)s', **datos)")))

    def test_los_mensajes_con_datos_expandido_del_modulo_se_recorren_y_pasan(self):
        """Premisa de la guarda: el modulo trae mensajes ``_(..., **datos)`` (los 4 de la ubicacion laboral de H-F4-08, hr_payslip.py) y TODOS pasan; sin esto el barrido
        no estaria ejerciendo la rama del ``**dict``."""
        ruta = os.path.join(os.path.dirname(l10n_co_nomina_electronica.__file__), 'models', 'hr_payslip.py')
        with open(ruta, encoding='utf-8') as f:
            arbol = ast.parse(f.read())
        con_datos = [nodo for nodo in ast.walk(arbol)
                     if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == '_'
                     and any(k.arg is None for k in nodo.keywords) and isinstance(nodo.args[0], ast.Constant)]
        self.assertGreaterEqual(len(con_datos), 4, 'Premisa: hr_payslip.py trae al menos los 4 mensajes con **datos de la ubicacion laboral.')
        for nodo in con_datos:
            with self.subTest(linea=nodo.lineno):
                self.assertIsNone(_formato_malo(nodo))
