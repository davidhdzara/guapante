# -*- coding: utf-8 -*-
"""DIAN hooks, response processing, and validation for account.move.

Handles:
- DIAN acceptance/rejection processing (name mutation)
- Pre-validation of partner data for DIAN
- UoM sanitization (DIAN FAV05/FBB05)
- License validation before DIAN send
- Duplicate consecutive protection
- l10n_co_dian method hooks (_l10n_co_dian_send_invoice_xml, etc.)
- action_send_and_print override
- User actions (retry, force accept, verify CUFE)
"""
import re
import logging

from pytz import timezone
from markupsafe import Markup
from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.fields import datetime as fields_datetime

_logger = logging.getLogger(__name__)


class AccountMoveDian(models.Model):
    """DIAN send/receive hooks for account.move."""

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # DIAN RESPONSE PROCESSING — Mutation to Legal Sequence
    # -------------------------------------------------------------------------

    def _insotech_process_dian_acceptance(self):
        """Process a DIAN acceptance: mutate PRE-INV → legal DIAN name."""
        for move in self:
            if move.insotech_dian_status not in ('pending', 'rejected'):
                _logger.warning(
                    "Insotech: Attempted to process DIAN acceptance for "
                    "move %s which is not in 'pending'/'rejected' status "
                    "(current: %s)",
                    move.id, move.insotech_dian_status
                )
                continue

            try:
                dian_name = move._insotech_compute_dian_compliant_name()
                if not dian_name:
                    dian_name = (
                        move.insotech_reserved_dian_name
                        or move.name
                    )
                    _logger.warning(
                        "Insotech: Could not compute DIAN name "
                        "for acceptance of move %s, using: %s",
                        move.id, dian_name,
                    )

                old_name = move.name

                _logger.info(
                    "Insotech: DIAN accepted move %s. "
                    "Final name: %s → %s",
                    move.id, old_name, dian_name
                )

                move.with_context(
                    skip_account_move_synchronization=True
                ).write({
                    'name': dian_name,
                    'insotech_dian_status': 'accepted',
                })

                # Increment usage counter on the company
                company = move.company_id
                company.sudo().write({
                    'insotech_usage_count':
                        company.insotech_usage_count + 1
                })

                # ── Capa 1: Persist last consecutive ──
                # IMPROVEMENT: Even without CUFE, we should persist the number
                # if we are accepting the invoice, to avoid sequence clashes.
                if move.move_type == 'out_invoice':
                    num_match = re.search(
                        r'(\d+)\s*$', dian_name
                    )
                    if num_match:
                        dian_num = int(num_match.group(1))
                        param_key = (
                            'insotech.dian.last_consecutive.%d'
                            % move.journal_id.id
                        )
                        current = int(
                            self.env[
                                'ir.config_parameter'
                            ].sudo().get_param(param_key, '0')
                        )
                        if dian_num > current:
                            self.env[
                                'ir.config_parameter'
                            ].sudo().set_param(
                                param_key, str(dian_num)
                            )
                            _logger.info(
                                "Insotech: Persisted last DIAN "
                                "consecutive for journal %d: %d "
                                "(Accepted state)",
                                move.journal_id.id, dian_num,
                            )

                # Log in chatter
                move.message_post(
                    body=Markup(
                        '✅ <b>Factura aceptada por la DIAN</b>'
                        '<br/>Nombre temporal: %s'
                        '<br/>Número definitivo: <b>%s</b>'
                    ) % (old_name, dian_name),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

            except Exception as e:
                _logger.error(
                    "Insotech: Error processing DIAN acceptance for "
                    "move %s: %s",
                    move.id, str(e)
                )
                raise UserError(_(
                    "Error al procesar la aceptación DIAN para la "
                    "factura %s: %s\n\n"
                    "Por favor contacte a soporte técnico.",
                    move.name, str(e)
                ))

    def _insotech_process_dian_rejection(self, error_message=''):
        """Process a DIAN rejection: restore PRE-INV and log error."""
        from ..services.dian_error_translator import translate_dian_error

        for move in self:
            if move.insotech_dian_status not in ('pending', 'rejected'):
                _logger.warning(
                    "Insotech: Attempted to process DIAN rejection for "
                    "move %s which is in '%s' status",
                    move.id, move.insotech_dian_status
                )
                continue

            _logger.warning(
                "Insotech: DIAN rejected move %s (name: %s). "
                "Error: %s",
                move.id, move.name, error_message
            )

            # Restore PRE-INV name
            pre_inv = move.insotech_pre_inv_name
            vals = {'insotech_dian_status': 'rejected'}
            if pre_inv and move.name != pre_inv:
                vals['name'] = pre_inv
                _logger.info(
                    "Insotech: Restoring PRE-INV name for rejected "
                    "move %s: %s → %s",
                    move.id, move.name, pre_inv,
                )
            move.with_context(
                skip_account_move_synchronization=True,
            ).write(vals)

            # ── Diagnóstico Inteligente ──
            diagnosis = translate_dian_error(error_message)
            display_name = pre_inv or move.name

            if diagnosis:
                link_html = Markup('')
                if diagnosis['category'] == 'partner' and move.partner_id:
                    link_html = Markup(
                        '<br/>🔗 <a href="/odoo/contacts/%s">'
                        'Abrir contacto para corregir</a>'
                    ) % move.partner_id.id
                elif diagnosis['category'] == 'journal' \
                        and move.journal_id:
                    link_html = Markup(
                        '<br/>🔗 Revise la configuración del '
                        'diario <b>%s</b>'
                    ) % move.journal_id.name

                body = Markup(
                    '❌ <b>Factura rechazada por la DIAN</b>'
                    '<br/>Nombre temporal conservado: '
                    '<b>%s</b><br/><br/>'
                    '📋 <b>Diagnóstico InSoTech:</b><br/>'
                    '%s<br/>'
                    '<i>%s</i>'
                    '%s<br/><br/>'
                    '<details>'
                    '<summary>🔧 Detalle técnico (DIAN)</summary>'
                    '<pre>%s</pre>'
                    '</details><br/>'
                    'Corrija el error y use '
                    '<i>"Reintentar Envío DIAN"</i>.'
                ) % (
                    display_name,
                    diagnosis['message'],
                    diagnosis['details'],
                    link_html,
                    error_message or 'Sin detalle',
                )
            else:
                body = Markup(
                    '❌ <b>Factura rechazada por la DIAN</b>'
                    '<br/>Nombre temporal conservado: '
                    '<b>%s</b>'
                    '<br/><b>Motivo:</b> %s'
                    '<br/>Corrija el error y use '
                    '<i>"Reintentar Envío DIAN"</i>.'
                ) % (
                    display_name,
                    error_message or 'Sin detalle',
                )

            move.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    # -------------------------------------------------------------------------
    # PRE-VALIDATION — Check partner data before DIAN send
    # -------------------------------------------------------------------------

    def _insotech_pre_validate_partner_for_dian(self):
        """Pre-validate partner data for DIAN electronic invoicing."""
        for move in self:
            if not move.insotech_is_co_edi:
                continue
            partner = move.partner_id
            if not partner:
                continue

            issues = []

            # 1. VAT / NIT
            if not partner.vat:
                issues.append((
                    'NIT / Cédula',
                    'Complete el número de identificación',
                ))

            # 2. Tipo de documento
            id_type = getattr(
                partner, 'l10n_latam_identification_type_id', None
            )
            if not id_type:
                issues.append((
                    'Tipo de documento',
                    'Seleccione CC, NIT, CE, etc.',
                ))

            # 3. DV para NIT (código 31)
            if id_type:
                doc_code = getattr(
                    id_type, 'l10n_co_document_code', ''
                )
                if doc_code == '31':
                    dv = getattr(
                        partner,
                        'l10n_co_verification_digit', None,
                    )
                    if not dv:
                        issues.append((
                            'Dígito de verificación',
                            'Obligatorio para NIT — '
                            'calcúlelo o ingréselo manualmente',
                        ))

            # 4. Ciudad con código DANE
            city = getattr(partner, 'city_id', None)
            if not city:
                issues.append((
                    'Ciudad',
                    'Seleccione una ciudad con código DANE',
                ))
            else:
                dane_code = getattr(city, 'l10n_co_edi_code', None)
                if not dane_code:
                    issues.append((
                        'Ciudad',
                        'La ciudad "%s" no tiene código DANE'
                        % city.name,
                    ))

            # 5. Código postal
            if not partner.zip:
                issues.append((
                    'Código postal',
                    'Ingrese un código postal válido (6 dígitos)',
                ))

            # 6. Dirección
            if not partner.street:
                issues.append((
                    'Dirección',
                    'Ingrese la dirección del contacto',
                ))

            # 7. Departamento
            if not partner.state_id:
                issues.append((
                    'Departamento',
                    'Seleccione el departamento',
                ))

            # 8. Obligaciones y Responsabilidades
            obligations = getattr(
                partner, 'l10n_co_edi_obligation_type_ids', None
            )
            if not obligations:
                issues.append((
                    'Obligaciones y Responsabilidades',
                    'Seleccione al menos una obligación (ej: R-99-PN)',
                ))

            # 9. Código UNSPSC en los productos
            for line in move.invoice_line_ids:
                if line.display_type or not line.product_id:
                    continue
                unspsc = getattr(line.product_id, 'unspsc_code_id', None)
                if not unspsc:
                    issues.append((
                        'Código UNSPSC (Líneas)',
                        'El producto "%s" no tiene configurada la '
                        'Categoría de UNSPSC' % line.product_id.name,
                    ))

            if not issues:
                continue

            raise UserError(_(
                "⚠️ La factura de \"%s\" tiene datos incompletos "
                "para facturación electrónica DIAN:\n\n%s\n\n"
                "Corrija los campos indicados antes de enviar.",
                partner.name,
                '\n'.join(
                    '• %s → %s' % (f, a) for f, a in issues
                ),
            ))

    # -------------------------------------------------------------------------
    # PRE-FLIGHT UoM SANITIZER (DIAN FAV05/FBB05)
    # -------------------------------------------------------------------------

    _DIAN_VALID_UNECE_CODES = {
        'C62', 'EA', 'KGM', 'LTR', 'MTR', 'MTK', 'MTQ',
        'GRM', 'TNE', 'HUR', 'DAY', 'MON', 'ANN', 'SET',
        'PR', 'PA', 'BX', 'CT', 'DZN', 'BE', 'BG', 'BO',
        'CI', 'PK', 'SA', 'ST', 'GL', 'FOT', 'INH', 'LBR',
        'ONZ', 'GLL', 'YRD', 'ACR', 'SMI', 'XPK', 'UN',
        'NAR', 'CCM', 'CMT', 'DMT', 'KMT', 'MMT', 'DLT',
        'MLT', 'CLT', 'HLT', 'MGM', 'DG', 'DTN', 'CGM',
        'XUN', 'NIU', 'ZZ', 'XBX', 'XPK', 'E48', 'E49', 'S7',
    }

    def _insotech_sanitize_uom_codes(self):
        """Pre-flight UoM code sanitizer for DIAN compliance."""
        for move in self:
            for line in move.invoice_line_ids:
                if line.display_type or not line.product_uom_id:
                    continue

                uom = line.product_uom_id
                unspsc = getattr(uom, 'unspsc_code_id', None)

                if not unspsc:
                    self._insotech_ensure_uom_unspsc(uom, 'EA')
                    continue

                current_code = unspsc.code or ''
                if current_code not in self._DIAN_VALID_UNECE_CODES:
                    _logger.warning(
                        "Insotech: UoM '%s' has invalid UNECE code '%s'. "
                        "Forcing to 'EA' for DIAN compliance.",
                        uom.name, current_code,
                    )
                    self._insotech_ensure_uom_unspsc(uom, 'EA')

    def _insotech_ensure_uom_unspsc(self, uom, target_code):
        """Ensure a UoM has the correct UNSPSC/UNECE code."""
        UnspscCode = self.env['product.unspsc.code']
        existing = UnspscCode.search([
            ('code', '=', target_code),
            ('applies_to', '=', 'uom'),
        ], limit=1)
        if not existing:
            existing = UnspscCode.create({
                'code': target_code,
                'name': 'each' if target_code == 'EA' else target_code,
                'applies_to': 'uom',
            })
            _logger.info(
                "Insotech: Created UNSPSC/UNECE record '%s' for UoM.",
                target_code,
            )
        if uom.unspsc_code_id != existing:
            uom.sudo().write({'unspsc_code_id': existing.id})
            _logger.info(
                "Insotech: Forced UoM '%s' → UNECE '%s' (id=%s).",
                uom.name, target_code, existing.id,
            )

    # -------------------------------------------------------------------------
    # DIAN SEND INTERCEPTION — License Validation
    # -------------------------------------------------------------------------

    def _insotech_validate_license_before_dian(self):
        """Validate the Insotech SaaS license before sending to DIAN."""
        for move in self:
            if not move.insotech_is_co_edi:
                continue
            company = move.company_id
            try:
                if not company._validate_and_report_license():
                    raise UserError(_(
                        "Su licencia Insotech no está activa o ha expirado.\n\n"
                        "El envío de la factura electrónica a la DIAN ha sido "
                        "bloqueado. Puede seguir creando y confirmando "
                        "facturas, pero no podrá transmitirlas a la DIAN "
                        "hasta renovar su licencia.\n\n"
                        "Por favor, contacte a soporte en www.insotech.it "
                        "para renovarla."
                    ))
            except UserError:
                raise
            except Exception as e:
                _logger.error(
                    "Insotech: Unexpected error validating license for "
                    "move %s: %s. Allowing operation to continue.",
                    move.id, str(e)
                )

    def _insotech_check_duplicate_consecutive(self):
        """Capa 2: Pre-send check to avoid sending duplicates."""
        for move in self:
            if not move.insotech_is_co_edi:
                continue
            if move.insotech_dian_status == 'accepted':
                continue
            if move.move_type != 'out_invoice':
                continue

            journal = move.journal_id
            param_key = (
                'insotech.dian.last_consecutive.%d'
                % journal.id
            )
            last_dian = int(
                self.env[
                    'ir.config_parameter'
                ].sudo().get_param(param_key, '0')
            )
            if not last_dian:
                continue

            dian_name = move._insotech_compute_dian_compliant_name()
            if not dian_name:
                continue

            num_match = re.search(r'(\d+)\s*$', dian_name)
            if not num_match:
                continue

            dian_num = int(num_match.group(1))
            prefix = (journal.code or '').strip()

            if dian_num <= last_dian:
                blocking_moves = self.env['account.move'].search([
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'posted'),
                    ('insotech_dian_status', '=', 'accepted'),
                    ('name', '=like', '%s%%' % prefix),
                ], limit=100)
                has_cufe = any(
                    getattr(m, 'l10n_co_edi_cufe_cude_ref', None)
                    for m in blocking_moves
                    if re.search(r'(\d+)\s*$', m.name or '')
                    and int(
                        re.search(r'(\d+)\s*$', m.name).group(1)
                    ) == dian_num
                )
                if not has_cufe:
                    _logger.info(
                        "Insotech: Capa 2 skip — consecutive %d "
                        "has no CUFE-backed invoice, allowing.",
                        dian_num,
                    )
                    continue

                next_available = last_dian + 1
                raise UserError(_(
                    "⚠️ El consecutivo %s%d ya fue enviado a la "
                    "DIAN previamente.\n\n"
                    "El último consecutivo registrado para este "
                    "diario es: %s%d\n\n"
                    "El siguiente disponible es: %s%d\n\n"
                    "Para corregir:\n"
                    "1. Vaya a la lista de facturas\n"
                    "2. Seleccione esta factura\n"
                    "3. Use 'Resecuenciar' para cambiar a %s%d",
                    prefix, dian_num,
                    prefix, last_dian,
                    prefix, next_available,
                    prefix, next_available,
                ))

    # -------------------------------------------------------------------------
    # HOOKS INTO l10n_co_dian — Intercept DIAN Send & Response
    # Odoo 18: uses _l10n_co_dian_send_invoice_xml (not _l10n_co_dian_post)
    # -------------------------------------------------------------------------

    def _l10n_co_dian_send_invoice_xml(self, xml: bytes):
        """Override l10n_co_dian's invoice XML sending method.

        Injects license validation and name swap before the native
        DIAN submission. On failure, restores the PRE-INV name.

        PROTECTION: Before sending, marks ``insotech_dian_xml_sent``
        and flushes to DB. This ensures the consecutive is permanently
        marked as "used" even if the DIAN request times out and
        Odoo's transaction rolls back partially.

        :param xml: The UBL XML bytes to send to DIAN.
        :returns: l10n_co_dian.document record.
        """
        self._insotech_validate_license_before_dian()
        self._insotech_swap_to_dian_name()

        # ── Mark XML as sent BEFORE the HTTP call ──
        # This flag persists even on timeout/rollback and prevents
        # the consecutive from being reassigned to another invoice.
        # NOTE: On retries, insotech_dian_xml_sent is already True
        # from the previous attempt. This is intentional — the flag
        # must remain True to prevent consecutive reuse. The autonomous
        # transaction only runs on the FIRST send attempt.
        for move in self:
            if move.insotech_is_co_edi and not move.insotech_dian_xml_sent:
                # Use autonomous transaction to prevent rollback on timeouts
                with self.env.registry.cursor() as cr:
                    env = self.env(cr=cr)
                    env_move = env['account.move'].browse(move.id)
                    env_move.with_context(
                        skip_account_move_synchronization=True,
                    ).write({'insotech_dian_xml_sent': True})
                
                # Update current transaction ORM cache
                move.with_context(
                    skip_account_move_synchronization=True,
                ).write({'insotech_dian_xml_sent': True})
                
                _logger.info(
                    "Insotech: Marked XML as sent for move %s "
                    "(reserved: %s) before DIAN submission.",
                    move.id, move.insotech_reserved_dian_name,
                )
        # Flush ORM cache to SQL before the HTTP call
        self.env.flush_all()

        # ── FIX #7: Selective unlink of rejected docs ──
        # The native super()._l10n_co_dian_send_invoice_xml() does:
        #   self.l10n_co_dian_document_ids.filtered(
        #       lambda doc: doc.state == 'invoice_rejected'
        #   ).unlink()
        # This deletes ALL rejected docs, including those with a valid
        # CUFE/identifier that might be needed for Regla 90 recovery.
        # We replace super() entirely to do a SELECTIVE unlink that
        # preserves docs with identifiers.
        self.ensure_one()
        rejected_docs = self.l10n_co_dian_document_ids.filtered(
            lambda doc: doc.state == 'invoice_rejected'
        )
        # Only unlink docs WITHOUT a CUFE — keep those that have one
        docs_to_delete = rejected_docs.filtered(lambda d: not d.identifier)
        docs_kept = rejected_docs - docs_to_delete
        if docs_kept:
            _logger.info(
                "Insotech: Keeping %d rejected docs with CUFE for "
                "move %s (Regla 90 recovery insurance).",
                len(docs_kept), self.id,
            )
        docs_to_delete.unlink()

        # Send to DIAN (replicates native logic)
        try:
            document = self.env['l10n_co_dian.document']._send_to_dian(
                xml=xml, move=self,
            )
        except Exception:
            self._insotech_swap_to_pre_inv_name()
            raise

        if document.state == 'invoice_accepted':
            self.with_context(no_new_invoice=True).message_post(
                body=_(
                    "The %s was accepted by the DIAN.",
                    dict(self._fields['move_type'].selection)[self.move_type],
                ) if not self.company_id.l10n_co_dian_demo_mode else _(
                    "The %s was validated locally in Demo Mode.",
                    dict(self._fields['move_type'].selection)[self.move_type],
                ),
                attachment_ids=document.attachment_id.copy().ids,
            )
        elif document.state != 'invoice_accepted':
            # FIX BUG #5: If DIAN returns a non-accepted state
            # (e.g. invoice_sending_failed from timeout, or
            # invoice_rejected), restore the PRE-INV name so the
            # invoice doesn't display the legal DIAN name without
            # actual DIAN acceptance.
            # Note: for invoice_rejected, _process_state_changes()
            # will ALSO restore the name, but we do it here too as
            # a safety net (belt + suspenders).
            _logger.info(
                "Insotech: DIAN returned non-accepted state '%s' "
                "for move %s. Restoring PRE-INV name.",
                document.state, self.id,
            )
            self._insotech_swap_to_pre_inv_name()
        return document

    # -------------------------------------------------------------------------
    # MAIN INTERCEPTION — action_send_and_print (Odoo 18/19)
    # -------------------------------------------------------------------------

    def action_send_and_print(self, **kwargs):
        """Pre-validate before opening the Send & Print wizard.

        The name swap MUST happen here because the UBL XML generator
        uses ``move.name`` to build the invoice number in the XML.
        The XML is generated BEFORE ``_l10n_co_dian_send_invoice_xml()``
        is called, so the name must already be the DIAN name (e.g.
        ``FE5221``) at this point.

        If the swap happened only inside ``_l10n_co_dian_send_invoice_xml``,
        the XML would contain ``PRE-INV/2026/05331`` which DIAN rejects
        with error FAD05a (invalid format).
        """
        self._insotech_validate_license_before_dian()
        self._insotech_check_duplicate_consecutive()
        self._insotech_pre_validate_partner_for_dian()
        self._insotech_sanitize_uom_codes()

        # Swap name to DIAN format BEFORE the wizard generates the XML.
        # This is required because _export_invoice() reads move.name.
        self._insotech_swap_to_dian_name()
        try:
            return super().action_send_and_print(**kwargs)
        except Exception:
            self._insotech_swap_to_pre_inv_name()
            raise

    # -------------------------------------------------------------------------
    # USER ACTIONS
    # -------------------------------------------------------------------------

    def action_insotech_retry_dian(self):
        """Button action: retry sending a rejected or pending invoice to DIAN."""
        for move in self:
            if move.insotech_dian_status not in ('rejected', 'pending'):
                raise UserError(_(
                    "Solo puede reintentar el envío de facturas que "
                    "estén pendientes o hayan sido rechazadas por la DIAN."
                ))
            move._insotech_validate_license_before_dian()
            # FIX #2: Use Colombia timezone (UTC-5) instead of UTC.
            # The native _post() stores a naive Colombia datetime in
            # l10n_co_dian_post_time. Using UTC here would cause the
            # IssueDate in the XML to be wrong between 7PM-12AM COL,
            # triggering DIAN rule FAD09e.
            move.write({
                'insotech_dian_status': 'pending',
                'l10n_co_dian_post_time': fields.Datetime.to_string(
                    fields_datetime.now(tz=timezone('America/Bogota'))
                ),
            })
            move.message_post(
                body=Markup(
                    '🔄 <b>Reintento de envío a la DIAN</b>'
                    '<br/>La factura será reenviada con nombre '
                    'temporal <b>%s</b>.'
                ) % move.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            _logger.info(
                "Insotech: User requested DIAN retry for move %s (%s)",
                move.id, move.name
            )
        # FIX #12: Process all moves in the loop above, but only
        # return the send action for the first move (UI limitation).
        # Using self[:1] ensures we don't silently skip moves.
        move = self[:1]
        if hasattr(move, 'action_send_and_print'):
            return move.action_send_and_print()
        elif hasattr(move, 'action_l10n_co_dian_send'):
            return move.action_l10n_co_dian_send()
        elif hasattr(move, 'button_send_dian'):
            return move.button_send_dian()
        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move.send',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_ids': self.ids,
                    'active_model': 'account.move',
                },
            }

    def action_insotech_force_dian_accept(self):
        """Manual action: force DIAN acceptance (admin only)."""
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_(
                "Solo los administradores contables pueden forzar "
                "la aceptación DIAN manualmente."
            ))
        if self.insotech_dian_status not in ('pending', 'rejected'):
            raise UserError(_(
                "Solo se puede forzar la aceptación para facturas "
                "en estado 'Pendiente' o 'Rechazada'."
            ))
        self._insotech_process_dian_acceptance()
        _logger.warning(
            "Insotech: Admin user %s forced DIAN acceptance for "
            "move %s (%s)",
            self.env.user.login, self.id, self.name
        )

    def action_insotech_verify_cufe(self):
        """Open the DIAN portal to verify invoice CUFE."""
        self.ensure_one()
        cufe = getattr(self, 'l10n_co_edi_cufe_cude_ref', None)
        if not cufe:
            raise UserError(_(
                "Esta factura no tiene un CUFE/CUDE asignado. "
                "Solo puede verificar facturas que hayan sido "
                "enviadas y aceptadas por la DIAN."
            ))
        url = (
            'https://catalogo-vpfe.dian.gov.co/User/'
            'SearchDocument?DocumentKey=%s' % cufe
        )
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
