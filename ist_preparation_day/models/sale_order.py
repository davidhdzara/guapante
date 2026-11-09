# -*- coding: utf-8 -*-
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .box_number import (
    CTX_ORIGIN,
    CTX_REASON,
    ORIGIN_ALTA,
    ORIGIN_REUBICACION,
    ORIGIN_RESET,
    box_origin,
    get_box_origin,
)
from .preparation_day import (
    _PG_CONCURRENCY_ERRORS,
    _current_session_date,
    _date_to_utc_range,
    _utc_datetime_to_session_date,
)

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Numeración diaria de cajas ("Caja #") para Preparation Day.

    Vive en este módulo (no en theme_guapante) porque nace y se consume acá: se
    asigna en action_load() y se muestra/resetea en Inventario (ver
    models/stock_picking.py de este mismo módulo) — es dominio de Preparation Day,
    nunca se expone en ecommerce/portal (verificado 2026-10-21: cero referencias
    en theme_guapante/views/shop, views/portal, controllers/shop.py,
    controllers/customer_portal.py).
    """
    _inherit = 'sale.order'

    daily_sequence = fields.Integer(
        string='# del día',
        default=0,
        copy=False,
        # Totales de grupo sin sentido (David, 2026-11-04 ~21:30): un
        # Integer suma por defecto en el encabezado de grupo (ver
        # Integer.aggregator='sum' en odoo/fields.py) — "Caja #" no es
        # una cantidad agregable (es un identificador, como 'sequence'
        # ya trata el propio core). aggregator=False acá se propaga
        # solo a los related 'daily_sequence' de stock.picking y de
        # guapante.preparation.day.line (ver _related_aggregator en
        # fields.py) — una sola fuente de verdad para TODAS las listas
        # donde aparece esta columna, sin tocar cada vista una por una.
        # DECISIÓN (David, 2026-11-04): no se agrega ninguna columna de
        # reemplazo (conteo de órdenes/productos) — el "(N)" del
        # encabezado de grupo ya cuenta las líneas.
        aggregator=False,
        help=(
            'Daily box number for the order\'s delivery date '
            '(pickings scheduled date).'
        ),
    )

    # ── Candado, historial y revisión (lote 4) ──────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        if any((v.get('daily_sequence') or 0) > 0 for v in vals_list) \
                and not get_box_origin(self.env):
            raise UserError(
                'El número de caja lo asigna el sistema; no se puede '
                'fijar al crear el pedido.'
            )
        return super().create(vals_list)

    def write(self, vals):
        if 'daily_sequence' not in vals:
            return super().write(vals)
        new = vals['daily_sequence'] or 0
        changing = self.filtered(lambda o: o.daily_sequence != new)
        if not changing:
            return super().write(vals)
        origin = get_box_origin(self.env)
        if not origin:
            raise UserError(
                'El número de caja no se edita a mano. Cambia solo por '
                'asignación automática, reubicación de fecha o el reinicio '
                'administrativo de cajas (que exige un motivo y queda en '
                'el historial).'
            )
        if new > 0 and changing.filtered(lambda o: o.daily_sequence > 0):
            raise UserError(
                'Las cajas nunca se renumeran: un pedido con número de caja '
                'solo puede volver a 0 por reinicio o reubicación y luego '
                'tomar el siguiente (MAX+1).'
            )
        reason = (self.env.context.get(CTX_REASON) or '').strip()
        if origin == ORIGIN_RESET and not reason:
            raise UserError('El reinicio de cajas exige un motivo.')
        snapshot = [(o, o.daily_sequence) for o in changing]
        res = super().write(vals)
        self._guapante_log_box_change(snapshot, new, origin, reason)
        return res

    def _guapante_box_date(self):
        """Jornada (fecha local) del PICK interno más temprano del pedido."""
        self.ensure_one()
        picks = self.env['stock.picking'].sudo().search([
            ('sale_id', '=', self.id),
            ('picking_type_code', '=', 'internal'),
            ('scheduled_date', '!=', False),
        ], order='scheduled_date', limit=1)
        if not picks:
            return False
        return _utc_datetime_to_session_date(self.env, picks.scheduled_date)

    def _guapante_log_box_change(self, snapshot, new, origin, reason):
        Log = self.env['guapante.box.number.log'].sudo()
        Log.create([{
            'order_id': order.id,
            'order_name': order.name,
            'company_id': order.company_id.id,
            'box_date': order._guapante_box_date(),
            'old_sequence': old,
            'new_sequence': new,
            'origin': str(origin),
            'reason': reason or False,
            'user_id': self.env.user.id,
        } for order, old in snapshot])

    @api.constrains('daily_sequence')
    def _check_daily_sequence_unique(self):
        # En una reubicación en lote los hermanos aún no reseteados
        # conservan su número viejo mientras su PICK ya cae en la fecha
        # nueva: ese estado es transitorio y lo cierra el chequeo de fin
        # de lote (stock.picking.write) / la revisión automática.
        if get_box_origin(self.env) == ORIGIN_REUBICACION:
            return
        for order in self.filtered(lambda o: o.daily_sequence > 0):
            dup = order._guapante_find_duplicates_for_order()
            if dup:
                raise ValidationError(
                    'La caja #%s ya está usada por %s ese día. Las cajas '
                    'son únicas por jornada.' % (
                        order.daily_sequence, ', '.join(dup.mapped('name')),
                    )
                )

    def _guapante_find_duplicates_for_order(self):
        """Otros pedidos de la misma compañía con la misma caja en alguna
        de las jornadas (PICK interno, cualquier estado) de este pedido."""
        self.ensure_one()
        picks = self.env['stock.picking'].sudo().search([
            ('sale_id', '=', self.id),
            ('picking_type_code', '=', 'internal'),
            ('scheduled_date', '!=', False),
        ])
        dups = self.browse()
        for day in {
            _utc_datetime_to_session_date(self.env, p.scheduled_date)
            for p in picks
        }:
            dt_start, dt_end = _date_to_utc_range(self.env, day)
            others = self.env['stock.picking'].sudo().search([
                ('scheduled_date', '>=', dt_start),
                ('scheduled_date', '<', dt_end),
                ('picking_type_code', '=', 'internal'),
                ('sale_id', '!=', False),
                ('sale_id', '!=', self.id),
                ('sale_id.daily_sequence', '=', self.daily_sequence),
                ('sale_id.company_id', '=', self.company_id.id),
            ]).mapped('sale_id')
            dups |= others
        return dups

    @api.model
    def _guapante_check_box_numbering(self, delivery_date):
        """Revisión automática de la jornada ``delivery_date``.

        Abre/cierra registros de ``guapante.box.number.issue`` y deja UNA
        nota (idempotente) en el chatter de la sesión. Los huecos por
        cancelación NO son error (regla de David): no se reportan.
        Devuelve la lista de hallazgos abiertos [(kind, order, seq, detail)].
        """
        date = fields.Date.to_date(delivery_date)
        dt_start, dt_end = _date_to_utc_range(self.env, date)
        Picks = self.env['stock.picking'].sudo().search([
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('sale_id', '!=', False),
        ])
        findings = []
        # (1) duplicados: misma compañía + mismo número en la jornada.
        groups = {}
        for order in Picks.mapped('sale_id').filtered(
                lambda o: o.daily_sequence > 0):
            groups.setdefault(
                (order.company_id.id, order.daily_sequence), self.browse(),
            )
            groups[(order.company_id.id, order.daily_sequence)] |= order
        for (_cid, seq), orders in groups.items():
            if len(orders) > 1:
                for order in orders:
                    findings.append((
                        'duplicate', order, seq,
                        'Caja #%s repetida en: %s' % (
                            seq, ', '.join(orders.mapped('name')),
                        ),
                    ))
        # (2) pedidos de la sesión SIN número y (3) cambios fuera del
        # historial (solo si el pedido ya tiene historial: los anteriores
        # al lote 4 no tienen línea base y no se marcan).
        Session = self.env['guapante.preparation.day'].sudo().search(
            [('date', '=', date)], limit=1,
        )
        session_orders = Session.line_ids.mapped('sale_order_id')
        for order in session_orders.filtered(
                lambda o: o.state in ('sale', 'done')
                and o.daily_sequence == 0):
            findings.append((
                'missing', order, 0, 'El pedido está en la sesión y no '
                'tiene número de caja',
            ))
        Log = self.env['guapante.box.number.log'].sudo()
        for order in session_orders.filtered(lambda o: o.daily_sequence > 0):
            last = Log.search(
                [('order_id', '=', order.id)], order='id desc', limit=1,
            )
            if last and last.new_sequence != order.daily_sequence:
                findings.append((
                    'outside_log', order, order.daily_sequence,
                    'El último registro del historial dice #%s y el pedido '
                    'tiene #%s' % (last.new_sequence, order.daily_sequence),
                ))
        self._guapante_sync_box_issues(date, findings, Session)
        return findings

    @api.model
    def _guapante_sync_box_issues(self, date, findings, session):
        Issue = self.env['guapante.box.number.issue'].sudo()
        existing = Issue.search([('box_date', '=', date), ('state', '=', 'open')])
        seen = set()
        for kind, order, seq, detail in findings:
            key = (kind, order.id, seq)
            seen.add(key)
            if not existing.filtered(
                    lambda i, k=key: (i.kind, i.order_id.id, i.sequence) == k):
                Issue.create({
                    'kind': kind, 'box_date': date, 'order_id': order.id,
                    'sequence': seq, 'detail': detail,
                })
        for issue in existing:
            if (issue.kind, issue.order_id.id, issue.sequence) not in seen:
                issue.write({
                    'state': 'resolved',
                    'resolved_date': fields.Datetime.now(),
                })
        if findings and session:
            lines = ''.join(
                '<li>%s — %s</li>' % (order.name, detail)
                for _kind, order, _seq, detail in findings
            )
            session._guapante_post_note_once(
                'Revisión de cajas: %d inconsistencia(s).<ul>%s</ul>' % (
                    len(findings), lines))

    @api.model
    def _cron_check_box_numbering(self):
        """Hoy y mañana (jornada local). Barato y acotado."""
        today = _current_session_date(self.env)
        for day in (today, fields.Date.add(today, days=1)):
            try:
                with self.env.cr.savepoint():
                    self._guapante_check_box_numbering(day)
            except _PG_CONCURRENCY_ERRORS:
                raise
            except Exception:
                _logger.exception(
                    'Guapante: revisión de cajas falló para %s', day)

    @api.model
    def _guapante_daily_sequence_code(
        self, company_id: int, delivery_date
    ) -> str:
        """Stable ir.sequence code: one counter per company and day."""
        d = fields.Date.to_date(delivery_date)
        cid = int(company_id) if company_id else 0
        return 'guapante.daily.%s.%s' % (cid, d.strftime('%Y%m%d'))

    @api.model
    def _guapante_max_daily_sequence_on_date(
        self, company_id: int, delivery_date, exclude_picking_ids=None
    ) -> int:
        """Max existing daily_sequence for orders on this delivery date.

        Includes ALL states (even cancelled) to prevent box number
        reuse after order cancellation.

        exclude_picking_ids (Propuesta A, Tech Lead 2026-11-04 — bug de
        reubicación en lote): ids de pickings que se están reubicando
        a esta MISMA fecha dentro del mismo stock.picking.write() que
        disparó este cálculo. super().write() ya movió el
        scheduled_date de TODOS ellos antes de que el loop de
        relocate() reasigne su daily_sequence uno por uno — así que,
        sin esto, los pedidos hermanos todavía no reseteados (su
        daily_sequence sigue siendo el de la fecha VIEJA, no 0 todavía)
        aparecían en este domain como si ya fueran parte de la fecha
        nueva, inflando el "máximo" y dejando huecos al principio
        (ej. cajas 4,5,6 en vez de 1,2,3 al reubicar 3 PICK juntos en
        un solo write). Excluirlos acá es seguro: si de verdad ya
        tienen un daily_sequence>0 vigente para la fecha nueva (porque
        ya se les asignó en una vuelta anterior de este mismo loop),
        ese pedido ya no pasa por este método de nuevo (el loop de
        _assign_daily_sequences salta a quien ya tiene daily_sequence).
        """
        dt_start, dt_end = _date_to_utc_range(self.env, delivery_date)
        cid = company_id if company_id else None
        domain_company = (
            [('company_id', '=', cid)]
            if cid
            else [('company_id', '=', False)]
        )
        # Solo pickings PICK (internal/Recolectar).
        PickDomain = [
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('sale_id', '!=', False),
            ('sale_id.daily_sequence', '>', 0),
        ]
        if cid:
            PickDomain.append(('company_id', '=', cid))
        if exclude_picking_ids:
            PickDomain.append(('id', 'not in', list(exclude_picking_ids)))

        Pickings = self.env['stock.picking'].sudo().search(PickDomain)
        Candidates = Pickings.mapped('sale_id')
        if not Candidates:
            return 0
        return max(Candidates.mapped('daily_sequence'))

    @api.model
    def _guapante_get_or_create_daily_ir_sequence(
        self, company_id: int, delivery_date, exclude_picking_ids=None
    ):
        """Return ir.sequence for (company, day); create if missing.

        SIEMPRE sincroniza number_next con el máximo real de la BD
        para evitar duplicados tras cancelaciones o ediciones manuales.

        exclude_picking_ids: ver _guapante_max_daily_sequence_on_date.
        """
        # sudo(): ir.sequence creation requiere permisos de admin
        # ya que el usuario de preparación normalmente no tiene
        # acceso a la configuración de secuencias.
        Sequence = self.env['ir.sequence'].sudo()
        code = self._guapante_daily_sequence_code(
            company_id, delivery_date,
        )
        seq = Sequence.search([('code', '=', code)], limit=1)

        max_existing = self._guapante_max_daily_sequence_on_date(
            company_id, delivery_date, exclude_picking_ids=exclude_picking_ids,
        )
        safe_next = max_existing + 1 if max_existing >= 0 else 1

        if seq:
            # CORRECCIÓN: Siempre sincronizar number_next con el max
            # real de la BD. Si alguien canceló órdenes, editó
            # manualmente, o la secuencia quedó desincronizada,
            # esto garantiza que el próximo número sea max + 1.
            if seq.number_next_actual != safe_next:
                seq.sudo().write({'number_next': safe_next})
                _logger.info(
                    'Guapante: synced ir.sequence %s number_next '
                    'to %d (was %d)',
                    code, safe_next, seq.number_next_actual,
                )
            return seq

        d = fields.Date.to_date(delivery_date)
        vals = {
            'name': 'Guapante delivery day %s (%s)' % (
                d.isoformat(), code,
            ),
            'code': code,
            'implementation': 'standard',
            'company_id': company_id if company_id else False,
            'active': True,
            'prefix': '',
            'suffix': '',
            'padding': 1,
            'number_increment': 1,
            'number_next': safe_next,
        }
        try:
            with self.env.cr.savepoint():
                seq = Sequence.create(vals)
        except IntegrityError:
            seq = Sequence.browse()
        if not seq:
            seq = Sequence.search([('code', '=', code)], limit=1)
        if not seq:
            _logger.error(
                'Guapante: failed to get ir.sequence for code %s',
                code,
            )
            raise UserError(
                'Could not initialize the daily order sequence. '
                'Please retry or contact support.'
            )
        return seq

    @api.model
    def _assign_daily_sequences(
        self, delivery_date, exclude_picking_ids=None
    ) -> None:
        """Assign daily_sequence to confirmed orders for a delivery date.

        Called from PreparationDay.action_load so the sequence is always
        scoped to the actual delivery date, not the order creation date.
        Orders that already have a sequence keep it; new orders receive
        the next number from an ir.sequence (concurrency-safe).

        exclude_picking_ids (Propuesta A): se pasa tal cual a
        _guapante_get_or_create_daily_ir_sequence — ver su docstring y
        el de _guapante_max_daily_sequence_on_date. No afecta qué
        pedidos se recorren acá (OrdersForDate sigue completo): solo
        afecta el cálculo del "máximo ya existente" para la fecha, que
        es donde vivía el bug de reubicación en lote.
        """
        # Buscar solo pickings PICK (internal/Recolectar) PENDIENTES.
        # Excluir done/cancel: órdenes ya entregadas no deben recibir
        # un nuevo número de caja (bug S00204/S00220).
        dt_start, dt_end = _date_to_utc_range(self.env, delivery_date)
        Pickings = self.env['stock.picking'].sudo().search([
            ('scheduled_date', '>=', dt_start),
            ('scheduled_date', '<', dt_end),
            ('picking_type_code', '=', 'internal'),
            ('state', 'not in', ('done', 'cancel')),
            ('sale_id', '!=', False),
            ('sale_id.state', 'in', ('sale', 'done')),
        ])
        OrdersForDate = Pickings.mapped('sale_id').sorted('id')
        # Candado de cajas: el alta usa SIEMPRE un origen del sistema; si
        # quien llama (reubicación) ya puso el suyo, se respeta.
        origin = get_box_origin(self.env) or box_origin(ORIGIN_ALTA)
        seq_by_company = {}
        Touched = self.env['sale.order']
        for order in OrdersForDate:
            if order.daily_sequence:
                continue
            cid = order.company_id.id if order.company_id else False
            if cid not in seq_by_company:
                seq_by_company[cid] = (
                    self.env['sale.order']
                    .sudo()
                    ._guapante_get_or_create_daily_ir_sequence(
                        cid, delivery_date,
                        exclude_picking_ids=exclude_picking_ids,
                    )
                )
            seq = seq_by_company[cid]
            next_str = seq.next_by_id()
            try:
                order.with_context(
                    **{CTX_ORIGIN: origin}
                ).daily_sequence = int(next_str)
            except (TypeError, ValueError) as err:
                _logger.error(
                    'Guapante: invalid sequence value %r from %s: %s',
                    next_str, seq.display_name, err,
                )
                raise
            Touched |= order
        if Touched:
            Touched.flush_recordset(['daily_sequence'])

    def action_confirm(self):
        """Al confirmar, asegura la sesión de Preparación del Día de
        CADA fecha en la que caiga alguno de los pickings internos
        resultantes — hoy o futura (Regla de la jornada, David
        2026-10-29; antes solo se auto-creaba si la fecha era "hoy").

        Plan de carga automática, paso e2 (2026-10-29): además de
        asegurar la sesión, la agrega a ella (alta incremental si ya
        estaba cargada, autopoblación completa si recién se creó).
        PreparationDay._guapante_add_confirmed_order() hace TODO esto
        (resolver/crear la sesión y agregar la orden) dentro de su
        propio savepoint — incluida la resolución de la sesión, nunca
        suelta acá, porque ninguna parte de esto puede tumbar la
        confirmación de la venta, ni siquiera si crear la sesión
        fallara.
        """
        res = super().action_confirm()
        Session = self.env['guapante.preparation.day']
        for order in self:
            Pickings = order.picking_ids.filtered(
                lambda p: (
                    p.picking_type_code == 'internal'
                    and p.scheduled_date
                    and p.state not in ('done', 'cancel')
                )
            )
            session_dates = {
                _utc_datetime_to_session_date(self.env, p.scheduled_date)
                for p in Pickings
            }
            for date_val in session_dates:
                Session._guapante_add_confirmed_order(date_val, order)
        return res

    def _action_cancel(self):
        """Lote 3 (David, 2026-11-09): al cancelar el pedido (método,
        botón o wizard nativo sale.order.cancel — los tres terminan
        acá), sus líneas pendientes desaparecen de Preparación y del
        Picking sin tener que pulsar «Cargar». Ventas e Inventario
        quedan en «Cancelado», como siempre. Nunca puede tumbar la
        cancelación: el trabajo va en su propio savepoint (ver
        PreparationDay._guapante_remove_cancelled_order_lines)."""
        res = super()._action_cancel()
        try:
            with self.env.cr.savepoint():
                self.env['guapante.preparation.day'].sudo(
                )._guapante_remove_cancelled_order_lines(self)
        except _PG_CONCURRENCY_ERRORS:
            raise
        except Exception:
            _logger.exception(
                'Guapante: no se pudieron retirar de Preparación las '
                'líneas de los pedidos cancelados %s.',
                ', '.join(self.mapped('name')),
            )
        return res
