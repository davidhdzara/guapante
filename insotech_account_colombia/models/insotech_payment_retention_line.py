from odoo import models, fields, api

class InsotechPaymentRetentionLine(models.TransientModel):
    _name = 'insotech.payment.retention.line'
    _description = 'Línea de Retención en Asistente de Pagos'

    payment_register_id = fields.Many2one(
        'account.payment.register', 
        string='Asistente de Pago',
        ondelete='cascade'
    )
    retention_concept_id = fields.Many2one(
        'insotech.retention.concept', 
        string='Concepto a Ajustar', 
        required=True
    )
    amount = fields.Monetary(
        string='Monto', 
        required=True
    )
    currency_id = fields.Many2one(
        related='payment_register_id.currency_id', 
        depends=['payment_register_id']
    )
