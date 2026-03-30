# -*- coding: utf-8 -*-
# =============================================================================
# INVESTIGACIÓN DE CAMPOS — Odoo 19 Enterprise + l10n_co_dian
#
# El modelo account.edi.document es donde Odoo registra el estado de cada
# documento electrónico enviado a la DIAN. Campos relevantes (verificados
# en staging 2026-03-21):
#
#   state           Selection  → Estado del documento EDI
#                                Valores típicos: 'to_send', 'sent', 'cancelled'
#   error           HTML       → Mensaje de error de la DIAN (si rechaza)
#   move_id         Many2one   → Referencia a account.move (la factura)
#   edi_format_id   Many2one   → Formato EDI (identifica que es DIAN)
#   edi_format_name Char       → Nombre del formato (ej. 'CO DIAN')
#   blocking_level  Selection  → Nivel de bloqueo (error/warning)
#   attachment_id   Many2one   → Archivo adjunto (XML firmado)
#
# Campos l10n_co_* en account.move (verificados en staging):
#   l10n_co_edi_cufe_cude_ref   Char  → CUFE/CUDE/CUDS (se llena al aceptar)
#   l10n_co_edi_type            Selection → Tipo de documento
#   l10n_co_edi_operation_type  Selection → Tipo de operación
#   l10n_co_edi_transaction     Char  → ID de transacción
#   l10n_co_dian_update_commercial_event_enabled  Boolean
#
# Estrategia del hook:
#   Heredamos account.edi.document y sobreescribimos write().
#   Cuando state cambia a 'sent' en un documento EDI de formato DIAN
#   (edi_format_name que contenga 'co' o 'dian'), llamamos
#   _insotech_process_dian_acceptance() en el move_id.
#   Cuando error se llena (y state no es 'sent'), llamamos
#   _insotech_process_dian_rejection().
# =============================================================================

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountEdiDocument(models.Model):
    """Hook into EDI document state changes to auto-process DIAN responses.

    When l10n_co_dian sends the electronic invoice to the DIAN and receives
    the ApplicationResponse, it updates the account.edi.document record's
    state and error fields. This override detects those changes and triggers
    the corresponding PRE-INV → legal name mutation (acceptance) or error
    logging (rejection) on the linked account.move.
    """

    _inherit = 'account.edi.document'

    def write(self, vals):
        """Override write to detect DIAN state changes.

        Called by l10n_co_dian when it processes the DIAN's
        ApplicationResponse. We check if:
        1. The state changes to 'sent' → DIAN accepted → mutate name
        2. An error is written → DIAN rejected → log and keep PRE-INV
        """
        # Collect moves that need processing BEFORE the write
        # (so we can compare old vs new state)
        moves_to_accept = self.env['account.move']
        moves_to_reject = self.env['account.move']
        error_message = vals.get('error', '')

        if 'state' in vals or 'error' in vals:
            for doc in self:
                # Only process DIAN EDI documents
                if not self._insotech_is_dian_format(doc):
                    continue

                move = doc.move_id
                if not move or move.insotech_dian_status != 'pending':
                    continue

                new_state = vals.get('state', doc.state)
                new_error = vals.get('error', doc.error)

                if new_state == 'sent' and doc.state != 'sent':
                    # DIAN accepted the invoice
                    moves_to_accept |= move
                elif new_error and not doc.error and new_state != 'sent':
                    # DIAN rejected (error appeared for the first time)
                    moves_to_reject |= move

        # Perform the actual write first
        result = super().write(vals)

        # Now process the detected changes
        for move in moves_to_accept:
            try:
                _logger.info(
                    "Insotech: DIAN acceptance detected via EDI document "
                    "for move %s (name: %s). Triggering name mutation.",
                    move.id, move.name
                )
                move._insotech_process_dian_acceptance()
            except Exception as e:
                _logger.error(
                    "Insotech: Error auto-processing DIAN acceptance "
                    "for move %s: %s",
                    move.id, str(e)
                )
                # Don't raise — the DIAN acceptance was successful,
                # we just failed to mutate the name. Admin can use
                # "Forzar Aceptación DIAN" manually.

        for move in moves_to_reject:
            try:
                # Sanitize HTML from DIAN error using 2-layer strategy
                # (lxml → regex fallback → html.escape last resort)
                from ..services.dian_error_translator import (
                    sanitize_dian_error,
                )
                clean_error = sanitize_dian_error(error_message)

                _logger.warning(
                    "Insotech: DIAN rejection detected via EDI document "
                    "for move %s (name: %s). Error: %s",
                    move.id, move.name, clean_error
                )
                move._insotech_process_dian_rejection(
                    error_message=clean_error
                )
            except Exception as e:
                _logger.error(
                    "Insotech: Error auto-processing DIAN rejection "
                    "for move %s: %s",
                    move.id, str(e)
                )

        return result

    @staticmethod
    def _insotech_is_dian_format(edi_doc):
        """Check if the EDI document uses a Colombian DIAN format.

        Checks the edi_format_name for known patterns that indicate
        the document is a Colombian electronic invoice.

        :param edi_doc: account.edi.document record
        :returns: True if the EDI format is DIAN-related
        """
        format_name = (edi_doc.edi_format_name or '').lower()
        # Common format names in l10n_co_dian:
        # - "Colombian Electronic Invoicing"
        # - "UBL 2.1 (Colombia)"
        # - "CO DIAN"
        # - "Facturación Electrónica Colombia"
        return any(keyword in format_name for keyword in [
            'colombia', 'dian', 'ubl 2.1', 'co ',
        ])


