# -*- coding: utf-8 -*-
"""Los 4 crons del módulo nacen INACTIVOS en una instalación nueva (decisión del TL, 22-nov; igual que v19) y sus datos son ``noupdate="1"``: una actualización (``-u``) no cambia el
estado de una base que ya los tiene (producción, con los envíos pausados a mano, queda igual).

Se afirma sobre el XML de los datos (lo que instala una base nueva) y sobre la marca ``noupdate`` de cada registro en la base (lo que protege a las bases existentes). El estado ``active`` real
de una base existente es dato de esa base y NO se afirma aquí."""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import file_open

_CRONES = {
    'ir_cron_ne_habilitacion': 'data/ir_cron_habilitacion.xml',
    'ir_cron_ne_dian_status_recheck': 'data/ir_cron_dian_status_recheck.xml',
    'ir_cron_ne_documento_send': 'data/ir_cron_documento_send.xml',
    'ir_cron_ne_documento_recheck': 'data/ir_cron_documento_send.xml',
}


@tagged('post_install', '-at_install')
class TestCronesInactivos(TransactionCase):

    def _arbol(self, ruta):
        with file_open('l10n_co_nomina_electronica/%s' % ruta, 'rb') as archivo:
            return etree.parse(archivo)

    def test_01_los_cuatro_crons_estan_en_el_xml_con_active_false(self):
        for xmlid, ruta in _CRONES.items():
            registro = self._arbol(ruta).xpath("//record[@id='%s'][@model='ir.cron']" % xmlid)
            self.assertEqual(len(registro), 1, xmlid)
            activo = registro[0].xpath("./field[@name='active']")
            self.assertEqual(len(activo), 1, '%s: debe declarar active explícito' % xmlid)
            self.assertEqual(activo[0].get('eval'), 'False', '%s nace inactivo' % xmlid)

    def test_02_los_datos_de_los_crons_son_noupdate_para_que_el_u_no_cambie_el_estado_de_una_base_existente(self):
        for xmlid, ruta in _CRONES.items():
            registro = self._arbol(ruta).xpath("//record[@id='%s']" % xmlid)[0]
            envolturas = [nodo for nodo in registro.iterancestors() if nodo.get('noupdate') == '1']
            self.assertTrue(envolturas, '%s está en un bloque noupdate="1" del XML' % xmlid)
            dato = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('name', '=', xmlid)])
            self.assertEqual(len(dato), 1, xmlid)
            self.assertTrue(dato.noupdate, '%s: la base lo marca noupdate (una actualización no lo toca)' % xmlid)

    def test_03_todos_los_crons_del_modulo_estan_cubiertos(self):
        """Si alguien agrega un quinto cron al módulo, esta prueba obliga a decidir su estado inicial."""
        crons = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'ir.cron')])
        self.assertEqual(set(crons.mapped('name')), set(_CRONES), 'Los crons del módulo son exactamente los 4 de la decisión')
