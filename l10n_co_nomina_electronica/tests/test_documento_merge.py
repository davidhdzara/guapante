# -*- coding: utf-8 -*-
"""Spike de la etapa 3 (doc 53 §5.3, §18.5): fusion pura de los diccionarios de varios recibos en UN
documento mensual. Valores a mano; funcion sin Odoo."""

import copy

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import documento_merge as dm


def _recibo(sueldo='1500000.00', dias='15', aux='124547.50', salud='60000.00', pension='60000.00'):
    return {
        'trabajador': {'NumeroDocumento': '1020304050', 'Sueldo': '3000000.00'},
        'pago': {'Forma': '1', 'Metodo': '10'},
        'empleador': {'NIT': '900123456'},
        'informacion_general': {'PeriodoNomina': '4', 'TipoXML': '102'},
        'numero_secuencia': {'Numero': 'NE1'},
        'devengados': {
            'Basico': {'DiasTrabajados': dias, 'SueldoTrabajado': sueldo},
            'Transporte': {'AuxilioTransporte': aux}},
        'deducciones': {
            'Salud': {'Porcentaje': '4.00', 'Deduccion': salud},
            'FondoPension': {'Porcentaje': '4.00', 'Deduccion': pension}},
        'devengados_total': 1624547.50, 'deducciones_total': 120000.00,
    }


PERIODO = {'FechaLiquidacionInicio': '2026-03-01', 'FechaLiquidacionFin': '2026-03-31'}


@tagged('post_install', '-at_install')
class TestDocumentoMerge(TransactionCase):
    def _doc(self, recibos, fechas=('2026-03-15', '2026-03-31')):
        return dm.fusionar_documento(recibos, fechas_pagos=list(fechas), periodo=PERIODO)

    def test_dos_quincenas_suman_basico_transporte_y_deducciones(self):
        doc = self._doc([_recibo(), _recibo()])
        self.assertEqual(doc['devengados']['Basico'], {'DiasTrabajados': '30', 'SueldoTrabajado': '3000000.00'})
        self.assertEqual(doc['devengados']['Transporte'], [{'AuxilioTransporte': '249095.00'}])
        self.assertEqual(doc['deducciones']['Salud'], {'Porcentaje': '4.00', 'Deduccion': '120000.00'})
        self.assertEqual(doc['deducciones']['FondoPension']['Deduccion'], '120000.00')

    def test_totales_son_la_suma_de_los_recibos(self):
        doc = self._doc([_recibo(), _recibo()])
        self.assertEqual(doc['totales'], {
            'DevengadosTotal': '3249095.00', 'DeduccionesTotal': '240000.00',
            'ComprobanteTotal': '3009095.00'})
        self.assertEqual(doc['comprobante_total'], 3009095.0)

    def test_periodo_nomina_es_mensual_y_las_fechas_de_pago_son_distintas_y_ordenadas(self):
        doc = self._doc([_recibo(), _recibo()], fechas=('2026-03-31', '2026-03-15', '2026-03-15'))
        self.assertEqual(doc['informacion_general']['PeriodoNomina'], '5')
        self.assertEqual(doc['fechas_pagos'], ['2026-03-15', '2026-03-31'])
        self.assertEqual(doc['periodo'], PERIODO)

    def test_las_listas_se_concatenan_sin_colapsar(self):
        a, b = _recibo(), _recibo()
        a['devengados']['HEDs'] = [{'Cantidad': '4', 'Porcentaje': '25.00', 'Pago': '48000.00'}]
        b['devengados']['HEDs'] = [{'Cantidad': '2', 'Porcentaje': '25.00', 'Pago': '24000.00'}]
        b['devengados']['Incapacidades'] = [{'Cantidad': '2', 'Tipo': '1', 'Pago': '66666.67'}]
        doc = self._doc([a, b])
        self.assertEqual([h['Cantidad'] for h in doc['devengados']['HEDs']], ['4', '2'])
        self.assertEqual(len(doc['devengados']['Incapacidades']), 1)

    def test_prima_y_retencion_se_suman_como_nodos_unicos_y_escalares(self):
        a, b = _recibo(), _recibo()
        b['devengados']['Primas'] = {'Cantidad': '178', 'Pago': '1624547.50'}
        a['deducciones']['RetencionFuente'] = '100000.00'
        b['deducciones']['RetencionFuente'] = '479649.00'
        doc = self._doc([a, b])
        self.assertEqual(doc['devengados']['Primas'], {'Cantidad': '178', 'Pago': '1624547.50'})
        self.assertEqual(doc['deducciones']['RetencionFuente'], '579649.00')

    def test_vacaciones_concatenan_cada_grupo(self):
        a, b = _recibo(), _recibo()
        a['devengados']['Vacaciones'] = {'VacacionesComunes': [{'Cantidad': '5', 'Pago': '500000.00'}]}
        b['devengados']['Vacaciones'] = {
            'VacacionesComunes': [{'Cantidad': '2', 'Pago': '200000.00'}],
            'VacacionesCompensadas': [{'Cantidad': '3', 'Pago': '300000.00'}]}
        doc = self._doc([a, b])
        self.assertEqual(len(doc['devengados']['Vacaciones']['VacacionesComunes']), 2)
        self.assertEqual(len(doc['devengados']['Vacaciones']['VacacionesCompensadas']), 1)

    def test_porcentaje_distinto_en_el_mes_falla_con_error_claro(self):
        a, b = _recibo(), _recibo()
        b['deducciones']['Salud']['Porcentaje'] = '12.50'
        with self.assertRaises(dm.ErrorFusion) as exc:
            self._doc([a, b])
        self.assertIn('Porcentaje', str(exc.exception))

    def test_trabajador_distinto_falla_nombrando_la_seccion(self):
        a, b = _recibo(), _recibo()
        b['trabajador'] = dict(b['trabajador'], Sueldo='3500000.00')
        with self.assertRaises(dm.ErrorFusion) as exc:
            self._doc([a, b])
        self.assertIn('trabajador', str(exc.exception))

    def test_sin_fecha_de_pago_o_sin_recibos_falla(self):
        with self.assertRaises(dm.ErrorFusion):
            self._doc([_recibo()], fechas=())
        with self.assertRaises(dm.ErrorFusion):
            self._doc([])

    def test_no_modifica_los_diccionarios_de_entrada(self):
        a, b = _recibo(), _recibo()
        copia = copy.deepcopy(a)
        self._doc([a, b])
        self.assertEqual(a, copia)

    def test_un_recibo_sin_transporte_no_genera_transporte(self):
        a = _recibo()
        a['devengados'].pop('Transporte')
        doc = self._doc([a])
        self.assertNotIn('Transporte', doc['devengados'])
