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

from markupsafe import Markup
from odoo import models, _
from odoo.exceptions import UserError

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
            if move.insotech_dian_status != 'pending':
                _logger.warning(
                    "Insotech: Attempted to process DIAN acceptance for "
                    "move %s which is not in 'pending' status (current: %s)",
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
                cufe = getattr(
                    move, 'l10n_co_edi_cufe_cude_ref', None
                )
                if not cufe:
                    _logger.info(
                        "Insotech: Skipping Capa 1 persist for "
                        "move %s — no CUFE (force-accepted?)",
                        move.id,
                    )
                else:
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
                                "consecutive for journal %d: %d",
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
                    ) >= dian_num
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

    def _l10n_co_dian_send_invoice_xml(self, *args, **kwargs):
        """Override l10n_co_dian's invoice XML sending method (Odoo 18)."""
        self._insotech_validate_license_before_dian()
        self._insotech_swap_to_dian_name()
        try:
            if hasattr(super(), '_l10n_co_dian_send_invoice_xml'):
                return super()._l10n_co_dian_send_invoice_xml(
                    *args, **kwargs
                )
        except Exception:
            self._insotech_swap_to_pre_inv_name()
            raise
        return True

    def _hook_invoice_document_before_pdf(self, *args, **kwargs):
        """Override the Print & Send hook for DIAN processing."""
        self._insotech_validate_license_before_dian()
        self._insotech_swap_to_dian_name()
        try:
            if hasattr(
                super(), '_hook_invoice_document_before_pdf'
            ):
                return super()._hook_invoice_document_before_pdf(
                    *args, **kwargs
                )
        except Exception:
            self._insotech_swap_to_pre_inv_name()
            raise
        return True

    # -------------------------------------------------------------------------
    # MAIN INTERCEPTION — action_send_and_print (Odoo 18/19)
    # -------------------------------------------------------------------------

    def action_send_and_print(self, **kwargs):
        """Override the Send & Print action to swap name first."""
        self._insotech_validate_license_before_dian()
        self._insotech_check_duplicate_consecutive()
        self._insotech_pre_validate_partner_for_dian()
        self._insotech_sanitize_uom_codes()

        self._insotech_swap_to_dian_name()
        try:
            result = super().action_send_and_print(**kwargs)
        except Exception:
            self._insotech_swap_to_pre_inv_name()
            raise

        # POST-SEND: Check if DIAN accepted during this call
        for move in self:
            if move.insotech_dian_status != 'pending':
                continue
            try:
                move.invalidate_recordset(
                    ['l10n_co_edi_cufe_cude_ref']
                )
                cufe = getattr(
                    move, 'l10n_co_edi_cufe_cude_ref', None
                )
                if cufe:
                    _logger.info(
                        "Insotech: Post-send DIAN acceptance "
                        "detected for move %s (CUFE: %s...)",
                        move.id, str(cufe)[:20],
                    )
                    move._insotech_process_dian_acceptance()
            except Exception as e:
                _logger.warning(
                    "Insotech: Post-send acceptance check "
                    "failed for move %s: %s (non-blocking)",
                    move.id, str(e),
                )

        return result

    # -------------------------------------------------------------------------
    # USER ACTIONS
    # -------------------------------------------------------------------------

    def action_insotech_retry_dian(self):
        """Button action: retry sending a rejected invoice to DIAN."""
        for move in self:
            if move.insotech_dian_status != 'rejected':
                raise UserError(_(
                    "Solo puede reintentar el envío de facturas que "
                    "hayan sido rechazadas por la DIAN."
                ))
            move._insotech_validate_license_before_dian()
            move.write({'insotech_dian_status': 'pending'})
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
