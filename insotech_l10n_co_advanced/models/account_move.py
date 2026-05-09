# -*- coding: utf-8 -*-
"""InSoTech account.move base — Fields and computed properties.

This is the SLIM coordinator file. Business logic is split into:
- account_move_preinv.py       → PRE-INV sequence protection & name swap
- account_move_dian.py         → DIAN hooks, response processing, validation
- account_move_contingency.py  → Contingency Type 04 handling
- account_move_radian.py       → RADIAN irrevocability checks
"""
# =============================================================================
# INVESTIGACIÓN — Odoo 19 Enterprise + l10n_co_dian (2026-03-21)
#
# SequenceMixin (account/models/sequence_mixin.py):
#   - Odoo 19 NO usa ir.sequence para account.move. El name se computa
#     internamente via _compute_name() + _get_last_sequence().
#   - _get_last_sequence_domain() determina qué movimientos se consideran
#     para derivar el patrón de secuencia del diario.
#   - Nuestro override añade AND name NOT LIKE 'PRE-INV%' para evitar
#     contaminación del patrón.
#
# _post() en Odoo 19:
#   - El método se llama _post(soft=True), no action_post().
#   - Asigna el name al confirmar via SequenceMixin._compute_name().
#   - Nuestro approach: dejar que _post() asigne normalmente, guardar
#     el nombre original en insotech_reserved_dian_name, luego renombrar
#     a PRE-INV. Al aceptar DIAN, restaurar desde reserved.
#
# l10n_co_dian — Campos en account.move (verificados en staging):
#   l10n_co_edi_cufe_cude_ref        Char      CUFE/CUDE/CUDS
#   l10n_co_edi_type                 Selection Tipo de Documento
#   l10n_co_edi_operation_type       Selection Tipo de operación
#   l10n_co_edi_transaction          Char      ID de transacción (CO)
#   l10n_co_edi_attachment_url       Char      URL para Anexos
#   l10n_co_edi_is_support_document  Boolean   Documento de apoyo
#   l10n_co_edi_debit_note           Boolean   Nota de Débito
#   l10n_co_edi_payment_option_id    Many2one  Método de pago
#
# l10n_co_dian — Respuesta DIAN via account.edi.document:
#   state           Selection  Estado (to_send → sent = aceptada)
#   error           HTML       Mensaje de error DIAN (si rechaza)
#   move_id         Many2one   Factura vinculada
#   edi_format_id   Many2one   Formato EDI (DIAN)
#   edi_format_name Char       Nombre del formato
#   blocking_level  Selection  Nivel de bloqueo
#
# Hook automático: account_edi_document.py hereda account.edi.document
# y sobreescribe write() para detectar cambios de state/error.
# =============================================================================

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extend account.move to protect DIAN resolution consecutives.

    This module implements the PRE-INV → FE- sequence mutation pattern:
    1. On posting, Colombian EDI invoices get a temporary PRE-INV name.
    2. The DIAN resolution consecutive is NOT consumed.
    3. When DIAN accepts, the name mutates to the legal sequence (e.g. FE-845).
    4. When DIAN rejects, the PRE-INV name stays and the user can correct & retry.
    """

    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    insotech_dian_status = fields.Selection(
        selection=[
            ('not_applicable', 'No Aplica'),
            ('pending', 'Pendiente DIAN'),
            ('accepted', 'Aceptada por DIAN'),
            ('rejected', 'Rechazada por DIAN'),
        ],
        string="Estado DIAN (Insotech)",
        default='not_applicable',
        copy=False,
        tracking=True,
        help="Estado de validación de la factura ante la DIAN. "
             "Gestionado por el módulo Insotech."
    )

    # Extend native operation_type with contingency codes
    l10n_co_edi_operation_type = fields.Selection(
        selection_add=[
            ('03', 'Contingencia Proveedor Tecnológico'),
            ('04', 'Contingencia DIAN'),
        ],
        ondelete={
            '03': lambda recs: recs.write({'l10n_co_edi_operation_type': '10'}),
            '04': lambda recs: recs.write({'l10n_co_edi_operation_type': '10'}),
        }
    )

    insotech_pre_inv_name = fields.Char(
        string="Nombre Temporal PRE-INV",
        copy=False,
        readonly=True,
        help="Nombre temporal asignado mientras la factura está pendiente "
             "de validación por la DIAN."
    )

    insotech_reserved_dian_name = fields.Char(
        string="Nombre DIAN Reservado",
        copy=False,
        readonly=True,
        help="Nombre legal de la resolución DIAN asignado por Odoo al "
             "confirmar. Se restaura cuando la DIAN acepta la factura."
    )

    insotech_dian_xml_sent = fields.Boolean(
        string="XML Enviado a DIAN",
        default=False,
        copy=False,
        readonly=True,
        help="Se marca como True justo ANTES de enviar el XML a la DIAN. "
             "Una vez marcado, el consecutivo reservado NO puede ser "
             "reasignado a otra factura, incluso si el envío falla por "
             "timeout. Esto previene la duplicación de consecutivos "
             "cuando la DIAN acepta pero Odoo no recibe la respuesta."
    )

    insotech_is_co_edi = fields.Boolean(
        string="Es Factura EDI Colombiana",
        compute='_compute_insotech_is_co_edi',
        store=True,
        help="Indica si esta factura debe ser procesada como factura "
             "electrónica colombiana ante la DIAN."
    )

    amount_to_words = fields.Char(
        string="Monto en Letras (RADIAN)",
        compute="_compute_amount_to_words",
        help="Monto total en letras requerido por el Código de Comercio."
    )

    # -- Resolution counter fields (Feature 2) --

    insotech_resolution_used = fields.Integer(
        string="Números Usados",
        compute='_compute_insotech_resolution_info',
        help="Cantidad de números de resolución DIAN consumidos "
             "en el diario actual.",
    )
    insotech_resolution_max = fields.Integer(
        string="Números Autorizados",
        compute='_compute_insotech_resolution_info',
        help="Rango total de números autorizados por la resolución "
             "DIAN del diario.",
    )
    insotech_resolution_percent = fields.Float(
        string="% Disponible",
        compute='_compute_insotech_resolution_info',
        help="Porcentaje de números de resolución DIAN disponibles.",
    )
    insotech_resolution_color = fields.Char(
        string="Color Resolución",
        compute='_compute_insotech_resolution_info',
        help="Clase CSS de color para el indicador de resolución.",
    )
    insotech_resolution_progress_width = fields.Integer(
        string="Ancho Barra Resolución",
        compute='_compute_insotech_resolution_info',
        help="Porcentaje de consumo para la barra de progreso.",
    )

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS
    # -------------------------------------------------------------------------

    @api.depends('amount_total', 'currency_id')
    def _compute_amount_to_words(self):
        for move in self:
            text = move.currency_id.amount_to_text(move.amount_total) \
                if move.currency_id else ''
            if text:
                text = f"SON: {text.upper()}"
            move.amount_to_words = text

    def _get_dian_signature_value(self):
        """Extract ds:SignatureValue from the signed DIAN XML attachment."""
        self.ensure_one()
        attachment = getattr(self, 'l10n_co_dian_attachment_id', False)
        if not attachment:
            return ''
        try:
            import base64
            from lxml import etree
            content = base64.b64decode(attachment.datas)
            root = etree.fromstring(content)
            ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
            sig_nodes = root.findall('.//ds:SignatureValue', ns)
            if sig_nodes and sig_nodes[0].text:
                return sig_nodes[0].text.strip()
        except Exception:
            pass
        return ''

    @api.depends('move_type', 'journal_id', 'company_id')
    def _compute_insotech_is_co_edi(self):
        """Determine if a move is a Colombian EDI invoice."""
        for move in self:
            is_co_edi = False
            if move.move_type in ('out_invoice', 'out_refund'):
                company = move.company_id
                journal = move.journal_id
                if company and company.country_id and \
                        company.country_id.code == 'CO':
                    is_co_edi = self._insotech_check_journal_dian_enabled(
                        journal
                    )
            move.insotech_is_co_edi = is_co_edi

    @api.depends('journal_id', 'company_id')
    def _compute_insotech_resolution_info(self):
        """Compute DIAN resolution usage statistics."""
        for move in self:
            move.insotech_resolution_used = 0
            move.insotech_resolution_max = 0
            move.insotech_resolution_percent = 0.0
            move.insotech_resolution_color = ''
            move.insotech_resolution_progress_width = 0

            try:
                if not move.insotech_is_co_edi or not move.journal_id:
                    continue

                journal = move.journal_id
                min_range = 0
                max_range = 0
                if 'l10n_co_edi_min_range_number' in journal._fields:
                    min_range = journal.l10n_co_edi_min_range_number or 0
                if 'l10n_co_edi_max_range_number' in journal._fields:
                    max_range = journal.l10n_co_edi_max_range_number or 0

                if not max_range:
                    continue

                total_authorized = max_range - min_range + 1
                used_count = self.search_count([
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'posted'),
                    ('move_type', 'in', (
                        'out_invoice', 'out_refund',
                    )),
                    ('name', 'not like', 'PRE-INV%'),
                ])

                percent_available = 0.0
                if total_authorized > 0:
                    percent_available = (
                        (total_authorized - used_count)
                        / total_authorized
                    ) * 100.0
                    percent_available = max(
                        0.0, min(100.0, percent_available)
                    )

                if percent_available > 50:
                    color = 'success'
                elif percent_available > 20:
                    color = 'warning'
                else:
                    color = 'danger'

                move.insotech_resolution_used = used_count
                move.insotech_resolution_max = total_authorized
                move.insotech_resolution_percent = percent_available
                move.insotech_resolution_color = color
                move.insotech_resolution_progress_width = min(
                    100, int(100 - percent_available)
                )
            except Exception:
                _logger.debug(
                    "Insotech: Could not compute resolution info "
                    "for move %s, skipping.", move.id,
                    exc_info=True,
                )

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _insotech_check_journal_dian_enabled(self, journal):
        """Check if a journal is enabled for DIAN electronic invoicing."""
        if not journal:
            return False

        if hasattr(journal, 'l10n_co_dian_provider'):
            if journal.l10n_co_dian_provider:
                _logger.debug(
                    "Insotech: Journal '%s' is DIAN-enabled "
                    "(l10n_co_dian_provider = '%s')",
                    journal.name, journal.l10n_co_dian_provider
                )
                return True

        if hasattr(journal, 'l10n_co_edi_dian_authorization_number'):
            if journal.l10n_co_edi_dian_authorization_number:
                _logger.debug(
                    "Insotech: Journal '%s' has DIAN resolution '%s'",
                    journal.name,
                    journal.l10n_co_edi_dian_authorization_number
                )
                return True

        _logger.debug(
            "Insotech: Journal '%s' has NO DIAN configuration. "
            "Skipping PRE-INV protection.",
            journal.name
        )
        return False

    def _insotech_get_pre_inv_name(self):
        """Generate a temporary PRE-INV name using ir.sequence."""
        return self.env['ir.sequence'].next_by_code('insotech.pre.inv') \
            or 'PRE-INV/0000'
