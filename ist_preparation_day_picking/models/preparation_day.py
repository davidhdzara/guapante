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

    def action_view_product_claims(self) -> dict:
        """Nivel 1 de Picking (Fase B): kanban de product.claim agrupado
        por status — reemplaza al kanban de líneas como punto de entrada
        real desde action_resolve_picking_handoff. El kanban de líneas
        (action_view_picking_kanban) se mantiene vivo todavía como destino
        TEMPORAL de Asignarme/Continuar/Retomar hasta que exista el
        Nivel 2 real (Fase C) — ver action_open_lines_kanban en el modelo
        de claim.
        """
        self.ensure_one()
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError(
                'No tienes acceso a la pantalla de Picking.'
            )
        return {
            'name': 'Picking',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.claim',
            'view_mode': 'kanban',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'fullscreen',
            'context': {
                'guapante_picking_flow': True,
                'picking_wizard_id': self.id,
            },
            # Estado vacío nativo — las líneas solo nacen en action_load()
            # (que un operario de Picking nunca dispara), así que una
            # sesión recién auto-creada por la Fase A puede no tener nada
            # todavía (Tech Lead, punto 8).
            'help': (
                '<p class="o_view_nocontent_smiling_face">'
                'La sesión de hoy todavía no está cargada.</p>'
                '<p>Pídele a un supervisor que la cargue desde '
                'Preparación › Sesiones.</p>'
            ),
        }

    def action_view_picking_kanban(self) -> dict:
        """Abre Picking: kanban a pantalla completa de las líneas
        pendientes de esta sesión — báscula + PIN, sin paso de
        selección de producto (eso ya lo resuelve el Summary kanban +
        wizard existentes).

        Chequeo de grupo explícito en Python: el botón ya se oculta por
        grupo en la vista, pero esto devuelve un dict dinámico (no un
        ir.actions.act_window con id propio), así que un groups_id en
        un registro XML no alcanzaría a protegerlo solo — hace falta
        esta verificación para que el acceso quede cerrado también si
        alguien llama al método directamente, no solo por UI.
        """
        self.ensure_one()
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError(
                'No tienes acceso a la pantalla de Picking.'
            )
        return {
            'name': 'Picking',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.line',
            'view_mode': 'kanban',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'fullscreen',
            # Marca de origen para write() en ist_preparation_day — un
            # pesaje que sale de Picking exige operario identificado activo;
            # sin esta marca write() no puede distinguir este kanban de una
            # edición inline en la pestaña Productos (Fase A, hallazgo de
            # Tech Lead: con el cierre por inactividad, la sola presencia de
            # un PIN en sesión ya no alcanza como señal confiable de
            # origen — la sesión puede haber expirado justo mientras
            # pesaba).
            'context': {'guapante_picking_flow': True},
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
