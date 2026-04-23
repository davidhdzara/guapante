from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    insotech_retention_calculated = fields.Boolean(
        string='Retenciones Calculadas',
        default=False,
        copy=False,
    )

    def action_calculate_retentions(self) -> None:
        """Botón principal: Calcula y aplica retenciones DIAN
        en facturas de proveedor según UVT, obligaciones
        del proveedor y conceptos configurados.
        """
        self.ensure_one()

        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(
                _("Esta acción solo aplica a facturas de proveedor.")
            )
        if self.state != 'draft':
            raise UserError(
                _("Solo puede calcular retenciones en facturas borrador.")
            )

        partner = self.partner_id
        if not partner:
            raise UserError(_("Seleccione un proveedor primero."))

        # ── 1. Validar obligaciones DIAN del proveedor ──
        obligations = partner.l10n_co_edi_obligation_type_ids.mapped('name')
        if 'O-15' in obligations:
            return self._insotech_notify(
                _("Proveedor '%s' es Autorretenedor (O-15). "
                  "No se practican retenciones.") % partner.name,
                sticky=True,
            )
        if 'O-47' in obligations:
            return self._insotech_notify(
                _("Proveedor '%s' pertenece al Régimen Simple (O-47). "
                  "No se practican retenciones.") % partner.name,
                sticky=True,
            )

        # ── 2. Obtener UVT del año de la factura ──
        invoice_year = (self.invoice_date or fields.Date.today()).year
        uvt = self.env['insotech.uvt'].search(
            [('year', '=', invoice_year)], limit=1,
        )
        if not uvt:
            raise UserError(
                _("No hay UVT configurada para el año %s. "
                  "Vaya a Contabilidad > Configuración > Tabla UVT "
                  "y registre el valor.") % invoice_year
            )

        # ── 3. Calcular base en UVT ──
        base_amount = self.amount_untaxed
        if not base_amount:
            return self._insotech_notify(
                _("La factura no tiene monto base para calcular."),
            )
        base_en_uvt = base_amount / uvt.value

        # ── 4. Obtener conceptos aplicables ──
        concepts = partner.insotech_retention_concept_ids.filtered(
            lambda c: c.direction in ('purchase', 'both')
            and c.purchase_tax_id
        )
        if not concepts:
            return self._insotech_notify(
                _("El proveedor '%s' no tiene conceptos de retención "
                  "de compra configurados. Configúrelos en la ficha "
                  "del contacto, pestaña Contabilidad.") % partner.name,
                sticky=True,
            )

        # ── 5. Aplicar retenciones ──
        applied = []
        existing_tax_ids = set()
        product_lines = self.invoice_line_ids.filtered(
            lambda ln: ln.display_type not in (
                'line_section', 'line_note',
            )
        )
        for line in product_lines:
            existing_tax_ids.update(line.tax_ids.ids)

        taxes_to_add = self.env['account.tax']
        for concept in concepts:
            if concept.purchase_tax_id.id in existing_tax_ids:
                continue
            if base_en_uvt < concept.base_uvt:
                continue
            taxes_to_add |= concept.purchase_tax_id
            applied.append(
                f"• {concept.name}: {concept.percentage}%"
                f" ({concept.purchase_tax_id.name})"
            )

        if taxes_to_add:
            for line in product_lines:
                line.write({
                    'tax_ids': [
                        fields.Command.link(tax.id)
                        for tax in taxes_to_add
                    ],
                })

        if applied:
            self.insotech_retention_calculated = True
            body = _(
                "<b>Retenciones DIAN aplicadas (%s):</b><br/>%s"
            ) % (len(applied), "<br/>".join(applied))
            self.message_post(body=body)
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'current',
            }
        return self._insotech_notify(
            _("No se aplicaron retenciones. La base (%.1f UVT) "
              "no supera los mínimos de los conceptos configurados, "
              "o los impuestos ya estaban aplicados.") % base_en_uvt,
        )

    def _insotech_notify(
        self,
        message: str,
        notify_type: str = 'warning',
        sticky: bool = False,
    ) -> dict:
        """Retorna una notificación visual al usuario."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Motor de Retenciones DIAN"),
                'message': message,
                'type': notify_type,
                'sticky': sticky,
            },
        }

