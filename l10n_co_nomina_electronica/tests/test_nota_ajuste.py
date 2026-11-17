# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 6a (doc 53 §23.16): servicio ``services/nota_ajuste`` y la nota de ajuste del documento mensual
(XML, CUNE 103 y numeración propia). Todo con *mock*: nada llama a la DIAN. Valores a mano.

- ``TestNotaAjusteServicio`` (``BaseCase``): las funciones puras.
- ``TestDocumentoNotaXml`` (``TransactionCase``): datos del XML, predecesor, CUNE y consecutivo de la nota.
"""

import base64
import copy
import hashlib
from datetime import date
from unittest.mock import MagicMock

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import (
    dian_utils, nomina_xml_builder, nota_ajuste, xml_signer)

from .common_documento import DocumentoFixture
from .test_documento_generar import FECHA, HORA, PIN, _quincena_con_prima
from .test_documento_merge import _recibo

NS_NOMINA = 'dian:gov:co:facturaelectronica:NominaIndividual'
NS_AJUSTE = 'dian:gov:co:facturaelectronica:NominaIndividualDeAjuste'
# XML del documento ORIGINAL: lleva FechaGen (el predecesor la lee de aquí).
XML_PADRE = ('<NominaIndividual xmlns="%s"><InformacionGeneral FechaGen="2026-04-01"/></NominaIndividual>'
             % NS_NOMINA).encode()
# XML de la nota (stub del constructor): CUNE y QR se insertan dentro de <Reemplazar>/<Eliminar>.
XML_NOTA = ('<NominaIndividualDeAjuste xmlns="%s"><Reemplazar><InformacionGeneral/></Reemplazar>'
            '</NominaIndividualDeAjuste>' % NS_AJUSTE).encode()
PRED = {'NumeroPred': 'NE00000015', 'CUNEPred': 'c' * 96, 'FechaGenPred': '2026-04-01'}


def _datos():
    return {
        'periodo': {'FechaIngreso': '2024-03-01'},
        'numero_secuencia': {'Prefijo': 'NA', 'Numero': 'NA00000007', 'Consecutivo': '00000007',
                             'CodigoTrabajador': '1020304050'},
        'lugar_generacion': {'Pais': 'CO'}, 'proveedor_xml': {'SoftwareSC': 'SC'},
        'informacion_general': {'TipoXML': '103'}, 'empleador': {'NIT': '900123456'},
        'trabajador': {'NumeroDocumento': '1020304050'}, 'pago': {'Forma': '1'},
        'fechas_pagos': ['2026-03-15'], 'devengados': {'Basico': {}}, 'deducciones': {'Salud': {}},
        'devengados_total': 1.0, 'deducciones_total': 2.0, 'comprobante_total': 3.0,
        'totales': {'DevengadosTotal': '4249095.00', 'DeduccionesTotal': '240000.00',
                    'ComprobanteTotal': '4009095.00'},
    }


@tagged('post_install', '-at_install')
class TestNotaAjusteServicio(BaseCase):

    def test_predecesor(self):
        self.assertEqual(nota_ajuste.predecesor('NE1', 'cune', '2026-04-01'),
                         {'NumeroPred': 'NE1', 'CUNEPred': 'cune', 'FechaGenPred': '2026-04-01'})

    def test_reemplazar_copia_las_secciones_y_pone_el_predecesor(self):
        datos = _datos()
        r = nota_ajuste.reemplazar_desde(datos, PRED)
        self.assertEqual(r['predecesor'], PRED)
        for seccion in ('periodo', 'numero_secuencia', 'lugar_generacion', 'proveedor_xml', 'informacion_general',
                        'empleador', 'trabajador', 'pago', 'fechas_pagos', 'devengados', 'deducciones',
                        'devengados_total', 'deducciones_total', 'comprobante_total'):
            self.assertEqual(r[seccion], datos[seccion], seccion)
        self.assertNotIn('totales', r)
        self.assertEqual(r['numero_secuencia']['CodigoTrabajador'], '1020304050')   # Reemplazar SÍ lo lleva

    def test_reemplazar_sin_una_seccion_falla_como_siempre(self):
        datos = _datos()
        del datos['lugar_generacion']
        with self.assertRaises(KeyError):
            nota_ajuste.reemplazar_desde(datos, PRED)

    def test_eliminar_solo_lleva_las_secciones_del_xsd(self):
        datos = _datos()
        r = nota_ajuste.eliminar_desde(datos, PRED)
        self.assertEqual(set(r), {'predecesor', 'numero_secuencia', 'lugar_generacion', 'proveedor_xml',
                                  'informacion_general', 'empleador'})
        self.assertEqual(r['predecesor'], PRED)
        self.assertEqual(r['numero_secuencia'], {'Prefijo': 'NA', 'Numero': 'NA00000007', 'Consecutivo': '00000007'})

    def test_eliminar_no_modifica_el_diccionario_de_entrada(self):
        datos = _datos()
        antes = copy.deepcopy(datos)
        nota_ajuste.eliminar_desde(datos, PRED)
        self.assertEqual(datos, antes)
        self.assertIn('CodigoTrabajador', datos['numero_secuencia'])

    def test_cune_valores_de_un_reemplazar_son_los_totales_y_el_trabajador(self):
        v = nota_ajuste.cune_valores(False, _datos()['totales'], '1020304050')
        self.assertEqual(v, {'val_dev': '4249095.00', 'val_ded': '240000.00', 'val_tol': '4009095.00',
                             'doc_trab': '1020304050'})

    def test_cune_valores_de_un_eliminar_son_los_fijos_del_anexo(self):
        v = nota_ajuste.cune_valores(True, {}, '1020304050')
        self.assertEqual(v, {'val_dev': '0.00', 'val_ded': '0.00', 'val_tol': '0.00', 'doc_trab': '0'})

    def test_cune_valores_sin_totales_falla_si_no_es_eliminar(self):
        with self.assertRaises(KeyError):
            nota_ajuste.cune_valores(False, {}, '1')

    def test_fecha_gen_de_xml(self):
        self.assertEqual(nota_ajuste.fecha_gen_de_xml(XML_PADRE), '2026-04-01')

    def test_fecha_gen_de_xml_sin_atributo_o_sin_informacion_general(self):
        self.assertEqual(nota_ajuste.fecha_gen_de_xml(
            ('<N xmlns="%s"><InformacionGeneral/></N>' % NS_NOMINA).encode()), '')
        self.assertEqual(nota_ajuste.fecha_gen_de_xml(b'<N/>'), '')

    def test_fecha_gen_de_xml_ilegible_lanza(self):
        with self.assertRaises(etree.XMLSyntaxError):
            nota_ajuste.fecha_gen_de_xml(b'no es xml')

    def test_fecha_gen_dentro_de_una_nota(self):
        """En una nota la información general vive dentro de <Reemplazar>: se busca en todo el árbol."""
        xml = ('<A xmlns="%s"><Reemplazar><InformacionGeneral FechaGen="2026-05-02"/></Reemplazar></A>'
               % NS_AJUSTE).encode()
        self.assertEqual(nota_ajuste.fecha_gen_de_xml(xml), '2026-05-02')


@tagged('post_install', '-at_install')
class TestDocumentoNotaXml(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Nota Ajuste')
        cls.env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-ID', 'software_pin': PIN, 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '2'
        cls.secuencia = cls.env['ir.sequence'].create({
            'name': 'Secuencia NE nota', 'prefix': 'NE', 'padding': 8, 'number_next': 15,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        cls.company.l10n_co_ne_sequence_id = cls.secuencia           # la compañía ya trae una propia (relleno 10)
        # La compañía también trae su secuencia de ajuste: se reutiliza y se ajusta (otra con el mismo código y la
        # misma compañía dejaría la elección ambigua).
        cls.secuencia_ajuste = cls.env['ir.sequence'].search([
            ('code', '=', 'l10n_co_nomina.ajuste'), ('company_id', '=', cls.company.id)], limit=1)
        cls.secuencia_ajuste.write({'prefix': 'NA', 'padding': 8, 'number_next': 7, 'implementation': 'no_gap'})

    def setUp(self):
        super().setUp()

        def fabrica(slip):
            datos = copy.deepcopy(_quincena_con_prima() if slip.date_to.day > 15 else _recibo())
            datos['informacion_general'] = dict(datos['informacion_general'], FechaGen=FECHA, HoraGen=HORA)
            datos['lugar_generacion'] = {'Pais': 'CO', 'DepartamentoEstado': '11', 'MunicipioCiudad': '11001',
                                         'Idioma': 'es'}
            datos['numero_secuencia'] = dict(datos['numero_secuencia'], CodigoTrabajador='1020304050')
            return datos
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: fabrica(s))
        self._patch(dian_utils, 'compute_software_security_code', lambda *a: 'SC')
        self._patch(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        self._patch(type(self.env['l10n.co.ne.documento']), '_ne_validar_datos_recibo', lambda s, slip: None)
        self._patch(type(self.company), '_get_ne_certificate', lambda s: True)
        self._patch(dian_utils, 'clean_nit', lambda *a, **k: '900123456')
        self._patch(xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None))
        self._patch(xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)
        self._patch(nomina_xml_builder, 'build_nomina_individual_v2', lambda datos: XML_PADRE)
        self.build_nota = MagicMock(name='build_nota_ajuste_v2', return_value=XML_NOTA)
        self._patch(nomina_xml_builder, 'build_nota_ajuste_v2', self.build_nota)
        # El documento ORIGINAL: generado (NE00000015) y aceptado por la DIAN (intento de fixture).
        self.padre = self._documento(date(2024, 3, 1))
        self.padre._ne_validar()
        self.padre.action_generar_xml()
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.padre.id, 'state': 'invoice_accepted', 'identifier': self.padre.cune,
            'numero': self.padre.consecutive, 'datetime': date(2026, 4, 2)})

    def _nota(self, tipo='1', **vals):
        datos = {'company_id': self.company.id, 'employee_id': self.padre.employee_id.id,
                 'contract_id': self.padre.contract_id.id, 'period': self.padre.period, 'is_adjustment': True,
                 'adjustment_type': tipo, 'adjustment_ref_cune': self.padre.cune, 'parent_id': self.padre.id}
        datos.update(vals)
        return self.env['l10n.co.ne.documento'].create(datos)

    def _sin_secuencias_de_ajuste(self):
        """Desactiva TODAS las secuencias de ajuste, también la sin compañía que trae el módulo como dato."""
        self.env['ir.sequence'].search([('code', '=', 'l10n_co_nomina.ajuste')]).write({'active': False})

    def _cune(self, consecutivo, dev, ded, tol, doc_trab):
        raw = (consecutivo + FECHA + HORA + dev + ded + tol + '900123456' + doc_trab + '103' + PIN + '2')
        return hashlib.sha384(raw.encode()).hexdigest()

    # ── recibos derivados de la cadena (D-1, opción A) ───────────────
    def test_los_recibos_de_la_nota_son_los_del_padre_sin_reenlazar(self):
        nota = self._nota()
        self.assertEqual(nota._ne_recibos_para_xml(), self.padre.payslip_ids)
        self.assertFalse(nota.payslip_ids)                                  # no reenlaza: el M2O sigue en el original
        self.assertEqual(self.padre.payslip_ids.l10n_co_ne_documento_id, self.padre)

    def test_un_original_usa_sus_propios_recibos(self):
        self.assertEqual(self.padre._ne_recibos_para_xml(), self.padre.payslip_ids)

    def test_un_recibo_cancelado_del_padre_no_cuenta(self):
        nota = self._nota()
        cancelado = self.padre.payslip_ids.sorted('date_to')[-1]
        cancelado.state = 'cancel'
        self.assertEqual(nota._ne_recibos_para_xml(), self.padre.payslip_ids - cancelado)

    def test_la_cadena_sube_por_parent_id(self):
        primera = self._nota()
        segunda = self._nota(parent_id=primera.id)
        self.assertEqual(segunda._ne_recibos_para_xml(), self.padre.payslip_ids)

    # ── predecesor ───────────────────────────────────────────────────
    def test_predecesor_del_padre(self):
        self.assertEqual(self._nota()._ne_predecesor(), {
            'NumeroPred': 'NE00000015', 'CUNEPred': self.padre.cune, 'FechaGenPred': '2026-04-01'})

    def test_predecesor_sin_padre_o_con_padre_no_aceptado(self):
        with self.assertRaisesRegex(UserError, 'original'):
            self._nota(parent_id=False)._ne_predecesor()
        self.padre.intento_ids.state = 'invoice_pending'
        with self.assertRaisesRegex(UserError, 'aceptado'):
            self._nota()._ne_predecesor()

    def test_predecesor_con_cune_de_referencia_distinto(self):
        with self.assertRaisesRegex(UserError, 'CUNE de referencia'):
            self._nota(adjustment_ref_cune='z' * 96)._ne_predecesor()

    def test_predecesor_sin_xml_o_sin_fecha_es_error_claro_no_vacio(self):
        nota = self._nota()
        adjunto = self.padre.xml_attachment_id
        self.padre.xml_attachment_id = False
        with self.assertRaisesRegex(UserError, 'XML del documento original'):
            nota._ne_predecesor()
        self.padre.xml_attachment_id = adjunto
        adjunto.datas = base64.b64encode(('<N xmlns="%s"><InformacionGeneral/></N>' % NS_NOMINA).encode())
        with self.assertRaisesRegex(UserError, 'FechaGen'):
            nota._ne_predecesor()
        adjunto.datas = base64.b64encode(b'no es xml')
        with self.assertRaisesRegex(UserError, 'FechaGen'):
            nota._ne_predecesor()

    # ── datos del XML ────────────────────────────────────────────────
    def test_datos_de_una_nota_reemplazar(self):
        nota = self._nota('1')
        datos = nota._collect_documento_data('NA00000007')
        self.assertEqual(datos['informacion_general']['TipoXML'], '103')
        self.assertEqual(datos['novedad'], {'CUNENov': self.padre.cune, 'value': True})
        self.assertEqual(datos['tipo_nota'], '1')
        reemplazar = datos['reemplazar']
        self.assertEqual(reemplazar['predecesor'], {
            'NumeroPred': 'NE00000015', 'CUNEPred': self.padre.cune, 'FechaGenPred': '2026-04-01'})
        self.assertEqual(reemplazar['numero_secuencia']['Prefijo'], 'NA')
        self.assertEqual(reemplazar['numero_secuencia']['Numero'], 'NA00000007')
        self.assertEqual(reemplazar['devengados'], datos['devengados'])
        self.assertEqual(reemplazar['fechas_pagos'], ['2026-03-15', '2026-03-31'])
        self.assertNotIn('eliminar', datos)
        # Los totales fusionados son los de los recibos del padre (4.249.095,00 con la prima).
        self.assertEqual(datos['totales']['DevengadosTotal'], '4249095.00')

    def test_datos_de_una_nota_eliminar(self):
        datos = self._nota('2')._collect_documento_data('NA00000007')
        self.assertEqual(datos['tipo_nota'], '2')
        self.assertEqual(set(datos['eliminar']), {'predecesor', 'numero_secuencia', 'lugar_generacion',
                                                  'proveedor_xml', 'informacion_general', 'empleador'})
        self.assertNotIn('CodigoTrabajador', datos['eliminar']['numero_secuencia'])
        self.assertNotIn('reemplazar', datos)

    def test_el_original_no_cambia(self):
        """Un documento que no es nota sigue armando la nómina individual (TipoXML 102 del recibo)."""
        datos = self.padre._collect_documento_data()
        self.assertNotIn('tipo_nota', datos)
        self.assertNotIn('novedad', datos)
        self.assertNotEqual(datos['informacion_general'].get('TipoXML'), '103')

    # ── generar la nota ──────────────────────────────────────────────
    def test_genera_la_nota_reemplazar_con_el_consecutivo_de_ajuste(self):
        nota = self._nota('1')
        siguiente_nomina = self.secuencia.number_next_actual
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000007')
        self.assertEqual(self.secuencia.number_next_actual, siguiente_nomina)        # la de nómina no se gasta
        self.assertEqual(self.secuencia_ajuste.number_next_actual, 8)
        # (la corrida en seco de 3b también arma el XML: la llamada que cuenta es la última, con el número real)
        self.assertEqual(self.build_nota.call_args.args[0]['numero_secuencia']['Numero'], 'NA00000007')
        self.assertEqual(nota.xml_attachment_id.name, 'ne_SIN_NIT_NA00000007.xml')
        self.assertEqual(nota.cune, self._cune('NA00000007', '4249095.00', '240000.00', '4009095.00', '1020304050'))
        xml = etree.fromstring(base64.b64decode(nota.xml_attachment_id.datas))
        info = xml.find('.//{%s}InformacionGeneral' % NS_AJUSTE)
        self.assertEqual(info.get('CUNE'), nota.cune)
        self.assertEqual(info.get('EncripCUNE'), 'CUNE-SHA384')
        self.assertEqual(nota.etapa, 'ready')
        self.assertFalse(nota.state)

    def test_genera_la_nota_eliminar_con_el_cune_de_valores_fijos(self):
        nota = self._nota('2')
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000007')
        self.assertEqual(nota.cune, self._cune('NA00000007', '0.00', '0.00', '0.00', '0'))
        self.assertEqual(self.build_nota.call_args.args[0]['tipo_nota'], '2')

    def test_el_cune_de_una_nota_difiere_del_de_una_nomina_con_los_mismos_datos(self):
        nota = self._nota('1')
        nota.action_generar_xml()
        con_102 = hashlib.sha384(('NA00000007' + FECHA + HORA + '4249095.00' + '240000.00' + '4009095.00'
                                  + '900123456' + '1020304050' + '102' + PIN + '2').encode()).hexdigest()
        self.assertNotEqual(nota.cune, con_102)

    def test_regenerar_antes_de_enviar_reutiliza_el_consecutivo_de_ajuste(self):
        nota = self._nota('1')
        nota.action_generar_xml()
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000007')
        self.assertEqual(self.secuencia_ajuste.number_next_actual, 8)

    def test_la_secuencia_de_la_compania_gana_a_la_sin_compania(self):
        self.env['ir.sequence'].create({
            'name': 'Secuencia NA global', 'code': 'l10n_co_nomina.ajuste', 'prefix': 'NA', 'padding': 8,
            'number_next': 100, 'implementation': 'no_gap', 'company_id': False})
        nota = self._nota('1')
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000007')

    def test_solo_con_secuencia_sin_compania_se_usa_esa(self):
        self._sin_secuencias_de_ajuste()
        self.env['ir.sequence'].create({
            'name': 'Secuencia NA global', 'code': 'l10n_co_nomina.ajuste', 'prefix': 'NA', 'padding': 8,
            'number_next': 100, 'implementation': 'no_gap', 'company_id': False})
        nota = self._nota('1')
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000100')

    def test_sin_secuencia_de_ajuste_error_claro_que_nombra_la_compania(self):
        self._sin_secuencias_de_ajuste()
        nota = self._nota('1')
        with self.assertRaises(UserError) as exc:
            nota.action_generar_xml()
        self.assertIn(self.company.name, str(exc.exception))
        self.assertIn('l10n_co_nomina.ajuste', str(exc.exception))
        self.assertFalse(nota.consecutive)

    def test_sin_prefijo_de_ajuste_error_claro_sin_gastar_numero(self):
        self.company.l10n_co_ne_adjust_prefix = False
        nota = self._nota('1')
        with self.assertRaises(UserError) as exc:
            nota.action_generar_xml()
        self.assertIn(self.company.name, str(exc.exception))
        self.assertIn('prefijo de notas de ajuste', str(exc.exception))
        self.assertEqual(self.secuencia_ajuste.number_next_actual, 7)
        self.assertFalse(nota.consecutive)

    def test_el_prefijo_de_nomina_no_afecta_a_la_nota(self):
        self.company.l10n_co_ne_payroll_prefix = False
        nota = self._nota('1')
        nota.action_generar_xml()
        self.assertEqual(nota.consecutive, 'NA00000007')

    def test_un_padre_eliminado_no_admite_nota(self):
        """Un eliminado conserva su último intento ACEPTADO: sin la guarda explícita se aceptaría como padre (§26b)."""
        nota = self._nota('1')
        self.padre.eliminado = True
        self.assertEqual(self.padre.state, 'invoice_accepted')
        with self.assertRaisesRegex(UserError, 'no eliminado'):
            nota.action_generar_xml()
        self.assertFalse(nota.consecutive)

    def test_la_nota_sin_padre_aceptado_no_se_genera(self):
        nota = self._nota('1')
        self.padre.intento_ids.state = 'invoice_pending'
        with self.assertRaises(UserError):
            nota.action_generar_xml()
        self.assertFalse(nota.consecutive)

    # ── alertas de la nota ───────────────────────────────────────────
    def test_validar_una_nota_reemplazar_no_da_bloqueos_ni_avisos_de_totales(self):
        nota = self._nota('1')
        nota._ne_validar()
        # Sin alertas el campo Json vacío se lee False (no []): el resto del código usa `alertas or []`.
        claves = {a['key'] for a in nota.alertas or []}
        self.assertNotIn('sin_recibos', claves)
        self.assertNotIn('totales_nodos', claves)
        self.assertEqual(nota.etapa, 'ready')

    def test_validar_una_nota_eliminar_no_pide_salud_ni_concilia_totales(self):
        nota = self._nota('2')
        nota._ne_validar()
        # Sin alertas el campo Json vacío se lee False (no []): el resto del código usa `alertas or []`.
        claves = {a['key'] for a in nota.alertas or []}
        self.assertNotIn('sin_seguridad_social', claves)
        self.assertNotIn('totales_nodos', claves)
        self.assertEqual(nota.etapa, 'ready')

    def test_la_nota_con_padre_no_aceptado_queda_con_bloqueo(self):
        nota = self._nota('1')
        self.padre.intento_ids.state = 'invoice_pending'
        nota._ne_validar()
        self.assertIn('xml', {a['key'] for a in nota.alertas if a['level'] == 'danger'})
        self.assertEqual(nota.etapa, 'draft')
