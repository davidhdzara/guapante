# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _current_session_date,
)


class PreparationDay(models.Model):
    _inherit = 'guapante.preparation.day'

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
        """
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'ist_preparation_day_picking.action_picking_app'
        )
        action['context'] = {'default_session_id': self.id}
        return action

    @api.model
    def action_resolve_picking_handoff(self) -> dict:
        """Llamado por el componente OWL de la app una vez identificado el
        operario: resuelve a qué kanban de Picking entrar.

        Si hay una sesión puntual en el contexto de la acción (entrada por
        el botón del form vía action_open_picking_app), la respeta. Si no
        (entrada por el ícono/menú de la app), resuelve "la sesión de hoy"
        reusando _current_session_date / _ensure_session_for_date — crea la
        sesión en borrador si todavía no existe, mismo comportamiento que ya
        dispara sale_order.action_confirm() para pedidos confirmados hoy.
        """
        session_id = self.env.context.get('default_session_id')
        if session_id:
            Session = self.browse(session_id)
        else:
            today = _current_session_date(self.env)
            Session = self._ensure_session_for_date(today)
        return Session.action_view_picking_kanban()
