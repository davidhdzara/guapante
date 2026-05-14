# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class GuapanteMcpTools(models.AbstractModel):
    """Stateless collection of all MCP tool implementations.

    Called via self.env['guapante.mcp.tools'].tool_<name>(**kwargs).
    All methods return plain Python dicts (JSON-serializable).
    Access enforcement (scope, partner isolation) is the caller's responsibility.
    """

    _name = 'guapante.mcp.tools'
    _description = 'Guapante MCP Tool Implementations'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @api.model
    def _invoice_to_dict(self, invoice):
        lines = []
        for line in invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        ):
            lines.append({
                'product': line.product_id.name or line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'subtotal': line.price_subtotal,
                'taxes': [t.name for t in line.tax_ids],
            })

        dian_status = getattr(invoice, 'insotech_dian_status', 'not_applicable')
        dian_name = getattr(invoice, 'insotech_reserved_dian_name', '') or invoice.name
        cufe = getattr(invoice, 'l10n_co_edi_cufe_cude_ref', '') or ''
        portal_url = ''
        if hasattr(invoice, 'get_portal_url'):
            try:
                portal_url = invoice.get_portal_url()
            except Exception:
                pass

        return {
            'id': invoice.id,
            'name': invoice.name,
            'dian_name': dian_name,
            'cufe': cufe,
            'dian_status': dian_status,
            'partner': invoice.partner_id.name,
            'partner_vat': invoice.partner_id.vat or '',
            'date': str(invoice.invoice_date or ''),
            'date_due': str(invoice.invoice_date_due or ''),
            'state': invoice.state,
            'payment_state': invoice.payment_state,
            'amount_untaxed': invoice.amount_untaxed,
            'amount_tax': invoice.amount_tax,
            'amount_total': invoice.amount_total,
            'amount_residual': invoice.amount_residual,
            'currency': invoice.currency_id.name,
            'lines': lines,
            'portal_url': portal_url,
        }

    # ------------------------------------------------------------------
    # Billing tools (available to admin + user scopes)
    # ------------------------------------------------------------------

    @api.model
    def tool_list_invoices(self, partner_id=None, state=None,
                           date_from=None, date_to=None, limit=20):
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '!=', 'cancel'),
        ]
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))
        if state:
            domain.append(('payment_state', '=', state))
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))

        invoices = self.env['account.move'].sudo().search(
            domain,
            limit=min(int(limit), 50),
            order='invoice_date desc',
        )
        return {
            'total': len(invoices),
            'invoices': [
                {
                    'id': inv.id,
                    'name': inv.name,
                    'partner': inv.partner_id.name,
                    'date': str(inv.invoice_date or ''),
                    'date_due': str(inv.invoice_date_due or ''),
                    'amount_total': inv.amount_total,
                    'amount_residual': inv.amount_residual,
                    'payment_state': inv.payment_state,
                    'dian_status': getattr(inv, 'insotech_dian_status', 'not_applicable'),
                }
                for inv in invoices
            ],
        }

    @api.model
    def tool_get_invoice(self, invoice_id, partner_id=None):
        invoice = self.env['account.move'].sudo().browse(int(invoice_id))
        if not invoice.exists() or invoice.move_type not in ('out_invoice', 'out_refund'):
            return {'error': f'Factura {invoice_id} no encontrada.'}
        if partner_id and invoice.partner_id.id != int(partner_id):
            return {'error': 'No tiene acceso a esta factura.'}
        return self._invoice_to_dict(invoice)

    @api.model
    def tool_get_outstanding_balance(self, partner_id):
        partner = self.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists():
            return {'error': 'Partner no encontrado.'}
        invoices = self.env['account.move'].sudo().search([
            ('partner_id', '=', int(partner_id)),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ['paid', 'reversed']),
        ])
        overdue = invoices.filtered(
            lambda i: i.invoice_date_due and i.invoice_date_due < fields.Date.today()
        )
        return {
            'partner': partner.name,
            'total_pending': sum(invoices.mapped('amount_residual')),
            'total_overdue': sum(overdue.mapped('amount_residual')),
            'overdue_count': len(overdue),
            'pending_count': len(invoices),
        }

    @api.model
    def tool_get_payment_link(self, invoice_id, partner_id=None):
        invoice = self.env['account.move'].sudo().browse(int(invoice_id))
        if not invoice.exists():
            return {'error': 'Factura no encontrada.'}
        if partner_id and invoice.partner_id.id != int(partner_id):
            return {'error': 'No tiene acceso a esta factura.'}
        portal_url = ''
        if hasattr(invoice, 'get_portal_url'):
            try:
                portal_url = invoice.get_portal_url()
            except Exception:
                pass
        return {
            'invoice_id': invoice.id,
            'invoice_name': invoice.name,
            'amount_due': invoice.amount_residual,
            'portal_url': portal_url,
        }

    # ------------------------------------------------------------------
    # Billing tools (admin scope only)
    # ------------------------------------------------------------------

    @api.model
    def tool_get_partner_statement(self, partner_id, date_from=None, date_to=None):
        domain = [
            ('partner_id', '=', int(partner_id)),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ]
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))
        invoices = self.env['account.move'].sudo().search(domain, order='invoice_date asc')
        rows = []
        running_balance = 0.0
        for inv in invoices:
            sign = 1.0 if inv.move_type == 'out_invoice' else -1.0
            amount = inv.amount_total * sign
            running_balance += amount
            rows.append({
                'date': str(inv.invoice_date or ''),
                'name': inv.name,
                'type': inv.move_type,
                'amount': amount,
                'paid': (inv.amount_total - inv.amount_residual) * sign,
                'balance': running_balance,
            })
        return {
            'partner_id': int(partner_id),
            'rows': rows,
            'final_balance': running_balance,
        }

    @api.model
    def tool_get_retention_summary(self, partner_id, date_from=None, date_to=None):
        domain = [
            ('partner_id', '=', int(partner_id)),
            ('move_type', 'in', ['in_invoice', 'out_invoice']),
            ('state', '=', 'posted'),
        ]
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))
        invoices = self.env['account.move'].sudo().search(domain)
        totals = {'retefuente': 0.0, 'reteica': 0.0, 'reteiva': 0.0, 'parafiscal': 0.0}
        for inv in invoices:
            for line in inv.line_ids.filtered(lambda l: l.tax_line_id):
                concept = self.env['insotech.retention.concept'].sudo().search(
                    [('tax_id', '=', line.tax_line_id.id)], limit=1
                )
                if not concept:
                    concept = self.env['insotech.retention.concept'].sudo().search(
                        [('purchase_tax_id', '=', line.tax_line_id.id)], limit=1
                    )
                if concept and concept.type in totals:
                    totals[concept.type] += abs(line.balance)
        return {'partner_id': int(partner_id), 'retentions': totals}

    @api.model
    def tool_send_invoice_email(self, invoice_id):
        invoice = self.env['account.move'].sudo().browse(int(invoice_id))
        if not invoice.exists():
            return {'error': f'Factura {invoice_id} no encontrada.'}
        if invoice.state != 'posted':
            return {'error': 'Solo se pueden enviar facturas publicadas (estado: posted).'}
        try:
            invoice.action_send_and_print()
            return {'success': True, 'message': f'Factura {invoice.name} enviada por email.'}
        except Exception as e:
            _logger.error("MCP tool_send_invoice_email: %s", e)
            return {'error': str(e)}

    @api.model
    def tool_get_dian_status(self, invoice_id):
        invoice = self.env['account.move'].sudo().browse(int(invoice_id))
        if not invoice.exists():
            return {'error': 'Factura no encontrada.'}
        dian_doc = self.env['l10n_co_dian.document'].sudo().search(
            [('move_id', '=', int(invoice_id))],
            order='id desc',
            limit=1,
        )
        return {
            'invoice_name': invoice.name,
            'dian_status': getattr(invoice, 'insotech_dian_status', 'not_applicable'),
            'reserved_name': getattr(invoice, 'insotech_reserved_dian_name', '') or '',
            'cufe': getattr(invoice, 'l10n_co_edi_cufe_cude_ref', '') or '',
            'dian_document_state': dian_doc.state if dian_doc else 'none',
            'dian_message': str(dian_doc.message or '') if dian_doc else '',
        }

    @api.model
    def tool_add_invoice_note(self, invoice_id, note):
        invoice = self.env['account.move'].sudo().browse(int(invoice_id))
        if not invoice.exists():
            return {'error': 'Factura no encontrada.'}
        invoice.message_post(body=note, message_type='comment')
        return {'success': True, 'invoice': invoice.name}

    # ------------------------------------------------------------------
    # Order tools
    # ------------------------------------------------------------------

    @api.model
    def tool_list_orders(self, partner_id=None, state=None,
                         date_from=None, date_to=None, limit=20):
        domain = []
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))
        if state:
            domain.append(('state', '=', state))
        if date_from:
            domain.append(('date_order', '>=', date_from))
        if date_to:
            domain.append(('date_order', '<=', date_to))
        orders = self.env['sale.order'].sudo().search(
            domain,
            limit=min(int(limit), 50),
            order='date_order desc',
        )
        return {
            'total': len(orders),
            'orders': [
                {
                    'id': o.id,
                    'name': o.name,
                    'partner': o.partner_id.name,
                    'date': str(o.date_order or ''),
                    'state': o.state,
                    'amount_total': o.amount_total,
                    'invoice_status': o.invoice_status,
                }
                for o in orders
            ],
        }

    @api.model
    def tool_get_order(self, order_id, partner_id=None):
        order = self.env['sale.order'].sudo().browse(int(order_id))
        if not order.exists():
            return {'error': f'Pedido {order_id} no encontrado.'}
        if partner_id and order.partner_id.id != int(partner_id):
            return {'error': 'No tiene acceso a este pedido.'}
        lines = [
            {
                'product': line.product_id.name or line.name,
                'quantity': line.product_uom_qty,
                'qty_delivered': line.qty_delivered,
                'price_unit': line.price_unit,
                'subtotal': line.price_subtotal,
            }
            for line in order.order_line
        ]
        invoices = [
            {'id': inv.id, 'name': inv.name, 'payment_state': inv.payment_state}
            for inv in order.invoice_ids.filtered(lambda i: i.state != 'cancel')
        ]
        return {
            'id': order.id,
            'name': order.name,
            'partner': order.partner_id.name,
            'date': str(order.date_order or ''),
            'state': order.state,
            'amount_untaxed': order.amount_untaxed,
            'amount_tax': order.amount_tax,
            'amount_total': order.amount_total,
            'invoice_status': order.invoice_status,
            'lines': lines,
            'invoices': invoices,
        }
