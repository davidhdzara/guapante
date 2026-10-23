# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import plaintext2html

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

        Exige dueño activo, no solo "que no sea de otro" (Tech Lead,
        corrección sobre la primera versión): un claim sin dueño
        (Pendiente, o recién liberado al Terminar su última caja) no deja
        pesar/Listo/Corregir a nadie sin pasar antes por Asignarme. Esto
        es consecuencia directa del plan: Terminado es solo lectura desde
        Picking — una corrección post-cierre la hace un supervisor desde
        la pestaña Productos, no un operario de Picking sin asignación.
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
            if not Claim or Claim.assigned_employee_id.id != employee_id:
                if Claim and not Claim.assigned_employee_id:
                    raise UserError(
                        f'Asígnate {Claim.product_tmpl_id.name} primero '
                        '— actualiza la pantalla.'
                    )
                raise UserError(
                    f'{line.product_description or "Esta caja"} no está '
                    'asignada a ti — actualiza la pantalla.'
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

    def action_add_note(self, text: str) -> bool:
        """Fase D — engrane de Nivel 2, "Agregar nota": mismo ownership
        que action_undo_line (self._check_picking_ownership, exige
        guapante_picking_flow en contexto del llamador — el JS lo pasa
        explícito, igual que en los otros métodos de Nivel 2).

        Nota interna (subtype mail.mt_note) en el picking INTERNO de
        esta caja (stock_move_id.picking_id) — no en el picking de
        venta/salida, sino en el que mueve la caja dentro de la bodega,
        que es el único al que esta línea está ligada. Caso borde (Tech
        Lead): stock_move_id puede ser False (ver create() en
        ist_preparation_day/preparation_day.py — una línea se crea sin
        move cuando no hay uno que mapear) — ahí cae a la sesión
        (wizard_id), con el número de caja en el texto para no perder a
        qué caja corresponde.
        """
        self.ensure_one()
        clean_text = (text or '').strip()
        if not clean_text:
            raise UserError('La nota no puede estar vacía.')
        self._check_picking_ownership()
        employee_id = (
            get_active_prep_operator_id(request.session, refresh=True)
            if request else False
        )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        # Tech Lead: message_post(body=<str>) trata el cuerpo como HTML
        # — texto libre de un operario ("<b>x</b>", "a < b") se
        # renderizaba como HTML activo y los saltos de línea se
        # perdían. plaintext2html() escapa entidades y convierte \n en
        # <br/>, devolviendo un Markup ya seguro — mismo cuidado que el
        # resto del chatter de Picking (peso, detener, etc.).
        Picking = self.stock_move_id.picking_id
        if Picking:
            body = plaintext2html(f'{clean_text}\n(por {Employee.name})')
            Picking.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')
        else:
            body = plaintext2html(
                f'Caja #{self.daily_sequence} — {clean_text}\n(por {Employee.name})'
            )
            self.wizard_id.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')
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

    # .name (no .display_name): la tarjeta de Nivel 2 tampoco debe
    # mostrar el código interno (especificación visual, David
    # 2026-10-23) — mismo motivo que product_tmpl_name en el claim.
    product_name = fields.Char(related='product_id.name', string='Producto (sin código)')

    # Chips de grado de madurez y tamaño en la tarjeta de Nivel 2 —
    # widget nativo many2many_tags, cero CSS propio. Vienen de
    # sale_line_id porque el pedido se hace con create_variant='no_variant'
    # (hallazgo de Fase C, grounded en datos reales de producción: el
    # 100% de las variantes de líneas needs_weighing=True tienen
    # product_template_attribute_value_ids vacío — el atributo real
    # elegido por el cliente vive en la línea de venta, no en la
    # variante del producto).
    no_variant_attribute_value_ids = fields.Many2many(
        'product.template.attribute.value',
        related='sale_line_id.product_no_variant_attribute_value_ids',
        string='Madurez / Tamaño',
    )

    # Para el botón "Corregir" de Nivel 2 (terminada): solo visible
    # mientras el claim de esta línea siga siendo mío — una vez
    # Terminado el producto completo, el claim se libera y Corregir deja
    # de estar disponible (Tech Lead: "Terminado es solo lectura desde
    # Picking", mismo _check_picking_ownership que ya lo exige en el
    # servidor — este campo solo evita mostrar un botón que el servidor
    # igual va a rechazar).
    claim_is_mine = fields.Boolean(compute='_compute_claim_is_mine')

    def _compute_claim_is_mine(self) -> None:
        for line in self:
            Claim = line.wizard_id.product_claim_ids.filtered(
                lambda c: c.product_tmpl_id == line.product_id
            )
            line.claim_is_mine = bool(Claim and Claim.is_mine)

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
