# -*- coding: utf-8 -*-
"""RADIAN irrevocability checks for account.move.

Blocks the creation of NC/ND on invoices that have been accepted
as título valor (eventos RADIAN 033/035).
"""
import logging

from markupsafe import Markup
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveRadian(models.Model):
    """RADIAN irrevocability mixin for account.move."""

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # RADIAN IRREVOCABILITY — Block NC/ND on accepted invoices
    # -------------------------------------------------------------------------

    def _insotech_check_radian_irrevocability(self):
        """Block NC/ND on invoices accepted as título valor (RADIAN).

        When a credit note (out_refund) references an invoice that has
        event 033 (Aceptación Expresa) or 035 (Aceptación Tácita),
        the invoice is considered irrevocable and NC/ND should be
        blocked.

        Users with the `group_radian_override` security group can
        bypass this check, but an alert is ALWAYS posted in the
        chatter.

        Legal basis: Resolución 000165/2023 (título valor)
        """
        RadianEvent = self.env.get('insotech.radian.event')
        if RadianEvent is None:
            return

        for move in self:
            if move.move_type != 'out_refund':
                continue

            # Find the original invoice this NC reverses
            original = move.reversed_entry_id
            if not original:
                continue

            # Check if the original has acceptance events (033/035)
            acceptance_count = RadianEvent.search_count([
                ('move_id', '=', original.id),
                ('event_code', 'in', ('033', '035')),
                ('state', '!=', 'error'),
            ])
            if not acceptance_count:
                continue

            # This invoice has been accepted → irrevocable
            has_override = self.env.user.has_group(
                'insotech_l10n_co_advanced.group_radian_override'
            )

            if has_override:
                # User has override permission → allow but log alert
                _logger.warning(
                    "Insotech RADIAN: User %s (override group) "
                    "creating NC on accepted invoice %s",
                    self.env.user.login, original.name,
                )
                try:
                    move.message_post(
                        body=Markup(
                            '⚠️ <b>ALERTA RADIAN:</b> Esta Nota '
                            'Crédito se emite sobre la factura '
                            '<b>%s</b> que ya fue aceptada como '
                            'título valor.<br/>'
                            'Acción realizada por: <b>%s</b> '
                            '(permiso de override RADIAN).'
                        ) % (
                            original.name,
                            self.env.user.name,
                        ),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception:
                    pass
            else:
                # No override → BLOCK
                raise UserError(_(
                    "⛔ No se puede emitir una Nota Crédito sobre "
                    "la factura %s.\n\n"
                    "Esta factura ya fue aceptada como título valor "
                    "(evento RADIAN 033/035) y es irrevocable.\n\n"
                    "Si necesita emitir esta NC, contacte al "
                    "administrador para que le asigne el permiso:\n"
                    "\"RADIAN: Permitir NC/ND sobre facturas "
                    "aceptadas\"",
                    original.name,
                ))
