# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F2-03 (regla general del TL, 22-nov): TODO metodo publico (sin «_») que llega a ``res.company._get_ne_certificate`` —generar, firmar, transmitir o consultar a la DIAN— llama a
``_ne_exigir_administrador_de_nomina``. Un boton con ``groups`` solo se oculta y un metodo publico se puede llamar por RPC: esta es la barrera real. Los crons pasan por ``env.su``.

La prueba recorre el codigo del modulo (AST de ``models/`` y ``wizard/``): arma el grafo de llamadas POR NOMBRE de metodo (el despacho de Odoo es dinamico, asi que se sobreaproxima: un nombre repetido
en dos clases cuenta para las dos), calcula todo lo que alcanza el certificado y exige la guarda en cada metodo publico alcanzado. Falla y NOMBRA el metodo si uno nuevo llega al certificado sin ella.
Limite conocido: no ve llamadas dinamicas por ``getattr`` con un nombre armado en tiempo de ejecucion."""

import ast
import collections
import glob
import os

from odoo.tests.common import BaseCase, tagged

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMIDERO = '_get_ne_certificate'
GUARDA = '_ne_exigir_administrador_de_nomina'
# Metodos publicos que HOY llegan al certificado (para que un cambio en el analisis, que dejaria la prueba vacia, se note).
CONOCIDOS = {
    'action_generate_ne_xml', 'action_regenerate_ne_xml', 'action_send_ne_dian', 'action_mass_generate_ne_xml', 'action_mass_send_ne_dian', 'action_check_dian_status', 'action_send_test_set',
    'action_generar_xml', 'start', 'action_iniciar_habilitacion_nomina', 'action_send_and_print', 'action_check_status',
    'action_iniciar_habilitacion', 'action_iniciar_habilitacion_individual', 'action_iniciar_habilitacion_ajuste', 'action_prepare_individual', 'action_prepare_ajuste',
    'action_send_individual', 'action_send_ajuste', 'action_check_individual_status', 'action_check_ajuste_status'}


def _metodos():
    """{(archivo, clase, metodo): (nombres que llama, linea)} de ``models/`` y ``wizard/``."""
    metodos = {}
    for ruta in sorted(glob.glob(os.path.join(RAIZ, 'models', '*.py')) + glob.glob(os.path.join(RAIZ, 'wizard', '*.py'))):
        arbol = ast.parse(open(ruta, encoding='utf-8').read())
        for clase in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
            for funcion in [n for n in clase.body if isinstance(n, ast.FunctionDef)]:
                llama = set()
                for nodo in ast.walk(funcion):
                    if isinstance(nodo, ast.Call):
                        if isinstance(nodo.func, ast.Attribute):
                            llama.add(nodo.func.attr)
                        elif isinstance(nodo.func, ast.Name):
                            llama.add(nodo.func.id)
                metodos[(os.path.relpath(ruta, RAIZ), clase.name, funcion.name)] = (llama, funcion.lineno)
    return metodos


def _que_llegan_al_certificado(metodos):
    alcanzan = {clave for clave, (llama, _l) in metodos.items() if SUMIDERO in llama and clave[2] != SUMIDERO}
    avanzo = True
    while avanzo:
        avanzo = False
        nombres = {clave[2] for clave in alcanzan}
        for clave, (llama, _l) in metodos.items():
            if clave not in alcanzan and clave[2] != SUMIDERO and llama & nombres:
                alcanzan.add(clave)
                avanzo = True
    return alcanzan


@tagged('post_install', '-at_install')
class TestGuardaDeTransmision(BaseCase):

    def test_todo_metodo_publico_que_llega_al_certificado_lleva_la_guarda_del_administrador_de_nomina(self):
        metodos = _metodos()
        publicos = sorted(clave for clave in _que_llegan_al_certificado(metodos) if not clave[2].startswith('_'))
        self.assertTrue(publicos, 'El analisis no encontro ningun metodo publico: la prueba estaria vacia')
        sin_guarda = [clave for clave in publicos if GUARDA not in metodos[clave][0]]
        self.assertFalse(
            sin_guarda,
            'Metodos publicos que llegan al certificado SIN %s (agregarla como primera linea; los crons pasan por env.su): %s' % (
                GUARDA, ', '.join('%s:%s.%s (l.%s)' % (a, c, m, metodos[(a, c, m)][1]) for a, c, m in sin_guarda)))

    def test_el_analisis_encuentra_los_metodos_publicos_conocidos(self):
        metodos = _metodos()
        encontrados = {clave[2] for clave in _que_llegan_al_certificado(metodos) if not clave[2].startswith('_')}
        self.assertFalse(CONOCIDOS - encontrados, 'El analisis dejo de ver: %s' % sorted(CONOCIDOS - encontrados))

    def test_la_unica_lectura_del_certificado_sin_pasar_por_el_metodo_es_el_campo_de_ajustes(self):
        """Nadie lee ``l10n_co_ne_certificate_ids`` ni ``certificate.certificate`` fuera de ``_get_ne_certificate`` (que usa sudo), salvo el campo relacionado de Ajustes (administrador del sistema)."""
        lecturas = collections.defaultdict(list)
        for ruta in sorted(glob.glob(os.path.join(RAIZ, 'models', '*.py')) + glob.glob(os.path.join(RAIZ, 'wizard', '*.py')) + glob.glob(os.path.join(RAIZ, 'services', '*.py'))):
            arbol = ast.parse(open(ruta, encoding='utf-8').read())
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Attribute) and nodo.attr == 'l10n_co_ne_certificate_ids':
                    lecturas[os.path.relpath(ruta, RAIZ)].append(nodo.lineno)
        self.assertEqual(sorted(lecturas), ['models/res_company.py'], 'Otra lectura de l10n_co_ne_certificate_ids: %s' % dict(lecturas))
