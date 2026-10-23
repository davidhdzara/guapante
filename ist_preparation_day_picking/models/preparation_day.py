# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _current_session_date,
)


class PreparationDay(models.Model):
    _inherit = 'guapante.preparation.day'

    product_claim_ids = fields.One2many(
        'guapante.preparation.day.product.claim', 'wizard_id',
        string='Nivel 1 de Picking',
    )

    def action_load(self) -> bool:
        """Extiende action_load() del padre sin tocarlo: además de
        reconstruir summaries (ya lo hace el padre), reconstruye los
        claims del Nivel 1. No se dispara desde un tablet — los operarios
        de Picking nunca llaman esto (Tech Lead, Fase B: no se quiere que
        corra en medio del pesaje), solo lo usa quien carga la sesión
        (Preparación › Sesiones).
        """
        res = super().action_load()
        self._rebuild_product_claims()
        return res

    def _rebuild_product_claims(self) -> None:
        """Mismo patrón que _rebuild_summary() del padre (línea ~968):
        crea un claim 'pending' por cada plantilla distinta que todavía no
        tenga uno, borra los que ya no tienen NINGUNA línea. Nunca borra
        un claim que tiene líneas, aunque estén todas is_done — ese es el
        estado 'done', no "ya no existe" (Tech Lead, Fase B)."""
        self.ensure_one()
        Claim = self.env['guapante.preparation.day.product.claim']
        templates = self.line_ids.mapped('product_id')
        Claim._ensure_claims_for_templates(self, templates)
        StaleClaims = self.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id not in templates
        )
        if StaleClaims:
            StaleClaims.sudo().unlink()
        Claim._refresh_expected_kg_per_unit(self, templates)

    def action_save_line_weight(self, line_id: int) -> bool:
        """Extiende action_save_line_weight() del padre con dos cosas de
        Fase C:

        1) Ownership (punto 3 de Tech Lead): este método es público y se
           puede llamar por RPC directo sin pasar antes por write() (que
           es donde vive el resto del chequeo de ownership, ver
           PreparationDayLine) — sin esto, ese camino directo se
           saltaba el control de "esta caja no es tuya".

        2) Aviso de cierre de operación (punto 4): self.action_mark_done()
           del padre, si corresponde, corre DENTRO de esta misma llamada
           — nunca dentro de un write() de Line que envuelva todo el
           ciclo (ver PreparationDayLine.write(): el write interno que
           hace este mismo método es solo is_done=True, ANTES de que
           action_mark_done() se ejecute). Por eso el aviso vive acá,
           envolviendo la llamada completa, y no en write() — ahí nunca
           ve la transición cuando este método se llama directo (el
           mismo escenario de RPC del punto 1).
        """
        self.env['guapante.preparation.day.line'].browse(
            line_id,
        )._check_picking_ownership()
        was_done_before = self.state == 'done'
        res = super().action_save_line_weight(line_id)
        if not was_done_before and self.state == 'done':
            self.env['bus.bus']._sendone(
                f'guapante_preparation_day-{self.id}',
                'picking_operation_finished',
                {},
            )
        return res

    def action_view_product_claims(self) -> dict:
        """Nivel 1 de Picking como client action propio (especificación
        visual, 2026-10-23 — decisión final de Tech Lead tras dos
        rondas de kanban nativo + t-inherit que nunca igualaron la
        tarjeta/barra de Taller real: el envoltorio o_kanban_record del
        kanban no se podía quitar). Punto de entrada real desde
        action_resolve_picking_handoff.

        Ya no hace falta devolver un xmlid+context para forzar el
        camino de markup() de doAction() (el bug de 'help' escapado era
        específico de un campo Html de ir.actions.act_window, que un
        client action no tiene) ni la variante doble de 'help' según
        estado: el componente OWL
        (preparation_picking_level1_display.js) decide el texto de
        estado vacío él mismo (state.hasLines, calculado con los datos
        que ya carga).

        context: 'guapante_picking_flow' vive en la ACCIÓN (no solo en
        llamadas RPC sueltas) porque el watcher de inactividad lo lee de
        action.currentController.action.context
        (preparation_picking_idle_watcher.js).
        """
        self.ensure_one()
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError(
                'No tienes acceso a la pantalla de Picking.'
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'guapante_picking_level1',
            'target': 'fullscreen',
            'context': {
                'guapante_picking_flow': True,
                'wizard_id': self.id,
            },
        }

    def action_open_picking_app(self) -> dict:
        """Botón "Picking" del form de la sesión — entra por la app
        (pantalla de NIP primero), no directo al kanban (Fase A, hallazgo
        de Tech Lead: "no se puede saltar" tiene que ser cierto también
        desde este botón, no solo desde el ícono/menú).

        Lleva la sesión puntual en contexto para que el handoff respete la
        fecha del formulario que se está viendo — no fuerza "hoy": un
        supervisor revisando un PK/PICK histórico debe entrar a esa sesión,
        no a la de hoy.

        El context se arma a mano (no se reemplaza entero) para no perder
        'guapante_picking_flow' — sin esa marca el watcher de inactividad no
        reconoce la pantalla de NIP como parte de Picking cuando se entra
        por este botón. La clave es 'picking_session_id', no
        'default_session_id': un prefijo 'default_' se propaga como valor
        por defecto a cualquier create() hecho con este contexto, y hay
        modelos con un campo session_id (POS, entre otros) — no vale la
        pena el riesgo (hallazgo de Tech Lead).
        """
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'ist_preparation_day_picking.action_picking_app'
        )
        action['context'] = {
            'guapante_picking_flow': True,
            'picking_session_id': self.id,
        }
        return action

    @api.model
    def action_resolve_picking_handoff(self) -> dict:
        """Llamado por el componente OWL de la app una vez identificado el
        operario: resuelve a qué sesión entrar y abre el Nivel 1 (Fase B
        — antes abría el kanban de líneas directo; ese sigue existiendo
        como destino temporal de Asignarme/Continuar/Retomar, ver
        action_open_lines_kanban en el modelo de claim).

        Si hay una sesión puntual en el contexto de la acción (entrada por
        el botón del form vía action_open_picking_app), la respeta. Si no
        (entrada por el ícono/menú de la app), resuelve "la sesión de hoy"
        reusando _current_session_date / _ensure_session_for_date — crea la
        sesión en borrador si todavía no existe, mismo comportamiento que ya
        dispara sale_order.action_confirm() para pedidos confirmados hoy.
        """
        session_id = self.env.context.get('picking_session_id')
        if session_id:
            Session = self.browse(session_id)
        else:
            today = _current_session_date(self.env)
            Session = self._ensure_session_for_date(today)
        return Session.action_view_product_claims()
