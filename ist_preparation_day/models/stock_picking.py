# -*- coding: utf-8 -*-
from odoo import fields, models

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
            for picking in PreWriteRelevant:
                if not new_dt:
                    continue
                old_date = _utc_datetime_to_session_date(
                    self.env, picking.scheduled_date,
                )
                new_date = _utc_datetime_to_session_date(self.env, new_dt)
                if old_date != new_date:
                    DayChanging |= picking
            if DayChanging:
                self.env['guapante.preparation.day']._guapante_check_no_weighed_lines(
                    DayChanging,
                )
            old_dates = {p.id: p.scheduled_date for p in DayChanging}

        res = super().write(vals)

        if old_dates:
            Session = self.env['guapante.preparation.day']
            for picking in self.browse(list(old_dates.keys())):
                Session._guapante_relocate_picking(
                    picking, old_dates[picking.id],
                )
        return res

    def action_reset_daily_sequence(self) -> dict:
        """Resetea la numeración de cajas para los pickings seleccionados.

        Pone daily_sequence = 0 en las sale.order vinculadas,
        reinicia la ir.sequence del día correspondiente y limpia
        las líneas de preparación del día asociadas.

        Revisado contra el algoritmo de renumeración de e3
        (PreparationDay._guapante_renumber_session, 2026-10-30): no
        hay conflicto, es una excepción DELIBERADA. e3 trata los
        números de órdenes canceladas como ocupados para siempre
        (nunca se reutilizan) consultando directamente
        daily_sequence > 0 — un pedido reseteado acá queda en 0 y por
        lo tanto deja de contar como ocupado, liberando ese número
        para que una flexible lo tome en la próxima renumeración. Es
        lo esperado: esta acción es un reinicio administrativo total
        del día (reinicia también el ir.sequence a 1), no el camino
        normal — se mantiene tal cual, sin cambios por e3.
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
                    'Ejecuta "Ver pedidos" en Preparación '
                    'del Día para reasignar desde #1.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
