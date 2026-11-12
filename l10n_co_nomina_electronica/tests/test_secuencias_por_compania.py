# -*- coding: utf-8 -*-
"""M1 (doc 51): cada compania colombiana lleva sus propias secuencias de nomina electronica
(consecutivo NE, temporal PRE-NOM, ajuste NA); una compania de otro pais no recibe ninguna.
La migracion conserva el siguiente numero (nunca reinicia ni salta).
Valores a mano: prefijo NE y relleno de 10 digitos -> el primer numero es 'NE0000000001'."""

import importlib.util
import os
from datetime import date

from odoo.tests.common import TransactionCase, tagged


def _migracion():
    ruta = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.3.0.175',
                        'post-secuencias_por_compania.py')
    spec = importlib.util.spec_from_file_location('migracion_175', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@tagged('post_install', '-at_install')
class TestSecuenciasPorCompania(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Secuencias', 'country_id': cls.env.ref('base.co').id})
        cls.a = cls._compania('Empresa A Secuencias', 'base.co')
        cls.b = cls._compania('Empresa B Secuencias', 'base.co')
        cls.m = cls._compania('Empresa M Secuencias', 'base.mx')
        cls.plantilla_ne = cls.env.ref(
            'l10n_co_nomina_electronica.seq_l10n_co_nomina_electronica')
        cls.plantilla_ajuste = cls.env.ref('l10n_co_nomina_electronica.seq_l10n_co_nomina_ajuste')

    @classmethod
    def _compania(cls, nombre, pais):
        return cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 
            'name': nombre, 'country_id': cls.env.ref(pais).id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN'})

    def _con_consecutivo(self, company, numero, prefijo='NE'):
        empleado = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Emp %s %s' % (company.name, numero), 'company_id': company.id})
        contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'C', 'employee_id': empleado.id, 'company_id': company.id,
            'structure_type_id': self.tipo.id, 'wage': 1000000.0,
            'date_start': date(2026, 1, 1), 'state': 'open'})
        slip = self.env['hr.payslip'].create({
            'name': 'R', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': company.id, 'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        slip.l10n_co_ne_consecutive = '%s%010d' % (prefijo, numero)
        return slip

    def _como_heredada(self, company):
        """Deja a la compania como antes de .175: apuntando a las secuencias compartidas."""
        propias = self.env['ir.sequence'].search([
            ('company_id', '=', company.id), ('code', 'like', 'l10n_co_nomina.%')])
        company.l10n_co_ne_sequence_id = self.plantilla_ne
        company.l10n_co_ne_pre_sequence_id = self.env.ref(
            'l10n_co_nomina_electronica.seq_l10n_co_nomina_temporal')
        propias.unlink()

    def test_cada_compania_colombiana_tiene_las_suyas_desde_1(self):
        for company in (self.a, self.b):
            self.assertEqual(company.l10n_co_ne_sequence_id.company_id, company)
            self.assertEqual(company.l10n_co_ne_pre_sequence_id.company_id, company)
            self.assertEqual(company.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000001')
        self.assertNotEqual(self.a.l10n_co_ne_sequence_id, self.b.l10n_co_ne_sequence_id)
        # la de A ya gasto un numero y la de B sigue en 2 al pedir el siguiente de cada una
        self.assertEqual(self.a.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000002')
        self.assertEqual(self.b.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000002')

    def test_la_compania_mexicana_no_recibe_secuencias(self):
        self.assertFalse(self.m.l10n_co_ne_sequence_id)
        self.assertFalse(self.m.l10n_co_ne_pre_sequence_id)
        self.assertFalse(self.env['ir.sequence'].search_count(
            [('company_id', '=', self.m.id), ('code', 'like', 'l10n_co_nomina.%')]))

    def test_migracion_unica_compania_conserva_el_siguiente_compartido(self):
        migracion = _migracion()
        self._como_heredada(self.a)
        self.plantilla_ne.number_next = 82
        migracion.separar_secuencias(self.env, self.a)
        self.assertEqual(self.a.l10n_co_ne_sequence_id.company_id, self.a)
        self.assertEqual(self.a.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000082')

    def test_migracion_dos_companias_una_con_historial(self):
        """A usado hasta 41 y el compartido en 82 (numeros quemados): A sigue en 82; B, sin
        historial, empieza en 1."""
        migracion = _migracion()
        self._como_heredada(self.a)
        self._como_heredada(self.b)
        self._con_consecutivo(self.a, 40)
        self._con_consecutivo(self.a, 41)
        self.plantilla_ne.number_next = 82
        migracion.separar_secuencias(self.env, self.a | self.b)
        self.assertEqual(self.a.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000082')
        self.assertEqual(self.b.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000001')

    def test_migracion_dos_companias_con_historial_cada_una_sigue_la_suya(self):
        migracion = _migracion()
        self._como_heredada(self.a)
        self._como_heredada(self.b)
        self._con_consecutivo(self.a, 41)
        self._con_consecutivo(self.b, 10)
        self.plantilla_ne.number_next = 82
        migracion.separar_secuencias(self.env, self.a | self.b)
        self.assertEqual(self.a.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000042')
        self.assertEqual(self.b.l10n_co_ne_sequence_id.next_by_id(), 'NE0000000011')

    def test_migracion_es_idempotente(self):
        migracion = _migracion()
        propia = self.a.l10n_co_ne_sequence_id
        migracion.separar_secuencias(self.env, self.a | self.b)
        self.assertEqual(self.a.l10n_co_ne_sequence_id, propia)

    def test_el_ajuste_usa_la_secuencia_propia_de_la_compania(self):
        propia = self.env['ir.sequence'].search([
            ('company_id', '=', self.a.id), ('code', '=', 'l10n_co_nomina.ajuste')])
        self.assertEqual(len(propia), 1)
        self.assertEqual(propia.prefix, 'NA')
        self.assertEqual(propia.next_by_id(), 'NA0000000001')
