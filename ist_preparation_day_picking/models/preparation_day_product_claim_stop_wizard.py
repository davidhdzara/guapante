# -*- coding: utf-8 -*-
from odoo import fields, models

from .preparation_day_product_claim import STOP_REASONS


class PreparationDayProductClaimStopWizard(models.TransientModel):
    """Diálogo nativo (target='new') para pedir el motivo de detención —
    lista corta fija, sin texto libre, tal como pidió David."""
    _name = 'guapante.preparation.day.product.claim.stop.wizard'
    _description = 'Motivo de detención — Nivel 1 de Picking'

    claim_id = fields.Many2one(
        'guapante.preparation.day.product.claim',
        required=True,
        readonly=True,
    )
    reason = fields.Selection(STOP_REASONS, required=True)

    def action_confirm(self) -> dict:
        self.ensure_one()
        self.claim_id.action_stop(self.reason)
        return {'type': 'ir.actions.act_window_close'}
