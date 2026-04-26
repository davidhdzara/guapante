from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    insotech_retention_calculated = fields.Boolean(
        string='Retenciones Calculadas',
        default=False,
        copy=False,
    )

    # ──────────────────────────────────────────────────
    #  Auto-cálculo: al cambiar proveedor o líneas
    # ──────────────────────────────────────────────────

    @api.onchange('partner_id')
    def _onchange_partner_apply_retentions(self) -> None:
        """Al seleccionar proveedor en factura de compra,
        inyecta automáticamente los taxes de retención del
        proveedor en las líneas existentes.
        """
        if (
            self.move_type not in ('in_invoice', 'in_refund')
            or not self.partner_id
        ):
            return

        partner = self.partner_id
        obligations = partner.l10n_co_edi_obligation_type_ids.mapped('name')
        if 'O-15' in obligations or 'O-47' in obligations:
            return

        concepts = partner.insotech_retention_concept_ids.filtered(
            lambda c: c.direction in (direction, 'both')
            and (c.purchase_tax_id if direction == 'purchase' else c.tax_id)
        )
        if not concepts:
            return

        vendor_taxes = concepts.mapped('purchase_tax_id')
        for line in self.invoice_line_ids.filtered(
            lambda ln: ln.display_type not in (
                'line_section', 'line_note',
            )
        ):
            existing_ids = set(line.tax_ids.ids)
            new_taxes = vendor_taxes.filtered(
                lambda t: t.id not in existing_ids
            )
            if new_taxes:
                line.tax_ids |= new_taxes

    # ──────────────────────────────────────────────────
    #  Botón manual (respaldo / recalcular)
    # ──────────────────────────────────────────────────

    def action_calculate_retentions(self) -> None:
        """Botón principal: Calcula y aplica retenciones DIAN
        en facturas de proveedor según UVT, obligaciones
        del proveedor y conceptos configurados.
        """
        self.ensure_one()

        if self.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
            raise UserError(
                _("Esta acción solo aplica a facturas de proveedor y cliente.")
            )
        
        direction = 'purchase' if self.move_type in ('in_invoice', 'in_refund') else 'sale'
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
            # Si es compra y el proveedor es O-15, no le retenemos.
            # Si es venta y el cliente es O-15, igual nosotros le podemos facturar la retención si NO somos O-15,
            # pero en Colombia, si el cliente es O-15 (Gran Contribuyente/Autorretenedor), él nos va a retener.
            # En ventas, la inyección es una "Anticipación" de lo que el cliente nos retendrá.
            pass  # En ventas, el cliente O-15 SI nos retiene, así que procedemos normal. En compras, no le retenemos.
            if direction == 'purchase':
                return self._insotech_notify(
                    _("Proveedor '%s' es Autorretenedor (O-15). "
                      "No se practican retenciones.") % partner.name,
                    sticky=True,
                )
        if 'O-47' in obligations:
            if direction == 'purchase':
                return self._insotech_notify(
                    _("Proveedor '%s' pertenece al Régimen Simple (O-47). "
                      "No se practican retenciones.") % partner.name,
                    sticky=True,
                )
            else:
                return self._insotech_notify(
                    _("Cliente '%s' pertenece al Régimen Simple (O-47). "
                      "No nos practica retenciones.") % partner.name,
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
            lambda c: c.direction in (direction, 'both')
            and (c.purchase_tax_id if direction == 'purchase' else c.tax_id)
        )
        if not concepts:
            return self._insotech_notify(
                _("El proveedor '%s' no tiene conceptos de retención "
                  "de compra configurados. Configúrelos en la ficha "
                  "del contacto, pestaña Contabilidad.") % partner.name,
                sticky=True,
            )

        # ── 5. Retenciones del proveedor (Nivel 1) ──
        applied = []
        product_lines = self.invoice_line_ids.filtered(
            lambda ln: ln.display_type not in (
                'line_section', 'line_note',
            )
        )

        vendor_taxes = self.env['account.tax']
        for concept in concepts:
            if base_en_uvt < concept.base_uvt:
                continue
            target_tax = concept.purchase_tax_id if direction == 'purchase' else concept.tax_id
            vendor_taxes |= target_tax
            applied.append(
                f"• {concept.name}: {concept.percentage}%"
                f" ({target_tax.name})"
            )

        # ── 6. Parafiscales del producto (Nivel 2) ──
        line_parafiscals = {}
        for line in product_lines:
            product = line.product_id
            if not product:
                continue
            template = product.product_tmpl_id
            parafiscal = template.insotech_parafiscal_concept_id
            target_pf_tax = parafiscal.purchase_tax_id if direction == 'purchase' else parafiscal.tax_id
            if (
                parafiscal
                and target_pf_tax
                and base_en_uvt >= parafiscal.base_uvt
            ):
                line_parafiscals[line.id] = parafiscal

        # ── 7. Escribir taxes sin duplicar ──
        for line in product_lines:
            existing_ids = set(line.tax_ids.ids)
            taxes_for_line = self.env['account.tax']

            for tax in vendor_taxes:
                if tax.id not in existing_ids:
                    taxes_for_line |= tax

            parafiscal = line_parafiscals.get(line.id)
            if parafiscal:
                target_pf_tax = parafiscal.purchase_tax_id if direction == 'purchase' else parafiscal.tax_id
                if target_pf_tax and target_pf_tax.id not in existing_ids:
                    taxes_for_line |= target_pf_tax
                    pf_label = (
                        f"• {parafiscal.name}: {parafiscal.percentage}%"
                        f" ({target_pf_tax.name})"
                        f" [{line.product_id.name}]"
                    )
                if pf_label not in applied:
                    applied.append(pf_label)

            if taxes_for_line:
                line.write({
                    'tax_ids': [
                        fields.Command.link(tax.id)
                        for tax in taxes_for_line
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


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_parafiscal(self) -> None:
        """Al seleccionar un producto en una línea de factura
        de compra, inyecta automáticamente el tax parafiscal
        del producto si está configurado.
        """
        if (
            not self.product_id
            or not self.move_id
            or self.move_id.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund')
        ):
            return
            
        direction = 'purchase' if self.move_id.move_type in ('in_invoice', 'in_refund') else 'sale'

        template = self.product_id.product_tmpl_id
        parafiscal = template.insotech_parafiscal_concept_id
        if parafiscal:
            target_pf_tax = parafiscal.purchase_tax_id if direction == 'purchase' else parafiscal.tax_id
            if target_pf_tax and target_pf_tax.id not in self.tax_ids.ids:
                self.tax_ids |= target_pf_tax

        # También inyectar retenciones del proveedor
        partner = self.move_id.partner_id
        if not partner:
            return
        obligations = partner.l10n_co_edi_obligation_type_ids.mapped('name')
        if 'O-15' in obligations or 'O-47' in obligations:
            return

        concepts = partner.insotech_retention_concept_ids.filtered(
            lambda c: c.direction in (direction, 'both')
            and (c.purchase_tax_id if direction == 'purchase' else c.tax_id)
        )
        for concept in concepts:
            target_tax = concept.purchase_tax_id if direction == 'purchase' else concept.tax_id
            if target_tax and target_tax.id not in self.tax_ids.ids:
                self.tax_ids |= target_tax
