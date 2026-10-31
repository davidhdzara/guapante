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
            self._check_qty_uom_supported()
            if self.env.context.get('guapante_picking_flow'):
                # is_qty_estimated (Tech Lead, punto b — kg Y unidades): se
                # fija SIEMPRE junto con actual_kg en este camino —
                # explícito en los dos sentidos (True al aceptar lo
                # precargado sin editar, False en cualquier edición real,
                # incluida una corrección posterior) para que nunca quede
                # un valor viejo pegado. Nunca True en una línea
                # needs_weighing=True, sin importar qué contexto llegue —
                # es solo para los casos sin pesaje (kg directo o unidades).
                vals = dict(vals)
                vals['is_qty_estimated'] = (
                    bool(self.env.context.get('guapante_qty_estimated'))
                    and not any(self.mapped('needs_weighing'))
                )
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
            get_active_prep_operator_id(self.env, request.session, refresh=True)
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
        res = super().action_undo_line()
        # is_qty_estimated (Tech Lead, punto b): el padre ya resetea
        # actual_kg a 0.0 — sin una caja despachada no hay "lo pedido
        # aceptado sin verificar" que señalar. Write aparte porque el del
        # padre usa skip_auto_save, sin 'actual_kg' en su propio vals (va
        # directo a super().write() del ORM, no pasa por el bloque de
        # arriba).
        self.write({'is_qty_estimated': False})
        return res

    def action_mark_line_ready(self) -> bool:
        """Botón "Listo" de Nivel 2 para líneas needs_weighing=False
        (Fase C, punto 2 de Tech Lead) — reemplazado en la UI por
        "confirmar sin editar" el valor precargado (punto b, kg directo o
        unidades), pero se mantiene aquí: sigue siendo un camino válido
        por RPC directo (Tech Lead, decisión del punto b, item 5). El
        padre no tiene un camino separado para estas líneas — la pestaña
        Productos usa la misma lista y el mismo widget scale_weight para
        TODAS las pendientes, sin distinguir needs_weighing (confirmado
        leyendo el código, no hay nada que reutilizar de ahí). En vez de
        inventar un cierre propio, este método solo escribe estimated_kg
        en actual_kg bajo contexto de Picking — eso entra por el write()
        YA existente (is_picking_flow -> action_save_line_weight() del
        padre), con todo su blindaje (ownership arriba, operario activo,
        propagación a stock, auto-cierre de producto/sesión) sin
        duplicar nada. guapante_qty_estimated=True: este camino SIEMPRE
        acepta lo pedido sin verificar, por definición.
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
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({
                'actual_kg': line.estimated_kg,
            })
        return True

    def action_add_note(self, text: str) -> bool:
        """Fase D / punto c (David, vía Tech Lead 2026-10-29) — "Agregar
        nota" de Nivel 2: SIN exigir dueño del claim — basta estar
        identificado con NIP (operario activo y autorizado). Antes
        reutilizaba _check_picking_ownership() como el resto de Nivel 2
        (Asignarme primero); David encontró eso innecesario para dejar
        una observación — una caja ya Terminada, o de un producto sin
        dueño actual, también puede necesitar una nota. Chequeo propio,
        más laxo que ownership: solo "¿quién es, y sigue siendo un
        operario autorizado?", sin tocar el claim para nada.

        SIEMPRE se publica en el chatter de la SESIÓN (wizard_id) — es
        donde David espera verla — con "Caja #N — texto (por operario)".
        Además, cuando esta caja tiene un picking interno real
        (stock_move_id.picking_id), el MISMO texto se publica también
        ahí — dos chatters, un post en cada uno, nunca duplicado dentro
        del mismo. Antes era uno u otro (picking si existía, sesión como
        fallback); ahora la sesión es incondicional y el picking es un
        extra cuando existe.
        """
        self.ensure_one()
        clean_text = (text or '').strip()
        if not clean_text:
            raise UserError('La nota no puede estar vacía.')
        employee_id = (
            get_active_prep_operator_id(self.env, request.session, refresh=True)
            if request else False
        )
        if not employee_id:
            raise UserError(
                'Debes identificarte con tu PIN antes de dejar una nota.'
            )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        if (
            not Employee.exists()
            or not Employee.active
            or not Employee.is_guapante_prep_operator
        ):
            raise UserError(
                'Tu identificación de operario ya no es válida — vuelve a '
                'ingresar tu PIN.'
            )
        # Tech Lead: message_post(body=<str>) trata el cuerpo como HTML
        # — texto libre de un operario ("<b>x</b>", "a < b") se
        # renderizaba como HTML activo y los saltos de línea se
        # perdían. plaintext2html() escapa entidades y convierte \n en
        # <br/>, devolviendo un Markup ya seguro — mismo cuidado que el
        # resto del chatter de Picking (peso, detener, etc.).
        body = plaintext2html(
            f'Caja #{self.daily_sequence} — {clean_text}\n(por {Employee.name})'
        )
        self.wizard_id.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')
        Picking = self.stock_move_id.picking_id
        if Picking:
            Picking.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')
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

    # Informativo, para reportes de Fase 2 (Tech Lead, 2026-10-29, punto
    # b): True solo cuando el operario aceptó el valor precargado (lo
    # pedido) SIN verificar de verdad en una línea needs_weighing=False —
    # cubre los dos casos sin pesaje real (kg/g pedido directo Y
    # unidades), no solo kg. Kilos/hora y promedios necesitan distinguir
    # esto de un valor real, y actual_kg == estimated_kg por sí solo es
    # ambiguo (podría coincidir por casualidad) y no se puede reconstruir
    # después. Lo escribe write() (arriba) y action_mark_line_ready();
    # nunca True en una línea que sí necesita pesaje real (needs_weighing
    # =True). Líneas que ya existían antes de este campo quedan en False
    # — "desconocido", NO "valor real confirmado".
    is_qty_estimated = fields.Boolean(
        string='Cantidad = lo pedido (sin confirmar aparte)',
        default=False,
    )

    # Unidad en la que la tarjeta de Nivel 2 debe capturar el valor real
    # (Tech Lead, 2026-10-29, punto b) — NO es uom_mode (cómo el cliente
    # vio la cantidad en la tienda: puede ser 'g' y esto seguir en kg,
    # son preguntas distintas). "kg" cuando el producto usa la UoM de
    # REFERENCIA de la categoría Weight (factor 1.0 — confirmado por
    # datos reales de staging Y producción, 2026-10-29: ningún producto
    # vendible usa hoy una UoM de peso no-referencia, ej. gramos reales
    # con factor 0.001); "und" cuando usa la UoM de referencia de la
    # categoría Unit (datos reales: 0 líneas con cantidad no entera en
    # ese grupo — no hay evidencia de unidades fraccionarias). False/
    # vacío en cualquier otro caso (otra categoría, ej. Hours, o una UoM
    # de peso/unidad NO-referencia) — Preparación solo maneja kg y
    # unidades hoy (David, vía Tech Lead): un default silencioso ahí
    # sería un número en la unidad equivocada sin que nadie lo note, así
    # que se trata como "no soportado" (ver _check_qty_uom_supported) en
    # vez de asumir kg o unidades a ciegas. No almacenado: se deriva
    # fresco de la UoM del producto, igual que expected_kg_per_unit
    # arriba.
    qty_uom_label = fields.Char(compute='_compute_qty_uom_label')

    def _compute_qty_uom_label(self) -> None:
        weight_categ = self.env.ref(
            'uom.product_uom_categ_kgm', raise_if_not_found=False,
        )
        unit_categ = self.env.ref(
            'uom.product_uom_categ_unit', raise_if_not_found=False,
        )
        for line in self:
            uom = line.product_product_id.uom_id
            if weight_categ and uom.category_id == weight_categ and uom.factor == 1.0:
                line.qty_uom_label = 'kg'
            elif unit_categ and uom.category_id == unit_categ and uom.factor == 1.0:
                line.qty_uom_label = 'und'
            else:
                line.qty_uom_label = False

    def _check_qty_uom_supported(self) -> None:
        """Preparación solo maneja productos en kg o unidades (David,
        vía Tech Lead 2026-10-29) — nunca un default silencioso: si la
        UoM del producto no cae en ninguno de esos dos casos
        (qty_uom_label vacío), error claro en vez de capturar/guardar un
        número en la unidad equivocada sin que nadie lo note. No-op
        fuera de Picking (sin guapante_picking_flow en contexto) — mismo
        patrón que _check_picking_ownership."""
        if not self.env.context.get('guapante_picking_flow'):
            return
        unsupported = self.filtered(lambda l: not l.qty_uom_label)
        if unsupported:
            names = ', '.join(
                line.product_description or line.product_product_id.display_name
                or 'Este producto'
                for line in unsupported
            )
            raise UserError(
                f'{names}: Preparación solo maneja productos en kg o '
                'unidades — pide al administrador corregir la unidad '
                'base del producto antes de continuar.'
            )

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
