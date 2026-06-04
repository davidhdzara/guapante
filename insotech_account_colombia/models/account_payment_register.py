import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


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
    @api.depends(
        'insotech_total_retentions',
        'can_edit_wizard',
        'source_amount',
        'source_amount_currency',
        'source_currency_id',
        'company_id',
        'currency_id',
        'payment_date',
        'installments_mode',
        'journal_id',
        'group_payment'
    )
    def _compute_amount(self) -> None:
        """En Odoo 18, amount es un campo computado. Debemos inyectar
        la deducción de nuestras retenciones después del cálculo nativo.
        """
        super()._compute_amount()
        for wizard in self:
            is_custom = getattr(wizard, 'custom_user_amount', False)
            if wizard.insotech_total_retentions > 0 and not is_custom:
                wizard.amount = wizard.amount - wizard.insotech_total_retentions

    def action_create_payments(self) -> dict:
        """Captura las retenciones antes de que el wizard
        TransientModel se consuma, luego ejecuta el pago
        estándar y post-procesa los ajustes contables.

        Fix mayo-2026: Se capturan line_ids como IDs antes
        del super() para sobrevivir al consumo del wizard.
        Se invalida caché y se filtran líneas reconciliadas
        para garantizar la conciliación del ajuste.
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

        # ── Fix: Capturar TODOS los datos del wizard ANTES del super ──
        # El TransientModel puede vaciarse o perder relaciones
        # tras super().action_create_payments().
        captured_line_ids = self.line_ids.ids if self.line_ids else []
        captured_journal_id = self.journal_id.id
        captured_payment_date = self.payment_date
        captured_communication = self.communication or ''
        captured_payment_type = self.payment_type

        # Forzar factura abierta si hay retenciones
        if retention_data:
            self.write({'payment_difference_handling': 'open'})

        # Pago estándar de Odoo
        res = super().action_create_payments()

        # Post-proceso de retenciones con datos capturados
        if retention_data and captured_line_ids:
            self._create_insotech_retention_adjustments(
                retention_data,
                captured_line_ids=captured_line_ids,
                journal_id=captured_journal_id,
                payment_date=captured_payment_date,
                communication=captured_communication,
                is_inbound=captured_payment_type == 'inbound',
            )

        return res

    def _create_insotech_retention_adjustments(
        self,
        retention_data: list,
        captured_line_ids: list = None,
        journal_id: int = None,
        payment_date=None,
        communication: str = '',
        is_inbound: bool = False,
    ) -> None:
        """Crea un asiento contable de ajuste que cruza las
        retenciones con la cuenta por cobrar/pagar de la
        factura original, y lo concilia automáticamente.

        Fix mayo-2026: Usa IDs capturados pre-super para
        encontrar las líneas de factura y conciliar
        correctamente, incluso en pagos agrupados.
        """
        move_model = self.env['account.move']
        aml_model = self.env['account.move.line']

        # ── Obtener líneas frescas desde IDs capturados ──
        if captured_line_ids:
            lines = aml_model.browse(captured_line_ids).exists()
        else:
            # Fallback al flujo anterior (compatibilidad)
            lines = self.line_ids if hasattr(self, 'line_ids') else aml_model

        if not lines:
            _logger.warning(
                "InSoTech Retenciones: No hay líneas para "
                "procesar ajuste. communication=%s",
                communication,
            )
            return

        # Invalidar caché para obtener estado post-pago
        lines.invalidate_recordset(
            ['amount_residual', 'reconciled', 'matched_debit_ids',
             'matched_credit_ids'],
        )

        partner_id = lines[0].partner_id.id
        account_receivable_payable = lines[0].account_id

        move_lines = []
        total_adjustment = 0.0

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
            'journal_id': journal_id,
            'date': payment_date,
            'ref': _(
                "Ajuste Retenciones %s",
            ) % communication,
            'line_ids': move_lines,
        })
        adjustment_move.action_post()

        # ── Conciliar con las facturas originales ──
        cp_line = adjustment_move.line_ids.filtered(
            lambda l: (
                l.account_id.id
                == account_receivable_payable.id
            ),
        )
        if not cp_line:
            _logger.error(
                "InSoTech Retenciones: No se encontró línea "
                "de contrapartida en el ajuste %s",
                adjustment_move.name,
            )
            return

        # Fix: filtrar líneas ya totalmente reconciliadas
        # y re-leer estado fresco desde BD
        lines.invalidate_recordset(['reconciled', 'amount_residual'])
        lines_to_reconcile = lines.filtered(
            lambda l: not l.reconciled
        )

        if not lines_to_reconcile:
            _logger.warning(
                "InSoTech Retenciones: Todas las líneas de "
                "factura ya están reconciliadas. Ajuste %s "
                "queda sin conciliar.",
                adjustment_move.name,
            )
            return

        try:
            (lines_to_reconcile + cp_line).reconcile()
            _logger.info(
                "InSoTech Retenciones: Ajuste %s conciliado "
                "exitosamente con %d líneas de factura.",
                adjustment_move.name,
                len(lines_to_reconcile),
            )
        except Exception:
            _logger.exception(
                "InSoTech Retenciones: Error al conciliar "
                "ajuste %s. Intentando conciliación "
                "individual...",
                adjustment_move.name,
            )
            # Fallback: intentar conciliar la CP del ajuste
            # directamente con cada línea de factura
            # que tenga residual pendiente
            self._reconcile_adjustment_fallback(
                cp_line, lines_to_reconcile,
                adjustment_move.name,
            )

    def _reconcile_adjustment_fallback(
        self,
        cp_line,
        invoice_lines,
        adj_name: str,
    ) -> None:
        """Conciliación de respaldo: intenta conciliar
        la línea de contrapartida del ajuste con cada
        línea de factura individualmente.

        Esto funciona cuando .reconcile() en bloque falla
        por líneas con estados incompatibles.
        """
        for inv_line in invoice_lines:
            if inv_line.reconciled:
                continue
            try:
                (inv_line + cp_line).reconcile()
                _logger.info(
                    "InSoTech Retenciones: Fallback OK para "
                    "ajuste %s con línea %s (AML %d)",
                    adj_name,
                    inv_line.move_id.name,
                    inv_line.id,
                )
                # Si cp_line ya se reconcilió, parar
                cp_line.invalidate_recordset(['reconciled'])
                if cp_line.reconciled:
                    break
            except Exception:
                _logger.exception(
                    "InSoTech Retenciones: Fallback falló "
                    "para ajuste %s con AML %d",
                    adj_name,
                    inv_line.id,
                )
