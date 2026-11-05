# -*- coding: utf-8 -*-
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError

from .preparation_day import (
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
                order.daily_sequence = int(next_str)
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
