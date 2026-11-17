# -*- coding: utf-8 -*-
"""Catálogo de actividades económicas ARL (Decreto 768 de 2022) y su uso en el contrato.

Cubre: búsqueda por código o por descripción, propuesta de la Clase de Riesgo al elegir la
actividad, aviso no bloqueante si se edita la clase a mano, vigencia y unicidad del catálogo, y el
script de post-migración que mapea el texto viejo (solo coincidencia exacta).

Los códigos y clases de estas pruebas son de PRUEBA (sintéticos): el contenido normativo real del
catálogo no se valida aquí.
"""

import importlib.util
import os
from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


def _cargar_migracion(nombre):
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'migrations', '18.0.3.0.114', nombre)
    spec = importlib.util.spec_from_file_location('l10n_co_migracion_114_' + nombre[:4], ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@tagged('post_install', '-at_install')
class TestActividadEconomicaArl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Ciiu = cls.env['l10n.co.pila.ciiu']
        cls.act_bajo = Ciiu.create({'code': 'T0001', 'name': 'Actividad de prueba de oficina',
                                    'risk_class': '1'})
        cls.act_alto = Ciiu.create({'code': 'T0002', 'name': 'Actividad de prueba de minería',
                                    'risk_class': '5'})
        co = cls.env.ref('base.co')
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Actividad ARL'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Actividad ARL', 'country_id': co.id})

    def _contrato(self, **extra):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Actividad ARL', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        vals = {
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Actividad ARL', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2024, 1, 1), 'state': 'open'}
        vals.update(extra)
        return self.env['hr.contract'].create(vals)

    def test_busqueda_por_codigo_y_por_descripcion(self):
        Ciiu = self.env['l10n.co.pila.ciiu']
        por_codigo = [r[0] for r in Ciiu.name_search('T0002')]
        por_nombre = [r[0] for r in Ciiu.name_search('minería')]
        self.assertIn(self.act_alto.id, por_codigo)
        self.assertIn(self.act_alto.id, por_nombre)
        self.assertNotIn(self.act_bajo.id, por_nombre)

    def test_display_name_incluye_codigo_y_descripcion(self):
        self.assertEqual(self.act_alto.display_name, '[T0002] Actividad de prueba de minería')

    def test_elegir_actividad_propone_la_clase_de_riesgo(self):
        contrato = self._contrato()
        contrato.l10n_co_pila_actividad_economica = self.act_alto
        contrato._onchange_pila_actividad_economica()
        self.assertEqual(contrato.l10n_co_pila_clase_riesgo, '5')
        # y sigue editable
        contrato.l10n_co_pila_clase_riesgo = '2'
        self.assertEqual(contrato.l10n_co_pila_clase_riesgo, '2')

    def test_clase_distinta_a_la_de_la_actividad_avisa_sin_bloquear(self):
        contrato = self._contrato(l10n_co_pila_actividad_economica=self.act_alto.id)
        contrato.l10n_co_pila_clase_riesgo = '2'
        resultado = contrato._onchange_pila_clase_riesgo_vs_actividad()
        self.assertIn('warning', resultado)
        self.assertIn('T0002', resultado['warning']['message'])
        contrato.flush_recordset()  # guardar no se bloquea

    def test_clase_igual_a_la_de_la_actividad_no_avisa(self):
        contrato = self._contrato(l10n_co_pila_actividad_economica=self.act_alto.id)
        contrato.l10n_co_pila_clase_riesgo = '5'
        self.assertFalse(contrato._onchange_pila_clase_riesgo_vs_actividad())

    def test_sin_actividad_no_avisa(self):
        contrato = self._contrato()
        contrato.l10n_co_pila_clase_riesgo = '3'
        self.assertFalse(contrato._onchange_pila_clase_riesgo_vs_actividad())

    def test_vigencia_invertida_se_rechaza(self):
        with self.assertRaises(ValidationError):
            self.env['l10n.co.pila.ciiu'].create({
                'code': 'T0003', 'name': 'Vigencia invertida', 'risk_class': '2',
                'date_start': date(2026, 1, 1), 'date_end': date(2025, 1, 1)})

    def test_codigo_y_vigencia_duplicados_se_rechazan(self):
        Ciiu = self.env['l10n.co.pila.ciiu']
        Ciiu.create({'code': 'T0004', 'name': 'Una', 'risk_class': '2', 'date_start': date(2022, 5, 16)})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            Ciiu.create({'code': 'T0004', 'name': 'Otra', 'risk_class': '3',
                         'date_start': date(2022, 5, 16)})

    def test_migracion_mapea_solo_coincidencia_exacta(self):
        post = _cargar_migracion('post-map_actividad_economica.py')
        cr = self.env.cr
        cr.execute('ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS '
                   'l10n_co_pila_actividad_economica_legacy varchar')
        exacto = self._contrato()
        inexacto = self._contrato()
        # .161: la clase de riesgo ya no tiene default '1'; se fija una explícita para probar que
        # la migración no la pisa.
        exacto.l10n_co_pila_clase_riesgo = '3'
        self.env.flush_all()
        cr.execute(
            'UPDATE hr_contract SET l10n_co_pila_actividad_economica_legacy = %s WHERE id = %s',
            (' T0002 ', exacto.id))
        cr.execute(
            'UPDATE hr_contract SET l10n_co_pila_actividad_economica_legacy = %s WHERE id = %s',
            ('texto que no es un código', inexacto.id))
        post.migrate(cr, '18.0.3.0.113')
        exacto.invalidate_recordset(['l10n_co_pila_actividad_economica'])
        inexacto.invalidate_recordset(['l10n_co_pila_actividad_economica'])
        self.assertEqual(exacto.l10n_co_pila_actividad_economica, self.act_alto)
        self.assertFalse(inexacto.l10n_co_pila_actividad_economica)
        # no pisa la clase de riesgo ya guardada; sin coincidencia, sigue vacía (sin default)
        exacto.invalidate_recordset(['l10n_co_pila_clase_riesgo'])
        inexacto.invalidate_recordset(['l10n_co_pila_clase_riesgo'])
        self.assertEqual(exacto.l10n_co_pila_clase_riesgo, '3')
        self.assertFalse(inexacto.l10n_co_pila_clase_riesgo)


@tagged('post_install', '-at_install')
class TestCatalogoCiiuDecreto768(TransactionCase):
    """Contenido cargado desde data/l10n_co_pila_ciiu.xml (Anexo técnico del Decreto 768 de 2022,
    fuente oficial depurada por David: 1.108 filas con 4 duplicados exactos = 1.104 actividades)."""

    def test_se_cargaron_las_1104_actividades(self):
        cargadas = self.env['ir.model.data'].search_count([
            ('module', '=', 'l10n_co_nomina_electronica'),
            ('model', '=', 'l10n.co.pila.ciiu'), ('name', '=like', 'ciiu_%')])
        self.assertEqual(cargadas, 1104)

    def test_clase_de_riesgo_es_el_primer_digito_del_codigo(self):
        for xmlid_name in ('ciiu_2016101', 'ciiu_1131201', 'ciiu_5931201'):
            actividad = self.env.ref('l10n_co_nomina_electronica.' + xmlid_name)
            self.assertEqual(actividad.risk_class, actividad.code[0], xmlid_name)

    def test_actividad_conocida_con_su_descripcion(self):
        actividad = self.env.ref('l10n_co_nomina_electronica.ciiu_2016101')
        self.assertEqual(actividad.risk_class, '2')
        self.assertTrue(actividad.name.startswith('Actividades de apoyo a la agricultura'))
