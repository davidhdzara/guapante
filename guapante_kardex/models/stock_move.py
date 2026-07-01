from odoo import models

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)
        self.env['guapante.kardex.daily']._sync_moves(self)
        return res
