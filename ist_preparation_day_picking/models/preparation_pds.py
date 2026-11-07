# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import AccessError

from .preparation_day import _picking_session_date
from .preparation_day_product_claim import STOP_REASONS

# Tech Lead, revisión de b63a385: una sola fuente — STOP_REASONS ya
# vive en preparation_day_product_claim.py, no se duplica acá.
_STOP_REASON_LABELS = dict(STOP_REASONS)


class PreparationDay(models.Model):
    _inherit = 'guapante.preparation.day'

    def get_pds_operacion_board_data(self):
        """Datos de solo lectura para la Pantalla A (PDS Operación) —
        Tech Lead, plan aprobado 2026-11-06, 3 ajustes.

        Ajuste (3): el chequeo de grupo vive AQUÍ, no solo en el menú
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
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_admin'
        ):
            raise AccessError(
                'Solo un administrador de Preparación puede ver la '
                'pantalla PDS Operación.'
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
            'session_id': Session.id,
            'session_date': fields.Date.to_string(Session.date),
            'total_lines': Session.total_lines,
            'done_lines': Session.done_lines,
            'pending_lines': Session.pending_lines,
            'global_progress_pct': Session.global_progress_pct,
            'columns': columns,
        }

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
