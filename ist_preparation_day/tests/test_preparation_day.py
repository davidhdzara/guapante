# -*- coding: utf-8 -*-
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.controllers.preparation_day_identification_controller import (
    PreparationDayIdentificationController,
)
from odoo.addons.ist_preparation_day.models.const_preparation import (
    IDLE_TIMEOUT_PARAM_KEY,
    PREP_OPERATOR_IDLE_TIMEOUT_SECONDS,
    PREP_OPERATOR_LAST_ACTIVITY_KEY,
    PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY,
    PREP_OPERATOR_PIN_MAX_FAILURES,
    PREP_OPERATOR_SESSION_KEY,
    get_active_prep_operator_id,
    get_idle_timeout_seconds,
    get_pin_lockout_remaining_seconds,
    set_active_prep_operator,
)
from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)


@tagged('post_install', '-at_install')
class TestPreparationDay(TransactionCase):
    """Tests for the Preparation Day session workflow."""

    def setUp(self):
        """Fija el timeout de inactividad al default histórico antes de
        cada test (David/Tech Lead, 2026-11-02) — un valor viejo que
        haya quedado puesto a mano en la base real (ej. una prueba
        manual en Ajustes) no debe filtrarse a los tests, que no deben
        depender del estado de la base. Los tests que prueban su propio
        valor (0, negativo, personalizado, sin parámetro) lo sobre-
        escriben ellos mismos después de este baseline, sin conflicto."""
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, str(PREP_OPERATOR_IDLE_TIMEOUT_SECONDS),
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Prep',
                'code': 'TWP',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'

        cls.partner = cls.env['res.partner'].create({
            'name': 'Restaurante Test Prep',
        })
        cls.child_partner = cls.env['res.partner'].create({
            'name': 'Cocina Principal',
            'parent_id': cls.partner.id,
        })

        # Producto por peso (kg)
        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')
        cls.product_weight = cls.env['product.product'].create({
            'name': 'Aguacate Hass Test Prep',
            'type': 'consu',
            'list_price': 5000.0,
            'uom_id': cls.uom_kg.id,
            'uom_po_id': cls.uom_kg.id,
        })

        # Producto por unidad
        cls.product_unit = cls.env['product.product'].create({
            'name': 'Bolsa Plástica Test',
            'type': 'consu',
            'list_price': 200.0,
        })

        # Fecha de entrega: 14 días en el futuro (evita colisiones)
        cls.delivery_date = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']),
            days=14,
        )

    def _create_confirmed_order(
        self, product=None, qty=5.0, partner=None
    ):
        """Helper: create and confirm a sale order, set picking date."""
        if product is None:
            product = self.product_weight
        if partner is None:
            partner = self.child_partner

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
            })],
        })
        order.action_confirm()

        # Fijar la fecha de picking para que coincida con delivery_date.
        # dt_start ya está en UTC (medianoche LOCAL del delivery_date
        # convertida a UTC) — usar fields.Datetime.to_datetime(date) aquí
        # sería incorrecto: lo guardaría como medianoche UTC "naive", que
        # cae antes de que arranque la ventana que busca action_load()
        # (ver _date_to_utc_range), dejando el picking fuera del rango.
        dt_start, _dt_end = _date_to_utc_range(self.env, self.delivery_date)
        for picking in order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ):
            picking.scheduled_date = dt_start

        return order

    def _create_session(self):
        """Helper: ensure a preparation day session exists for
        self.delivery_date. Idempotente (vía _ensure_session_for_date)
        a propósito: con la Regla de la jornada (2026-10-29), fijar
        scheduled_date de un picking ya puede haber creado la sesión
        de esa fecha como efecto lateral — crear por duplicado
        chocaría con _check_unique_date.
        """
        return self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.delivery_date)

    # ── Tests de Creación de Sesión ──

    def test_session_create_default_name(self):
        """Session should get an auto-generated name from the daily
        sequence (PK/PICK/NNNNN) instead of the default 'Nueva Sesión'.
        """
        session = self._create_session()
        self.assertNotEqual(session.name, 'Nueva Sesión')
        self.assertRegex(session.name, r'^PK/PICK/\d+$')
        self.assertEqual(session.state, 'draft')

    def test_date_field_labels_match_their_real_meaning(self):
        """David, observación #5 (2026-10-29): `date` es la jornada (la
        fecha programada del PICK) y `date_start` es cuándo se cargó la
        sesión — estaban rotulados al revés en el formulario. Guarda de
        regresión barata contra un revert accidental del rótulo."""
        Fields = self.env['guapante.preparation.day']._fields
        self.assertEqual(Fields['date'].string, 'Fecha programada')
        self.assertEqual(Fields['date_start'].string, 'Cargada el')

    def test_no_duplicate_menu_under_inventory_operations(self):
        """Corrección #3 (David, 2026-10-31): "Preparación del Día" ya
        no debe aparecer dentro de Inventario › Operaciones (columna
        "Empleos", stock_picking_batch.menu_stock_jobs) — solo existe
        la app propia "Preparación". Guarda de regresión contra un
        revert accidental del menuitem viejo."""
        with self.assertRaises(ValueError):
            self.env.ref('ist_preparation_day.menu_preparation_day')

        app_menu = self.env.ref('ist_preparation_day.menu_preparation_day_app')
        self.assertEqual(app_menu.action.res_model, 'guapante.preparation.day')

    # ── Tests de action_load() ──

    def test_action_load_creates_lines(self):
        """action_load should create preparation lines for confirmed orders."""
        self._create_confirmed_order(qty=2.5)
        session = self._create_session()
        session.action_load()

        self.assertEqual(session.state, 'loaded')
        self.assertTrue(
            len(session.line_ids) > 0,
            "Session should have preparation lines after load",
        )

    def test_action_load_no_orders_raises(self):
        """action_load should raise UserError if no orders for the date."""
        # Fecha lejana sin órdenes
        session = self.env['guapante.preparation.day'].create({
            'date': fields.Date.add(
                fields.Date.context_today(self.env['sale.order']),
                days=90,
            ),
        })
        with self.assertRaises(UserError):
            session.action_load()

    def test_action_load_deduplicates(self):
        """Loading twice should not duplicate existing lines."""
        self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        count_after_first = len(session.line_ids)

        session.action_load()
        count_after_second = len(session.line_ids)

        self.assertEqual(
            count_after_first,
            count_after_second,
            "Second load should not duplicate lines",
        )

    def test_action_load_adds_new_orders(self):
        """Loading after new order should add only the new line."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        count_first = len(session.line_ids)

        # Crear otra orden para la misma fecha
        self._create_confirmed_order(
            product=self.product_unit, qty=10.0,
        )
        session.action_load()

        self.assertGreater(
            len(session.line_ids),
            count_first,
            "Second load should pick up newly created orders",
        )

    def test_action_load_cleans_cancelled_orders(self):
        """Lines from cancelled orders should be removed on reload."""
        order = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        self.assertTrue(len(session.line_ids) > 0)

        # Cancelar la orden y sus movimientos
        order.action_cancel()
        if order.state != 'cancel':
            order.write({'state': 'cancel'})
        for picking in order.picking_ids:
            if picking.state != 'cancel':
                picking.action_cancel()

        session.action_load()

        pending_from_cancelled = session.line_ids.filtered(
            lambda l: l.sale_order_id == order and not l.is_done
        )
        self.assertFalse(
            pending_from_cancelled,
            "Lines from cancelled orders should be cleaned up",
        )

    def test_action_load_preserves_done_lines(self):
        """Lines already marked is_done should NOT be removed on reload."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        # Simular completar una línea
        line = session.line_ids[0]
        line.with_context(skip_auto_save=True).write({
            'actual_kg': 1.5,
            'is_done': True,
        })
        session.action_load()

        done_line = session.line_ids.filtered(lambda l: l.is_done)
        self.assertTrue(
            done_line,
            "Done lines should be preserved across reloads",
        )

    def test_action_load_customer_hierarchy(self):
        """Lines should show parent as main_customer_name for child contacts."""
        self._create_confirmed_order(
            partner=self.child_partner, qty=1.0,
        )
        session = self._create_session()
        session.action_load()

        line = session.line_ids[0]
        self.assertEqual(
            line.main_customer_name,
            self.partner.name,
            "main_customer_name should be the parent partner",
        )

    # ── Tests de Summary ──

    def test_summary_created_on_load(self):
        """Summary records should be created per product variant."""
        self._create_confirmed_order(
            product=self.product_weight, qty=3.0,
        )
        self._create_confirmed_order(
            product=self.product_unit, qty=5.0,
        )
        session = self._create_session()
        session.action_load()

        self.assertGreaterEqual(
            len(session.summary_ids),
            2,
            "Should have at least 2 summaries (one per product)",
        )

    def test_summary_totals(self):
        """Summary should aggregate estimated_kg from all lines."""
        self._create_confirmed_order(
            product=self.product_weight, qty=2.0,
        )
        self._create_confirmed_order(
            product=self.product_weight, qty=3.0,
        )
        session = self._create_session()
        session.action_load()

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        self.assertTrue(summary)
        self.assertAlmostEqual(
            summary.total_estimated_kg,
            5.0,
            places=2,
            msg="Summary should aggregate all line estimated_kg values",
        )
        self.assertEqual(summary.order_count, 2)

    def test_summary_progress(self):
        """Progress % should reflect done vs total lines."""
        self._create_confirmed_order(
            product=self.product_weight, qty=1.0,
        )
        self._create_confirmed_order(
            product=self.product_weight, qty=1.0,
        )
        session = self._create_session()
        session.action_load()

        # Completar una de las dos líneas
        weight_lines = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        if len(weight_lines) >= 2:
            weight_lines[0].with_context(skip_auto_save=True).write({
                'actual_kg': 1.0,
                'is_done': True,
            })

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        if summary and len(weight_lines) >= 2:
            self.assertAlmostEqual(
                summary.progress_pct,
                50.0,
                places=0,
                msg="Progress should be 50% when 1 of 2 lines is done",
            )

    # ── Tests de action_save_line_weight() ──

    def test_save_line_weight_marks_done(self):
        """Saving a weight should mark the line as done."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        self.assertTrue(line)
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.8})
        session.action_save_line_weight(line.id)

        self.assertTrue(
            line.is_done,
            "Line should be marked as done after saving weight",
        )

    def test_save_line_weight_creates_log(self):
        """Saving weight should create a picking log entry."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.1})
        session.action_save_line_weight(line.id)

        log = self.env['guapante.picking.log'].search([
            ('wizard_id', '=', session.id),
            ('product_product_id', '=', line.product_product_id.id),
        ])
        self.assertTrue(
            log,
            "A picking log entry should be created after saving weight",
        )
        self.assertAlmostEqual(log.actual_kg, 2.1, places=2)

    def test_save_line_weight_updates_summary(self):
        """Saving weight should update the summary total_done_kg."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.9})
        session.action_save_line_weight(line.id)

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        self.assertAlmostEqual(
            summary.total_done_kg,
            1.9,
            places=2,
            msg="Summary total_done_kg should include the saved weight",
        )

    def test_save_line_weight_ignores_zero(self):
        """Saving with actual_kg=0 should NOT mark as done."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        result = session.action_save_line_weight(line.id)

        self.assertFalse(result)
        self.assertFalse(line.is_done)

    def test_auto_finish_session(self):
        """Session should auto-finish when all lines are done."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        for line in session.line_ids:
            line.with_context(skip_auto_save=True).write(
                {'actual_kg': 1.0}
            )
            session.action_save_line_weight(line.id)

        self.assertEqual(
            session.state,
            'done',
            "Session should auto-finish when no pending lines remain",
        )

    # ── Tests de identificación por PIN (Fase 1, 2026-10-19 — módulo propio desde 2026-10-21) ──
    # El gate solo aplica dentro de un contexto HTTP real (ver comentario en
    # action_save_line_weight), así que se simula con un mock de `request` —
    # sin mock (como en los tests de arriba), request es falsy y el gate no corre.

    def test_save_line_weight_requires_pin_when_http_context(self):
        """Con contexto HTTP pero sin operario identificado, debe fallar."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        mock_request = MagicMock()
        mock_request.session = {}
        with patch(
            'odoo.addons.ist_preparation_day.models.preparation_day.request',
            mock_request,
        ):
            with self.assertRaises(UserError):
                session.action_save_line_weight(line.id)

    def test_save_line_weight_logs_identified_employee(self):
        """Con operario identificado en sesión, el log debe guardar su employee_id."""
        employee = self.env['hr.employee'].create({
            'name': 'Operario Test Prep',
            # l10n_co_nomina_electronica exige cuenta bancaria cuando el
            # método de pago es transferencia (default); el PIN de
            # Preparación del Día no tiene relación con esto.
            'l10n_co_ne_payment_method': '10',
            # Desde que get_active_prep_operator_id valida esto él
            # mismo (Tech Lead, 2026-10-31), hace falta el flag incluso
            # para este test de identificación, no solo para los de
            # "Operarios autorizados".
            'is_guapante_prep_operator': True,
        })
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        with patch(
            'odoo.addons.ist_preparation_day.models.preparation_day.request',
            mock_request,
        ):
            session.action_save_line_weight(line.id)

        log = self.env['guapante.picking.log'].search([
            ('wizard_id', '=', session.id),
            ('product_product_id', '=', line.product_product_id.id),
        ])
        self.assertEqual(
            log.employee_id,
            employee,
            "El log debe registrar al operario identificado por PIN",
        )

    def test_identify_operator_blocks_duplicate_pin(self):
        """Gap #1: un PIN compartido por 2 empleados marcados debe
        bloquear, no adivinar."""
        self.env['hr.employee'].create({
            'name': 'Operario A', 'pin': '4321',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })
        self.env['hr.employee'].create({
            'name': 'Operario B', 'pin': '4321',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = {}
        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            result = PreparationDayIdentificationController().identify_operator(
                pin='4321',
            )

        self.assertFalse(result['success'])
        self.assertNotIn(PREP_OPERATOR_SESSION_KEY, mock_request.session)
        self.assertNotIn(
            'Operario A', result.get('error', ''),
            'El mensaje de PIN duplicado no debe revelar quién lo tiene',
        )
        self.assertNotIn(
            'Operario B', result.get('error', ''),
            'El mensaje de PIN duplicado no debe revelar quién lo tiene',
        )

    def test_identify_operator_succeeds_when_marked_and_active(self):
        """David (2026-10-29): "Operarios autorizados" se queda — un
        empleado marcado y activo sí puede identificarse."""
        employee = self.env['hr.employee'].create({
            'name': 'Operario Marcado', 'pin': '5555',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = {}
        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            result = PreparationDayIdentificationController().identify_operator(
                pin='5555',
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['employee_id'], employee.id)

    def test_identify_operator_rejects_unmarked_employee(self):
        """Tener PIN configurado NO alcanza — hay que estar marcado en
        "Operarios autorizados" (David, 2026-10-29, corrección sobre la
        decisión anterior de quitar el marcador)."""
        self.env['hr.employee'].create({
            'name': 'Operario Sin Marcar', 'pin': '7777',
            'l10n_co_ne_payment_method': '10',
        })

        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = {}
        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            result = PreparationDayIdentificationController().identify_operator(
                pin='7777',
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'PIN no reconocido.')

    def test_identify_operator_ignores_archived_employee_pin(self):
        """Un empleado marcado pero archivado no debe poder
        identificarse aunque su PIN siga configurado (QA, 2026-10-29:
        "que siga filtrando solo empleados activos")."""
        employee = self.env['hr.employee'].create({
            'name': 'Operario Archivado', 'pin': '6666',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })
        employee.active = False

        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = {}
        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            result = PreparationDayIdentificationController().identify_operator(
                pin='6666',
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'PIN no reconocido.')

    # ── Límite de intentos del NIP (Tech Lead, 2026-10-31, punto b) ──

    def _identify(self, session, pin):
        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = session
        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            return PreparationDayIdentificationController().identify_operator(
                pin=pin,
            )

    def test_pin_lockout_after_max_failures(self):
        """PREP_OPERATOR_PIN_MAX_FAILURES intentos con PIN no reconocido
        seguidos bloquean esta sesión de navegador — el siguiente
        intento, aunque sea el PIN correcto, debe rechazarse sin ni
        siquiera consultar hr.employee."""
        employee = self._create_valid_operator(pin='9999')
        session = {}
        for _ in range(PREP_OPERATOR_PIN_MAX_FAILURES):
            result = self._identify(session, 'pin-que-no-existe')
            self.assertFalse(result['success'])

        self.assertIn(PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY, session)
        result = self._identify(session, '9999')
        self.assertFalse(
            result['success'],
            'El bloqueo debe rechazar incluso el PIN correcto',
        )
        self.assertTrue(result.get('locked_seconds'))
        self.assertNotIn(PREP_OPERATOR_SESSION_KEY, session)

    def test_pin_lockout_message_appears_on_the_failure_that_triggers_it(self):
        """Tech Lead, 2026-10-31: el intento que ACTIVA el bloqueo (el
        5º) debe responder ya con el mensaje de bloqueo y
        locked_seconds — no el mensaje normal de "PIN no reconocido"
        seguido de un 6º intento recién ahí avisando. Antes de este
        fix el operario veía 5 veces el mismo error sin enterarse del
        bloqueo hasta el siguiente intento."""
        session = {}
        for _ in range(PREP_OPERATOR_PIN_MAX_FAILURES - 1):
            result = self._identify(session, 'pin-que-no-existe')
            self.assertFalse(result.get('locked_seconds'))

        result = self._identify(session, 'pin-que-no-existe')
        self.assertFalse(result['success'])
        self.assertTrue(result.get('locked_seconds'))
        self.assertAlmostEqual(result['locked_seconds'], 60, delta=2)

    def test_pin_empty_does_not_count_as_failure(self):
        """El PIN vacío ('Ingresa tu PIN') no es un intento fallido —
        no debe acercar al bloqueo."""
        session = {}
        for _ in range(PREP_OPERATOR_PIN_MAX_FAILURES):
            result = self._identify(session, '')
            self.assertEqual(result['error'], 'Ingresa tu PIN.')

        self.assertEqual(get_pin_lockout_remaining_seconds(session), 0)

    def test_pin_success_clears_failure_counter(self):
        """Identificarse con éxito reinicia el contador — no basta con
        fallar 4 veces antes de entrar bien y luego sumar sobre lo
        viejo."""
        employee = self._create_valid_operator(pin='1212')
        session = {}
        for _ in range(PREP_OPERATOR_PIN_MAX_FAILURES - 1):
            self._identify(session, 'pin-que-no-existe')

        result = self._identify(session, '1212')
        self.assertTrue(result['success'])

        # Un solo fallo después de un éxito no debe bloquear — el
        # contador de antes de entrar bien ya no debe seguir sumando.
        result = self._identify(session, 'pin-que-no-existe')
        self.assertFalse(result['success'])
        self.assertFalse(result.get('locked_seconds'))

    def test_pin_lockout_expires_after_timeout(self):
        """Pasado PREP_OPERATOR_PIN_LOCKOUT_SECONDS, el bloqueo se
        limpia solo — un intento nuevo (correcto) vuelve a funcionar."""
        employee = self._create_valid_operator(pin='3434')
        session = {}
        for _ in range(PREP_OPERATOR_PIN_MAX_FAILURES):
            self._identify(session, 'pin-que-no-existe')
        self.assertIn(PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY, session)

        # Simula que ya pasó el minuto de bloqueo.
        session[PREP_OPERATOR_PIN_LOCKOUT_UNTIL_KEY] = time.time() - 1
        result = self._identify(session, '3434')
        self.assertTrue(result['success'])

    # ── Tests de cierre por inactividad en Picking (Fase A, 2026-10-22) ──

    def _create_valid_operator(self, pin='4242'):
        """Empleado operario válido (active, is_guapante_prep_operator) —
        desde que get_active_prep_operator_id valida esto él mismo
        (Tech Lead, 2026-10-31), un id inventado como 42 ya no basta
        para estos tests."""
        return self.env['hr.employee'].create({
            'name': 'Operario Helper Test', 'pin': pin,
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

    def test_get_active_prep_operator_id_expires_after_timeout(self):
        """Un timestamp de actividad viejo (>5 min) debe expirar la sesión del
        operario, no devolver el employee_id heredado."""
        employee = self._create_valid_operator()
        session = {}
        set_active_prep_operator(session, employee.id)
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = (
            time.time() - PREP_OPERATOR_IDLE_TIMEOUT_SECONDS - 1
        )

        result = get_active_prep_operator_id(self.env, session)

        self.assertFalse(result, "Debe expirar pasados los 5 minutos")
        self.assertNotIn(
            PREP_OPERATOR_SESSION_KEY, session,
            "La sesión vencida debe limpiarse, no solo ignorarse",
        )

    def test_get_idle_timeout_seconds_defaults_to_300_without_param(self):
        """Sin el parámetro seteado, el default debe seguir siendo el
        comportamiento histórico (5 minutos) — sin sorpresas al instalar."""
        self.env['ir.config_parameter'].sudo().search([
            ('key', '=', IDLE_TIMEOUT_PARAM_KEY),
        ]).unlink()
        self.assertEqual(
            get_idle_timeout_seconds(self.env),
            PREP_OPERATOR_IDLE_TIMEOUT_SECONDS,
        )

    def test_get_idle_timeout_seconds_reads_custom_value(self):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, '600',
        )
        self.assertEqual(get_idle_timeout_seconds(self.env), 600)

    def test_get_idle_timeout_seconds_non_numeric_falls_back_to_default(self):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, 'no-es-un-numero',
        )
        self.assertEqual(
            get_idle_timeout_seconds(self.env),
            PREP_OPERATOR_IDLE_TIMEOUT_SECONDS,
        )

    def test_get_idle_timeout_seconds_negative_falls_back_to_default(self):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, '-30',
        )
        self.assertEqual(
            get_idle_timeout_seconds(self.env),
            PREP_OPERATOR_IDLE_TIMEOUT_SECONDS,
        )

    def test_get_idle_timeout_seconds_zero_is_valid_sin_bloqueo(self):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, '0',
        )
        self.assertEqual(get_idle_timeout_seconds(self.env), 0)

    def test_get_active_prep_operator_id_zero_timeout_never_expires(self):
        """0 = sin bloqueo: una actividad viejísima (horas) NO debe
        expirar la sesión del operario."""
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, '0',
        )
        employee = self._create_valid_operator()
        session = {}
        set_active_prep_operator(session, employee.id)
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = time.time() - 3600 * 8

        result = get_active_prep_operator_id(self.env, session)

        self.assertEqual(
            result, employee.id,
            "Con el parámetro en 0 la sesión nunca debe expirar por tiempo",
        )

    def test_get_active_prep_operator_id_custom_timeout_respected(self):
        """Con el parámetro en 60s, una actividad de 90s atrás ya debe
        expirar — aunque esté muy por debajo del default de 300s."""
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, '60',
        )
        employee = self._create_valid_operator()
        session = {}
        set_active_prep_operator(session, employee.id)
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = time.time() - 90

        result = get_active_prep_operator_id(self.env, session)

        self.assertFalse(result)

    def test_get_active_prep_operator_id_refresh_true_extends_session(self):
        """refresh=True (acción real del operario) debe extender la ventana."""
        employee = self._create_valid_operator()
        session = {}
        set_active_prep_operator(session, employee.id)
        old_timestamp = time.time() - 250  # dentro de la ventana, pero vieja
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = old_timestamp

        result = get_active_prep_operator_id(self.env, session, refresh=True)

        self.assertEqual(result, employee.id)
        self.assertGreater(
            session[PREP_OPERATOR_LAST_ACTIVITY_KEY], old_timestamp,
            "refresh=True debe actualizar el timestamp de actividad",
        )

    def test_get_active_prep_operator_id_refresh_false_does_not_extend(self):
        """refresh=False (consulta de solo lectura, ej. watchdog del cliente)
        no debe extender la ventana — si lo hiciera, el timeout nunca se
        cumpliría mientras la pestaña siga preguntando."""
        employee = self._create_valid_operator()
        session = {}
        set_active_prep_operator(session, employee.id)
        old_timestamp = time.time() - 250
        session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = old_timestamp

        result = get_active_prep_operator_id(self.env, session, refresh=False)

        self.assertEqual(result, employee.id)
        self.assertEqual(
            session[PREP_OPERATOR_LAST_ACTIVITY_KEY], old_timestamp,
            "refresh=False no debe tocar el timestamp de actividad",
        )

    def test_get_active_prep_operator_id_clears_session_when_deactivated(self):
        """Tech Lead (2026-10-31): si el operario se desactiva a mitad de
        turno, el helper debe dejar de aceptarlo — no solo la pantalla de
        NIP, también cualquier escritura de Picking que pase por acá."""
        employee = self._create_valid_operator(pin='4243')
        session = {}
        set_active_prep_operator(session, employee.id)
        employee.active = False

        result = get_active_prep_operator_id(self.env, session, refresh=True)

        self.assertFalse(result)
        self.assertNotIn(PREP_OPERATOR_SESSION_KEY, session)

    def test_get_active_prep_operator_id_clears_session_when_flag_removed(self):
        """Mismo caso que arriba pero quitando is_guapante_prep_operator en
        vez de archivar — David (2026-10-29): el flag sigue siendo
        obligatorio para operar, no solo tener PIN."""
        employee = self._create_valid_operator(pin='4244')
        session = {}
        set_active_prep_operator(session, employee.id)
        employee.is_guapante_prep_operator = False

        result = get_active_prep_operator_id(self.env, session, refresh=True)

        self.assertFalse(result)
        self.assertNotIn(PREP_OPERATOR_SESSION_KEY, session)

    def test_current_operator_endpoint_clears_deactivated_operator(self):
        """Tech Lead (2026-10-31): el endpoint que consulta la pantalla de
        NIP (y el idle watcher) también debe dejar de reconocer a un
        operario desactivado a mitad de turno — no solo el helper en
        aislamiento, el camino HTTP real que usa el cliente."""
        employee = self._create_valid_operator(pin='4246')
        mock_request = MagicMock()
        mock_request.env = self.env
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        employee.active = False

        with patch(
            'odoo.addons.ist_preparation_day.controllers'
            '.preparation_day_identification_controller.request',
            mock_request,
        ):
            result = PreparationDayIdentificationController().current_operator()

        self.assertFalse(result['employee_id'])
        self.assertNotIn(PREP_OPERATOR_SESSION_KEY, mock_request.session)

    def test_picking_flow_weight_with_expired_session_raises(self):
        """Hallazgo de Tech Lead: un pesaje que sale de Picking
        (guapante_picking_flow=True) con el operario expirado debe fallar
        con un error claro, nunca colarse por la rama de Productos."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        line = session.line_ids[:1]

        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, 999999)
        mock_request.session[PREP_OPERATOR_LAST_ACTIVITY_KEY] = (
            time.time() - PREP_OPERATOR_IDLE_TIMEOUT_SECONDS - 1
        )
        with patch(
            'odoo.addons.ist_preparation_day.models.preparation_day.request',
            mock_request,
        ):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).write(
                    {'actual_kg': 1.5}
                )

        self.assertEqual(
            line.actual_kg, 0.0,
            "La línea no debe quedar con el peso aplicado si el pesaje falló",
        )
        self.assertFalse(line.is_done)

    def test_non_picking_flow_weight_still_uses_productos_branch(self):
        """Regresión: un pesaje SIN el flag de Picking (edición inline normal
        de la pestaña Productos) debe seguir funcionando igual que antes,
        sin exigir operario identificado."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        line = session.line_ids[:1]

        line.write({'actual_kg': 1.5})

        self.assertTrue(
            line.is_done,
            "Sin el flag de Picking, el pesaje debe registrarse igual que "
            "antes por la pestaña Productos (sin exigir PIN)",
        )

    # ── Tests de action_undo_line() ──

    def test_undo_line_reverts_to_pending(self):
        """Undoing a line should set is_done=False and actual_kg=0."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({
            'actual_kg': 2.3,
            'is_done': True,
        })
        line.action_undo_line()

        self.assertFalse(line.is_done)
        self.assertAlmostEqual(line.actual_kg, 0.0, places=2)

    def test_undo_line_updates_summary(self):
        """Undoing should subtract from summary total_done_kg.

        Segundo producto (David/Tech Lead, 2026-11-02, M-1): mismo
        motivo que en test_undo_line_clears_done_stamp — sin un segundo
        pendiente, terminar la única línea cierra la sesión y
        action_undo_line() queda bloqueado por el guard de cierre."""
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(product=self.product_unit, qty=3.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.5})
        session.action_save_line_weight(line.id)

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        done_before = summary.total_done_kg

        line.action_undo_line()

        self.assertAlmostEqual(
            summary.total_done_kg,
            done_before - 2.5,
            places=2,
            msg="Undo should subtract the weight from summary",
        )

    # ── Tests de done_by_employee_id / done_date (punto 4 de Tech Lead, 2026-11-02) ──

    def test_save_line_weight_stamps_done_by_employee_and_date(self):
        """Pesaje por Picking (PIN) debe estampar quién y cuándo."""
        employee = self.env['hr.employee'].create({
            'name': 'Operario Stamp Test',
            'l10n_co_ne_payment_method': '10',
            'is_guapante_prep_operator': True,
        })
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        with patch(
            'odoo.addons.ist_preparation_day.models.preparation_day.request',
            mock_request,
        ):
            session.action_save_line_weight(line.id)

        self.assertEqual(line.done_by_employee_id, employee)
        self.assertTrue(line.done_date)

    def test_register_weight_from_productos_tab_stamps_employee_from_user(self):
        """Edición inline desde Productos (sin PIN): done_by_employee_id
        sale del empleado vinculado al usuario de Odoo logueado."""
        employee = self.env['hr.employee'].create({
            'name': 'Supervisor Stamp Test',
            'l10n_co_ne_payment_method': '10',
            'user_id': self.env.user.id,
        })
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.write({'actual_kg': 1.5})

        self.assertEqual(line.done_by_employee_id, employee)
        self.assertTrue(line.done_date)

    def test_register_weight_from_productos_tab_stamps_date_without_employee(self):
        """Sin empleado vinculado al usuario logueado, done_by_employee_id
        queda vacío pero done_date se estampa igual (Tech Lead, 2026-11-02)."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.write({'actual_kg': 1.5})

        self.assertFalse(line.done_by_employee_id)
        self.assertTrue(line.done_date)

    def test_register_weight_correction_does_not_overwrite_done_stamp(self):
        """Una corrección post-cierre no debe pisar quién/cuándo completó
        la línea la PRIMERA vez."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        employee = self.env['hr.employee'].create({
            'name': 'Supervisor Original Stamp',
            'l10n_co_ne_payment_method': '10',
            'user_id': self.env.user.id,
        })
        line = session.line_ids[:1]
        line.write({'actual_kg': 1.5})
        original_employee = line.done_by_employee_id
        original_date = line.done_date
        self.assertEqual(original_employee, employee)

        line.write({'actual_kg': 1.8})

        self.assertEqual(
            line.done_by_employee_id, original_employee,
            "Una corrección no debe cambiar quién completó la línea",
        )
        self.assertEqual(
            line.done_date, original_date,
            "Una corrección no debe cambiar cuándo se completó la línea",
        )

    def test_undo_line_clears_done_stamp(self):
        """Devolver una línea a Pendiente debe limpiar done_by_employee_id
        y done_date, no solo is_done/actual_kg.

        Segundo producto (David/Tech Lead, 2026-11-02, M-1): una sesión
        de un solo producto se auto-cierra al terminar su única línea
        (pending_total == 0) y action_undo_line() ya no permite devolver
        a Pendiente una línea de sesión cerrada (guard nuevo) — sin un
        segundo producto pendiente, este test terminaría probando el
        guard de cierre, no la reversa que le da nombre."""
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(product=self.product_unit, qty=3.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        line.write({'actual_kg': 1.5})
        self.assertTrue(line.done_date)

        line.action_undo_line()

        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.done_date)

    # ── Edición inline de admin: 0 sobre una Terminada = action_undo_line,
    # negativo bloqueado en todos los orígenes (M-1, David/Tech Lead,
    # 2026-11-02) ──

    def test_write_zero_on_done_line_reverts_via_action_undo_line(self):
        """Poner actual_kg en 0 sobre una línea ya Terminada, vía write()
        (como hace la edición inline de admin en la lista de líneas),
        debe tener el mismo efecto que llamar action_undo_line() directo:
        vuelve a Pendiente, limpia done_by/done_date y el stock.

        Segundo producto (David/Tech Lead, 2026-11-02, M-1): sin un
        segundo pendiente, terminar la única línea cierra la sesión y
        el segundo write (a 0) chocaría con el guard de sesión cerrada
        en vez de probar la reversa — eso se prueba aparte."""
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(product=self.product_unit, qty=3.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        line.write({'actual_kg': 1.5})
        self.assertTrue(line.is_done)

        line.write({'actual_kg': 0})

        self.assertFalse(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.done_date)

    def test_write_negative_actual_kg_raises(self):
        """Ningún origen puede escribir un peso negativo — guard parejo
        en CORE, antes de que el valor llegue a super().write()."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        with self.assertRaises(UserError):
            line.write({'actual_kg': -1.0})
        self.assertEqual(line.actual_kg, 0.0, 'el valor negativo no debe escribirse')

    # ── Edición inline de admin: casilla "Terminado" (E4, David/Tech
    # Lead, 2026-11-02) — mismo write() de CORE, dispatch track_done ──

    def test_write_is_done_true_marks_done_like_weighing(self):
        """Marcar Terminado (sin tocar el peso) con un peso ya puesto > 0
        reusa _register_weight_from_productos_tab() entero."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})
        self.assertFalse(line.is_done, 'setup: peso puesto, aún no Terminado')

        line.write({'is_done': True})

        self.assertTrue(line.is_done)
        self.assertTrue(line.done_date)

    def test_write_is_done_true_with_zero_weight_raises(self):
        """Marcar Terminado sin un peso registrado (actual_kg<=0) da un
        UserError claro — nunca un Terminado de un peso que no existe."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        self.assertEqual(line.actual_kg, 0.0, 'setup: sin peso puesto')

        with self.assertRaises(UserError):
            line.write({'is_done': True})
        self.assertFalse(line.is_done, 'el guard bloquea antes de marcar nada')

    def test_write_is_done_false_reverts_via_action_undo_line(self):
        """Desmarcar Terminado (sin tocar el peso) tiene el mismo efecto
        que action_undo_line(): vuelve a Pendiente, limpia done_by/
        done_date y el peso.

        Segundo producto (mismo motivo que test_write_zero_on_done_
        line_reverts_via_action_undo_line): sin uno pendiente, terminar
        la única línea cierra la sesión y el segundo write chocaría con
        el guard de sesión cerrada en vez de probar la reversa."""
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(product=self.product_unit, qty=3.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        line.write({'actual_kg': 1.5})
        self.assertTrue(line.is_done)

        line.write({'is_done': False})

        self.assertFalse(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.done_date)

    def test_write_is_done_and_actual_kg_together_treated_as_weighing(self):
        """Marcar Terminado Y escribir un peso nuevo en la misma fila no
        pasa por track_done — el camino de actual_kg (track_kg) decide
        todo solo con el peso, is_done termina correcto igual."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        self.assertEqual(line.actual_kg, 0.0, 'setup: sin peso puesto')

        line.write({'actual_kg': 1.5, 'is_done': True})

        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 1.5)
        self.assertTrue(line.done_date)

    def test_write_is_done_with_other_field_applies_both(self):
        """track_done hace return antes de llegar a super().write(vals)
        — si vals trae OTRA clave además de is_done, debe escribirse
        igual (Tech Lead, 2026-11-02): no es el camino de hoy desde la
        vista (solo is_done o solo actual_kg llegan editables), pero
        write() es público y nada impide una llamada RPC/Python con
        más claves en el mismo vals."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        line.write({
            'is_done': True,
            'product_description': 'Descripción editada aparte',
        })

        self.assertTrue(line.is_done)
        self.assertEqual(line.product_description, 'Descripción editada aparte')

    # ── Tests de write() override ──

    def test_write_actual_kg_auto_saves(self):
        """Writing actual_kg > 0 should auto-trigger save."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        self.assertTrue(line)

        # Escribir actual_kg sin skip_auto_save debe auto-guardar
        line.write({'actual_kg': 1.5})

        self.assertTrue(
            line.is_done,
            "Writing actual_kg > 0 without skip_auto_save should "
            "auto-mark as done",
        )

    def test_write_skip_auto_save(self):
        """Writing with skip_auto_save=True should NOT auto-trigger."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        self.assertFalse(
            line.is_done,
            "skip_auto_save context should prevent auto-save",
        )

    # ── Tests de Product Wizard ──

    def test_product_wizard_lists(self):
        """Wizard should separate pending and done lines correctly."""
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        weight_lines = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        if len(weight_lines) < 2:
            return  # Skip if product was merged

        # Completar una línea
        weight_lines[0].with_context(skip_auto_save=True).write({
            'actual_kg': 1.0,
            'is_done': True,
        })

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        if not summary:
            return

        # Abrir wizard
        action = summary.action_select_product()
        wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].browse(action['res_id'])

        self.assertEqual(len(wizard.detail_line_done_ids), 1)
        self.assertEqual(len(wizard.detail_line_pending_ids), 1)
        self.assertAlmostEqual(
            wizard.progress_percentage, 50.0, places=0,
        )

    def test_product_wizard_back_to_session(self):
        """action_back_to_session should return correct action dict."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        summary = session.summary_ids[:1]
        if not summary:
            return

        action = summary.action_select_product()
        wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].browse(action['res_id'])

        back_action = wizard.action_back_to_session()
        self.assertEqual(
            back_action['res_model'],
            'guapante.preparation.day',
        )
        self.assertEqual(back_action['res_id'], session.id)

    # ── Tests de Session Lifecycle ──

    def test_session_reopen(self):
        """Reopening a done session should set state to loaded."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        session.action_mark_done()
        self.assertEqual(session.state, 'done')

        session.action_reopen()
        self.assertEqual(session.state, 'loaded')

    def test_session_reopen_allows_new_orders(self):
        """Reopening then loading should pick up new orders."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        session.action_mark_done()
        session.action_reopen()

        # Agregar una nueva orden
        self._create_confirmed_order(
            product=self.product_unit, qty=5.0,
        )
        session.action_load()

        has_unit_product = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_unit
        )
        self.assertTrue(
            has_unit_product,
            "Reopened session should pick up new orders on load",
        )

    # ── Tests de _get_display_qty() ──

    def test_display_qty_kg_mode(self):
        """Kg mode should display raw quantity."""
        order = self._create_confirmed_order(qty=2.5)
        sol = order.order_line.filtered(
            lambda l: l.product_id == self.product_weight
        )[:1]
        if sol:
            sol.uom_mode = 'kg'
            result = self.env[
                'guapante.preparation.day.line'
            ]._get_display_qty(sol)
            self.assertEqual(result, ('2.5', 'kg'))

    def test_display_qty_g_mode(self):
        """Gram mode should convert kg to grams."""
        order = self._create_confirmed_order(qty=0.5)
        sol = order.order_line.filtered(
            lambda l: l.product_id == self.product_weight
        )[:1]
        if sol:
            sol.uom_mode = 'g'
            result = self.env[
                'guapante.preparation.day.line'
            ]._get_display_qty(sol)
            self.assertEqual(result, ('500', 'g'))

    def test_action_export_excel(self):
        """action_export_excel should return correct action url dict."""
        session = self._create_session()
        action = session.action_export_excel()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/web/guapante/preparation_day/', action['url'])
        self.assertIn('/export_excel', action['url'])
