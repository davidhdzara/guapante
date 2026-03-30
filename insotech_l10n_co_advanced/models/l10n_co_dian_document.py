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
