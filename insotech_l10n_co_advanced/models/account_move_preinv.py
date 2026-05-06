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
        1. Resets any PRE-INV names to '/' so SequenceMixin generates fresh.
        2. Lets super()._post() run normally (assigns journal sequence name).
        3. Computes a UNIQUE reserved DIAN consecutive (independent of
           SequenceMixin) using ir.config_parameter + pending invoice scan.
        4. Replaces the name with a temporary PRE-INV/YYYY/NNNNN.
        5. Marks the invoice as 'pending' DIAN validation.

        For non-Colombian-EDI invoices, the flow is completely untouched.
        """
        # FIX: Reset PRE-INV names BEFORE super()._post() so that Odoo's
        # SequenceMixin generates a fresh journal sequence instead of
        # incrementing the contaminated PRE-INV pattern.
        for move in self:
            if move.insotech_is_co_edi \
                    and move.move_type in ('out_invoice', 'out_refund') \
                    and move.name \
                    and move.name.startswith('PRE-INV'):
                _logger.info(
                    "Insotech: Resetting PRE-INV name '%s' to '/' for "
                    "move %s before _post() to prevent sequence "
                    "contamination.",
                    move.name, move.id,
                )
                move.with_context(
                    skip_account_move_synchronization=True,
                ).write({'name': '/'})

        # Call super — this assigns the journal sequence name
        posted = super()._post(soft=soft)

        for move in posted:
            try:
                if move.insotech_is_co_edi and \
                        move.move_type in ('out_invoice', 'out_refund'):

                    # ─── Compute UNIQUE reserved DIAN name ───
                    # Instead of trusting SequenceMixin (which can't see
                    # PRE-INV moves and assigns duplicates), we compute
                    # the next consecutive ourselves using ALL sources:
                    #   1. ir.config_parameter (last DIAN-accepted number)
                    #   2. Pending invoices' reserved_dian_name
                    #   3. Posted FE* invoices in the DB
                    reserved_name = self._insotech_next_dian_consecutive(
                        move,
                    )

                    pre_inv_name = move._insotech_get_pre_inv_name()

                    _logger.info(
                        "Insotech: Protecting DIAN consecutive for "
                        "move %s. Reserved: %s → Temporary: %s",
                        move.id, reserved_name, pre_inv_name,
                    )

                    move.with_context(
                        skip_account_move_synchronization=True
                    ).write({
                        'name': pre_inv_name,
                        'insotech_pre_inv_name': pre_inv_name,
                        'insotech_reserved_dian_name': reserved_name,
                        'insotech_dian_status': 'pending',
                    })

                    move.message_post(
                        body=Markup(
                            '🔒 <b>Protección de consecutivo DIAN activada</b>'
                            '<br/>Nombre temporal: <b>%s</b>'
                            '<br/>Consecutivo reservado: <b>%s</b>'
                            '<br/>El número definitivo se asignará tras '
                            'la aceptación electrónica.'
                        ) % (pre_inv_name, reserved_name),
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

    def _insotech_next_dian_consecutive(self, move):
        """Compute the next unique DIAN consecutive for a move.

        Scans ALL sources to find the highest used consecutive number
        and returns the next one. This guarantees uniqueness even when
        multiple invoices are confirmed while DIAN is down.

        Sources scanned (highest wins):
        1. ir.config_parameter 'insotech.dian.last_consecutive.{journal_id}'
        2. All pending invoices' insotech_reserved_dian_name in the journal
        3. All posted non-PRE-INV invoices in the journal

        :param move: account.move record being posted
        :returns: DIAN-compliant name (e.g. 'FE2574')
        """
        journal = move.journal_id
        prefix = (journal.code or '').strip()
        min_range = getattr(
            journal, 'l10n_co_edi_min_range_number', 0
        ) or 0
        max_range = getattr(
            journal, 'l10n_co_edi_max_range_number', 0
        ) or 0

        highest = 0

        # Source 1: ir.config_parameter (last DIAN-accepted consecutive)
        ICP = self.env['ir.config_parameter'].sudo()
        param_key = 'insotech.dian.last_consecutive.%d' % journal.id
        last_accepted = int(ICP.get_param(param_key, '0'))
        if last_accepted > highest:
            highest = last_accepted

        # Source 2: Pending invoices with reserved_dian_name in this journal
        pending_moves = self.env['account.move'].search([
            ('journal_id', '=', journal.id),
            ('insotech_reserved_dian_name', '!=', False),
            ('insotech_dian_status', 'in', ('pending', 'rejected')),
            ('id', '!=', move.id),  # Exclude the move being posted
        ])
        for pm in pending_moves:
            m = re.search(r'(\d+)\s*$', pm.insotech_reserved_dian_name or '')
            if m:
                num = int(m.group(1))
                if num > highest:
                    highest = num

        # Source 3: Posted non-PRE-INV invoices (fallback)
        if not highest:
            posted_moves = self.env['account.move'].search([
                ('journal_id', '=', journal.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('name', 'not like', 'PRE-INV%'),
                ('name', '!=', '/'),
            ], order='name desc', limit=10)
            for pm in posted_moves:
                m = re.search(r'(\d+)\s*$', pm.name or '')
                if m:
                    num = int(m.group(1))
                    if num > highest:
                        highest = num

        next_num = highest + 1

        # Apply DIAN range offset if needed
        if min_range and next_num < min_range:
            next_num = min_range

        if max_range and next_num > max_range:
            raise UserError(_(
                "La resolución DIAN del diario '%s' se ha agotado.\n\n"
                "Siguiente número: %s%d\n"
                "Rango autorizado: %s%d – %s%d\n\n"
                "Debe solicitar una nueva resolución de facturación "
                "a la DIAN y configurarla en el diario."
            ) % (
                journal.name,
                prefix, next_num,
                prefix, min_range,
                prefix, max_range,
            ))

        dian_name = '%s%d' % (prefix, next_num)

        _logger.info(
            "Insotech: Next DIAN consecutive for journal %s: %s "
            "(highest found: %d, sources: ICP=%d, pending=%d moves, "
            "posted fallback scanned)",
            journal.name, dian_name, highest,
            last_accepted, len(pending_moves),
        )

        return dian_name

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
