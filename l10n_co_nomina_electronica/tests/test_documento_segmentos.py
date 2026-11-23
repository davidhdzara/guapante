# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F3-04, opción A del doc 95 (decisiones del TL del 23-nov; doc 98): cuando el tipo de trabajador de un empleado cambia dentro del mes y la compañía activó la separación, el mes se parte en un documento
mensual por tramo CONSECUTIVO (A, B, A = tres); del segundo en adelante el XML lleva ``Novedad = true`` con el CUNE del anterior y no sale hasta que el anterior sea aceptado. Apagado (por defecto) el módulo
es el de siempre. NO VERIFICADO con la DIAN (doc 95 §4): nada de esto se ha transmitido. Todo con *mock*: ninguna prueba llama a la DIAN.

Las pruebas de la función pura y del lector del XML no necesitan Odoo; las demás usan el fixture del documento mensual y parchean la CLAVE del segmento (el tipo de trabajador real del aprendiz se prueba en
``test_aprendiz_regimen``)."""

import base64
import copy
from datetime import date, timedelta
from unittest.mock import MagicMock

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, documento_segmentos, ne_xml_utils, nomina_xml_builder, soap_client, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_enviar import ACEPTADA, PENDIENTE
from .test_documento_generar import FECHA, HORA, NS, PIN, _quincena_con_prima
from .test_documento_merge import _recibo

A, B, C = ('12', '00'), ('19', '00'), ('01', '00')
CUNE_1 = 'a' * 96


def _xml_con_novedad(datos):
    """Un XML mínimo como el que arma el constructor: ``Novedad`` primero (si el documento la lleva) e ``InformacionGeneral`` para insertar el CUNE."""
    novedad = datos.get('novedad')
    nodo = '<Novedad CUNENov="%s">true</Novedad>' % novedad['CUNENov'] if novedad else ''
    return ('<NominaIndividual xmlns="%s">%s<InformacionGeneral/></NominaIndividual>' % (NS, nodo)).encode()


@tagged('post_install', '-at_install')
class TestSegmentarPura(BaseCase):
    """``documento_segmentos.segmentar``: rachas consecutivas de la misma clave (sin Odoo)."""

    def test_sin_recibos_no_hay_segmentos(self):
        self.assertEqual(documento_segmentos.segmentar([]), [])

    def test_sin_cambio_de_clave_es_un_solo_segmento(self):
        self.assertEqual(documento_segmentos.segmentar([A]), [[0]])
        self.assertEqual(documento_segmentos.segmentar([A, A, A]), [[0, 1, 2]])

    def test_lectiva_a_practica_son_dos_segmentos(self):
        self.assertEqual(documento_segmentos.segmentar([A, A, B, B]), [[0, 1], [2, 3]])

    def test_a_b_a_son_TRES_segmentos_consecutivos_y_no_dos_por_clave(self):
        """Decisión del TL (Q2): la cadena CUNENov sigue el orden en el tiempo; agrupar por clave reordenaría documentos ya transmitidos."""
        self.assertEqual(documento_segmentos.segmentar([A, B, A]), [[0], [1], [2]])
        self.assertEqual(documento_segmentos.segmentar([A, A, B, A, A]), [[0, 1], [2], [3, 4]])

    def test_una_clave_sin_resolver_se_suma_al_segmento_abierto(self):
        self.assertEqual(documento_segmentos.segmentar([None, A, A]), [[0, 1, 2]])
        self.assertEqual(documento_segmentos.segmentar([A, None, B]), [[0, 1], [2]])
        self.assertEqual(documento_segmentos.segmentar([A, None, A]), [[0, 1, 2]])
        self.assertEqual(documento_segmentos.segmentar([A, B, None, A]), [[0], [1, 2], [3]])
        self.assertEqual(documento_segmentos.segmentar([None, None]), [[0, 1]])

    def test_el_lector_del_xml_da_el_cunenov_o_vacio(self):
        con = ('<NominaIndividual xmlns="%s"><Novedad CUNENov="abc">true</Novedad><InformacionGeneral/></NominaIndividual>' % NS).encode()
        sin = ('<NominaIndividual xmlns="%s"><InformacionGeneral/></NominaIndividual>' % NS).encode()
        self.assertEqual(ne_xml_utils.cunenov_de_xml(con), 'abc')
        self.assertEqual(ne_xml_utils.cunenov_de_xml(sin), '')


@tagged('post_install', '-at_install')
class TestDocumentoPorSegmento(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Segmentos')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '1'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE segmentos', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        cls.company.l10n_co_ne_sequence_id = cls.secuencia

    def setUp(self):
        super().setUp()
        self.claves = {}          # id del recibo -> clave (para un caso puntual)
        self.clave_por_dia = lambda dia: A if dia <= 15 else B          # por defecto: hasta el 15 «A», después «B»

        def clave(slip):
            return self.claves.get(slip.id) or self.clave_por_dia(slip.date_to.day)

        def fabrica(slip):
            datos = copy.deepcopy(_quincena_con_prima() if slip.date_to.day > 15 else _recibo())
            datos['informacion_general'] = dict(datos['informacion_general'], FechaGen=FECHA, HoraGen=HORA)
            return datos
        self._patch(type(self.env['hr.payslip']), '_ne_clave_segmento', lambda s: clave(s))
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: fabrica(s))
        self._patch(dian_utils, 'compute_software_security_code', lambda *a: 'SC')
        self._patch(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        self._patch(type(self.env['l10n.co.ne.documento']), '_ne_validar_datos_recibo', lambda s, slip: None)
        self._patch(type(self.company), '_get_ne_certificate', lambda s: True)
        self._patch(dian_utils, 'clean_nit', lambda *a, **k: '900123456')
        self._patch(xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None))
        self._patch(xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)
        self._patch(nomina_xml_builder, 'build_nomina_individual_v2', _xml_con_novedad)
        self.soap = MagicMock(name='send_nomina_sync', return_value=ACEPTADA)
        self._patch(soap_client, 'send_nomina_sync', self.soap)
        self.trigger = MagicMock(name='_trigger')
        self._patch(type(self.env['ir.cron']), '_trigger', self.trigger)
        self.bus = MagicMock(name='_sendone')
        self._patch(type(self.env['bus.bus']), '_sendone', self.bus)
        self.Doc = self.env['l10n.co.ne.documento']

    # ── ayudas ──────────────────────────────────────────────────────
    def _recibos_sueltos(self, **kwargs):
        """Los recibos pagados de un mes (fixture del documento mensual) SIN documento, listos para ``_ne_preparar``."""
        doc = self._documento(date(2024, 3, 1), **kwargs)
        recibos = doc.payslip_ids
        recibos.write({'l10n_co_ne_documento_id': False})
        doc.unlink()
        return recibos

    def _segmentados(self, encendido=True, **kwargs):
        self.company.l10n_co_ne_segmentar_mes = encendido
        recibos = self._recibos_sueltos(**kwargs)
        return recibos, self.Doc._ne_preparar(recibos)['documentos'].filtered(lambda d: not d.is_adjustment).sorted('segmento')

    def _aceptar(self, doc):
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'numero': 'ACEPTADO-%s' % doc.id, 'identifier': doc.cune, 'datetime': fields.Datetime.now() + timedelta(minutes=1)})
        self.assertEqual(doc.state, 'invoice_accepted')

    def _generados(self, docs):
        for doc in docs:
            doc._ne_validar()
            doc.action_generar_xml()
        return docs

    # ── la separación apagada: todo como siempre ────────────────────
    def test_apagado_el_mes_con_cambio_de_tipo_sigue_siendo_un_solo_documento(self):
        recibos, docs = self._segmentados(encendido=False)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs.segmento, 1)
        self.assertEqual(docs.payslip_ids, recibos)
        self.assertFalse(docs.novedad_de_id)
        self.assertFalse(any(recibos.mapped('l10n_co_ne_aviso_segmento')))

    def test_el_ajuste_viene_apagado_por_defecto(self):
        self.assertFalse(self.env['res.company'].create({'name': 'Compañía Sin Ajuste', 'country_id': self.env.ref('base.co').id,
                                                          'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
                                                          'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'}).l10n_co_ne_segmentar_mes)

    # ── encendido: un documento por segmento ────────────────────────
    def test_encendido_hay_un_documento_por_segmento_y_el_segundo_es_novedad_del_primero(self):
        recibos, docs = self._segmentados()
        self.assertEqual(docs.mapped('segmento'), [1, 2])
        uno, dos = docs
        self.assertEqual(uno.payslip_ids.mapped('date_to'), [date(2026, 3, 15)])
        self.assertEqual(dos.payslip_ids.mapped('date_to'), [date(2026, 3, 31)])
        self.assertFalse(uno.novedad_de_id)
        self.assertEqual(dos.novedad_de_id, uno)
        self.assertTrue(dos.name.endswith('(2)'))
        self.assertFalse(uno.name.endswith('(1)'))

    def test_preparar_otra_vez_no_duplica_ni_cambia_los_documentos(self):
        recibos, docs = self._segmentados()
        otra = self.Doc._ne_preparar(recibos)['documentos'].filtered(lambda d: not d.is_adjustment).sorted('segmento')
        self.assertEqual(otra, docs)

    def test_a_b_a_da_tres_documentos_en_cadena_lineal(self):
        self.clave_por_dia = lambda dia: B if 15 < dia <= 25 else A       # A hasta el 15, B del 16 al 25 y otra vez A
        recibos, docs = self._segmentados(pagos=((10, 10), (20, 20), (31, 31)))
        self.assertEqual(docs.mapped('segmento'), [1, 2, 3])
        self.assertEqual(docs[1].novedad_de_id, docs[0])
        self.assertEqual(docs[2].novedad_de_id, docs[1])             # el inmediato anterior, no el primero

    def test_sin_cambio_de_tipo_encendido_sigue_siendo_un_documento_sin_novedad(self):
        self.claves = {}
        self.company.l10n_co_ne_segmentar_mes = True
        recibos = self._recibos_sueltos(pagos=((5, 5), (12, 12)))
        docs = self.Doc._ne_preparar(recibos)['documentos']
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs.segmento, 1)
        self.assertFalse(docs.novedad_de_id)

    def test_la_unicidad_es_por_segmento(self):
        _recibos, docs = self._segmentados()
        uno = docs[0]
        with self.assertRaises(ValidationError):                       # otro original del mismo segmento
            self.Doc.create({'company_id': uno.company_id.id, 'employee_id': uno.employee_id.id, 'period': uno.period, 'segmento': 1})
        tres = self.Doc.create({'company_id': uno.company_id.id, 'employee_id': uno.employee_id.id, 'period': uno.period, 'segmento': 3})
        self.assertEqual(tres.segmento, 3)

    def test_la_nota_de_ajuste_hereda_el_segmento_de_su_original(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        self._aceptar(docs[0])
        self._aceptar(docs[1])
        nota = docs[1].action_crear_ajuste('1')
        self.assertEqual(nota.segmento, 2)
        self.assertEqual(nota.parent_id, docs[1])

    # ── el periodo provisional del segmento (NV doc 95 §4.2) ────────
    def test_con_el_mes_partido_el_periodo_de_cada_documento_es_el_de_sus_recibos(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        periodo_1 = uno._collect_documento_data()['periodo']
        periodo_2 = dos._collect_documento_data()['periodo']
        self.assertEqual((periodo_1['FechaLiquidacionInicio'], periodo_1['FechaLiquidacionFin']), ('2026-03-01', '2026-03-15'))
        self.assertEqual((periodo_2['FechaLiquidacionInicio'], periodo_2['FechaLiquidacionFin']), ('2026-03-16', '2026-03-31'))

    def test_sin_mes_partido_el_periodo_es_el_mes_entero(self):
        self.company.l10n_co_ne_segmentar_mes = True
        recibos = self._recibos_sueltos(pagos=((5, 5), (12, 12)))
        doc = self.Doc._ne_preparar(recibos)['documentos']
        periodo = doc._collect_documento_data()['periodo']
        self.assertEqual((periodo['FechaLiquidacionInicio'], periodo['FechaLiquidacionFin']), ('2026-03-01', '2026-03-31'))

    # ── la «Novedad» del XML ────────────────────────────────────────
    def test_el_segundo_documento_lleva_novedad_con_el_cune_del_primero_y_el_primero_no(self):
        _recibos, docs = self._segmentados()
        uno, dos = docs
        with self.assertRaisesRegex(UserError, 'Genere primero el XML del documento anterior'):
            dos._collect_documento_data()                                   # estricto: sin el CUNE del anterior no se arma
        self.assertNotIn('novedad', dos._collect_documento_data(validando=True))     # al validar solo se prueba la fusión
        uno.cune = CUNE_1
        self.assertEqual(dos._collect_documento_data()['novedad'], {'CUNENov': CUNE_1, 'value': True})
        self.assertNotIn('novedad', uno._collect_documento_data())

    def test_el_xml_generado_del_segundo_documento_lleva_el_cunenov_del_primero(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        self.assertTrue(uno.cune)
        self.assertEqual(ne_xml_utils.cunenov_de_xml(base64.b64decode(dos.xml_attachment_id.datas)), uno.cune)
        self.assertEqual(ne_xml_utils.cunenov_de_xml(base64.b64decode(uno.xml_attachment_id.datas)), '')

    def test_un_porcentaje_distinto_con_el_mismo_tipo_sigue_deteniendo_con_error_que_nombra_al_empleado(self):
        """Decisión del TL (Q3): el porcentaje NO entra en la clave. Dos recibos del mismo tipo con porcentajes distintos no se separan: la fusión se detiene."""
        self.company.l10n_co_ne_segmentar_mes = True
        recibos = self._recibos_sueltos(pagos=((5, 5), (12, 12)))
        original = type(self.env['hr.payslip'])._collect_payslip_data

        def con_porcentaje_distinto(slip):
            datos = original(slip)
            if slip.date_to.day == 12:
                datos['deducciones']['Salud'] = dict(datos['deducciones']['Salud'], Porcentaje='5.00')
            return datos
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', con_porcentaje_distinto)
        doc = self.Doc._ne_preparar(recibos)['documentos']
        self.assertEqual(len(doc), 1)
        with self.assertRaises(UserError) as error:
            doc._collect_documento_data()
        self.assertIn('Porcentaje', str(error.exception))
        self.assertIn(doc.employee_id.name, str(error.exception))

    def test_con_la_separacion_apagada_el_error_de_cambio_de_tipo_conserva_el_mensaje_y_dice_donde_activarla(self):
        self.company.l10n_co_ne_segmentar_mes = False
        original = type(self.env['hr.payslip'])._collect_payslip_data

        def con_tipo_distinto(slip):
            datos = original(slip)
            datos['trabajador'] = dict(datos.get('trabajador') or {}, TipoTrabajador='12' if slip.date_to.day <= 15 else '19')
            return datos
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', con_tipo_distinto)
        recibos = self._recibos_sueltos()
        doc = self.Doc._ne_preparar(recibos)['documentos']
        with self.assertRaises(UserError) as error:
            doc._collect_documento_data()
        for esperado in ('cambia de tipo de trabajador dentro del mes', 'Separar el mes en documentos por cambio de tipo de trabajador', 'NO está verificado con la DIAN'):
            self.assertIn(esperado, str(error.exception))

    # ── el segundo espera al primero ────────────────────────────────
    def test_el_segundo_espera_mientras_el_primero_no_este_aceptado(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        self.assertFalse(uno._ne_espera_anterior())                     # el primero no espera a nadie
        self.assertIn('queda pendiente hasta que', dos._ne_espera_anterior())
        self._aceptar(uno)
        self.assertFalse(dos._ne_espera_anterior())                     # aceptado y con el CUNENov vigente

    def test_si_el_anterior_fue_rechazado_el_segundo_no_espera_en_vano_da_error(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': uno.id, 'state': 'invoice_rejected', 'numero': 'RECHAZADO-1', 'identifier': uno.cune, 'datetime': fields.Datetime.now() + timedelta(minutes=1)})
        self.assertEqual(uno.state, 'invoice_rejected')
        with self.assertRaisesRegex(UserError, 'rechazó el documento anterior'):
            dos._ne_espera_anterior()

    def test_si_el_xml_del_segundo_lleva_un_cunenov_que_ya_no_es_el_del_anterior_hay_que_regenerarlo(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        self._aceptar(uno)
        uno.cune = 'b' * 96                                              # el anterior se regeneró: su CUNE cambió
        with self.assertRaisesRegex(UserError, 'Genere de nuevo el XML'):
            dos._ne_espera_anterior()

    def test_con_la_separacion_apagada_el_segundo_no_sale(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        self.company.l10n_co_ne_segmentar_mes = False
        with self.assertRaisesRegex(UserError, 'apagada'):
            docs[1]._ne_espera_anterior()
        with self.assertRaisesRegex(UserError, 'apagada'):
            docs[1]._ne_precondiciones_envio(permitir_espera=True)

    def test_encolar_acepta_esperar_y_enviar_no(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        with self.assertRaisesRegex(UserError, 'queda pendiente hasta que'):
            dos._ne_precondiciones_envio()                              # enviar: no
        dos._ne_encolar()                                               # encolar: sí (el cron lo deja en espera)
        self.assertTrue(dos.is_being_sent)

    def test_el_cron_deja_en_espera_al_segundo_y_lo_envia_cuando_el_primero_es_aceptado(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        self.soap.return_value = PENDIENTE                              # el primero queda pendiente de veredicto
        (uno | dos)._ne_encolar()
        self.Doc._cron_enviar_cola()
        self.assertEqual(uno.state, 'invoice_pending')
        self.assertEqual(self.soap.call_count, 1)                       # al segundo NO se le llamó a la DIAN
        self.assertTrue(dos.is_being_sent)
        self.assertNotIn('error', dos.sending_data)
        self.assertGreater(fields.Datetime.to_datetime(dos.sending_data['proximo']), fields.Datetime.now())      # se reintenta más tarde
        self.assertTrue(dos.message_ids.filtered(lambda m: m.body and 'queda pendiente hasta que' in str(m.body)))
        # el primero se acepta (la reconsulta): el segundo sale en la siguiente pasada
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': uno.id, 'state': 'invoice_accepted', 'numero': 'ACEPTADO-1', 'identifier': uno.cune, 'datetime': fields.Datetime.now() + timedelta(minutes=1)})
        self.assertEqual(uno.state, 'invoice_accepted')
        dos.sending_data = dict(dos.sending_data, proximo='2000-01-01 00:00:00')
        self.soap.return_value = ACEPTADA
        self.Doc._cron_enviar_cola()
        self.assertEqual(dos.state, 'invoice_accepted')

    def test_una_pasada_envia_los_dos_en_orden_si_el_primero_es_aceptado(self):
        _recibos, docs = self._segmentados()
        self._generados(docs)
        uno, dos = docs
        (uno | dos)._ne_encolar()
        self.Doc._cron_enviar_cola()
        self.assertEqual((uno.state, dos.state), ('invoice_accepted', 'invoice_accepted'))
        self.assertEqual(self.soap.call_count, 2)

    # ── lo ya transmitido no se rehace (Q6) ─────────────────────────
    def test_un_recibo_que_abriria_un_segmento_antes_de_uno_transmitido_no_se_adopta_y_se_avisa(self):
        recibos, docs = self._segmentados()
        self._generados(docs)
        self._aceptar(docs[0])
        self._aceptar(docs[1])
        # llega un recibo del 5 de marzo con OTRO tipo: quedaría ANTES de los dos documentos ya transmitidos
        nuevo = self.env['hr.payslip'].create({
            'name': 'Recibo tardío', 'employee_id': docs[0].employee_id.id, 'contract_id': docs[0].contract_id.id, 'company_id': self.company.id,
            'struct_id': recibos[0].struct_id.id, 'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 5)})
        nuevo.write({'state': 'paid', 'paid_date': date(2026, 3, 5)})
        self.claves[nuevo.id] = C
        antes = self.Doc.search([('employee_id', '=', docs[0].employee_id.id)])
        self.Doc._ne_preparar(nuevo)
        self.assertEqual(self.Doc.search([('employee_id', '=', docs[0].employee_id.id)]), antes)      # no se creó ningún documento
        self.assertFalse(nuevo.l10n_co_ne_documento_id)                                                # y no se adoptó
        aviso = self.Doc._ne_aviso_de_segmento(nuevo)
        self.assertTrue(aviso)
        self.assertIn('no coinciden con los segmentos de hoy', aviso)
        nuevo.invalidate_recordset()
        self.assertEqual(nuevo.l10n_co_ne_aviso_segmento, aviso)                                      # el recibo lo muestra

    def test_un_recibo_tardio_de_un_segmento_transmitido_se_adopta_en_su_nota_y_no_en_otro_documento(self):
        recibos, docs = self._segmentados()
        self._generados(docs)
        self._aceptar(docs[0])
        self._aceptar(docs[1])
        nota = docs[1].action_crear_ajuste('1')                         # la nota Reemplazar del segmento 2
        nuevo = self.env['hr.payslip'].create({
            'name': 'Recibo tardío B', 'employee_id': docs[0].employee_id.id, 'contract_id': docs[0].contract_id.id, 'company_id': self.company.id,
            'struct_id': recibos[0].struct_id.id, 'date_from': date(2026, 3, 20), 'date_to': date(2026, 3, 25)})
        nuevo.write({'state': 'paid', 'paid_date': date(2026, 3, 25)})          # día 25 -> clave B, la del segmento 2 (el recibo del 31)
        self.Doc._ne_preparar(nuevo)
        self.assertEqual(nuevo.l10n_co_ne_documento_id, nota)
        self.assertFalse(docs[0].payslip_ids & nuevo)

    # ── el ajuste solo lo cambia el administrador del sistema ───────
    def _usuario(self, login, grupos):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    def test_solo_el_administrador_del_sistema_cambia_el_ajuste(self):
        admin_nomina = self._usuario('seg_admin_nomina', ['hr_payroll.group_hr_payroll_manager'])
        with self.assertRaisesRegex(AccessError, 'administrador del sistema'):
            self.company.with_user(admin_nomina).write({'l10n_co_ne_segmentar_mes': True})
        self.assertFalse(self.company.l10n_co_ne_segmentar_mes)
        sistema = self._usuario('seg_sistema', ['base.group_system'])
        self.company.with_user(sistema).write({'l10n_co_ne_segmentar_mes': True})
        self.assertTrue(self.company.l10n_co_ne_segmentar_mes)
