# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError

from .preparation_day import _picking_session_date
from .preparation_day_product_claim import STOP_REASONS

# Tech Lead, revisión de b63a385: una sola fuente — STOP_REASONS ya
# vive en preparation_day_product_claim.py, no se duplica acá.
_STOP_REASON_LABELS = dict(STOP_REASONS)

PDS_STOPPED_ALERT_PARAM = 'ist_preparation_day_picking.pds_stopped_alert_minutes'
PDS_STOPPED_ALERT_DEFAULT = 30
PDS_STOPPED_ALERT_MIN = 1
PDS_STOPPED_ALERT_MAX = 1440


def _iso_utc(value):
    """Datetime naive (UTC, como los guarda Odoo) → ISO con Z, o False."""
    return value.strftime('%Y-%m-%dT%H:%M:%SZ') if value else False


class PreparationDay(models.Model):
    _inherit = 'guapante.preparation.day'

    @api.model
    def get_pds_operacion_board_data(self):
        """Datos de solo lectura para la Pantalla A (PDS Operación) —
        Tech Lead, plan aprobado 2026-11-06, 3 ajustes.

        Ajuste (3): el chequeo de grupo («Reportes y PDS», Tema A,
        2026-11-08) vive AQUÍ, no solo en el menú
        (defensa en profundidad para RPC directo) — mismo patrón que
        action_reopen() en este mismo módulo. Ningún sudo(): el acceso
        base a guapante.preparation.day/line/product.claim y a
        hr.employee ya es de base.group_user (ver
        ist_preparation_day/security/ir.model.access.csv) — el
        operario de Picking SÍ puede leer estos modelos, así que lo
        que bloquea la pantalla para él es ESTE check de grupo, no un
        permiso de modelo. No hace falta sudo para nada de lo que
        sigue.

        Ajuste (2): la sesión que se muestra es la misma que resuelve
        el tablet (_picking_session_date, corte configurable por
        _get_picking_switch_hour, hoy 21:00) — NO _current_session_date
        (esa es la del cron de respaldo/los filtros de los Reportes,
        T13). Se resuelve de nuevo en cada llamada (no se cachea en el
        front) para que la pantalla cambie sola de jornada sin
        recargar la página — el componente la vuelve a pedir en su
        refresco de respaldo periódico.
        """
        # Tema A (2026-11-08): solo quien tenga el permiso «Reportes y
        # PDS» (grupo aparte, sin relación con group_preparation_admin):
        # un Administrador de Preparación sin ese permiso NO la ve.
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_reports_pds'
        ):
            raise AccessError(
                'Solo quien tenga el permiso «Reportes y PDS» puede ver '
                'la pantalla PDS Operación.'
            )

        target_date = _picking_session_date(self.env)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', target_date)], limit=1,
        )
        if not Session:
            return {
                'has_session': False,
                'session_date': fields.Date.to_string(target_date),
            }

        columns = {'pending': [], 'in_progress': [], 'stopped': [], 'done': []}
        # Una sola búsqueda de los intervalos 'working' abiertos de la
        # sesión (no una por tarjeta): ~100+ tarjetas por jornada.
        # sudo() acotado a esta lectura: «Reportes y PDS» no es lector del
        # modelo de intervalos (solo group_preparation_admin lo es).
        open_working = self.env['guapante.preparation.interval'].sudo().search([
            ('wizard_id', '=', Session.id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ])
        for claim in Session.product_claim_ids:
            Lines = claim._get_lines()
            if not Lines:
                continue
            card = {
                'claim_id': claim.id,
                'product_name': claim.product_tmpl_name,
                'order_count': len(Lines.mapped('sale_order_id')),
                'done_line_count': claim.total_line_count - claim.pending_line_count,
                'total_line_count': claim.total_line_count,
            }
            card.update(self._pds_card_indicators(
                claim, Lines, Session, open_working))
            if claim.status == 'in_progress':
                card['operator_name'] = claim.assigned_employee_id.name or False
            elif claim.status == 'done':
                # claim.assigned_employee_id ya quedó en False acá —
                # _maybe_release_finished_claim() (preparation_day_line.py)
                # lo limpia a propósito al completarse, dejando la
                # identidad del pesaje en cada línea (done_by_employee_id/
                # done_date), nunca en el claim. Mismo criterio que
                # get_claims_for_level1_display (done_by_employee_name):
                # quien pesó la línea MÁS RECIENTE — False si ninguna
                # línea trae ese dato (producto terminado antes de 4a).
                StampedLines = Lines.filtered(
                    lambda l: l.done_by_employee_id and l.done_date
                )
                card['operator_name'] = (
                    max(StampedLines, key=lambda l: (l.done_date, l.id))
                    .done_by_employee_id.name
                    if StampedLines else False
                )
            if claim.status == 'stopped':
                card['stop_reason_label'] = _STOP_REASON_LABELS.get(
                    claim.stop_reason, claim.stop_reason
                )
            columns[claim.status].append(card)

        return {
            'has_session': True,
            'server_now': _iso_utc(fields.Datetime.now()),
            'stopped_alert_s': self._pds_stopped_alert_seconds(),
            'session_id': Session.id,
            'session_date': fields.Date.to_string(Session.date),
            'total_lines': Session.total_lines,
            'done_lines': Session.done_lines,
            'pending_lines': Session.pending_lines,
            'global_progress_pct': Session.global_progress_pct,
            'columns': columns,
        }

    @api.model
    def action_open_pds_operacion(self):
        """Abre la Pantalla A (PDS Operación) — ir.actions.client
        target=fullscreen, mismo patrón ya usado por
        preparation_day_product_claim.py/preparation_day.py/
        preparation_picking_level2_display.js en este repo."""
        return {
            'type': 'ir.actions.client',
            'tag': 'guapante_pds_operacion',
            'target': 'fullscreen',
            'name': 'PDS Operación',
        }

    @api.model
    def _pds_stopped_alert_seconds(self):
        """Umbral (s) a partir del cual un Detenido se marca como alerta.
        Parámetro `ist_preparation_day_picking.pds_stopped_alert_minutes`
        (default 30, mín 1, máx 1440; inválido → 30)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PDS_STOPPED_ALERT_PARAM, str(PDS_STOPPED_ALERT_DEFAULT))
        try:
            minutes = int(float(raw))
        except (TypeError, ValueError):
            minutes = PDS_STOPPED_ALERT_DEFAULT
        minutes = max(PDS_STOPPED_ALERT_MIN, min(PDS_STOPPED_ALERT_MAX, minutes))
        return minutes * 60

    @api.model
    def _pds_delivery_partner(self, order):
        """Dirección de entrega de una orden (David/Tech Lead, 2026-11-10):
        `partner_shipping_id`, NO partner_id ni el padre — cada dirección es
        una entrega física distinta. Un solo lugar para cambiarlo. sudo()
        acotado: «Reportes y PDS» puede no tener acceso de lectura a Ventas."""
        return order.sudo().partner_shipping_id

    @api.model
    def _pds_card_indicators(self, claim, Lines, Session, open_working):
        """Indicadores de solo lectura de una tarjeta del PDS Operación
        (tiempo en el estado actual, kg, clientes esperando, sin stock,
        sin pesar). Nada de esto escribe ni usa sudo."""
        status = claim.status
        pending = Lines.filtered(lambda l: not l.is_done)
        done = Lines - pending
        weighed = done.filtered(lambda l: l.actual_kg > 0)
        # Racha actual del operario ASIGNADO (no acumulado): intervalo
        # 'working' abierto de ese claim y ese operario, el más reciente.
        working = open_working.filtered(
            lambda i: i.claim_id == claim
            and i.employee_id == claim.assigned_employee_id
        ).sorted('start_dt', reverse=True)[:1]
        since = False
        if status == 'stopped':
            since = claim.stopped_since
        elif status == 'in_progress':
            since = working.start_dt or claim.assigned_date
        elif status == 'pending':
            since = Session.date_start
        elif status == 'done':
            stamped = done.filtered('done_date')
            since = max(stamped.mapped('done_date')) if stamped else False
        return {
            'status_since': _iso_utc(since),
            'weighed_kg': round(sum(weighed.mapped('actual_kg')), 2),
            'expected_kg': round(sum(Lines.mapped('estimated_kg')), 2),
            'waiting_customers': len({
                self._pds_delivery_partner(l.sale_order_id).id
                for l in pending if l.sale_order_id
            }),
            'zero_line_count': len(done.filtered(lambda l: l.actual_kg == 0)),
            'no_weigh_yet': bool(
                status == 'in_progress' and working
                and not working.lines_done and not working.first_weigh_dt),
        }
