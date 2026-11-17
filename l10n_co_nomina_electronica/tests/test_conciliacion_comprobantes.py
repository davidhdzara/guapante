# -*- coding: utf-8 -*-
"""Frente 5, C4 (doc 58 §3): conciliación del comprobante de pago con el documento mensual. Solo ALERTA (no bloquea ni
toca el XML) y nombra el recibo y las diferencias; las líneas sin nodo en el XML de la DIAN son diferencias legítimas."""
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestConciliacionComprobantes(DocumentoFixture, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Conciliación Comprobantes')

    def _lineas(self, recibo, *lineas):
        for codigo, total in lineas:
            regla = self.env['hr.salary.rule'].search(
                [('code', '=', codigo), ('struct_id', '=', recibo.struct_id.id)], limit=1)
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id, 'quantity': 1.0,
                'rate': 100.0, 'amount': total, 'total': total})

    def _doc(self, **xml):
        """Documento con 2 recibos; el XML dice devengado/deducciones de ``xml`` (por recibo)."""
        doc = self._documento(date(2024, 3, 1))
        for recibo in doc.payslip_ids:
            self._lineas(recibo, ('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0),
                         ('CO_PENSION_EMP', -120000.0), ('CO_NETO', 2760000.0))
        datos = {'devengados_total': xml.get('dev', 3000000.0), 'deducciones_total': xml.get('ded', 240000.0)}
        patcher = patch.object(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: dict(datos))
        patcher.start()
        self.addCleanup(patcher.stop)
        return doc

    def test_si_el_comprobante_cuadra_con_el_xml_no_hay_diferencias(self):
        doc = self._doc()
        self.assertEqual(doc._ne_conciliar_comprobantes(), [])

    def test_una_linea_sin_nodo_en_el_xml_se_nombra_con_su_diferencia(self):
        doc = self._doc(dev=2800000.0)             # el XML lleva 200.000 menos de devengado que el comprobante
        diferencias = doc._ne_conciliar_comprobantes()
        self.assertEqual(len(diferencias), 2)
        self.assertEqual({d['recibo'] for d in diferencias}, set(doc.payslip_ids))
        self.assertEqual((diferencias[0]['dev'], diferencias[0]['ded'], diferencias[0]['neto']),
                         (200000.0, 0.0, 200000.0))

    def test_una_diferencia_menor_a_un_peso_no_cuenta(self):
        doc = self._doc(dev=3000000.40)
        self.assertEqual(doc._ne_conciliar_comprobantes(), [])

    def test_un_recibo_sin_linea_de_neto_se_informa_con_su_motivo_y_no_falla(self):
        doc = self._doc()
        primero = doc.payslip_ids.sorted('date_to')[0]
        primero.line_ids.filtered(lambda l: l.code == 'CO_NETO').unlink()
        diferencias = doc._ne_conciliar_comprobantes()
        self.assertEqual(len(diferencias), 1)
        self.assertEqual(diferencias[0]['recibo'], primero)
        self.assertIn('línea de neto', diferencias[0]['motivo'])

    def test_la_diferencia_sale_como_alerta_de_advertencia_que_nombra_el_recibo_y_no_bloquea(self):
        doc = self._doc(dev=2800000.0)
        doc_datos = {'devengados': {}, 'deducciones': {'Salud': {}, 'FondoPension': {}},
                     'totales': {'DevengadosTotal': '0.00', 'DeduccionesTotal': '0.00'}}
        with patch.object(type(doc), '_collect_documento_data', lambda s, **k: doc_datos), \
                patch.object(dian_utils, 'compute_software_security_code', lambda *a: 'SC'):
            alertas = doc._ne_validar_xml()
        conciliacion = [a for a in alertas if a['key'] == 'conciliacion_comprobantes']
        self.assertEqual(len(conciliacion), 1)
        self.assertEqual(conciliacion[0]['level'], 'warning')                 # no bloquea
        self.assertIn(doc.payslip_ids[:1].display_name, conciliacion[0]['message'])
        self.assertIn('El XML no se modifica', conciliacion[0]['message'])

    def test_conciliar_no_escribe_ni_cambia_el_xml(self):
        doc = self._doc(dev=2800000.0)
        antes = (doc.xml_attachment_id, doc.cune, doc.payslip_ids, doc.alertas)
        doc._ne_conciliar_comprobantes()
        self.assertEqual((doc.xml_attachment_id, doc.cune, doc.payslip_ids, doc.alertas), antes)
