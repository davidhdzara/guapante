# -*- coding: utf-8 -*-
"""Frente 5, C6a (doc 58 §13): datos de la representación gráfica leídos del XML VALIDADO (Res. 13 arts. 5 y 17, Anexo
§13.1). Solo existe para un documento aceptado por la DIAN; nada se recalcula."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import representacion_grafica

from .common_documento import DocumentoFixture

NS = 'dian:gov:co:facturaelectronica:NominaIndividual'
CUNE = 'e5bac48e354bc907bccff0ea7d45fbf784f0a8e7243b58337361e1fbd430489d'
QR = 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=' + CUNE


def _xml(cune=CUNE, qr=QR, numero='NE15', cuerpo=None):
    cuerpo = cuerpo if cuerpo is not None else (
        '<Devengados><Basico DiasTrabajados="30" SueldoTrabajado="3000000.00"/>'
        '<Transporte AuxilioTransporte="200000.00"/></Devengados>'
        '<Deducciones><Salud Porcentaje="4.00" Deduccion="120000.00"/>'
        '<FondoPension Porcentaje="4.00" Deduccion="120000.00"/></Deducciones>'
        '<DevengadosTotal>3200000.00</DevengadosTotal><DeduccionesTotal>240000.00</DeduccionesTotal>'
        '<ComprobanteTotal>2960000.00</ComprobanteTotal>')
    return ('<NominaIndividual xmlns="%s">'
            '<NumeroSecuenciaXML Prefijo="NE" Consecutivo="15" Numero="%s"/>'
            '<ProveedorXML RazonSocial="Proveedor Software SAS" NIT="900111222" DV="1" SoftwareID="soft-1"/>'
            '<CodigoQR>%s</CodigoQR>'
            '<InformacionGeneral Ambiente="1" TipoXML="102" CUNE="%s" EncripCUNE="CUNE-SHA384" FechaGen="2026-04-05" '
            'HoraGen="10:30:00-05:00" PeriodoNomina="5"/>'
            '<Empleador RazonSocial="Empresa Representación SAS" NIT="900123456" DV="8"/>'
            '<Trabajador PrimerApellido="Gómez" SegundoApellido="Pérez" PrimerNombre="Ana" OtrosNombres="María" '
            'NumeroDocumento="1020304050"/>'
            '<Pago Forma="1" Metodo="10"/>%s</NominaIndividual>' % (NS, numero, qr, cune, cuerpo)).encode()


@tagged('post_install', '-at_install')
class TestRepresentacionGrafica(DocumentoFixture, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Representación')

    # ── el servicio puro ─────────────────────────────────────────────
    def test_datos_del_art_5_salen_del_xml(self):
        d = representacion_grafica.datos_representacion(_xml())
        self.assertEqual(d['tipo'], 'documento')
        self.assertEqual((d['cune'], d['numero']), (CUNE, 'NE15'))                     # arts. 5.4 y 5.5
        self.assertEqual(d['empleador']['RazonSocial'], 'Empresa Representación SAS')   # 5.2
        self.assertEqual(d['empleador']['NIT'], '900123456')
        self.assertEqual(d['trabajador']['NumeroDocumento'], '1020304050')              # 5.3
        self.assertEqual((d['fecha_generacion'], d['hora_generacion']), ('2026-04-05', '10:30:00-05:00'))   # 5.11
        self.assertEqual(d['medio_pago'], {'Forma': '1', 'Metodo': '10'})               # 5.10
        self.assertEqual(d['proveedor']['SoftwareID'], 'soft-1')                         # 5.13
        self.assertEqual((d['devengados_total'], d['deducciones_total'], d['comprobante_total']),
                         ('3200000.00', '240000.00', '2960000.00'))                      # 5.6 a 5.8

    def test_los_conceptos_se_leen_tal_como_vienen_en_el_xml(self):
        d = representacion_grafica.datos_representacion(_xml())
        self.assertIn(('Basico', 'SueldoTrabajado', '3000000.00'), d['devengados'])
        self.assertIn(('Transporte', 'AuxilioTransporte', '200000.00'), d['devengados'])
        self.assertIn(('Salud', 'Deduccion', '120000.00'), d['deducciones'])
        self.assertNotIn('DiasTrabajados', [f[1] for f in d['devengados']])            # no es dinero

    def test_el_qr_es_el_mismo_del_xml_con_la_url_de_consulta_y_el_cune(self):
        d = representacion_grafica.datos_representacion(_xml())
        self.assertEqual(d['qr_url'], QR)
        self.assertTrue(d['qr_url'].endswith('documentkey=' + CUNE))

    def test_sin_cune_numero_o_qr_el_xml_no_sirve_y_lo_dice(self):
        with self.assertRaisesRegex(representacion_grafica.ErrorRepresentacion, 'CUNE'):
            representacion_grafica.datos_representacion(_xml(cune=''))
        with self.assertRaisesRegex(representacion_grafica.ErrorRepresentacion, 'CodigoQR'):
            representacion_grafica.datos_representacion(_xml(qr=''))
        with self.assertRaisesRegex(representacion_grafica.ErrorRepresentacion, 'número'):
            representacion_grafica.datos_representacion(_xml(numero=''))

    def test_nota_de_ajuste_reemplazar_y_eliminar_art_17(self):
        base = _xml().decode()
        nota = base.replace('<NominaIndividual xmlns="%s">' % NS, '<NominaIndividual xmlns="%s"><Reemplazar>' % NS) \
                   .replace('</NominaIndividual>', '</Reemplazar></NominaIndividual>')
        nota = nota.replace('<NumeroSecuenciaXML', '<ReemplazandoPredecesor NumeroPred="NE10" CUNEPred="%s" '
                            'FechaGenPred="2026-03-05"/><NumeroSecuenciaXML' % ('a' * 96), 1)
        d = representacion_grafica.datos_representacion(nota.encode())
        self.assertEqual(d['tipo'], 'nota_reemplazar')
        self.assertEqual(d['predecesor']['NumeroPred'], 'NE10')                         # art. 17.3
        eliminar = nota.replace('Reemplazar', 'Eliminar').replace('ReemplazandoPredecesor', 'EliminandoPredecesor')
        self.assertEqual(representacion_grafica.datos_representacion(eliminar.encode())['tipo'], 'nota_eliminar')

    # ── el documento: solo aceptado ──────────────────────────────────
    def _aceptar(self, doc, xml=None):
        doc.write({'cune': CUNE, 'consecutive': 'NE15'})
        doc.xml_attachment_id = self.env['ir.attachment'].create({
            'name': 'NE15.xml', 'raw': xml or _xml(), 'res_model': 'l10n.co.ne.documento', 'res_id': doc.id})
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'identifier': CUNE, 'numero': 'NE15',
            'datetime': '2026-04-06 10:00:00'})

    def test_un_documento_aceptado_entrega_los_datos_del_xml(self):
        doc = self._documento(date(2024, 3, 1))
        self._aceptar(doc)
        self.assertEqual(doc.state, 'invoice_accepted')
        self.assertEqual(doc._ne_datos_representacion()['cune'], CUNE)

    def test_borrador_pendiente_y_rechazado_no_tienen_representacion(self):
        doc = self._documento(date(2024, 3, 1))
        doc.write({'cune': CUNE, 'consecutive': 'NE15'})
        with self.assertRaisesRegex(UserError, 'no está aceptado'):
            doc._ne_datos_representacion()                                              # sin enviar
        for estado in ('invoice_pending', 'invoice_rejected'):
            self.env['l10n.co.ne.documento.intento'].create({
                'documento_id': doc.id, 'state': estado, 'identifier': CUNE, 'numero': 'NE15',
                'datetime': '2026-04-06 10:00:00' if estado == 'invoice_pending' else '2026-04-07 10:00:00'})
            with self.assertRaisesRegex(UserError, 'no está aceptado'):
                doc._ne_datos_representacion()

    def test_un_documento_migrado_o_eliminado_no_tiene_representacion(self):
        doc = self._documento(date(2024, 3, 1))
        self._aceptar(doc)
        doc.eliminado = True
        with self.assertRaisesRegex(UserError, 'migrado o eliminado'):
            doc._ne_datos_representacion()

    def test_xml_sin_qr_da_error_claro_con_el_documento(self):
        doc = self._documento(date(2024, 3, 1))
        self._aceptar(doc, xml=_xml(qr=''))
        with self.assertRaisesRegex(UserError, 'CodigoQR'):
            doc._ne_datos_representacion()
