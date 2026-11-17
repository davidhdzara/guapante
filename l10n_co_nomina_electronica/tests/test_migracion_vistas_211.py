# -*- coding: utf-8 -*-
"""Migración .211 (doc 53 §26): se borra la vista heredada que el código ya no trae, antes de cargar el módulo. La vista
vieja nombraba un campo borrado y rompía la validación de la vista combinada del recibo en una base existente."""

import importlib.util
import os

from odoo.tests.common import TransactionCase, tagged

NOMBRE = 'view_payslip_form_ne_documento'


@tagged('post_install', '-at_install')
class TestMigracionVistas211(TransactionCase):

    def _migracion(self):
        ruta = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.3.0.211', 'pre-migration.py')
        spec = importlib.util.spec_from_file_location('pre_migracion_211', ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def _sembrar_vista_vieja(self):
        vista = self.env['ir.ui.view'].create({
            'name': 'hr.payslip.form.ne.documento (vista vieja simulada)', 'model': 'hr.payslip', 'type': 'form',
            'inherit_id': self.env.ref('hr_payroll.view_hr_payslip_form').id, 'priority': 100,
            'arch': '<xpath expr="//notebook" position="inside"><page string="DIAN" name="edi_documents_viejo"/></xpath>'})
        self.env['ir.model.data'].create({
            'module': 'l10n_co_nomina_electronica', 'name': NOMBRE, 'model': 'ir.ui.view', 'res_id': vista.id})
        self.env.flush_all()
        return vista

    def _hay_vista(self, vista_id):
        self.env.cr.execute('SELECT 1 FROM ir_ui_view WHERE id = %s', (vista_id,))
        return bool(self.env.cr.fetchone())

    def _hay_xmlid(self):
        self.env.cr.execute("""SELECT 1 FROM ir_model_data
                                WHERE module = 'l10n_co_nomina_electronica' AND name = %s""", (NOMBRE,))
        return bool(self.env.cr.fetchone())

    def test_borra_la_vista_vieja_y_su_xmlid(self):
        vista = self._sembrar_vista_vieja()
        self.assertTrue(self._hay_vista(vista.id) and self._hay_xmlid())
        self._migracion().migrate(self.env.cr, '18.0.3.0.210')
        self.assertFalse(self._hay_vista(vista.id))
        self.assertFalse(self._hay_xmlid())

    def test_es_idempotente_y_no_toca_otras_vistas(self):
        vista = self._sembrar_vista_vieja()
        propia = self.env.ref('l10n_co_nomina_electronica.view_payslip_form_ne')
        migracion = self._migracion()
        migracion.migrate(self.env.cr, '18.0.3.0.210')
        migracion.migrate(self.env.cr, '18.0.3.0.210')          # segunda corrida: no hace nada
        self.assertFalse(self._hay_vista(vista.id))
        self.assertTrue(self._hay_vista(propia.id))             # la vista vigente del recibo sigue ahí

    def test_sin_la_vista_no_hace_nada(self):
        self.assertFalse(self._hay_xmlid())
        self._migracion().migrate(self.env.cr, '18.0.3.0.210')
        self.assertFalse(self._hay_xmlid())
