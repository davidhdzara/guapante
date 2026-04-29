from odoo import _, api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    insotech_retention_line_ids = fields.One2many(
        'insotech.payment.retention.line',
        'payment_register_id',
        string='Retenciones o Ajustes (InSoTech)',
    )
    insotech_total_retentions = fields.Monetary(
        string='Total Ajustes',
        compute='_compute_insotech_total_retentions',
    )

    @api.depends('insotech_retention_line_ids.amount')
    def _compute_insotech_total_retentions(self) -> None:
        for wizard in self:
            wizard.insotech_total_retentions = sum(
                wizard.insotech_retention_line_ids.mapped('amount')
            )

    # ── Obs 3.1: Resta dinámica del monto al banco ──
    @api.onchange(
        'insotech_retention_line_ids',
        'insotech_retention_line_ids.amount',
    )
    def _onchange_insotech_retentions_update_amount(self) -> None:
        """Cuando el usuario agrega o modifica retenciones,
        el monto a pagar en banco se reduce automáticamente.
        """
        if not self.insotech_retention_line_ids:
            return
        total_retentions = sum(
            self.insotech_retention_line_ids.mapped('amount')
        )
        if total_retentions > 0 and self.source_amount_currency:
            self.amount = (
                self.source_amount_currency - total_retentions
            )

    def action_create_payments(self) -> dict:
        """Captura las retenciones antes de que el wizard
        TransientModel se consuma, luego ejecuta el pago
        estándar y post-procesa los ajustes contables.
        """
        # Capturar datos antes de que el wizard muera
        retention_data = []
        # Bug C: Leer la cuenta correcta según la dirección
        payment_direction = (
            'sale' if self.payment_type == 'inbound' else 'purchase'
        )
        for line in self.insotech_retention_line_ids:
            if line.amount != 0.0:
                concept = line.retention_concept_id
                account = concept.get_account_for_direction(
                    payment_direction,
                )
                retention_data.append({
                    'concept_id': concept.id,
                    'account_id': account.id,
                    'name': concept.name,
                    'amount': line.amount,
                })

        # Forzar factura abierta si hay retenciones
        if retention_data:
            self.write({'payment_difference_handling': 'open'})

        # Pago estándar de Odoo
        res = super().action_create_payments()

        # Post-proceso de retenciones
        if retention_data and self.line_ids:
            self._create_insotech_retention_adjustments(
                retention_data,
            )

        return res

    def _create_insotech_retention_adjustments(
        self, retention_data: list,
    ) -> None:
        """Crea un asiento contable de ajuste que cruza las
        retenciones con la cuenta por cobrar/pagar de la
        factura original, y lo concilia automáticamente.
        """
        move_model = self.env['account.move']

        for wizard in self:
            lines = wizard.line_ids
            if not lines:
                continue

            partner_id = lines[0].partner_id.id
            account_receivable_payable = lines[0].account_id

            move_lines = []
            total_adjustment = 0.0
            is_inbound = wizard.payment_type == 'inbound'

            for ret in retention_data:
                amount = ret['amount']
                total_adjustment += amount

                if is_inbound:
                    debit = amount if amount > 0 else 0.0
                    credit = -amount if amount < 0 else 0.0
                else:
                    debit = -amount if amount < 0 else 0.0
                    credit = amount if amount > 0 else 0.0

                move_lines.append((0, 0, {
                    'name': _("Ajuste: %s") % ret['name'],
                    'account_id': ret['account_id'],
                    'partner_id': partner_id,
                    'debit': debit,
                    'credit': credit,
                }))

            # Línea de contrapartida
            if is_inbound:
                debit_cp = (
                    -total_adjustment if total_adjustment < 0
                    else 0.0
                )
                credit_cp = (
                    total_adjustment if total_adjustment > 0
                    else 0.0
                )
            else:
                debit_cp = (
                    total_adjustment if total_adjustment > 0
                    else 0.0
                )
                credit_cp = (
                    -total_adjustment if total_adjustment < 0
                    else 0.0
                )

            move_lines.append((0, 0, {
                'name': _('Cruce de Retenciones InSoTech'),
                'account_id': account_receivable_payable.id,
                'partner_id': partner_id,
                'debit': debit_cp,
                'credit': credit_cp,
            }))

            adjustment_move = move_model.create({
                'journal_id': wizard.journal_id.id,
                'date': wizard.payment_date,
                'ref': _(
                    "Ajuste Retenciones %s",
                ) % (wizard.communication or ''),
                'line_ids': move_lines,
            })
            adjustment_move.action_post()

            # Conciliar con la factura original
            cp_line = adjustment_move.line_ids.filtered(
                lambda l: (
                    l.account_id.id
                    == account_receivable_payable.id
                ),
            )
            if cp_line:
                (lines + cp_line).reconcile()


