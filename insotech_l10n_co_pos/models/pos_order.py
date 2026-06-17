from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _export_for_ui(self, order):
        """
        Inyectar CUFE y QR al cargar órdenes antiguas para Reimpresión de Tirillas.
        Solo lee datos que ya existen en la factura electrónica asociada.
        """
        result = super(PosOrder, self)._export_for_ui(order)
        if order.account_move:
            if hasattr(order.account_move, 'l10n_co_edi_cufe_cude_ref'):
                result['dian_cufe'] = order.account_move.l10n_co_edi_cufe_cude_ref or ''
            if hasattr(order.account_move, 'l10n_co_edi_qr'):
                result['dian_qr'] = order.account_move.l10n_co_edi_qr or ''
        return result
