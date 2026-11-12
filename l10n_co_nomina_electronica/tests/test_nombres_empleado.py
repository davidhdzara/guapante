# -*- coding: utf-8 -*-
"""H-024 (split_name): nombres y apellidos del empleado, prellenados solo sin ambigüedad."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils

_PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'y', 'san', 'santa', 'da', 'di', 'van', 'von'}


@tagged('post_install', '-at_install')
class TestSplitName(TransactionCase):

    def test_una_palabra(self):
        self.assertEqual(dian_utils.split_name('Madonna', _PARTICULAS)['primer_nombre'], 'Madonna')

    def test_dos_palabras(self):
        r = dian_utils.split_name('María Rodríguez', _PARTICULAS)
        self.assertEqual((r['primer_nombre'], r['primer_apellido']), ('María', 'Rodríguez'))

    def test_cuatro_palabras(self):
        r = dian_utils.split_name('Juan Carlos García López', _PARTICULAS)
        self.assertEqual(r, {'primer_nombre': 'Juan', 'otros_nombres': 'Carlos',
                             'primer_apellido': 'García', 'segundo_apellido': 'López'})

    def test_tres_palabras_es_ambiguo(self):
        self.assertFalse(any(dian_utils.split_name('Juan Carlos Pérez', _PARTICULAS).values()))
        self.assertFalse(any(dian_utils.split_name('Mauricio Bedoya Gil', _PARTICULAS).values()))

    def test_particulas_son_ambiguas(self):
        self.assertFalse(any(dian_utils.split_name('María del Carmen López', _PARTICULAS).values()))
        self.assertFalse(any(dian_utils.split_name('Ana de la Cruz', _PARTICULAS).values()))

    def test_cinco_o_mas_es_ambiguo(self):
        self.assertFalse(any(dian_utils.split_name('Juan Carlos Andrés García López', _PARTICULAS).values()))

    def test_vacio(self):
        self.assertFalse(any(dian_utils.split_name('  ', _PARTICULAS).values()))


@tagged('post_install', '-at_install')
class TestNombresEmpleado(TransactionCase):

    def _empleado(self, name, **vals):
        # La compania activa debe ser colombiana: el prellenado solo corre para Colombia.
        self.env.company.partner_id.country_id = self.env.ref('base.co')
        return self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': name, **vals})

    def test_create_prellena_no_ambiguo(self):
        e = self._empleado('Juan Carlos García López')
        self.assertEqual(e._l10n_co_nombre_dian(), {
            'primer_nombre': 'Juan', 'otros_nombres': 'Carlos',
            'primer_apellido': 'García', 'segundo_apellido': 'López'})

    def test_create_deja_vacio_lo_ambiguo_y_exige_completar(self):
        e = self._empleado('Mauricio Bedoya Gil')
        self.assertFalse(e.l10n_co_primer_apellido)
        with self.assertRaisesRegex(UserError, 'Mauricio Bedoya Gil'):
            e._l10n_co_nombre_dian()

    def test_edicion_manual_es_la_fuente(self):
        e = self._empleado('Mauricio Bedoya Gil')
        e.write({'l10n_co_primer_nombre': 'Mauricio', 'l10n_co_primer_apellido': 'Bedoya',
                 'l10n_co_segundo_apellido': 'Gil'})
        self.assertEqual(e._l10n_co_nombre_dian()['segundo_apellido'], 'Gil')

    def test_create_respeta_campos_dados(self):
        e = self._empleado('Mauricio Bedoya Gil', l10n_co_primer_nombre='Mauricio',
                           l10n_co_otros_nombres='Bedoya', l10n_co_primer_apellido='Gil')
        self.assertEqual(e.l10n_co_otros_nombres, 'Bedoya')

    def test_renombrar_no_pisa_lo_editado_a_mano(self):
        e = self._empleado('Mauricio Bedoya Gil')
        e.write({'l10n_co_primer_nombre': 'Mauricio', 'l10n_co_primer_apellido': 'Bedoya'})
        e.write({'name': 'Mauricio Bedoya Gil Jr'})
        self.assertEqual(e.l10n_co_primer_apellido, 'Bedoya')

    def test_renombrar_actualiza_lo_prellenado(self):
        e = self._empleado('María Rodríguez')
        e.write({'name': 'María Gómez'})
        self.assertEqual(e.l10n_co_primer_apellido, 'Gómez')

    def test_falta_el_parametro_de_particulas_error_claro(self):
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'l10n_co_nomina_electronica.particulas_nombre')]).unlink()
        with self.assertRaisesRegex(UserError, 'particulas_nombre'):
            self._empleado('Pedro Pérez')

    def test_xml_trabajador_lee_los_campos(self):
        """_ne_trabajador() usa los campos del empleado, no el nombre partido."""
        e = self._empleado('Mauricio Bedoya Gil')
        e.write({'l10n_co_primer_nombre': 'Mauricio', 'l10n_co_otros_nombres': 'Andrés',
                 'l10n_co_primer_apellido': 'Bedoya', 'l10n_co_segundo_apellido': 'Gil'})
        nombre = e._l10n_co_nombre_dian()
        self.assertEqual(nombre['otros_nombres'], 'Andrés')
