# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import plaintext2html

from odoo.addons.ist_preparation_day.models.const_preparation import (
    get_active_prep_operator_id,
)


class StockScrap(models.Model):
    """Fase D — atribución de los desechos hechos desde Picking.

    do_scrap() (no action_validate()) es el único punto de extensión
    real: el asistente nativo de cantidad insuficiente
    (stock.warn.insufficient.qty.scrap.action_done()) llama
    scrap_id.do_scrap() directo, sin volver a pasar por
    action_validate() — confirmado leyendo
    stock/wizard/stock_warn_insufficient_qty.py. clean_context() de ese
    camino solo filtra claves 'default_*', así que guapante_picking_flow/
    picking_wizard_id/picking_claim_id (ninguna empieza con 'default_')
    sobreviven a los dos caminos.

    Fuera de Picking (sin guapante_picking_flow en contexto) este
    override es un no-op total — do_scrap() se comporta exactamente
    como el core, sin exigir operario ni escribir nada nuestro.
    """
    _inherit = 'stock.scrap'

    def do_scrap(self):
        is_picking_flow = bool(self.env.context.get('guapante_picking_flow'))
        employee_id = False
        Wizard = None
        if is_picking_flow:
            employee_id = (
                get_active_prep_operator_id(request.session, refresh=True)
                if request else False
            )
            if not employee_id:
                raise UserError(
                    'Tu sesión de operario expiró por inactividad. '
                    'Ingresa tu NIP de nuevo.'
                )
            # Tech Lead, corrección 2: la marca de contexto la controla
            # el cliente — si llega sin picking_claim_id/picking_wizard_id
            # nunca se cae al flujo sin chequeo, se corta acá.
            claim_id = self.env.context.get('picking_claim_id')
            wizard_id = self.env.context.get('picking_wizard_id')
            if not claim_id or not wizard_id:
                raise UserError(
                    'No se pudo identificar la sesión de Picking para '
                    'este desecho — actualiza la pantalla.'
                )
            Claim = self.env['guapante.preparation.day.product.claim'].browse(claim_id)
            if Claim.assigned_employee_id.id != employee_id:
                raise UserError(
                    f'No puedes desechar {Claim.product_tmpl_id.name} — '
                    'no está asignado a ti. Actualiza la pantalla.'
                )
            Wizard = self.env['guapante.preparation.day'].browse(wizard_id)
            # Tech Lead, corrección 2 de la segunda revisión: wizard_id
            # y claim_id vienen sueltos del contexto del cliente —
            # podrían apuntar a sesiones distintas (ej. contexto viejo
            # de una pestaña con F5 a medias). El claim tiene que ser
            # de ESA sesión, no basta con que exista.
            if Claim.wizard_id != Wizard:
                raise UserError(
                    'El desecho no coincide con la sesión activa — '
                    'actualiza la pantalla.'
                )
            for scrap in self:
                # Tech Lead, corrección 3: product_ids en el contexto del
                # diálogo solo acota el domain del campo product_id — no
                # impide teclear otro producto por RPC directo. Server-side
                # real: el producto desechado tiene que ser de la MISMA
                # plantilla que el claim que autoriza este desecho.
                if scrap.product_id.product_tmpl_id != Claim.product_tmpl_id:
                    raise UserError(
                        f'{scrap.product_id.name} no pertenece a '
                        f'{Claim.product_tmpl_id.name} — actualiza la pantalla.'
                    )
                # Tech Lead, corrección 1: 'origin' no está en
                # stock_scrap_form_view2 (solo en la vista form completa)
                # — default_origin no sirve, un default_* solo se aplica
                # a campos que la vista pide en default_get. Se escribe
                # acá, antes de super(), para que el movimiento de stock
                # (que usa origin or picking.name or name) quede
                # referenciado a la sesión real.
                if not scrap.origin:
                    scrap.origin = Wizard.name

        res = super().do_scrap()

        if is_picking_flow:
            Employee = self.env['hr.employee'].sudo().browse(employee_id)
            for scrap in self:
                reasons = ', '.join(
                    scrap.scrap_reason_tag_ids.mapped('name')
                ) or 'sin motivo'
                # Tech Lead: nombre de producto y motivos van
                # interpolados — message_post(body=<str>) los trata
                # como HTML. plaintext2html() escapa entidades, mismo
                # cuidado que en action_add_note().
                message = plaintext2html(
                    f'Desechado — {scrap.product_id.name}: {scrap.scrap_qty} '
                    f'{scrap.product_uom_id.name}, {reasons} (por {Employee.name}).'
                )
                scrap.message_post(body=message)
                Wizard.sudo().message_post(body=message)
        return res
