# -*- coding: utf-8 -*-
"""PDS Operación — indicadores de tarjeta (2026-11-10): tiempo en el estado
actual, kg, clientes por dirección de entrega, alerta de Detenido, «sin
pesar aún» y «sin stock». Todo lectura, vía call_kw como lo llama el JS."""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.api import call_kw
from odoo.tests.common import tagged
from odoo.tools.misc import file_path

from .test_preparation_day_product_claim import REQUEST_PATCH_TARGET
from .test_preparation_pds_operacion import TestPreparationPdsOperacion

REQUEST_PATCH_TARGET_ALIAS = REQUEST_PATCH_TARGET

PARAM = 'ist_preparation_day_picking.pds_stopped_alert_minutes'


@tagged('post_install', '-at_install')
class TestPreparationPdsIndicators(TestPreparationPdsOperacion):

    def _board(self):
        # Como en una petición REAL: sin cachés llenos por el superusuario de
        # la fixture, que ocultarían huecos de permisos (ACL de claims, perfil
        # público de hr.employee) para quien solo tiene «Reportes y PDS».
        self.env.invalidate_all()
        Model = self.env['guapante.preparation.day'].with_user(
            self.prep_admin_user)
        with patch('odoo.fields.Datetime.now',
                   return_value=self._now_before_switch_hour()):
            data = call_kw(Model, 'get_pds_operacion_board_data', [], {})
        json.dumps(data)  # viaja por JSON-RPC
        return data

    def _card(self, data, status):
        cards = data['columns'][status]
        self.assertEqual(len(cards), 1, status)
        return cards[0]

    def _one_claim_session(self, qty=2.0):
        """UN claim con DOS líneas (dos pedidos del mismo producto): así
        una línea hecha no vuelve 'done' a toda la tarjeta."""
        self._create_confirmed_order(qty=qty)
        session = self._load_session_with_product(qty=qty)
        self.assertEqual(len(session.line_ids), 2)
        return session, session.product_claim_ids

    def _weigh(self, line, kg):
        line.sudo().with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': kg,
            'done_by_employee_id': self.operator_a.id,
            'done_date': fields.Datetime.now(),
        })

    # ── payload básico ──

    def test_payload_has_server_now_and_alert_threshold(self):
        self._one_claim_session()
        data = self._board()
        self.assertTrue(data['server_now'].endswith('Z'))
        self.assertEqual(data['stopped_alert_s'], 1800)

    # ── tiempo en el estado actual ──

    def test_pending_card_since_is_session_date_start(self):
        session, _claim = self._one_claim_session()
        card = self._card(self._board(), 'pending')
        self.assertEqual(
            card['status_since'],
            session.date_start.strftime('%Y-%m-%dT%H:%M:%SZ'))

    def test_pending_card_without_date_start_has_no_since(self):
        session, _claim = self._one_claim_session()
        session.sudo().date_start = False
        self.assertFalse(self._card(self._board(), 'pending')['status_since'])

    def test_in_progress_since_is_open_working_interval_of_assigned(self):
        session, claim = self._one_claim_session()
        with patch(REQUEST_PATCH_TARGET_ALIAS, self._request_as(self.operator_a)):
            claim.action_assign()
        Interval = self.env['guapante.preparation.interval']
        mine = Interval.search([
            ('claim_id', '=', claim.id), ('kind', '=', 'working'),
            ('end_dt', '=', False), ('employee_id', '=', self.operator_a.id)])
        self.assertTrue(mine, 'Asignarme abre un intervalo working')
        start = fields.Datetime.now() - timedelta(minutes=7)
        mine.sudo().start_dt = start
        # intervalo abierto de OTRO operario: no cuenta
        Interval.sudo().create({
            'wizard_id': session.id, 'claim_id': claim.id,
            'employee_id': self.operator_b.id, 'kind': 'working',
            'start_dt': fields.Datetime.now() - timedelta(minutes=50),
            'last_touched_dt': fields.Datetime.now(),
        })
        card = self._card(self._board(), 'in_progress')
        self.assertEqual(
            card['status_since'], start.strftime('%Y-%m-%dT%H:%M:%SZ'))

    def test_stopped_since_reuses_claim_stopped_since(self):
        _session, claim = self._one_claim_session()
        with patch(REQUEST_PATCH_TARGET_ALIAS, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        claim.invalidate_recordset()
        card = self._card(self._board(), 'stopped')
        self.assertEqual(
            card['status_since'],
            claim.stopped_since.strftime('%Y-%m-%dT%H:%M:%SZ'))

    def test_done_since_is_last_done_date(self):
        session, claim = self._one_claim_session()
        first, last = (
            fields.Datetime.now() - timedelta(minutes=30),
            fields.Datetime.now() - timedelta(minutes=5))
        lines = session.line_ids
        for line, when in zip(lines, (first, last)):
            self._weigh(line, 1.0)
            line.sudo().done_date = when
        card = self._card(self._board(), 'done')
        self.assertEqual(
            card['status_since'], last.strftime('%Y-%m-%dT%H:%M:%SZ'))

    # ── kg ──

    def test_weighed_and_expected_kg(self):
        session, _claim = self._one_claim_session()
        lines = session.line_ids
        self.assertTrue(sum(lines.mapped('estimated_kg')) > 0)
        self._weigh(lines[0], 2.5)
        card = self._card(self._board(), 'pending')
        self.assertAlmostEqual(card['weighed_kg'], 2.5)
        self.assertAlmostEqual(
            card['expected_kg'], round(sum(lines.mapped('estimated_kg')), 2))

    # ── sin stock ──

    def test_zero_lines_counted_apart_from_weighed(self):
        session, _claim = self._one_claim_session()
        lines = session.line_ids
        self._weigh(lines[0], 0.0)
        card = self._card(self._board(), 'pending')
        self.assertEqual(card['zero_line_count'], 1)
        self.assertEqual(card['weighed_kg'], 0)

    def test_no_zero_lines_means_zero(self):
        session, _claim = self._one_claim_session()
        self._weigh(session.line_ids[0], 1.0)
        card = self._card(self._board(), 'pending')
        self.assertEqual(card['zero_line_count'], 0)

    # ── clientes por dirección de entrega ──

    def test_waiting_customers_by_shipping_address_not_parent(self):
        Partner = self.env['res.partner']
        parent = Partner.create({'name': 'Cliente padre PDS'})
        addr_a = Partner.create({'name': 'Dir A', 'parent_id': parent.id, 'type': 'delivery'})
        addr_b = Partner.create({'name': 'Dir B', 'parent_id': parent.id, 'type': 'delivery'})
        o1 = self._create_confirmed_order(qty=1.0)
        o2 = self._create_confirmed_order(qty=1.0)
        o3 = self._create_confirmed_order(qty=1.0)
        o1.partner_shipping_id = addr_a
        o2.partner_shipping_id = addr_b
        o3.partner_shipping_id = addr_b  # misma dirección que o2
        session = self._create_session()
        session.action_load()
        card = self._card(self._board(), 'pending')
        self.assertEqual(card['waiting_customers'], 2)
        # una línea hecha deja de contar para «esperando»
        done_line = session.line_ids.filtered(
            lambda l: l.sale_order_id == o1)
        self._weigh(done_line, 1.0)
        card = self._card(self._board(), 'pending')
        self.assertEqual(card['waiting_customers'], 1)

    # ── alerta de detenido (umbral) ──

    def test_stopped_alert_threshold_default_clamp_invalid(self):
        self._one_claim_session()
        Param = self.env['ir.config_parameter']
        for raw, expected in (
                ('30', 1800), ('5', 300), ('0', 60), ('99999', 86400),
                ('abc', 1800), ('', 1800)):
            Param.set_param(PARAM, raw)
            self.assertEqual(self._board()['stopped_alert_s'], expected, raw)

    # ── en progreso sin pesar ──

    def test_no_weigh_yet_only_while_open_interval_has_no_lines(self):
        session, claim = self._one_claim_session()
        with patch(REQUEST_PATCH_TARGET_ALIAS, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertTrue(self._card(self._board(), 'in_progress')['no_weigh_yet'])
        Interval = self.env['guapante.preparation.interval']
        Interval.search([
            ('claim_id', '=', claim.id), ('kind', '=', 'working'),
            ('end_dt', '=', False)]).sudo().lines_done = 1
        self.assertFalse(self._card(self._board(), 'in_progress')['no_weigh_yet'])

    def test_no_weigh_yet_false_outside_in_progress(self):
        self._one_claim_session()
        self.assertFalse(self._card(self._board(), 'pending')['no_weigh_yet'])

    # ── JS: contador y umbral (verificación de código) ──

    def test_js_and_template_show_counters(self):
        with open(file_path(
                'ist_preparation_day_picking/static/src/js/'
                'preparation_pds_operacion.xml'), encoding='utf-8') as fh:
            xml = fh.read()
        with open(file_path(
                'ist_preparation_day_picking/static/src/js/'
                'preparation_pds_operacion.js'), encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn('state.columns.stopped.length', xml)
        self.assertIn('detenidos ahora', xml)
        self.assertIn('sin stock', xml)
        self.assertIn('fa fa-clock-o', xml)
        self.assertIn('fa fa-user', xml)
        for emoji in ('⏱', '👤'):
            self.assertNotIn(emoji, xml, 'íconos nativos, no emojis')
        self.assertIn('Sin pesar aún', xml)
        self.assertIn('data.stopped_alert_s', js)
        self.assertEqual(js.count('window.setInterval'), 3)  # respaldo, etiqueta y rotación

    # ── permisos reales de «Reportes y PDS» (sin cachés de la fixture) ──

    def test_reports_group_can_read_board_with_operator_names(self):
        """Regresión: el grupo «Reportes y PDS» no tenía ACL de lectura sobre
        guapante.preparation.day.product.claim ni puede leer hr.employee
        (perfil público): el tablero reventaba con AccessError en una petición
        fresca (en las pruebas pasaba por cachés llenos de la fixture)."""
        session, claim = self._one_claim_session()
        # Las líneas se ordenan por is_done: una vez pesada la primera pasa al
        # final, así que hay que fijar ambas ANTES de pesar (si no, [1] sería
        # la misma ya pesada y la otra nunca se cerraría).
        first, second = session.line_ids
        with patch(REQUEST_PATCH_TARGET_ALIAS, self._request_as(self.operator_a)):
            claim.action_assign()
        self._weigh(first, 1.0)
        data = self._board()
        card = self._card(data, 'in_progress')
        self.assertEqual(card['operator_name'], self.operator_a.name)
        self._weigh(second, 1.0)
        data = self._board()
        self.assertEqual(
            self._card(data, 'done')['operator_name'], self.operator_a.name)

    def test_reports_group_has_read_only_acl_on_claims(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'guapante.preparation.day.product.claim'),
            ('group_id', '=', self.reports_group.id)])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read)
        self.assertFalse(acl.perm_write or acl.perm_create or acl.perm_unlink)
