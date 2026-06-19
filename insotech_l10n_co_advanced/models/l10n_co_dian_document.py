# -*- coding: utf-8 -*-
"""Extension of l10n_co_dian.document for DIAN contingency.

Adds automatic retry and recovery capabilities when DIAN's
validation service is unavailable (Contingencia Tipo 04).

Protocol per DIAN Resolución 000165/2023:
- 4 retry attempts with 20-second intervals
- If all fail → activate contingency mode
- Invoice goes to client (valid, signed, has CUFE)
- Retransmit within 48 hours when DIAN recovers

The retry is handled by a CRON (not blocking the UI),
and recovery is handled by a separate CRON.
"""

import json
import logging

from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class L10nCoDianDocument(models.Model):
    """Extend DIAN document with contingency tracking."""

    _inherit = 'l10n_co_dian.document'

    # -----------------------------------------------------------------
    # CONTINGENCY FIELDS
    # -----------------------------------------------------------------

    insotech_contingency_mode = fields.Boolean(
        string="Modo Contingencia",
        default=False,
        help="Activado si la factura se emitió en contingencia Tipo 04 "
             "(DIAN no respondió tras los reintentos).",
    )
    insotech_contingency_evidence = fields.Text(
        string="Evidencia de Reintentos",
        help="JSON con detalle de cada intento fallido: "
             "timestamps, HTTP codes, mensajes de error.",
    )
    insotech_contingency_activated_at = fields.Datetime(
        string="Contingencia Activada",
        help="Momento en que se activó el modo contingencia.",
    )
    insotech_contingency_resolved_at = fields.Datetime(
        string="Contingencia Resuelta",
        help="Momento en que se retransmitió exitosamente a DIAN.",
    )
    insotech_retry_count = fields.Integer(
        string="Intentos Realizados",
        default=0,
        help="Número de reintentos de envío realizados por el CRON.",
    )

    # -----------------------------------------------------------------
    # DIAN STATE DETECTION — Hook into create() AND write()
    #
    # The synchronous flow (SendBillSync) creates the document with
    # the final state directly via create(). The async flow
    # (SendTestSetAsync) updates the state later via write() when
    # _get_status_zip() is called. We need BOTH hooks.
    # -----------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Detect DIAN acceptance/rejection at creation time.

        The synchronous DIAN flow (``SendBillSync``) creates the
        ``l10n_co_dian.document`` with the final ``state`` directly.
        We must detect acceptance/rejection here, not only in write().
        """
        records = super().create(vals_list)
        self._process_state_changes(records)
        return records

    def write(self, vals):
        """Detect DIAN state changes on existing documents.

        Covers the async flow (``SendTestSetAsync``) where
        ``_get_status_zip()`` updates the state after creation,
        and manual state changes via the UI.
        """
        # Only process if state is actually changing
        if 'state' not in vals:
            return super().write(vals)

        # Snapshot which docs are transitioning
        new_state = vals['state']
        docs_changing = self.filtered(
            lambda d: d.state != new_state
        )

        result = super().write(vals)

        if docs_changing:
            self._process_state_changes(docs_changing)

        return result

    def _process_state_changes(self, docs):
        """Shared logic for create() and write() hooks.

        Detects acceptance, rejection, and Regla 90 scenarios,
        then triggers the appropriate Insotech flow.

        :param docs: l10n_co_dian.document recordset to process
        """
        for doc in docs:
            move = doc.move_id
            if not move:
                continue
            if not hasattr(move, 'insotech_dian_status'):
                continue
            if move.insotech_dian_status not in ('pending', 'rejected'):
                continue

            state = doc.state

            if state == 'invoice_accepted':
                try:
                    _logger.info(
                        "Insotech: DIAN acceptance detected for "
                        "move %s (%s) via l10n_co_dian.document.",
                        move.id, move.name,
                    )
                    move._insotech_process_dian_acceptance()
                except Exception as e:
                    _logger.error(
                        "Insotech: Error processing acceptance "
                        "for move %s: %s", move.id, str(e),
                        exc_info=True,
                    )
                    # FIX E-5: Post visible warning so the user
                    # knows acceptance processing failed.
                    try:
                        move.message_post(
                            body=(
                                '⚠️ <b>Error procesando aceptación DIAN</b>'
                                '<br/>La DIAN aceptó esta factura pero '
                                'hubo un error interno al procesar la '
                                'aceptación. Contacte soporte.<br/>'
                                'Error: %s'
                            ) % str(e)[:200],
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass

            elif state == 'invoice_rejected':
                try:
                    msg = self._extract_error_message(doc)

                    if self._is_regla_90(msg):
                        if self._recover_from_regla_90(move):
                            continue

                    _logger.warning(
                        "Insotech: DIAN rejection for move %s "
                        "(%s): %s", move.id, move.name, msg,
                    )
                    try:
                        from ..services.dian_error_translator import (
                            sanitize_dian_error,
                        )
                        msg = sanitize_dian_error(msg)
                    except ImportError:
                        pass
                    move._insotech_process_dian_rejection(
                        error_message=msg,
                    )
                except Exception as e:
                    _logger.error(
                        "Insotech: Error processing rejection "
                        "for move %s: %s", move.id, str(e),
                        exc_info=True,
                    )
                    # FIX E-6: Post visible warning for rejection error.
                    try:
                        move.message_post(
                            body=(
                                '⚠️ <b>Error procesando rechazo DIAN</b>'
                                '<br/>La DIAN rechazó esta factura pero '
                                'hubo un error interno al procesar el '
                                'rechazo. Contacte soporte.<br/>'
                                'Error: %s'
                            ) % str(e)[:200],
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass

    @staticmethod
    def _extract_error_message(doc) -> str:
        """Extract readable error message from a DIAN document.

        The native code stores errors in ``message_json`` (a dict)
        with key ``errors`` (list of strings) or ``status`` (string).
        Older flows may use a plain ``message`` text field.
        """
        # Try message_json first (native Odoo 18 format)
        msg_json = getattr(doc, 'message_json', None)
        if msg_json and isinstance(msg_json, dict):
            errors = msg_json.get('errors', [])
            if errors:
                return ' | '.join(str(e) for e in errors)
            status = msg_json.get('status', '')
            if status:
                return str(status)

        # Fallback to plain message field
        msg = getattr(doc, 'message', None)
        if msg:
            return str(msg)

        return ''

    @staticmethod
    def _is_regla_90(message: str) -> bool:
        """Check if a DIAN error message is Regla 90 (duplicate)."""
        if not message:
            return False
        msg_lower = message.lower()
        return (
            'regla: 90' in msg_lower
            or 'procesado anteriormente' in msg_lower
        )

    def _recover_from_regla_90(self, move) -> bool:
        """Attempt to recover from Regla 90 using a prior accepted
        OR sending_failed doc.

        When DIAN returns "Documento procesado anteriormente", it means
        a previous submission was accepted. We look for evidence in:

        1. A prior ``invoice_accepted`` doc (cleanest case).
        2. A prior ``invoice_sending_failed`` doc (timeout case):
           the XML reached the DIAN and was accepted, but Odoo
           never received the acknowledgement. The doc's attachment
           contains the signed XML (needed for QR / PDF generation).
           We PROMOTE the doc to ``invoice_accepted`` instead of
           creating a new empty one — this preserves the attachment.

        :param move: the account.move stuck in limbo
        :returns: True if recovery succeeded, False otherwise
        """
        from markupsafe import Markup

        # ── Strategy 1: prior accepted doc (cleanest) ──
        accepted_doc = self.search([
            ('move_id', '=', move.id),
            ('state', '=', 'invoice_accepted'),
        ], limit=1, order='id desc')

        if accepted_doc and accepted_doc.identifier:
            return self._finalize_regla_90_recovery(
                move, accepted_doc, source='accepted',
            )

        # ── Strategy 2: prior sending_failed doc (timeout) ──
        # The DIAN received and processed the invoice during a
        # request that timed out in Odoo. The doc's attachment
        # holds the signed XML → we promote it to preserve
        # the attachment for QR code and PDF generation.
        failed_doc = self.search([
            ('move_id', '=', move.id),
            ('state', '=', 'invoice_sending_failed'),
        ], limit=1, order='id desc')

        if failed_doc and failed_doc.identifier:
            _logger.info(
                "Insotech Regla 90: TIMEOUT RECOVERY for "
                "move %s — promoting sending_failed doc %d "
                "to accepted (CUFE: %s...).",
                move.name, failed_doc.id,
                failed_doc.identifier[:20],
            )
            # Promote the doc: change state, keep attachment
            failed_doc.write({'state': 'invoice_accepted'})
            return self._finalize_regla_90_recovery(
                move, failed_doc, source='timeout',
            )

        # ── No evidence found ──
        _logger.warning(
            "Insotech Regla 90: No prior accepted or "
            "sending_failed document found for move %s. "
            "Cannot auto-recover.",
            move.name,
        )
        return False

    def _finalize_regla_90_recovery(self, move, doc, source='accepted'):
        """Shared finalization for Regla 90 recovery.

        Writes the CUFE, cleans rejected docs, triggers the
        acceptance flow, and posts a chatter notification.

        :param move: the account.move to recover
        :param doc: the l10n_co_dian.document with the real CUFE
        :param source: 'accepted' or 'timeout' (for logging)
        :returns: True
        """
        from markupsafe import Markup

        identifier = doc.identifier

        _logger.info(
            "Insotech Regla 90: RECOVERY (%s) for move %s — "
            "CUFE %s... from doc %d.",
            source, move.name, identifier[:20], doc.id,
        )

        # Write the CUFE to the invoice
        if hasattr(move, 'l10n_co_edi_cufe_cude_ref'):
            move.with_context(
                skip_account_move_synchronization=True,
            ).write({
                'l10n_co_edi_cufe_cude_ref': identifier,
            })

        # Remove rejected duplicate documents (NOT the rescued one)
        rejected_docs = self.search([
            ('move_id', '=', move.id),
            ('state', '=', 'invoice_rejected'),
        ])
        if rejected_docs:
            _logger.info(
                "Insotech Regla 90: Cleaning %d rejected "
                "docs for move %s.",
                len(rejected_docs), move.name,
            )
            rejected_docs.unlink()

        # Trigger the standard acceptance flow
        move._insotech_process_dian_acceptance()

        # Log recovery in chatter
        try:
            if source == 'timeout':
                body = Markup(
                    '🔄 <b>Regla 90 + Timeout Recuperada</b>'
                    '<br/>La DIAN confirmó que esta factura fue '
                    'procesada durante un timeout anterior.'
                    '<br/>CUFE rescatado: <code>%s</code>'
                    '<br/>El XML firmado original se conservó '
                    'para la generación del PDF con QR.'
                ) % identifier[:30]
            else:
                body = Markup(
                    '🔄 <b>Regla 90 Recuperada</b>'
                    '<br/>La DIAN indicó que esta factura ya '
                    'fue procesada anteriormente.'
                    '<br/>Se rescató el CUFE del envío '
                    'original: <code>%s</code>'
                ) % identifier[:30]
            move.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        except Exception:
            pass

        return True

    # -----------------------------------------------------------------
    # CRON: RETRY FAILED SUBMISSIONS
    # -----------------------------------------------------------------

    @api.model
    def _cron_contingency_retry(self):
        """CRON: Retry failed DIAN submissions per DIAN protocol.

        Protocol (Resolución 000165/2023):
        1. Odoo native already made attempt #1 (resulted in
           state='invoice_sending_failed')
        2. This CRON does 1 retry per execution (runs every 5 min)
        3. Total attempts = max_retries (default 4)
        4. If all attempts fail → activates contingency mode

        One retry per CRON run avoids blocking the worker with
        sleep(). The 5-min CRON interval serves as the natural
        cadence between attempts.
        """
        failed_docs = self.search([
            ('state', '=', 'invoice_sending_failed'),
            ('insotech_contingency_mode', '=', False),
        ])

        if not failed_docs:
            return

        _logger.info(
            "Insotech Contingency: Found %d failed documents "
            "for retry.", len(failed_docs),
        )

        for doc in failed_docs:
            move = doc.move_id
            if not move:
                continue

            company = move.company_id
            max_retries = company.insotech_contingency_retries or 4

            # Odoo native already did attempt #1, so remaining =
            # max_retries - 1 (native) - retry_count (our CRONs)
            remaining = max_retries - 1 - doc.insotech_retry_count
            if remaining <= 0:
                self._activate_contingency(doc, move)
                continue

            evidence = json.loads(
                doc.insotech_contingency_evidence or '[]',
            )

            # ONE retry per CRON run (no sleep, no blocking)
            doc.insotech_retry_count += 1
            attempt_total = doc.insotech_retry_count + 1  # +1 native

            _logger.info(
                "Insotech Contingency: Retry %d/%d for %s "
                "(doc id=%d)",
                attempt_total, max_retries,
                move.name, doc.id,
            )

            xml_content = self._get_xml_for_retry(doc)
            if not xml_content:
                evidence.append({
                    'attempt': attempt_total,
                    'timestamp': fields.Datetime.now().isoformat(),
                    'error': 'Could not retrieve original XML '
                             'from attachment',
                })
                doc.insotech_contingency_evidence = json.dumps(
                    evidence,
                )
                continue

            success = False
            try:
                new_doc = self._safe_send_to_dian(xml_content, move)

                if new_doc and new_doc.state == 'invoice_accepted':
                    _logger.info(
                        "Insotech Contingency: Retry SUCCESS "
                        "for %s on attempt %d/%d",
                        move.name, attempt_total, max_retries,
                    )
                    evidence.append({
                        'attempt': attempt_total,
                        'timestamp': fields.Datetime.now().isoformat(),
                        'result': 'accepted',
                        'new_doc_id': new_doc.id,
                    })
                    success = True
                    try:
                        move.message_post(
                            body=(
                                f"✅ <b>Envío DIAN exitoso</b> en "
                                f"reintento {attempt_total}/{max_retries}"
                                f".<br/>Documento original (fallido) "
                                f"id={doc.id} superado."
                            ),
                            message_type='comment',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass
                elif new_doc:
                    evidence.append({
                        'attempt': attempt_total,
                        'timestamp': fields.Datetime.now().isoformat(),
                        'result': new_doc.state,
                        'message': str(
                            getattr(new_doc, 'message_json', '') or '',
                        ),
                    })
                else:
                    evidence.append({
                        'attempt': attempt_total,
                        'timestamp': fields.Datetime.now().isoformat(),
                        'error': '_send_to_dian not available '
                                 'on native model',
                    })
            except Exception as e:
                evidence.append({
                    'attempt': attempt_total,
                    'timestamp': fields.Datetime.now().isoformat(),
                    'error': str(e)[:500],
                })
                _logger.warning(
                    "Insotech Contingency: Retry %d failed "
                    "for %s: %s",
                    attempt_total, move.name, e,
                )

            doc.insotech_contingency_evidence = json.dumps(evidence)

            if not success:
                total_done = doc.insotech_retry_count + 1  # +1 native
                if total_done >= max_retries:
                    self._activate_contingency(doc, move)

        _logger.info("Insotech Contingency: Retry CRON complete.")

    # -----------------------------------------------------------------
    # CRON: RECOVERY (retransmit contingency invoices)
    # -----------------------------------------------------------------

    @api.model
    def _cron_contingency_recovery(self):
        """CRON: Retransmit contingency invoices when DIAN recovers.

        Runs every 30 minutes. For each unresolved contingency:
        1. Check if 48h deadline has passed → alert
        2. Try to re-send to DIAN
        3. If success → mark as resolved
        """
        contingent = self.search([
            ('insotech_contingency_mode', '=', True),
            ('insotech_contingency_resolved_at', '=', False),
        ])

        if not contingent:
            return

        _logger.info(
            "Insotech Recovery: Found %d contingency documents "
            "for retransmission.", len(contingent),
        )

        for doc in contingent:
            move = doc.move_id
            if not move:
                continue

            company = move.company_id
            deadline_hours = (
                company.insotech_contingency_deadline_hours or 48
            )
            if doc.insotech_contingency_activated_at:
                deadline = (
                    doc.insotech_contingency_activated_at
                    + timedelta(hours=deadline_hours)
                )
            else:
                deadline = None

            # Check 48h deadline
            now = fields.Datetime.now()
            if deadline and now > deadline:
                _logger.warning(
                    "Insotech Recovery: 48h deadline EXCEEDED "
                    "for %s (activated: %s, deadline: %s)",
                    move.name,
                    doc.insotech_contingency_activated_at,
                    deadline,
                )
                try:
                    move.message_post(
                        body=(
                            "🔴 <b>ALERTA CRÍTICA:</b> Han pasado "
                            f"más de {deadline_hours}h desde la "
                            "activación de contingencia Tipo 04 "
                            "y la factura AÚN no ha sido retransmitida "
                            "a la DIAN.<br/>"
                            "Acción requerida: verificar conectividad "
                            "con DIAN o contactar soporte."
                        ),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception:
                    pass
                continue

            # Try to retransmit
            xml_content = self._get_xml_for_retry(doc)
            if not xml_content:
                _logger.warning(
                    "Insotech Recovery: Could not get XML for %s",
                    move.name,
                )
                continue

            try:
                new_doc = self._safe_send_to_dian(xml_content, move)
                if new_doc and new_doc.state == 'invoice_accepted':
                    doc.insotech_contingency_resolved_at = now
                    _logger.info(
                        "Insotech Recovery: SUCCESS for %s — "
                        "contingency resolved.", move.name,
                    )
                    try:
                        move.message_post(
                            body=(
                                "✅ <b>Contingencia Tipo 04 resuelta"
                                "</b>.<br/>"
                                "La factura fue retransmitida y "
                                "aceptada por la DIAN.<br/>"
                                f"Activada: "
                                f"{doc.insotech_contingency_activated_at}"
                                f"<br/>Resuelta: {now}"
                            ),
                            message_type='comment',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass
                else:
                    _logger.info(
                        "Insotech Recovery: DIAN still unavailable "
                        "for %s (state=%s). Will retry.",
                        move.name, new_doc.state,
                    )
            except Exception as e:
                _logger.warning(
                    "Insotech Recovery: Retransmission failed "
                    "for %s: %s", move.name, e,
                )

        _logger.info("Insotech Recovery: CRON complete.")

    # -----------------------------------------------------------------
    # PRIVATE HELPERS
    # -----------------------------------------------------------------

    def _safe_send_to_dian(self, xml_content, move):
        """Safely call the native _send_to_dian method.

        The native l10n_co_dian.document model defines _send_to_dian()
        which we verified via inspect.getsource() in staging. However,
        as a defensive measure, we check the method exists before calling
        it. Returns None if the method is not available.
        """
        if not hasattr(self, '_send_to_dian'):
            _logger.error(
                "Insotech: _send_to_dian() not found on %s. "
                "The native l10n_co_dian module may have changed. "
                "Cannot retry DIAN submission for %s.",
                self._name, move.name,
            )
            return None
        return self._send_to_dian(xml_content, move)

    def _activate_contingency(self, doc, move):
        """Activate contingency mode for a failed document.

        Sets the operation_type to '04' (Contingencia DIAN),
        marks the document, and posts a chatter notification.
        """
        doc.insotech_contingency_mode = True
        doc.insotech_contingency_activated_at = fields.Datetime.now()

        # Set operation_type on the invoice if field exists
        if hasattr(move, 'l10n_co_edi_operation_type'):
            move.l10n_co_edi_operation_type = '04'

        _logger.warning(
            "Insotech Contingency: ACTIVATED for %s "
            "(document id=%d). All %d retries exhausted.",
            move.name, doc.id,
            (doc.insotech_retry_count + 1),
        )

        try:
            evidence = json.loads(
                doc.insotech_contingency_evidence or '[]',
            )
            evidence_summary = '<br/>'.join(
                f"Intento {e.get('attempt', '?')}: "
                f"{e.get('error', e.get('result', '?'))}"
                for e in evidence[-4:]
            )
            move.message_post(
                body=(
                    "⚠️ <b>CONTINGENCIA TIPO 04 ACTIVADA</b><br/>"
                    "La DIAN no respondió tras los reintentos "
                    "protocolo.<br/>"
                    "La factura es válida (tiene CUFE y firma) "
                    "pero pendiente de validación DIAN.<br/>"
                    "Un CRON intentará retransmitir cada 30 "
                    "minutos (plazo máximo: 48h).<br/><br/>"
                    f"<b>Evidencia:</b><br/>{evidence_summary}"
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        except Exception as e:
            _logger.debug(
                "Insotech: Could not post contingency "
                "notification for %s: %s", move.name, e,
            )

    @api.model
    def _get_xml_for_retry(self, doc):
        """Retrieve the original XML content from a DIAN document.

        The XML is stored in the attachment linked to the document.
        Returns the raw XML bytes, or None if not found.
        """
        if doc.attachment_id:
            try:
                import base64
                import io
                import zipfile
                from lxml import etree

                content = base64.b64decode(doc.attachment_id.datas)
                # Try to extract XML from zip first
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as zf:
                        for name in zf.namelist():
                            if name.endswith('.xml'):
                                return zf.read(name)
                except zipfile.BadZipFile:
                    pass
                # Try as raw XML
                try:
                    etree.fromstring(content)
                    return content
                except etree.XMLSyntaxError:
                    pass
            except Exception as e:
                _logger.debug(
                    "Insotech: Could not extract XML from "
                    "attachment %d: %s",
                    doc.attachment_id.id, e,
                )
        return None
