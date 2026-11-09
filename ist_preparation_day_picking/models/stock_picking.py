# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _guapante_can_reset_boxes(self) -> bool:
        """Lote 4: el Administrador de Preparación (Mauricio) también
        puede reiniciar cajas — con motivo y en el historial."""
        return (
            super()._guapante_can_reset_boxes()
            or self.env.user.has_group(
                'ist_preparation_day_picking.group_preparation_admin')
        )
