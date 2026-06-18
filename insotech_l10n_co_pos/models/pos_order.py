import logging

from odoo import models, api

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # READ POS DATA — Inyectar CUFE/QR en la respuesta al frontend
    # ------------------------------------------------------------------

    def read_pos_data(self, data, config_id):
        """Override para inyectar CUFE/QR/nombre DIAN en la respuesta.

        Solo aplica cuando la orden fue facturada (Recibo/Factura activo).
        Si no fue facturada, la tirilla se imprime sin datos DIAN.
        """
        result = super().read_pos_data(data, config_id)

        for order_data in result.get('pos.order', []):
            order = self.browse(order_data.get('id'))
            if order.exists() and order.account_move:
                move = order.account_move
                cufe = getattr(move, 'l10n_co_edi_cufe_cude_ref', '') or ''
                qr = ''
                if cufe:
                    qr = self._insotech_get_qr_from_move(move)

                order_data['dian_cufe'] = cufe
                order_data['dian_qr'] = qr
                order_data['dian_invoice_name'] = move.name or ''

                if cufe:
                    _logger.info(
                        "Insotech POS: CUFE para orden %s: %s...",
                        order.pos_reference, cufe[:20]
                    )
                else:
                    status = getattr(move, 'insotech_dian_status', 'N/A')
                    _logger.info(
                        "Insotech POS: Orden %s facturada sin CUFE aún. "
                        "Estado DIAN: %s, Move: %s",
                        order.pos_reference, status, move.name
                    )

        return result

    # ------------------------------------------------------------------
    # EXPORT FOR UI — Reimpresión de tirillas
    # ------------------------------------------------------------------

    def _export_for_ui(self, order):
        """Inyectar CUFE y QR al recargar órdenes para reimpresión."""
        result = super()._export_for_ui(order)
        if order.account_move:
            move = order.account_move
            result['dian_cufe'] = (
                getattr(move, 'l10n_co_edi_cufe_cude_ref', '') or ''
            )
            if result.get('dian_cufe'):
                result['dian_qr'] = self._insotech_get_qr_from_move(move)
            result['dian_invoice_name'] = move.name or ''
        return result

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _insotech_get_qr_from_move(self, move):
        """Obtener URL del QR desde la factura o documento DIAN."""
        qr = getattr(move, 'l10n_co_edi_qr', '') or ''
        if qr:
            return qr

        # Verificar que el modelo Enterprise existe
        if 'l10n_co_dian.document' not in self.env:
            return ''

        try:
            DianDoc = self.env['l10n_co_dian.document']
            doc = DianDoc.sudo().search([
                ('move_id', '=', move.id),
                ('state', '=', 'invoice_accepted'),
            ], limit=1, order='id desc')

            if doc and doc.attachment_id:
                try:
                    from lxml import etree
                    from urllib.parse import quote
                    from odoo.addons.l10n_co_dian.models import xml_utils
                except ImportError:
                    _logger.info(
                        "Insotech POS: l10n_co_dian no instalado, "
                        "QR no disponible"
                    )
                    return ''
                root = etree.fromstring(doc.attachment_id.raw)
                value = xml_utils._get_qr_code_value(
                    root, move.currency_id
                )
                return (
                    f'/report/barcode/?barcode_type=QR'
                    f'&value={quote(value)}'
                    f'&width=180&height=180'
                )
        except Exception as e:
            _logger.warning(
                "Insotech POS: Error obteniendo QR para move %s: %s",
                move.id, e
            )

        return ''
