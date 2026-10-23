# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PreparationDayLine(models.Model):
    _inherit = 'guapante.preparation.day.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Asegura el claim del Nivel 1 también al crear líneas, no solo en
        action_load() (Tech Lead, Fase B, punto 9: "asegura el claim cuando
        se crean líneas... así queda robusto"). _ensure_claims_for_templates
        no duplica nada — es create-if-missing, así que no importa si
        action_load() ya corrió la reconstrucción completa después."""
        Lines = super().create(vals_list)
        Claim = self.env['guapante.preparation.day.product.claim']
        templates_by_wizard = {}
        for line in Lines:
            if not line.product_id:
                continue
            templates_by_wizard.setdefault(
                line.wizard_id, self.env['product.template'],
            )
            templates_by_wizard[line.wizard_id] |= line.product_id
        for wizard, templates in templates_by_wizard.items():
            Claim._ensure_claims_for_templates(wizard, templates)
        return Lines

    def write(self, vals):
        """Al terminar la última línea pendiente de una plantilla, suelta
        el dueño del claim — en el flujo que termina la línea, no en el
        compute de status (Tech Lead, Fase B, punto 4): así, si después
        entra un pedido nuevo de esa plantilla (action_load agrega
        líneas), el claim vuelve a Pendiente sin dueño, no a "En progreso"
        de alguien que ya se fue."""
        res = super().write(vals)
        if 'is_done' in vals or 'actual_kg' in vals:
            self._maybe_release_finished_claim()
        return res

    def _maybe_release_finished_claim(self) -> None:
        templates = self.mapped('product_id')
        wizard_ids = self.mapped('wizard_id').ids
        if not templates or not wizard_ids:
            return
        Claims = self.env['guapante.preparation.day.product.claim'].sudo().search([
            ('wizard_id', 'in', wizard_ids),
            ('product_tmpl_id', 'in', templates.ids),
            ('assigned_employee_id', '!=', False),
        ])
        for claim in Claims:
            Lines = claim._get_lines()
            if Lines and all(line.is_done for line in Lines):
                claim.write({
                    'assigned_employee_id': False,
                    'assigned_date': False,
                })

    # Punto de montaje del widget de identificación por PIN en cada card
    # del kanban de Picking — el valor no se usa (operatorState es un
    # singleton compartido en JS), solo existe para que el widget se
    # monte. Mismo patrón que operator_identification en el wizard y
    # live_refresh_anchor en guapante.preparation.day.
    picking_operator_anchor = fields.Char(
        compute='_compute_picking_operator_anchor',
    )

    # Espejo de is_done con labels legibles — el kanban de Picking agrupa
    # por este campo en vez de por is_done directo, porque Odoo no deja
    # poner labels custom a un group_by de un Boolean (sale "No"/"Sí"
    # crudo). store=True porque el group_by de kanban necesita un campo
    # en la base de datos, no uno puramente en memoria.
    picking_status = fields.Selection(
        selection=[('pending', 'Pendiente'), ('done', 'Terminado')],
        compute='_compute_picking_status',
        store=True,
    )

    def _compute_picking_operator_anchor(self) -> None:
        for line in self:
            line.picking_operator_anchor = ''

    @api.depends('is_done')
    def _compute_picking_status(self) -> None:
        for line in self:
            line.picking_status = 'done' if line.is_done else 'pending'
