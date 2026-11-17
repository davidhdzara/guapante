# -*- coding: utf-8 -*-
"""Frente 4, U2 (doc 57): hoja del aportante con las listas de la Guía UGPP V-20.1 (p. 14-15). Nivel de
verificación: Guía y plantilla leídas; la aceptación en Storm User solo se prueba con Storm real (piloto)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import l10n_co_nomina_ugpp as ugpp


@tagged('post_install', '-at_install')
class TestUgppAportante(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Aportante UGPP', 'country_id': cls.env.ref('base.co').id, 'vat': '900123456-8',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'})
        cls.company.partner_id.l10n_latam_identification_type_id = cls.env.ref('l10n_co.rut')
        cls.company.write({'l10n_co_ugpp_legal_nature': 'privada', 'l10n_co_ugpp_contributor_type': 'empleador'})
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id})

    def test_aportante_con_nit_sin_dv_y_listas_de_la_guia(self):
        self.assertEqual(self.reporte._ugpp_datos_aportante(),
                         ['NI', 900123456, 'Empresa Aportante UGPP', 2, 1, 'NO'])

    def test_la_autorretencion_es_la_exoneracion_del_114_1(self):
        self.company.l10n_co_ne_exoneration_1607 = True
        self.assertEqual(self.reporte._ugpp_datos_aportante()[5], 'SI')
        self.assertNotIn('l10n_co_ugpp_special_autoretention', self.env['res.company']._fields)   # una sola fuente

    def test_cada_opcion_de_las_listas_tiene_su_codigo(self):
        company = self.env['res.company']
        self.assertEqual(set(ugpp._UGPP_NATURALEZA), {k for k, _v in company._fields['l10n_co_ugpp_legal_nature'].selection})
        self.assertEqual(set(ugpp._UGPP_TIPO_APORTANTE),
                         {k for k, _v in company._fields['l10n_co_ugpp_contributor_type'].selection})
        self.assertEqual(sorted(ugpp._UGPP_NATURALEZA.values()), [1, 2, 3, 4, 5])
        self.assertEqual(sorted(ugpp._UGPP_TIPO_APORTANTE.values()), [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])   # el 2 no existe

    def test_ya_no_existen_las_opciones_otra_ni_independiente(self):
        company = self.env['res.company']
        self.assertNotIn('otra', dict(company._fields['l10n_co_ugpp_legal_nature'].selection))
        self.assertNotIn('independiente', dict(company._fields['l10n_co_ugpp_contributor_type'].selection))

    def test_sin_naturaleza_ni_tipo_el_error_nombra_la_compania_y_lo_que_falta(self):
        self.company.write({'l10n_co_ugpp_legal_nature': False, 'l10n_co_ugpp_contributor_type': False})
        with self.assertRaises(UserError) as exc:
            self.reporte._ugpp_datos_aportante()
        mensaje = str(exc.exception)
        self.assertIn('Empresa Aportante UGPP', mensaje)
        self.assertIn('la naturaleza jurídica', mensaje)
        self.assertIn('el tipo de aportante', mensaje)

    def test_sin_tipo_de_identificacion_valido_no_asume_nit(self):
        self.company.partner_id.l10n_latam_identification_type_id = False
        with self.assertRaises(UserError) as exc:
            self.reporte._ugpp_datos_aportante()
        self.assertIn('tipo de identificación', str(exc.exception))

    def test_el_tipo_de_documento_del_aportante_solo_usa_codigos_de_la_guia(self):
        # Guía p. 14: NI, CC, CE, TI, PA, CD, SC, PE. CD y SC no se mapean (sin equivalente DIAN en el módulo).
        self.assertLessEqual(set(ugpp._UGPP_DOC_APORTANTE.values()), {'NI', 'CC', 'CE', 'TI', 'PA', 'CD', 'SC', 'PE'})
        self.assertEqual(ugpp._UGPP_DOC_APORTANTE['31'], 'NI')

    # ── migración 18.0.3.0.233 ───────────────────────────────────────
    def _migrar(self):
        import importlib.util
        import os
        ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '18.0.3.0.233',
                            'pre-ugpp_aportante_listas.py')
        spec = importlib.util.spec_from_file_location('mig_233_ugpp', ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        modulo.migrate(self.env.cr, '18.0.3.0.232')
        self.company.invalidate_recordset()

    def test_migracion_vacia_los_valores_retirados_y_no_toca_los_vigentes(self):
        self.env.cr.execute(
            "UPDATE res_company SET l10n_co_ugpp_legal_nature = 'otra', l10n_co_ugpp_contributor_type = 'independiente' "
            "WHERE id = %s", (self.company.id,))
        self.company.invalidate_recordset()
        self._migrar()
        self.assertFalse(self.company.l10n_co_ugpp_legal_nature)
        self.assertFalse(self.company.l10n_co_ugpp_contributor_type)
        self.company.write({'l10n_co_ugpp_legal_nature': 'mixta', 'l10n_co_ugpp_contributor_type': 'cooperativa'})
        self._migrar()
        self.assertEqual((self.company.l10n_co_ugpp_legal_nature, self.company.l10n_co_ugpp_contributor_type),
                         ('mixta', 'cooperativa'))      # idempotente: lo vigente no se toca
