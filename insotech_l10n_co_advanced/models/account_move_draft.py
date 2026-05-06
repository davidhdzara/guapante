# -*- coding: utf-8 -*-
import logging

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMoveDraft(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        """Override to protect DIAN sequences from being bypassed via draft state."""
        for move in self:
            if not getattr(move, 'insotech_is_co_edi', False):
                continue
                
            if getattr(move, 'insotech_dian_status', False) == 'accepted' or getattr(move, 'l10n_co_edi_cufe_cude_ref', False):
                raise UserError(_(
                    "NO PERMITIDO: Esta factura ya fue aceptada por la DIAN y cuenta con CUFE. "
                    "Restablecerla a borrador destruiría la trazabilidad legal. "
                    "Si necesita anularla, debe emitir una Nota Crédito."
                ))
                
            if getattr(move, 'insotech_dian_status', False) == 'pending':
                if not self.env.user.has_group('account.group_account_manager'):
                    raise UserError(_(
                        "Solo un Administrador Contable puede restablecer a borrador "
                        "una factura que está siendo procesada por la DIAN."
                    ))
                _logger.warning("Insotech: Factura pendiente %s forzada a borrador por admin %s", move.name, self.env.user.login)
                move.insotech_pre_inv_name = False
                move.insotech_dian_status = 'not_applicable'
                if move.insotech_reserved_dian_name:
                    move.name = move.insotech_reserved_dian_name
                    move.insotech_reserved_dian_name = False
                    
            if getattr(move, 'insotech_dian_status', False) == 'rejected':
                _logger.info(
                    "Insotech: Rejected move %s (%s) reset to draft. "
                    "Clearing PRE-INV fields and resetting name to '/' "
                    "so _post() generates a fresh sequence.",
                    move.id, move.name,
                )
                move.insotech_pre_inv_name = False
                move.insotech_dian_status = 'not_applicable'
                # FIX: Reset name to '/' instead of restoring the
                # reserved_dian_name (which may be a contaminated
                # PRE-INV string). This forces SequenceMixin to
                # generate a fresh journal sequence on re-confirm,
                # preventing consecutive gaps.
                move.insotech_reserved_dian_name = False
                move.name = '/'
                    
        return super().button_draft()
