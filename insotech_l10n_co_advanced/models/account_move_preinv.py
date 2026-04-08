# -*- coding: utf-8 -*-
"""PRE-INV sequence protection and name swap for account.move.

Implements the PRE-INV → FE- sequence mutation pattern:
1. On _post(), Colombian EDI invoices get a temporary PRE-INV name.
2. Name swap helpers toggle between PRE-INV and real DIAN name.
3. DIAN acceptance mutates to the legal sequence (e.g. FE-845).
4. DIAN rejection restores the PRE-INV name.
"""
import re
import logging

from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMovePreInv(models.Model):
    """PRE-INV sequence protection for account.move."""

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # SEQUENCEMIXIN PROTECTION — Prevent PRE-INV from corrupting sequences
    # -------------------------------------------------------------------------

    def _get_last_sequence_domain(self, relaxed=False):
        """Override to exclude PRE-INV temporary names from sequence search.

        Odoo 19's SequenceMixin uses _get_last_sequence_domain() to find
        the last posted name in the journal and derive the sequence pattern.
        If PRE-INV names are included, the SequenceMixin thinks the journal
        pattern is 'PRE-INV/YYYY/NNNNN' and generates more PRE-INV names
        instead of the real journal sequence (e.g. INV/2026/XXXX).
        """
        where_string, param = super()._get_last_sequence_domain(relaxed)
        where_string += " AND name NOT LIKE 'PRE-INV%%'"
        return where_string, param

    # -------------------------------------------------------------------------
    # _post() — Assign PRE-INV name instead of consuming DIAN consecutive
    # -------------------------------------------------------------------------

    def _post(self, soft=True):
        """Override _post to protect DIAN resolution consecutives.

        For Colombian EDI invoices (out_invoice, out_refund on DIAN-enabled
        journals), this method:
        1. Checks RADIAN irrevocability (blocks NC on accepted invoices).
        2. Lets super()._post() run normally (assigns journal sequence name).
        3. Immediately replaces the name with a temporary PRE-INV/YYYY/NNNNN.
        4. Marks the invoice as 'pending' DIAN validation.

        For non-Colombian-EDI invoices, the flow is completely untouched.
        """
        # Call super first — this assigns the journal sequence name
        posted = super()._post(soft=soft)

        for move in posted:
            try:
                if move.insotech_is_co_edi and \
                        move.move_type in ('out_invoice', 'out_refund'):
                    original_name = move.name
                    pre_inv_name = move._insotech_get_pre_inv_name()

                    _logger.info(
                        "Insotech: Protecting DIAN consecutive for move %s. "
                        "Original name: %s → Temporary: %s",
                        move.id, original_name, pre_inv_name
                    )

                    move.with_context(
                        skip_account_move_synchronization=True
                    ).write({
                        'name': pre_inv_name,
                        'insotech_pre_inv_name': pre_inv_name,
                        'insotech_reserved_dian_name': original_name,
                        'insotech_dian_status': 'pending',
                    })

                    move.message_post(
                        body=Markup(
                            '🔒 <b>Protección de consecutivo DIAN activada</b>'
                            '<br/>Nombre temporal: <b>%s</b>'
                            '<br/>El número definitivo se asignará tras '
                            'la aceptación electrónica.'
                        ) % pre_inv_name,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )

            except Exception as e:
                _logger.error(
                    "Insotech: Error protecting DIAN consecutive for "
                    "move %s: %s. The move was posted with its original "
                    "name to avoid blocking operations.",
                    move.id, str(e)
                )

        return posted

    # -------------------------------------------------------------------------
    # NAME SWAP HELPERS — Swap between PRE-INV and real DIAN name
    # -------------------------------------------------------------------------

    def _insotech_compute_dian_compliant_name(self):
        """Compute a DIAN-compliant invoice name.

        DIAN expects format: ``{Prefix}{Number}``
        Examples: ``FE1``, ``FEI23``, ``FEGU5001``

        The prefix is read dynamically from ``journal.code``.
        The number is extracted from ``insotech_reserved_dian_name``.

        If the DIAN resolution range starts at a number > 1
        but Odoo's SequenceMixin starts at 1, the method
        auto-offsets the number.

        :returns: DIAN-compliant name or None if not computable
        :raises UserError: if the number exceeds max_range
        """
        self.ensure_one()
        reserved = self.insotech_reserved_dian_name
        if not reserved:
            return None

        if self.move_type == 'out_refund':
            return reserved

        match = re.search(r'(\d+)\s*$', reserved)
        if not match:
            _logger.warning(
                "Insotech: Cannot extract number from "
                "reserved name '%s' for move %s",
                reserved, self.id,
            )
            return None

        raw_number = int(match.group(1))

        journal = self.journal_id
        prefix = (journal.code or '').strip()
        if not prefix:
            _logger.warning(
                "Insotech: Journal %s has no code/prefix "
                "for move %s",
                journal.id, self.id,
            )
            return None

        # DIAN RANGE VALIDATION & OFFSET
        min_range = getattr(
            journal, 'l10n_co_edi_min_range_number', 0
        ) or 0
        max_range = getattr(
            journal, 'l10n_co_edi_max_range_number', 0
        ) or 0

        if min_range and max_range:
            if raw_number < min_range:
                dian_number = min_range + (raw_number - 1)
                _logger.info(
                    "Insotech: Offsetting number for move %s: "
                    "raw=%d, min_range=%d → dian=%d",
                    self.id, raw_number, min_range, dian_number,
                )
            else:
                dian_number = raw_number

            if dian_number > max_range:
                raise UserError(_(
                    "La resolución DIAN del diario '%s' se ha "
                    "agotado.\n\n"
                    "Número calculado: %s%d\n"
                    "Rango autorizado: %s%d – %s%d\n\n"
                    "Debe solicitar una nueva resolución de "
                    "facturación a la DIAN y configurarla en "
                    "el diario."
                ) % (
                    journal.name,
                    prefix, dian_number,
                    prefix, min_range,
                    prefix, max_range,
                ))
        else:
            dian_number = raw_number
            _logger.debug(
                "Insotech: No DIAN range configured on "
                "journal %s, using raw number %d",
                journal.id, raw_number,
            )

        return '%s%d' % (prefix, dian_number)

    def _insotech_swap_to_dian_name(self):
        """Swap to DIAN-compliant name for XML generation.

        Before l10n_co_dian generates the UBL XML, ``move.name``
        must be in DIAN format (e.g. ``FE1``) instead of PRE-INV.
        """
        for move in self:
            if move.insotech_dian_status != 'pending':
                continue
            if not move.insotech_reserved_dian_name:
                continue

            dian_name = move._insotech_compute_dian_compliant_name()
            if not dian_name:
                _logger.warning(
                    "Insotech: Could not compute DIAN name "
                    "for move %s, using reserved name as-is: %s",
                    move.id, move.insotech_reserved_dian_name,
                )
                dian_name = move.insotech_reserved_dian_name

            if move.name != dian_name:
                _logger.info(
                    "Insotech: Swapping to DIAN name for "
                    "move %s: %s → %s (for XML generation)",
                    move.id, move.name, dian_name,
                )
                move.with_context(
                    skip_account_move_synchronization=True,
                ).write({'name': dian_name})
                move.invalidate_recordset(['name'])

    def _insotech_swap_to_pre_inv_name(self):
        """Restore the PRE-INV name after a failed send attempt."""
        for move in self:
            pre_inv = move.insotech_pre_inv_name
            if pre_inv and move.name != pre_inv:
                _logger.info(
                    "Insotech: Restoring PRE-INV name for move %s: "
                    "%s → %s",
                    move.id, move.name, pre_inv,
                )
                move.with_context(
                    skip_account_move_synchronization=True,
                ).write({'name': pre_inv})
                move.invalidate_recordset(['name'])
