# -*- coding: utf-8 -*-
"""Frente 5, C6b (doc 58 §13): informe PDF "Representación gráfica del documento soporte de pago de nómina electrónica":
datos mínimos de los arts. 5 y 17, QR del Anexo §13.1 (URL de consulta con el CUNE, ≥ 2 cm, en el pie que se repite en
TODAS las páginas), solo para documentos aceptados, nativo y multicliente."""
import re
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture
from .common_importes import valores_monetarios
from .test_representacion_grafica import CUNE, QR, _xml

REPORTE = 'l10n_co_nomina_electronica.action_report_representacion_grafica'


@tagged('post_install', '-at_install')
class TestRepresentacionGraficaInforme(DocumentoFixture, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Informe Representación')

    def _aceptado(self, xml=None):
        doc = self._documento(date(2024, 3, 1))
        doc.write({'cune': CUNE, 'consecutive': 'NE15'})
        doc.xml_attachment_id = self.env['ir.attachment'].create({
            'name': 'NE15.xml', 'raw': xml or _xml(), 'res_model': 'l10n.co.ne.documento', 'res_id': doc.id})
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'identifier': CUNE, 'numero': 'NE15',
            'datetime': '2026-04-06 10:00:00'})
        return doc

    def _html(self, doc):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [doc.id])
        return html.decode().replace('\xa0', ' ')

    def test_denominado_expresamente_y_con_los_datos_minimos_del_art_5(self):
        html = self._html(self._aceptado())
        self.assertIn('Documento soporte de pago de nómina electrónica', html)          # 5.1
        for dato in ('NE15', CUNE, 'Empresa Representación SAS', '900123456', '1020304050', 'Gómez', 'Proveedor Software SAS',
                     'soft-1', '2026-04-05'):
            self.assertIn(dato, html, dato)
        valores = valores_monetarios(html)
        for esperado in (3000000.0, 200000.0, 120000.0, 3200000.0, 240000.0, 2960000.0):
            self.assertIn(esperado, valores, esperado)                                   # 5.6 a 5.8

    def test_el_qr_es_la_url_de_consulta_con_el_cune_de_al_menos_2_cm_y_va_en_el_pie(self):
        html = self._html(self._aceptado())
        imagenes = re.findall(r'<img[^>]*/report/barcode/[^>]*>', html)
        self.assertEqual(len(imagenes), 1)                                              # un solo QR: el del pie repetido
        self.assertIn('QR', imagenes[0])
        self.assertIn('documentkey=' + CUNE, imagenes[0])
        ancho = int(re.search(r'width="(\d+)"', imagenes[0]).group(1))
        self.assertGreaterEqual(ancho, 76)                                              # 2 cm a 96 dpi = 75,6 px
        pie = html.split('class="footer', 1)[1]
        self.assertIn('/report/barcode/', pie)                                          # el QR vive en el pie, no en el cuerpo
        self.assertNotIn('/report/barcode/', html.split('class="footer', 1)[0])

    def test_solo_documentos_aceptados(self):
        doc = self._documento(date(2024, 3, 1))
        doc.write({'cune': CUNE, 'consecutive': 'NE15'})
        with self.assertRaisesRegex(UserError, 'no está aceptado'):
            self._html(doc)

    def test_nota_de_ajuste_lleva_el_contenido_del_art_17(self):
        base = _xml().decode()
        nota = base.replace('<NominaIndividual xmlns="dian:gov:co:facturaelectronica:NominaIndividual">',
                            '<NominaIndividual xmlns="dian:gov:co:facturaelectronica:NominaIndividual"><Reemplazar>') \
                   .replace('</NominaIndividual>', '</Reemplazar></NominaIndividual>') \
                   .replace('<NumeroSecuenciaXML', '<ReemplazandoPredecesor NumeroPred="NE10" CUNEPred="%s" '
                            'FechaGenPred="2026-03-05"/><NumeroSecuenciaXML' % ('a' * 96), 1)
        html = self._html(self._aceptado(xml=nota.encode()))
        self.assertIn('Nota de ajuste del documento soporte', html)
        self.assertIn('Reemplazar', html)
        self.assertIn('NE10', html)
        self.assertIn('a' * 96, html)                                                   # CUNE del documento que modifica

    def test_el_informe_es_nativo_sin_estilos_ni_textos_de_un_cliente(self):
        html = self._html(self._aceptado())
        self.assertNotIn('style=', html.split('class="article', 1)[1].split('class="footer', 1)[0])
        self.assertIn('o_company_', html)                                                # clases del diseño de la compañía
        self.assertNotIn('Guapante', html)

    def test_el_papel_deja_espacio_para_el_pie_del_qr(self):
        formato = self.env.ref(REPORTE).paperformat_id
        self.assertEqual((formato.format, formato.orientation), ('A4', 'Portrait'))
        self.assertFalse(formato.default)
        self.assertGreaterEqual(formato.margin_bottom, 35)                               # el QR de 2.6 cm cabe en el pie

    def test_esta_ligado_al_menu_imprimir_del_documento(self):
        accion = self.env.ref(REPORTE)
        self.assertEqual(accion.model, 'l10n.co.ne.documento')
        self.assertEqual(accion.binding_type, 'report')
