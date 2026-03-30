# -*- coding: utf-8 -*-
"""Contingency mode (Type 04) handling for account.move.

Intercepts write() to detect when a user switches an invoice to
contingency mode, permanently restoring the legal DIAN consecutive.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMoveContingency(models.Model):
    """Contingency Type 04 handling for account.move."""

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # CONTINGENCY MODE (TYPE 04) INTERCEPTION
    # -------------------------------------------------------------------------

    def write(self, vals):
        """Intercept modifications to account.move.

        If the user switches the invoice to Contingency Mode (04)
        while it's pending, we MUST permanently restore the legal
        DIAN consecutive *before* Odoo prints it, so the customer
        gets a legally valid PDF immediately.
        """
        res = super().write(vals)
        if 'l10n_co_edi_operation_type' in vals:
            for move in self:
                if (move.l10n_co_edi_operation_type == '04'
                        and move.insotech_dian_status == 'pending'):
                    if move.name and move.name.startswith('PRE-INV'):
                        move._insotech_restore_reserved_name()
        return res

    def _insotech_restore_reserved_name(self):
        """Permanently restore the official legal DIAN consecutive.

        Used for Contingency mode where the invoice is considered
        officially issued to the customer even without immediate
        DIAN response. This locks the sequence so it never reverts
        to PRE-INV upon network simulated errors.
        """
        for move in self:
            dian_name = move._insotech_compute_dian_compliant_name()
            if dian_name and move.name != dian_name:
                _logger.info(
                    "Insotech: Contingency Type 04 detected for "
                    "move %s. Restoring reserved name %s "
                    "permanently and destroying PRE-INV memory.",
                    move.id, dian_name,
                )
                move.with_context(
                    skip_account_move_synchronization=True
                ).write({
                    'name': dian_name,
                    'insotech_pre_inv_name': False,
                })
