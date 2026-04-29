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
        """Al cambiar el partner, forzamos un recálculo en las líneas existentes."""
        if self.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund') or not self.partner_id:
            return
        
        # Simplemente llamamos el onchange de las líneas para que se refresquen con el nuevo partner
        for line in self.invoice_line_ids:
            line._onchange_insotech_realtime_retentions()

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

        # ── 3. Calcular base en UVT (Multi-moneda y Acumulados) ──
        # Convertir a moneda base si aplica
        company_currency = self.company_id.currency_id
        if self.currency_id and self.currency_id != company_currency:
            base_amount_cop = self.currency_id._convert(
                self.amount_untaxed, company_currency, self.company_id, self.invoice_date or fields.Date.today()
            )
        else:
            base_amount_cop = self.amount_untaxed

        if not base_amount_cop:
            return self._insotech_notify(
                _("La factura no tiene monto base para calcular."),
            )
            
        # Calcular histórico del mes para topes acumulados
        first_day = (self.invoice_date or fields.Date.today()).replace(day=1)
        domain = [
            ('partner_id', '=', partner.id),
            ('move_type', '=', self.move_type),
            ('state', 'in', ('posted', 'draft')),
            ('invoice_date', '>=', first_day),
            ('id', '!=', self.id)
        ]
        month_moves = self.search(domain)
        accumulated_cop = sum(
            m.currency_id._convert(m.amount_untaxed, company_currency, m.company_id, m.invoice_date or fields.Date.today())
            if m.currency_id != company_currency else m.amount_untaxed
            for m in month_moves
        )
        
        base_en_uvt = base_amount_cop / uvt.value
        accumulated_uvt = (base_amount_cop + accumulated_cop) / uvt.value

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
        reteiva_taxes = self.env['account.tax']
        fiscal_position = self.fiscal_position_id
        accumulated_warning = False
        
        for concept in concepts:
            # Evaluar UVT (individual o acumulada)
            effective_uvt = accumulated_uvt if concept.accumulate_monthly else base_en_uvt
            if effective_uvt < concept.base_uvt:
                continue
                
            if concept.accumulate_monthly and base_en_uvt < concept.base_uvt:
                accumulated_warning = True
                
            target_tax = concept.purchase_tax_id if direction == 'purchase' else concept.tax_id
            if fiscal_position and target_tax:
                target_tax = fiscal_position.map_tax(target_tax)
            if target_tax:
                vendor_taxes |= target_tax
                if concept.type == 'reteiva':
                    reteiva_taxes |= target_tax
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
            if parafiscal and target_pf_tax:
                effective_uvt = accumulated_uvt if parafiscal.accumulate_monthly else base_en_uvt
                if effective_uvt >= parafiscal.base_uvt:
                    line_parafiscals[line.id] = parafiscal

        # ── 7. Limpiar impuestos de retención previos e inyectar nuevos ──
        # Identificar todos los posibles impuestos generados por conceptos
        all_retention_taxes = concepts.mapped('purchase_tax_id') | concepts.mapped('tax_id')
        all_retention_taxes |= self.env['insotech.retention.concept'].search([('type', '=', 'parafiscal')]).mapped('purchase_tax_id')
        all_retention_taxes |= self.env['insotech.retention.concept'].search([('type', '=', 'parafiscal')]).mapped('tax_id')
        
        for line in product_lines:
            # Remover impuestos de retención previos para no dejar impuestos "pegajosos"
            current_taxes = line.tax_ids - all_retention_taxes
            taxes_for_line = current_taxes
            existing_ids = set(current_taxes.ids)

            has_iva = any(
                t.amount > 0 and t.amount_type == 'percent' 
                and ('iva' in t.name.lower() or 'vat' in t.name.lower())
                for t in line.tax_ids
            )
            for tax in vendor_taxes:
                # Prevenir inyección de ReteIVA en líneas Exentas de IVA
                if tax in reteiva_taxes and not has_iva:
                    continue
                if tax.id not in existing_ids:
                    taxes_for_line |= tax

            parafiscal = line_parafiscals.get(line.id)
            if parafiscal:
                target_pf_tax = parafiscal.purchase_tax_id if direction == 'purchase' else parafiscal.tax_id
                if fiscal_position and target_pf_tax:
                    target_pf_tax = fiscal_position.map_tax(target_pf_tax)
                if target_pf_tax and target_pf_tax.id not in existing_ids:
                    taxes_for_line |= target_pf_tax
                    pf_label = (
                        f"• {parafiscal.name}: {parafiscal.percentage}%"
                        f" ({target_pf_tax.name})"
                        f" [{line.product_id.name}]"
                    )
                    if pf_label not in applied:
                        applied.append(pf_label)

            if taxes_for_line != line.tax_ids:
                line.write({
                    'tax_ids': [fields.Command.set(taxes_for_line.ids)],
                })

        if applied:
            self.insotech_retention_calculated = True
            body = _(
                "<b>Retenciones DIAN aplicadas (%s):</b><br/>%s"
            ) % (len(applied), "<br/>".join(applied))
            
            if accumulated_warning:
                body += _("<br/><br/>⚠️ <b>Aviso de Acumulación Mensual:</b> Se superó el tope UVT por acumulación de facturas anteriores en este mes. Odoo ha calculado la retención solo sobre el valor de esta factura (para cumplir matemáticamente con la DIAN). Deberá emitir una Nota Débito manual al proveedor por el valor retroactivo no retenido en las facturas previas.")
                
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

    @api.onchange('product_id', 'price_unit', 'quantity')
    def _onchange_insotech_realtime_retentions(self) -> None:
        """Motor en Tiempo Real (Híbrido).
        Calcula matemáticamente por línea si se superan los
        topes UVT, respetando obligaciones DIAN, e inyecta
        o retira el impuesto al instante.
        Aplica tanto a Compras como a Ventas.
        NO se dispara al editar tax_ids manualmente (Obs 4)
        para permitir que el usuario elimine impuestos.
        """
        if (
            not self.move_id
            or self.move_id.move_type not in (
                'in_invoice', 'in_refund',
                'out_invoice', 'out_refund',
            )
        ):
            return

        if self.display_type in ('line_section', 'line_note'):
            return

        partner = self.move_id.partner_id
        if not partner:
            return

        direction = (
            'purchase'
            if self.move_id.move_type in ('in_invoice', 'in_refund')
            else 'sale'
        )

        # 1. Validar Obligaciones (Exenciones)
        obligations = (
            partner.l10n_co_edi_obligation_type_ids.mapped('name')
        )
        if 'O-47' in obligations:
            return
        if 'O-15' in obligations and direction == 'purchase':
            return

        # 2. Leer UVT
        invoice_year = (
            self.move_id.invoice_date or fields.Date.today()
        ).year
        uvt = self.env['insotech.uvt'].search(
            [('year', '=', invoice_year)], limit=1,
        )
        if not uvt or uvt.value == 0:
            return

        # 3. Calcular Base de la Línea
        line_base_cop = self.price_unit * self.quantity
        company_currency = self.move_id.company_id.currency_id
        if (
            self.move_id.currency_id
            and self.move_id.currency_id != company_currency
        ):
            line_base_cop = self.move_id.currency_id._convert(
                line_base_cop,
                company_currency,
                self.move_id.company_id,
                self.move_id.invoice_date or fields.Date.today(),
            )
        base_en_uvt = line_base_cop / uvt.value

        # 4. Obtener Conceptos del Partner
        concepts = partner.insotech_retention_concept_ids.filtered(
            lambda c: c.direction in (direction, 'both')
        )

        # 5. Construir set de TODOS los taxes de retención
        #    (para poder aislar los taxes estándar como IVA)
        all_retention_taxes = (
            concepts.mapped('purchase_tax_id')
            | concepts.mapped('tax_id')
        )
        # Cachear parafiscales una sola vez por onchange
        parafiscal_concepts = self.env[
            'insotech.retention.concept'
        ].search([('type', '=', 'parafiscal')])
        all_retention_taxes |= (
            parafiscal_concepts.mapped('purchase_tax_id')
            | parafiscal_concepts.mapped('tax_id')
        )

        # Aislar impuestos estándar (IVA, etc.)
        current_standard_taxes = self.tax_ids - all_retention_taxes
        taxes_to_apply = current_standard_taxes

        has_iva = any(
            t.amount > 0
            and t.amount_type == 'percent'
            and (
                'iva' in t.name.lower()
                or 'vat' in t.name.lower()
            )
            for t in current_standard_taxes
        )

        fiscal_position = self.move_id.fiscal_position_id

        # 6. Evaluar Conceptos del Partner
        for concept in concepts:
            # Obs 5: Conceptos acumulativos se evalúan solo
            # via botón de contingencia, no en tiempo real
            if concept.accumulate_monthly:
                continue
            if base_en_uvt >= concept.base_uvt:
                target_tax = (
                    concept.purchase_tax_id
                    if direction == 'purchase'
                    else concept.tax_id
                )
                if fiscal_position and target_tax:
                    target_tax = fiscal_position.map_tax(
                        target_tax,
                    )
                if target_tax:
                    if concept.type == 'reteiva' and not has_iva:
                        continue
                    taxes_to_apply |= target_tax

        # 7. Evaluar Parafiscales del Producto
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            parafiscal = tmpl.insotech_parafiscal_concept_id
            if parafiscal and not parafiscal.accumulate_monthly:
                if base_en_uvt >= parafiscal.base_uvt:
                    target_pf_tax = (
                        parafiscal.purchase_tax_id
                        if direction == 'purchase'
                        else parafiscal.tax_id
                    )
                    if fiscal_position and target_pf_tax:
                        target_pf_tax = fiscal_position.map_tax(
                            target_pf_tax,
                        )
                    if target_pf_tax:
                        taxes_to_apply |= target_pf_tax

        # 8. Asignar finalmente a la línea
        if taxes_to_apply != self.tax_ids:
            self.tax_ids = taxes_to_apply

