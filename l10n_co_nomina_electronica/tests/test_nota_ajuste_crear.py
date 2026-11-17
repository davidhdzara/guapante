# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 4, commit 6b (doc 53 §23.16): crear la nota de ajuste, cadena de notas y adopción de recibos (D-1, D-2, D-5,
D-M). Todo con datos de fixture y sin llamar a la DIAN: el documento aceptado se arma con un intento aceptado."""

from datetime import date, datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestNotaAjusteCrear(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Nota Crear')

    def setUp(self):
        super().setUp()
        # El XML no se arma aquí (otra suite lo cubre): las alertas que dependen de él se anulan.
        self._patch(type(self.env['l10n.co.ne.documento']), '_ne_validar_xml', lambda s: [])
        self.padre = self._documento(date(2024, 3, 1))
        self.padre.write({'cune': 'a' * 96, 'consecutive': 'NE00000001'})
        self._intento(self.padre, 'invoice_accepted', datetime(2026, 4, 2))

    def _intento(self, doc, estado, fecha):
        return self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': estado, 'identifier': doc.cune, 'numero': doc.consecutive,
            'datetime': fecha})

    def _aceptar(self, nota, cune, fecha):
        nota.write({'cune': cune, 'consecutive': 'NA' + cune[:6]})
        self._intento(nota, 'invoice_accepted', fecha)

    def _recibo_nuevo(self, doc, dia_pago=20):
        slip = self.env['hr.payslip'].create({
            'name': 'Recibo tardío', 'employee_id': doc.employee_id.id, 'contract_id': doc.contract_id.id,
            'company_id': self.company.id, 'struct_id': self.struct.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        slip.write({'state': 'paid', 'paid_date': date(2026, 3, dia_pago)})
        return slip

    # ── Precondiciones ───────────────────────────────────────────────
    def test_origen_no_aceptado_da_error(self):
        for estado in ('invoice_pending', 'invoice_sending_failed'):
            doc = self._documento(date(2024, 3, 1), mes=4, pagos=((15, 15), (30, 30)))
            self._intento(doc, estado, datetime(2026, 5, 2))
            with self.assertRaises(UserError, msg=estado):
                doc.action_crear_ajuste('1')
        sin_enviar = self._documento(date(2024, 3, 1), mes=5)
        with self.assertRaises(UserError):
            sin_enviar.action_crear_ajuste('1')

    def test_origen_rechazado_no_lleva_nota(self):
        doc = self._documento(date(2024, 3, 1), mes=4, pagos=((15, 15), (30, 30)))
        doc.cune = 'b' * 96
        self._intento(doc, 'invoice_rejected', datetime(2026, 5, 2))
        with self.assertRaisesRegex(UserError, 'rechazado'):
            doc.action_crear_ajuste('1')

    def test_origen_eliminado_legacy_y_nota(self):
        self.padre.eliminado = True
        with self.assertRaisesRegex(UserError, 'eliminado'):
            self.padre.action_crear_ajuste('1')
        self.padre.eliminado = False
        self.padre.legacy = True
        with self.assertRaisesRegex(UserError, 'por recibo'):
            self.padre.action_crear_ajuste('1')
        self.padre.legacy = False
        nota = self.padre.action_crear_ajuste('1')
        with self.assertRaisesRegex(UserError, 'documento original'):
            nota.action_crear_ajuste('1')

    def test_tipo_invalido_y_fecha_futura(self):
        with self.assertRaises(UserError):
            self.padre.action_crear_ajuste('3')
        manana = fields.Date.context_today(self.padre) + timedelta(days=1)
        with self.assertRaisesRegex(UserError, 'futura'):
            self.padre.action_crear_ajuste('1', error_conocido_el=manana)

    def test_fecha_por_defecto_hoy_y_constraint(self):
        nota = self.padre.action_crear_ajuste('1')
        self.assertEqual(nota.error_conocido_el, fields.Date.context_today(nota))
        with self.assertRaises(ValidationError):
            nota.error_conocido_el = fields.Date.context_today(nota) + timedelta(days=2)

    def test_una_nota_en_curso_por_cadena(self):
        self.padre.action_crear_ajuste('1')
        with self.assertRaisesRegex(UserError, 'en curso'):
            self.padre.action_crear_ajuste('1')
        with self.assertRaisesRegex(UserError, 'en curso'):
            self.padre.action_crear_ajuste('2')

    def test_nota_rechazada_sin_regenerar_sigue_en_curso(self):
        nota = self.padre.action_crear_ajuste('1')
        nota.cune = 'c' * 96
        self._intento(nota, 'invoice_rejected', datetime(2026, 4, 5))
        self.assertEqual(self.padre._ne_nota_en_curso(), nota)
        with self.assertRaisesRegex(UserError, 'en curso'):
            self.padre.action_crear_ajuste('1')

    # ── Eliminar la última nota aceptada (David, 2026-11-14; doc 53 §28.3) ──
    def _cadena_con_dos_notas_aceptadas(self):
        n1 = self.padre.action_crear_ajuste('1')
        self._aceptar(n1, 'e' * 96, datetime(2026, 4, 10))
        n2 = self.padre.action_crear_ajuste('1')
        self._aceptar(n2, 'f' * 96, datetime(2026, 4, 20))
        return n1, n2

    def _aceptar_eliminacion(self, nota, cune, fecha):
        self._aceptar(nota, cune, fecha)
        nota._ne_aplicar_eliminacion()

    def test_eliminar_la_ultima_nota_aceptada_se_permite_y_apunta_a_ella(self):
        _n1, n2 = self._cadena_con_dos_notas_aceptadas()
        eliminar = self.padre.action_crear_ajuste('2')
        self.assertEqual(eliminar.parent_id, n2)
        self.assertEqual(eliminar.adjustment_ref_cune, n2.cune)
        self.assertFalse(eliminar.payslip_ids)

    def test_al_aceptarse_la_eliminacion_vuelve_a_ser_vigente_la_anterior(self):
        n1, n2 = self._cadena_con_dos_notas_aceptadas()
        eliminar = self.padre.action_crear_ajuste('2')
        self.assertEqual(self.padre._ne_ultimo_aceptado(), n2)           # aún vigente mientras no se acepte
        self._aceptar_eliminacion(eliminar, 'a1' * 48, datetime(2026, 4, 25))
        self.assertTrue(n2.eliminado)
        self.assertEqual(n2.eliminado_por_id, eliminar)
        self.assertFalse(n1.eliminado or self.padre.eliminado)            # el resto de la cadena intacto
        self.assertEqual(self.padre._ne_ultimo_aceptado(), n1)           # vuelve a ser vigente la nota previa
        self.assertEqual(n2.cune, 'f' * 96)                               # el CUNE de la eliminada no se reutiliza

    def test_la_siguiente_reemplazar_cuelga_de_la_nota_previa_no_de_la_eliminada(self):
        n1, n2 = self._cadena_con_dos_notas_aceptadas()
        eliminar = self.padre.action_crear_ajuste('2')
        self._aceptar_eliminacion(eliminar, 'a1' * 48, datetime(2026, 4, 25))
        nueva = self.padre.action_crear_ajuste('1')
        self.assertEqual(nueva.parent_id, n1)
        self.assertEqual(nueva.adjustment_ref_cune, n1.cune)
        self.assertNotEqual(nueva.adjustment_ref_cune, n2.cune)

    def test_la_eliminacion_vuelve_al_original_si_no_hay_nota_previa(self):
        n1 = self.padre.action_crear_ajuste('1')
        self._aceptar(n1, 'e' * 96, datetime(2026, 4, 10))
        eliminar = self.padre.action_crear_ajuste('2')
        self._aceptar_eliminacion(eliminar, 'a1' * 48, datetime(2026, 4, 25))
        self.assertEqual(self.padre._ne_ultimo_aceptado(), self.padre)
        self.assertEqual(self.padre.action_crear_ajuste('1').parent_id, self.padre)

    def test_d_s_la_nueva_reemplazar_adopta_los_recibos_de_la_nota_eliminada(self):
        n1 = self.padre.action_crear_ajuste('1')
        self._aceptar(n1, 'e' * 96, datetime(2026, 4, 10))
        tardio = self._recibo_nuevo(self.padre)
        n2 = self.padre.action_crear_ajuste('1')
        self.assertEqual(n2.payslip_ids, tardio)                          # N2 lo adoptó
        self._aceptar(n2, 'f' * 96, datetime(2026, 4, 20))
        eliminar = self.padre.action_crear_ajuste('2')
        self._aceptar_eliminacion(eliminar, 'a1' * 48, datetime(2026, 4, 25))
        nueva = self.padre.action_crear_ajuste('1')
        self.assertEqual(nueva.payslip_ids, tardio)                       # pasa a la nueva: no queda sin reportar
        self.assertIn(tardio, nueva.recibo_xml_ids)
        self.assertNotIn(tardio, n2.payslip_ids)

    def test_d_s_preparar_con_nota_abierta_tambien_adopta_los_de_la_eliminada(self):
        n1 = self.padre.action_crear_ajuste('1')
        self._aceptar(n1, 'e' * 96, datetime(2026, 4, 10))
        tardio = self._recibo_nuevo(self.padre)
        n2 = self.padre.action_crear_ajuste('1')
        self._aceptar(n2, 'f' * 96, datetime(2026, 4, 20))
        eliminar = self.padre.action_crear_ajuste('2')
        self._aceptar_eliminacion(eliminar, 'a1' * 48, datetime(2026, 4, 25))
        nueva = self.padre.action_crear_ajuste('1')
        tardio.write({'l10n_co_ne_documento_id': n2.id})                  # sigue ligado a la nota ELIMINADA
        self.env['l10n.co.ne.documento']._ne_preparar(tardio)
        self.assertEqual(tardio.l10n_co_ne_documento_id, nueva)

    def test_se_puede_eliminar_nota_por_nota_hasta_el_original(self):
        n1, n2 = self._cadena_con_dos_notas_aceptadas()
        for cune, fecha, objetivo in (('a1' * 48, datetime(2026, 4, 25), n2), ('a2' * 48, datetime(2026, 4, 26), n1)):
            eliminar = self.padre.action_crear_ajuste('2')
            self.assertEqual(eliminar.parent_id, objetivo)
            self._aceptar_eliminacion(eliminar, cune, fecha)
            self.assertTrue(objetivo.eliminado)
        ultima = self.padre.action_crear_ajuste('2')
        self.assertEqual(ultima.parent_id, self.padre)
        self._aceptar_eliminacion(ultima, 'a3' * 48, datetime(2026, 4, 27))
        self.assertTrue(self.padre.eliminado)
        with self.assertRaisesRegex(UserError, 'eliminado'):
            self.padre.action_crear_ajuste('1')

    def test_no_se_crea_otra_nota_mientras_la_eliminacion_esta_en_curso(self):
        self._cadena_con_dos_notas_aceptadas()
        self.padre.action_crear_ajuste('2')
        for tipo in ('1', '2'):
            with self.assertRaisesRegex(UserError, 'en curso'):
                self.padre.action_crear_ajuste(tipo)

    # ── Cadena y padre ───────────────────────────────────────────────
    def test_reemplazar_sobre_el_original(self):
        nota = self.padre.action_crear_ajuste('1')
        self.assertTrue(nota.is_adjustment)
        self.assertEqual(nota.adjustment_type, '1')
        self.assertEqual(nota.parent_id, self.padre)
        self.assertEqual(nota.adjustment_ref_cune, self.padre.cune)
        self.assertEqual((nota.period, nota.employee_id, nota.company_id, nota.contract_id),
                         (self.padre.period, self.padre.employee_id, self.company, self.padre.contract_id))
        self.assertEqual(nota.etapa, 'draft')
        self.assertFalse(nota.state)
        self.assertFalse(nota.consecutive)   # no gasta consecutivo
        self.assertEqual(self.padre.state, 'invoice_accepted')   # el original queda intacto

    def test_la_segunda_nota_cuelga_de_la_ultima_aceptada(self):
        primera = self.padre.action_crear_ajuste('1')
        self._aceptar(primera, 'e' * 96, datetime(2026, 4, 10))
        segunda = self.padre.action_crear_ajuste('1')
        self.assertEqual(segunda.parent_id, primera)
        self.assertEqual(segunda.adjustment_ref_cune, primera.cune)
        self.assertEqual(self.padre._ne_cadena(), self.padre | primera | segunda)
        self.assertEqual(segunda._ne_cadena(), self.padre | primera | segunda)

    def test_con_varias_aceptadas_gana_la_mas_reciente(self):
        primera = self.padre.action_crear_ajuste('1')
        self._aceptar(primera, 'e' * 96, datetime(2026, 4, 10))
        segunda = self.padre.action_crear_ajuste('1')
        self._aceptar(segunda, 'f' * 96, datetime(2026, 4, 20))
        self.assertEqual(self.padre._ne_ultimo_aceptado(), segunda)

    def test_original_eliminado_no_es_ultimo_aceptado(self):
        self.padre.eliminado = True
        self.assertFalse(self.padre._ne_ultimo_aceptado())

    def test_eliminar_no_adopta_recibos(self):
        self._recibo_nuevo(self.padre)
        nota = self.padre.action_crear_ajuste('2')
        self.assertEqual(nota.adjustment_type, '2')
        self.assertFalse(nota.payslip_ids)

    # ── Recibos (D-1, D-5, D-M) ──────────────────────────────────────
    def test_recibos_de_la_nota_son_los_de_la_cadena(self):
        recibos = self.padre.payslip_ids
        nota = self.padre.action_crear_ajuste('1')
        self.assertEqual(nota.recibo_xml_ids, recibos)
        self.assertEqual(self.padre.payslip_ids, recibos)   # el original no pierde ninguno
        self.assertFalse(nota.payslip_ids)

    def test_reemplazar_adopta_recibos_sin_documento(self):
        tardio = self._recibo_nuevo(self.padre)
        nota = self.padre.action_crear_ajuste('1')
        self.assertEqual(nota.payslip_ids, tardio)
        self.assertIn(tardio, nota.recibo_xml_ids)
        self.assertNotIn(tardio, self.padre.payslip_ids)

    def test_recibo_cancelado_del_original_sale_de_los_del_xml(self):
        nota = self.padre.action_crear_ajuste('1')
        cancelado = self.padre.payslip_ids[:1]
        cancelado.write({'state': 'cancel'})
        self.assertNotIn(cancelado, nota.recibo_xml_ids)

    def test_preparar_adopta_en_la_nota_abierta(self):
        nota = self.padre.action_crear_ajuste('1')
        tardio = self._recibo_nuevo(self.padre)
        res = self.env['l10n.co.ne.documento']._ne_preparar(tardio)
        self.assertEqual(tardio.l10n_co_ne_documento_id, nota)
        self.assertIn(nota, res['documentos'])
        self.assertNotIn(tardio, self.padre.payslip_ids)

    def test_preparar_sin_nota_abierta_deja_alerta_persistente(self):
        tardio = self._recibo_nuevo(self.padre)
        self.env['l10n.co.ne.documento']._ne_preparar(tardio)
        self.assertFalse(tardio.l10n_co_ne_documento_id)   # nunca se agrega a un documento aceptado
        claves = [a['key'] for a in (self.padre.alertas or [])]
        self.assertIn('recibo_tardio', claves)
        self.assertIn('aceptado', claves)

    def test_recibo_que_cambia_de_mes_sale_de_la_nota_abierta(self):
        tardio = self._recibo_nuevo(self.padre)
        nota = self.padre.action_crear_ajuste('1')
        self.assertEqual(nota.payslip_ids, tardio)
        tardio.paid_date = date(2026, 4, 5)
        self.env['l10n.co.ne.documento']._ne_preparar(tardio)
        self.assertNotIn(tardio, nota.payslip_ids)

    def test_nota_enviada_conserva_recibo_y_alerta(self):
        tardio = self._recibo_nuevo(self.padre)
        nota = self.padre.action_crear_ajuste('1')
        nota.cune = 'a1' * 48
        self._intento(nota, 'invoice_pending', datetime(2026, 4, 10))
        tardio.paid_date = date(2026, 4, 5)
        nota._ne_validar()
        self.assertTrue([a for a in nota.alertas if a['key'].startswith('recibo_otro_mes')])

    def test_borrar_nota_en_borrador_suelta_sus_recibos(self):
        tardio = self._recibo_nuevo(self.padre)
        nota = self.padre.action_crear_ajuste('1')
        nota.unlink()
        self.assertFalse(tardio.l10n_co_ne_documento_id)

    def test_nota_con_intentos_no_se_borra(self):
        nota = self.padre.action_crear_ajuste('1')
        nota.cune = 'a2' * 48
        self._intento(nota, 'invoice_rejected', datetime(2026, 4, 10))
        with self.assertRaises(UserError):
            nota.unlink()

    def test_botones_visibles_solo_en_documento_aceptado(self):
        arch = self.env.ref('l10n_co_nomina_electronica.view_l10n_co_ne_documento_form').arch_db
        for boton in ('action_crear_nota_reemplazar', 'action_crear_nota_eliminar'):
            self.assertIn(boton, arch)
        self.assertIn("state != 'invoice_accepted' or eliminado or legacy or is_adjustment", arch)
        accion = self.padre.action_crear_nota_reemplazar()
        self.assertEqual(accion['res_model'], 'l10n.co.ne.documento')
        self.assertTrue(self.env['l10n.co.ne.documento'].browse(accion['res_id']).is_adjustment)
