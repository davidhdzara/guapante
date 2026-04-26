from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    insotech_retention_line_ids = fields.One2many(
        'insotech.payment.retention.line',
        'payment_register_id',
        string='Retenciones o Ajustes (InSoTech)'
    )
    insotech_total_retentions = fields.Monetary(
        string='Total Ajustes',
        compute='_compute_insotech_total_retentions'
    )

    @api.depends('insotech_retention_line_ids.amount')
    def _compute_insotech_total_retentions(self):
        for wizard in self:
            wizard.insotech_total_retentions = sum(wizard.insotech_retention_line_ids.mapped('amount'))

    def action_create_payments(self):
        # Capturamos las retenciones antes de que el wizard se consuma
        retention_data = []
        for line in self.insotech_retention_line_ids:
            if line.amount != 0.0:
                retention_data.append({
                    'concept_id': line.retention_concept_id.id,
                    'account_id': line.retention_concept_id.account_id.id,
                    'name': line.retention_concept_id.name,
                    'amount': line.amount,
                })
        
        # Forzamos a que Odoo deje la factura "abierta" nativamente, porque nosotros la cuadraremos
        if retention_data:
            self.write({'payment_difference_handling': 'open'})
            
        # Ejecutamos la creación del pago estándar
        res = super(AccountPaymentRegister, self).action_create_payments()
        
        # Post-procesamos las retenciones si hay
        if retention_data and self.line_ids:
            self._create_insotech_retention_adjustments(retention_data)
            
        return res

    def _create_insotech_retention_adjustments(self, retention_data):
        move_model = self.env['account.move']
        
        for wizard in self:
            # Identificamos el partner y la cuenta por cobrar/pagar de las líneas de la factura
            lines = wizard.line_ids
            if not lines:
                continue
                
            partner_id = lines[0].partner_id.id
            account_receivable_payable = lines[0].account_id
            
            # Construimos las líneas del asiento de ajuste
            move_lines = []
            total_adjustment = 0.0
            
            for ret in retention_data:
                amount = ret['amount']
                total_adjustment += amount
                
                # Línea de la cuenta de retención (ej. 135515)
                # Si es un cobro a cliente (inbound), retención positiva significa que no nos pagó esa plata
                # por ende, Débito a la 1355 y Crédito a Cartera.
                is_inbound = wizard.payment_type == 'inbound'
                
                if is_inbound:
                    debit = amount if amount > 0 else 0.0
                    credit = -amount if amount < 0 else 0.0
                else:
                    debit = -amount if amount < 0 else 0.0
                    credit = amount if amount > 0 else 0.0
                
                move_lines.append((0, 0, {
                    'name': f"Ajuste: {ret['name']}",
                    'account_id': ret['account_id'],
                    'partner_id': partner_id,
                    'debit': debit,
                    'credit': credit,
                }))
                
            # Línea de contrapartida (Cartera / Proveedores)
            if is_inbound:
                debit_cp = -total_adjustment if total_adjustment < 0 else 0.0
                credit_cp = total_adjustment if total_adjustment > 0 else 0.0
            else:
                debit_cp = total_adjustment if total_adjustment > 0 else 0.0
                credit_cp = -total_adjustment if total_adjustment < 0 else 0.0
                
            move_lines.append((0, 0, {
                'name': 'Cruce de Retenciones InSoTech',
                'account_id': account_receivable_payable.id,
                'partner_id': partner_id,
                'debit': debit_cp,
                'credit': credit_cp,
            }))
            
            # Creamos el asiento en el mismo diario del pago
            move_vals = {
                'journal_id': wizard.journal_id.id,
                'date': wizard.payment_date,
                'ref': f"Ajuste Retenciones {wizard.communication or ''}",
                'line_ids': move_lines,
            }
            
            adjustment_move = move_model.create(move_vals)
            adjustment_move.action_post()
            
            # Conciliamos la línea de contrapartida con las líneas de la factura original
            # Esto es clave para que la factura pase a estado 'Pagado'
            cp_line = adjustment_move.line_ids.filtered(lambda l: l.account_id.id == account_receivable_payable.id)
            if cp_line:
                (lines + cp_line).reconcile()

