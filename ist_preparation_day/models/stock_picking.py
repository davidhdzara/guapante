# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

from .preparation_day import _utc_datetime_to_session_date


class StockPicking(models.Model):
    """Numeración diaria de cajas ("Caja #") sobre stock.picking.

    Separado de theme_guapante/models/stock_picking.py (que sigue dueño de
    Recolectar/logística de entrega: vehicle_id, driver_id, is_recolectar_operation,
    button_validate) — ver nota de dominio en models/sale_order.py de este módulo.
    """
    _inherit = 'stock.picking'

    daily_sequence = fields.Integer(
        string='Caja #',
        related='sale_id.daily_sequence',
        store=True,
        readonly=True,
    )

    def write(self, vals):
        """Al reprogramar scheduled_date de un picking interno
        pendiente: bloquea si la orden ya tiene algo pesado SOLO
        cuando el día calendario realmente cambia (hay dato real que
        se perdería), y si no, asegura la sesión de la fecha nueva
        (hoy o futura — Regla de la jornada, David 2026-10-29) y
        reubica la línea existente de forma incremental.

        Condición 1 (Tech Lead, 2026-10-29): NO basta con que
        'scheduled_date' esté en vals — Odoo y otros módulos escriben
        ese campo por muchas rutas (reservas, ajustes de hora) sin que
        cambie el día, y un picking con algo pesado puede seguir en
        uso normal de bodega el mismo día. El bloqueo y la reubicación
        solo aplican si el día calendario (hora Bogotá) del valor
        nuevo es distinto del que tenía antes.

        Corrección (b), Tech Lead 2026-10-31: además bloquea si la
        sesión del día NUEVO (destino) ya está 'done' — NUNCA por la
        del día viejo (origen). Si el origen está done y la orden ya
        tiene algo pesado, el bloqueo de líneas pesadas de abajo ya lo
        cubre; si el origen está done pero la orden entró después del
        cierre (sin líneas, solo una nota de e2), moverla a un día
        abierto es justo lo que necesita operación — bloquearla la
        dejaría atrapada en una jornada cerrada.

        El bloqueo corre ANTES de super().write() (así la escritura
        de bodega ni se intenta si hay que pararla); la reubicación
        corre DESPUÉS, y nunca puede tumbar la escritura ya guardada
        — ver _guapante_relocate_picking.
        """
        scheduled_changing = 'scheduled_date' in vals
        DayChanging = self.browse()
        old_dates = {}
        if scheduled_changing:
            new_dt = fields.Datetime.to_datetime(vals['scheduled_date'])
            PreWriteRelevant = self.filtered(
                lambda p: (
                    p.picking_type_code == 'internal'
                    and p.sale_id
                    and p.scheduled_date
                    and p.state not in ('done', 'cancel')
                )
            )
            new_dates_by_picking = {}
            for picking in PreWriteRelevant:
                if not new_dt:
                    continue
                old_date = _utc_datetime_to_session_date(
                    self.env, picking.scheduled_date,
                )
                new_date = _utc_datetime_to_session_date(self.env, new_dt)
                if old_date != new_date:
                    DayChanging |= picking
                    new_dates_by_picking[picking.id] = new_date

            if DayChanging:
                Session = self.env['guapante.preparation.day']
                blocked_descriptions = []
                for picking in DayChanging:
                    dest_date = new_dates_by_picking[picking.id]
                    DestSession = Session.sudo().search([
                        ('date', '=', dest_date),
                    ], limit=1)
                    if DestSession.state == 'done':
                        blocked_descriptions.append(
                            f'{picking.sale_id.name} ({dest_date})',
                        )
                if blocked_descriptions:
                    listed = ', '.join(sorted(set(blocked_descriptions)))
                    raise UserError(
                        f'No se puede reprogramar {listed}: la jornada '
                        'de ese día ya está cerrada (Terminada).'
                    )
                Session._guapante_check_no_weighed_lines(DayChanging)
            old_dates = {p.id: p.scheduled_date for p in DayChanging}

        res = super().write(vals)

        if old_dates:
            Session = self.env['guapante.preparation.day']
            batch_ids = list(old_dates.keys())
            # exclude_picking_ids debe ser solo los hermanos TODAVÍA NO
            # procesados en esta vuelta del loop, no el batch completo
            # (bug encontrado en test: con el batch completo fijo, cada
            # picking excluye también a los hermanos que YA recibieron
            # su daily_sequence nuevo en una vuelta anterior de este
            # mismo loop, así que el "máximo existente" se recalculaba
            # en 0 cada vez y los 3 terminaban con la misma caja #1).
            remaining = list(batch_ids)
            for picking in self.browse(batch_ids):
                remaining.remove(picking.id)
                Session._guapante_relocate_picking(
                    picking, old_dates[picking.id],
                    exclude_picking_ids=remaining,
                )
        return res

    def action_reset_daily_sequence(self) -> dict:
        """Resetea la numeración de cajas para los pickings seleccionados.

        Pone daily_sequence = 0 en las sale.order vinculadas,
        reinicia la ir.sequence del día correspondiente y limpia
        las líneas de preparación del día asociadas.

        Revisado contra la numeración append-only de sale_order.py
        (_guapante_max_daily_sequence_on_date/_assign_daily_sequences,
        actualizado 2026-11-03 tras eliminar
        _guapante_renumber_session): no hay conflicto, es una
        excepción DELIBERADA. El MAX trata los números de órdenes
        canceladas como ocupados para siempre (nunca se reutilizan)
        consultando directamente daily_sequence > 0 — un pedido
        reseteado acá queda en 0 y por lo tanto deja de contar como
        ocupado, liberando ese número para que la próxima orden
        nueva/reubicada/reparada lo tome vía MAX+1. Es lo esperado:
        esta acción es un reinicio administrativo total del día
        (reinicia también el ir.sequence a 1), no el camino normal.
        """
        Orders = self.mapped('sale_id').filtered(
            lambda o: o.daily_sequence > 0
        )
        if not Orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Reset de Cajas',
                    'message': (
                        'No se encontraron órdenes con número '
                        'de caja asignado en los pickings seleccionados.'
                    ),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        count = len(Orders)
        Orders.write({'daily_sequence': 0})

        # Resetear ir.sequence por cada (company, date) involucrada.
        dates_by_company = {}
        for picking in self.filtered(lambda p: p.sale_id in Orders):
            cid = picking.company_id.id or False
            sdate = (picking.scheduled_date or fields.Datetime.now()).date()
            dates_by_company.setdefault(cid, set()).add(sdate)

        Sequence = self.env['ir.sequence'].sudo()
        for cid, dates in dates_by_company.items():
            for d in dates:
                code = 'guapante.daily.%s.%s' % (
                    cid, d.strftime('%Y%m%d'),
                )
                seq = Sequence.search([('code', '=', code)], limit=1)
                if seq:
                    seq.write({'number_next': 1})

        # daily_sequence de la línea ya es related+store sobre la
        # orden (R5, 2026-10-29) — al resetear Orders arriba, las
        # líneas se sincronizan solas, no hace falta tocarlas.

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reset de Cajas',
                'message': (
                    f'{count} órdenes reseteadas. '
                    'Ejecuta "Actualizar pedidos" en Preparación '
                    'del Día para reasignar desde #1.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
