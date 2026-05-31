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

        Uses a PostgreSQL ``SELECT ... FOR UPDATE`` lock on
        ``ir_config_parameter`` to guarantee atomicity even under
        concurrent _post() calls.  The lock serializes all consecutive
        assignments for the same journal, making collisions impossible.

        Algorithm:
        1. Lock the ir_config_parameter row for this journal
           (or create it if missing).
        2. Read the current counter value.
        3. Scan pending invoices to detect any reserved numbers that
           are higher than the counter (catches edge cases like
           restored backups or manual edits).
        4. Write ``max(counter, highest_pending) + 1`` back to the
           locked row.
        5. Return the DIAN-compliant name.

        :param move: account.move record being posted
        :returns: DIAN-compliant name (e.g. 'FE2574')
        """
        journal = move.journal_id
        prefix = (journal.code or '').strip()
        min_range = getattr(
            journal, 'l10n_co_edi_min_range_number', 0,
        ) or 0
        max_range = getattr(
            journal, 'l10n_co_edi_max_range_number', 0,
        ) or 0

        param_key = (
            'insotech.dian.last_consecutive.%d' % journal.id
        )

        # ── Step 1: Atomic lock on ir_config_parameter ──
        # SELECT FOR UPDATE blocks any concurrent transaction from
        # reading this row until we COMMIT (or the transaction ends).
        self.env.cr.execute("""
            SELECT value
              FROM ir_config_parameter
             WHERE key = %s
               FOR UPDATE
        """, (param_key,))
        row = self.env.cr.fetchone()

        if row:
            counter = int(row[0] or '0')
        else:
            # Row doesn't exist yet — create it and lock it
            self.env['ir.config_parameter'].sudo().set_param(
                param_key, '0',
            )
            self.env.cr.execute("""
                SELECT value
                  FROM ir_config_parameter
                 WHERE key = %s
                   FOR UPDATE
            """, (param_key,))
            counter = 0

        # ── Step 2: Safety scan — pending/sent invoices ──
        # In case reserved numbers were assigned before the counter
        # was persisted (e.g. backup restore, manual edits), scan
        # pending moves to find the actual highest.
        # ALSO includes invoices where the XML was already sent to
        # DIAN (insotech_dian_xml_sent=True) — these consecutives
        # must NEVER be reused, even if the DIAN response was lost.
        highest = counter

        self.env.cr.execute("""
            SELECT insotech_reserved_dian_name
              FROM account_move
             WHERE journal_id = %s
               AND insotech_reserved_dian_name IS NOT NULL
               AND insotech_reserved_dian_name != ''
               AND (
                   insotech_dian_status IN ('pending', 'rejected')
                   OR insotech_dian_xml_sent = TRUE
               )
               AND id != %s
        """, (journal.id, move.id or 0))

        for (reserved,) in self.env.cr.fetchall():
            m = re.search(r'(\d+)\s*$', reserved or '')
            if m:
                num = int(m.group(1))
                if num > highest:
                    highest = num

        next_num = highest + 1

        # Apply DIAN range floor
        if min_range and next_num < min_range:
            next_num = min_range

        # Range exhaustion check
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

        # ── Step 3: Persist the new counter ──
        # Write the assigned number (not next_num-1) so the next call
        # sees this number as "already used".
        self.env.cr.execute("""
            UPDATE ir_config_parameter
               SET value = %s
             WHERE key = %s
        """, (str(next_num), param_key))

        dian_name = '%s%d' % (prefix, next_num)

        _logger.info(
            "Insotech: [ATOMIC] Next DIAN consecutive for journal %s: "
            "%s (counter was %d, highest pending=%d, assigned=%d)",
            journal.name, dian_name, counter, highest, next_num,
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

    # -------------------------------------------------------------------------
    # CANCELLATION — Release Consecutive
    # -------------------------------------------------------------------------

    def button_cancel(self):
        """Override cancellation to release DIAN consecutives safely.

        If a pending/rejected DIAN invoice is cancelled, we clear its
        reserved name ONLY if it's safe to do so (avoiding timeout duplicates).
        We also decrement the journal's config_parameter if this was the very
        last consecutive assigned, preventing 'huecos'.
        """
        for move in self:
            if move.insotech_is_co_edi and move.insotech_reserved_dian_name:
                can_release = False
                
                # 1. Seguridad: Si fue rechazada definitivamente, es seguro.
                if move.insotech_dian_status == 'rejected':
                    can_release = True
                # 2. Seguridad: Si está pendiente pero NUNCA se disparó el XML, es seguro.
                elif move.insotech_dian_status == 'pending' and not move.insotech_dian_xml_sent:
                    can_release = True
                    
                if can_release:
                    _logger.info(
                        "Insotech: Releasing DIAN consecutive '%s' for "
                        "cancelled move %s.",
                        move.insotech_reserved_dian_name, move.id,
                    )
                    
                    # Decrementar el High-Water Mark (ir.config_parameter) si era el último
                    try:
                        journal = move.journal_id
                        param_key = 'insotech.dian.last_consecutive.%d' % journal.id
                        current_param = self.env['ir.config_parameter'].sudo().get_param(param_key)
                        if current_param:
                            current_val = int(current_param)
                            m = re.search(r'(\d+)\s*$', move.insotech_reserved_dian_name)
                            if m and int(m.group(1)) == current_val:
                                self.env['ir.config_parameter'].sudo().set_param(param_key, str(current_val - 1))
                                _logger.info(
                                    "Insotech: Decremented last_consecutive for journal %s from %d to %d",
                                    journal.id, current_val, current_val - 1
                                )
                    except Exception as e:
                        _logger.error("Insotech: Failed to decrement config parameter: %s", str(e))

                    move.with_context(
                        skip_account_move_synchronization=True,
                    ).write({
                        'insotech_reserved_dian_name': False,
                        'insotech_dian_xml_sent': False,
                    })
                elif move.insotech_dian_status == 'pending' and move.insotech_dian_xml_sent:
                    raise UserError(_(
                        "⚠️ RIESGO DE DUPLICADO DIAN ⚠️\n\n"
                        "Esta factura intentó enviarse a la DIAN pero hubo un fallo de conexión "
                        "(Timeout). No se puede cancelar y liberar el consecutivo porque "
                        "la DIAN podría haberla procesado internamente.\n\n"
                        "Por favor, use el botón 'Reintentar Envío DIAN'. Si la DIAN "
                        "responde que ya existe, el sistema la marcará como Aceptada."
                    ))
                    
        return super().button_cancel()
