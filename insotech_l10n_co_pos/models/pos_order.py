from odoo import models, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_fields(self, ui_order):
        """
        Interceptamos la creación de la orden POS.
        Si no trae un cliente (partner_id) y la orden requiere factura (to_invoice),
        asignamos obligatoriamente el Consumidor Final (NIT 222222222222).
        """
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        
        # Si la orden viene para facturar y no tiene cliente
        if order_fields.get('to_invoice') and not order_fields.get('partner_id'):
            # Buscar Consumidor Final por NIT
            consumidor_final = self.env['res.partner'].search([
                ('vat', '=', '222222222222')
            ], limit=1)
            
            # Si no existe, lo creamos preventivamente
            if not consumidor_final:
                doc_type = self.env.ref('l10n_co.document_type_13', raise_if_not_found=False)
                consumidor_final = self.env['res.partner'].create({
                    'name': 'Consumidor Final',
                    'vat': '222222222222',
                    'l10n_latam_identification_type_id': doc_type.id if doc_type else False,
                    'is_company': False,
                })
            
            order_fields['partner_id'] = consumidor_final.id
            
        return order_fields

    def _export_for_ui(self, order):
        """
        Inyectar CUFE y QR al cargar órdenes antiguas para Reimpresión de Tirillas.
        """
        result = super(PosOrder, self)._export_for_ui(order)
        if order.account_move:
            if hasattr(order.account_move, 'l10n_co_edi_cufe_cude_ref'):
                result['dian_cufe'] = order.account_move.l10n_co_edi_cufe_cude_ref
            if hasattr(order.account_move, 'l10n_co_edi_qr'):
                result['dian_qr'] = order.account_move.l10n_co_edi_qr
        return result

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Interceptar el retorno de la orden al POS Frontend tras su validación (pago).
        Aquí forzamos el firmado DIAN e inyectamos el CUFE/QR en la respuesta de éxito.
        """
        res = super(PosOrder, self).create_from_ui(orders, draft=draft)
        
        for order_res in res:
            order_id = order_res.get('id')
            if order_id:
                order = self.browse(order_id)
                if order.account_move:
                    # Forzar el procesamiento EDI asíncrono para generar el XML y calcular el CUFE/QR
                    if hasattr(order.account_move, 'action_process_edi_web_services'):
                        try:
                            order.account_move.action_process_edi_web_services()
                        except Exception:
                            pass # No bloquear la caja si hay caída de DIAN
                            
                    if hasattr(order.account_move, 'l10n_co_edi_cufe_cude_ref'):
                        order_res['dian_cufe'] = order.account_move.l10n_co_edi_cufe_cude_ref
                    if hasattr(order.account_move, 'l10n_co_edi_qr'):
                        order_res['dian_qr'] = order.account_move.l10n_co_edi_qr
                        
        return res

