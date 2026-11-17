# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 3, D1 (doc 53 §28.6): lo transmitido SOLO en habilitación (set de pruebas) no es un reporte real. No se
migra como documento ``legacy`` y no entra a ningún documento mensual real; tampoco las notas de ajuste por recibo ni
los recibos de un documento migrado. Sin llamar a la DIAN."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestHistoriaHabilitacion(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Historia Habilitación')

    def setUp(self):
        super().setUp()
        self.Doc = self.env['l10n.co.ne.documento']
        # El XML no se arma aquí (otras suites lo cubren): las alertas que dependen de él se anulan.
        self._patch(type(self.Doc), '_ne_validar_xml', lambda s: [])
        self.doc = self._documento(date(2024, 3, 1))
        self.recibos = self.doc.payslip_ids              # dos quincenas de marzo, pagadas, dentro del documento
        self.a, self.b = self.recibos
        self.empleado = self.doc.employee_id

    def _nuevo(self, estado='paid', pago=date(2026, 3, 20)):
        """Otro recibo de marzo del mismo empleado (sin documento)."""
        slip = self.env['hr.payslip'].create({
            'name': 'Recibo extra', 'employee_id': self.empleado.id, 'contract_id': self.doc.contract_id.id,
            'company_id': self.company.id, 'struct_id': self.struct.id,
            'date_from': date(2026, 3, 16), 'date_to': date(2026, 3, 31)})
        slip.write({'state': estado, 'paid_date': pago})
        return slip

    def _transmitido(self, slip, numero):
        slip.write({'l10n_co_ne_state': 'accepted', 'l10n_co_ne_cune': 'c%03d' % numero * 3,
                    'l10n_co_ne_consecutive': 'NE%d' % numero, 'l10n_co_ne_documento_id': False})

    def _envio(self, slip, operacion):
        self.env['l10n.co.ne.exchange'].create_exchange(
            slip.company_id, operacion, 'https://dian.test/ws', {'RawRequest': b'<r/>'}, slip)

    # ── helper ───────────────────────────────────────────────────────
    def test_historia_solo_habilitacion(self):
        self.assertFalse(self.a._ne_historia_solo_habilitacion())                 # sin historia: puede ser real
        self.a.l10n_co_ne_hab_set_id = 'SET1'
        self.assertTrue(self.a._ne_historia_solo_habilitacion())                  # marcador propio
        self._envio(self.b, 'send_test_set')
        self._envio(self.b, 'get_status_zip')
        self.assertTrue(self.b._ne_historia_solo_habilitacion())                  # solo set de pruebas
        self._envio(self.b, 'send_sync')
        self.assertFalse(self.b._ne_historia_solo_habilitacion())                 # hubo un envío real

    # ── migración 1b ─────────────────────────────────────────────────
    def test_la_migracion_no_migra_lo_que_solo_tiene_historia_de_habilitacion(self):
        self._transmitido(self.a, 1)
        self._transmitido(self.b, 2)
        self.a.l10n_co_ne_hab_set_id = 'SET1'
        self._envio(self.b, 'send_test_set')
        self.assertFalse(self.Doc._ne_migrar_legacy(self.a | self.b))
        self.assertFalse((self.a | self.b).l10n_co_ne_documento_id)

    def test_la_migracion_si_migra_un_envio_real_y_un_consecutivo_sin_intercambios(self):
        self._transmitido(self.a, 1)
        self._transmitido(self.b, 2)
        self._envio(self.a, 'send_test_set')
        self._envio(self.a, 'send_sync')                  # tuvo un envío real además del set de pruebas
        creados = self.Doc._ne_migrar_legacy(self.a | self.b)   # b: consecutivo gastado, sin intercambios
        self.assertEqual(len(creados), 2)
        self.assertTrue(all(creados.mapped('legacy')))

    # ── el documento mensual real ────────────────────────────────────
    def test_recibos_del_mes_excluye_notas_por_recibo_legacy_y_habilitacion(self):
        normal = self.a
        nota, legacy, prueba = self.b, self._nuevo(), self._nuevo()
        nota.write({'l10n_co_ne_is_adjustment': True, 'l10n_co_ne_adjustment_ref_cune': 'a' * 96})
        doc_legacy = self.Doc.create({'company_id': self.company.id, 'employee_id': self.empleado.id,
                                      'period': date(2026, 3, 1), 'legacy': True})
        legacy.l10n_co_ne_documento_id = doc_legacy
        prueba.l10n_co_ne_hab_set_id = 'SET1'
        del_mes = self.Doc._ne_recibos_del_mes(self.company, self.empleado, date(2026, 3, 1))
        self.assertEqual(del_mes, normal)

    def test_preparar_ignora_con_motivo_los_recibos_que_no_entran(self):
        self.b.write({'l10n_co_ne_is_adjustment': True, 'l10n_co_ne_adjustment_ref_cune': 'a' * 96})
        self.doc.payslip_ids.write({'l10n_co_ne_documento_id': False})
        self.doc.unlink()
        resultado = self.Doc._ne_preparar(self.b)
        self.assertFalse(resultado['documentos'])
        self.assertEqual(resultado['sin_fecha'][0][0], self.b)
        self.assertIn('nota de ajuste por recibo', resultado['sin_fecha'][0][1])
        self.assertFalse(self.b.l10n_co_ne_documento_id)

    def test_la_alerta_de_recibos_que_faltan_no_cuenta_notas_ni_pruebas(self):
        # el documento tiene solo la primera quincena; la segunda es una nota por recibo y hay otra de pruebas
        self.b.write({'l10n_co_ne_documento_id': False, 'l10n_co_ne_is_adjustment': True,
                      'l10n_co_ne_adjustment_ref_cune': 'a' * 96})
        prueba = self._nuevo('done', False)
        prueba.write({'l10n_co_ne_hab_set_id': 'SET1', 'name': 'Recibo de prueba de habilitacion'})
        pendiente = self._nuevo('done', False)
        pendiente.name = 'Recibo pendiente real'     # nombres DISTINTOS: el assertNotIn compara por nombre
        self.assertNotEqual(prueba.display_name, pendiente.display_name)
        faltan = self.Doc._ne_recibos_que_faltan(self.company, self.empleado, date(2026, 3, 1), self.a)
        self.assertEqual(faltan, pendiente)                # la nota y la de pruebas no faltan; la pendiente sí
        self.doc._ne_validar()
        alerta = [x for x in self.doc.alertas if x['key'] == 'faltan_recibos']
        self.assertEqual(len(alerta), 1)
        self.assertIn(pendiente.display_name, alerta[0]['message'])
        self.assertNotIn(prueba.display_name, alerta[0]['message'])

    def test_el_asistente_agrupa_aparte_lo_que_no_entra(self):
        self.b.write({'l10n_co_ne_is_adjustment': True, 'l10n_co_ne_adjustment_ref_cune': 'a' * 96})
        grupos = self.env['l10n.co.ne.documento.send']._ne_grupos(self.a | self.b, self.Doc)
        motivos = [m for g in grupos for m in g['motivos']]
        self.assertTrue([m for m in motivos if 'nota de ajuste por recibo' in m])
        con_mes = [g for g in grupos if g['period']]
        self.assertEqual(con_mes[0]['recibos'], self.a)
