# -*- coding: utf-8 -*-
"""Menor de QA sobre «cx» (22-nov, decisión del TL): un embargo «Civil / Comercial» salía con la fila «Embargo Fiscal» (el nombre del nodo del XML de la DIAN, no el de un embargo
civil). La regla ``CO_EMBARGO`` se llama ahora «Embargo judicial» y su línea lleva el nombre del TIPO real (``result_name`` nativo) cuando el empleado tiene un solo tipo de embargo
abierto. El nodo del XML (``EmbargoFiscal``) no cambia. NO EJECUTADAS en Odoo al escribirlas."""

from odoo.tests.common import tagged

from . import test_libranzas_tope


@tagged('post_install', '-at_install')
class TestEmbargoNombreLinea(test_libranzas_tope.TestLibranzasNominaReal):

    def _tipo(self, xmlid):
        return self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)

    def _linea_embargo(self, nombre, tipos):
        slip = self._payslip(nombre)
        for xmlid in tipos:
            self._asignacion(slip, self._tipo(xmlid), 400000.0, self.juzgado)
        slip.compute_sheet()
        linea = self._linea(slip, 'CO_EMBARGO')
        self.assertEqual(len(linea), 1, 'Premisa: la regla del embargo genera una sola línea')
        return slip, linea

    def test_la_regla_se_llama_embargo_judicial_y_el_nodo_dian_no_cambia(self):
        regla = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_co_embargo')
        self.assertEqual(regla.name, 'Embargo judicial')
        self.assertNotIn('Fiscal', regla.name)
        self.assertEqual(regla.l10n_co_ne_dian_concept, 'EmbargoFiscal', 'El nodo del XML es el del Anexo Técnico: no cambia')

    def test_un_solo_tipo_la_linea_lleva_el_nombre_del_tipo_real(self):
        for xmlid in ('input_l10n_co_embargo_civil', 'input_l10n_co_embargo_alimentos', 'input_l10n_co_embargo_cooperativa'):
            slip, linea = self._linea_embargo('Embargo %s' % xmlid, [xmlid])
            tipo = self._tipo(xmlid)
            self.assertEqual(linea.name, tipo.name, xmlid)
            self.assertNotIn('Fiscal', linea.name)
            self.assertEqual(slip._ne_nombre_embargo(), tipo.name)

    def test_el_nombre_llega_a_conceptos_de_pago(self):
        slip, linea = self._linea_embargo('Embargo en conceptos', ['input_l10n_co_embargo_civil'])
        fila = slip.l10n_co_concepto_ids.filtered(lambda f: f.line_id == linea)
        self.assertEqual(fila.name, 'Embargo - Civil / Comercial')

    def test_varios_tipos_la_linea_lleva_el_nombre_neutro_de_la_regla(self):
        slip, linea = self._linea_embargo('Embargo varios', ['input_l10n_co_embargo_civil', 'input_l10n_co_embargo_alimentos'])
        self.assertFalse(slip._ne_nombre_embargo())
        self.assertEqual(linea.name, 'Embargo judicial')
