# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.ist_preparation_day.models.const_preparation import (
    get_active_prep_operator_id,
)


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
        if 'actual_kg' in vals:
            # Ownership antes de super().write() (Fase C, punto 3 de Tech
            # Lead) — no-op si no viene guapante_picking_flow en contexto
            # (ej. edición inline desde la pestaña Productos).
            self._check_picking_ownership()
        res = super().write(vals)
        if 'is_done' in vals or 'actual_kg' in vals:
            self._maybe_release_finished_claim()
        if 'is_done' in vals:
            # El Nivel 1 no se entera solo — _notify_bus() en el modelo de
            # claim solo corre en sus propias acciones (Asignarme, Detener,
            # etc.), así que un pesaje hecho en el kanban de líneas (que
            # cambia is_done pero no pasa por ninguna acción del claim)
            # dejaba a los demás tablets viendo "En progreso — Asignado a
            # X" y el contador de pendientes viejos hasta recargar a mano
            # (hallazgo de Tech Lead). Uno por sesión afectada, no uno por
            # línea — un pesaje en lote de varias líneas de la misma
            # sesión no debe mandar N notificaciones idénticas.
            self._notify_picking_claims_bus()
        # El aviso de "operación completa terminó" (punto 4 de Tech Lead)
        # NO vive acá: action_mark_done() del padre corre DESPUÉS de que
        # el write de is_done=True (el que dispara este método) ya
        # volvió — este write() nunca llega a ver la transición. Vive en
        # el override de action_save_line_weight() en preparation_day.py,
        # que sí envuelve la llamada completa (incluido action_mark_done)
        # tanto si se dispara por write() como si se llama directo
        # (el mismo escenario de RPC del punto 3).
        return res

    def _check_picking_ownership(self) -> None:
        """Chequeo de ownership compartido (Fase C, punto 3 de Tech Lead):
        antes solo vivía implícito dentro de write() al exigir operario
        activo — eso no cubre action_save_line_weight(line_id) ni
        action_undo_line(), públicos y llamables por RPC directo sin
        pasar por write() con actual_kg. Un solo helper, tres llamadas
        (acá, y los overrides de esos dos métodos), para que ningún
        camino de Picking quede sin el control de "esta caja no es
        tuya".

        No-op si la llamada no viene de Picking (sin
        guapante_picking_flow en contexto) — fuera de Picking (pestaña
        Productos) no aplica ownership por caja, solo el ACL normal.
        """
        if not self.env.context.get('guapante_picking_flow'):
            return
        employee_id = (
            get_active_prep_operator_id(request.session, refresh=True)
            if request else False
        )
        if not employee_id:
            raise UserError(
                'Tu sesión de operario expiró por inactividad. '
                'Ingresa tu NIP de nuevo.'
            )
        for line in self:
            if not line.wizard_id or not line.product_id:
                continue
            Claim = line.wizard_id.product_claim_ids.filtered(
                lambda c: c.product_tmpl_id == line.product_id
            )
            # Solo rechaza si el claim tiene OTRO dueño puesto — un claim
            # sin dueño (pendiente, o recién liberado al terminar su
            # última caja) no bloquea a nadie, igual que Asignarme acepta
            # cualquier claim pendiente. Comparar contra
            # assigned_employee_id vacío (False) habría dejado
            # action_undo_line inservible justo después de terminar un
            # producto, que es exactamente cuando el claim se libera.
            if (
                Claim
                and Claim.assigned_employee_id
                and Claim.assigned_employee_id.id != employee_id
            ):
                raise UserError(
                    f'{Claim.product_tmpl_id.name} no está asignado a ti '
                    '— actualiza la pantalla.'
                )

    def action_undo_line(self) -> bool:
        """Mismo ownership que write() con actual_kg (Fase C, punto 3 de
        Tech Lead) — este método es público y no pasa por ahí: su propio
        write() interno usa skip_auto_save, sin guapante_picking_flow en
        contexto, así que el chequeo de write() no lo cubre solo."""
        self._check_picking_ownership()
        return super().action_undo_line()

    def action_mark_line_ready(self) -> bool:
        """Botón "Listo" de Nivel 2 para líneas needs_weighing=False
        (Fase C, punto 2 de Tech Lead): el padre no tiene un camino
        separado para estas líneas — la pestaña Productos usa la misma
        lista y el mismo widget scale_weight para TODAS las pendientes,
        sin distinguir needs_weighing (confirmado leyendo el código, no
        hay nada que reutilizar de ahí). En vez de inventar un cierre
        propio, este método solo escribe estimated_kg en actual_kg bajo
        contexto de Picking — eso entra por el write() YA existente
        (is_picking_flow -> action_save_line_weight() del padre), con
        todo su blindaje (ownership arriba, operario activo, propagación
        a stock, auto-cierre de producto/sesión) sin duplicar nada.
        """
        for line in self:
            if line.is_done:
                continue
            if line.estimated_kg <= 0:
                raise UserError(
                    f'{line.product_description} no tiene cantidad '
                    'estimada — no se puede marcar Listo. Avisa a un '
                    'supervisor.'
                )
            line.with_context(guapante_picking_flow=True).write({
                'actual_kg': line.estimated_kg,
            })
        return True

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

    def _notify_picking_claims_bus(self) -> None:
        Bus = self.env['bus.bus']
        for wizard_id in self.mapped('wizard_id').ids:
            Bus._sendone(
                f'guapante_preparation_day-{wizard_id}',
                'picking_claim_updated',
                {},
            )

    # Kg esperado por unidad para la plantilla de esta línea, leído del
    # claim de Nivel 1 (Fase C) — no almacenado: siempre se deriva fresco
    # del campo vivo en el claim, para no tener dos copias del mismo
    # número que puedan desincronizarse. Lo lee la tarjeta de Nivel 2
    # (JS) para la alerta de peso sospechoso; en 0.0 cuando la plantilla
    # no tiene historia suficiente (sentinel de "sin alerta").
    expected_kg_per_unit = fields.Float(
        compute='_compute_expected_kg_per_unit',
        digits=(10, 4),
    )

    def _compute_expected_kg_per_unit(self) -> None:
        for line in self:
            Claim = line.wizard_id.product_claim_ids.filtered(
                lambda c: c.product_tmpl_id == line.product_id
            )
            line.expected_kg_per_unit = Claim.expected_kg_per_unit if Claim else 0.0

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

    @api.depends('is_done')
    def _compute_picking_status(self) -> None:
        for line in self:
            line.picking_status = 'done' if line.is_done else 'pending'
