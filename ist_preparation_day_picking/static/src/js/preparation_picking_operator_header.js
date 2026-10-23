import { useService } from "@web/core/utils/hooks";
import { Component, xml } from "@odoo/owl";

import { operatorState, clearOperator } from "@ist_preparation_day/js/preparation_operator_state";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

// Compartido por Nivel 1 y Nivel 2 (Fase C, punto 3 de Tech Lead: "arriba
// solo el nombre del operario y Cerrar sesión", en los dos niveles — el
// plan lo pide explícitamente, no es opcional). Nivel 1 y Nivel 2 son
// client actions propios (preparation_picking_level1_display.xml /
// preparation_picking_level2_display.xml, especificación visual
// 2026-10-23) que construyen su propia barra a mano y embeben este
// componente ahí — sin t-inherit ni slot de ControlPanel nativo.
export class PickingOperatorHeader extends Component {
    static template = xml`
        <div class="d-flex align-items-center gap-2">
            <span t-if="operatorState.employeeName" class="text-muted">
                <i class="fa fa-id-badge me-1"/>
                <t t-esc="operatorState.employeeName"/>
            </span>
            <button type="button" class="btn btn-sm btn-outline-danger" t-on-click="onLogout">
                Cerrar sesión
            </button>
        </div>
    `;
    static props = {};

    setup() {
        this.operatorState = operatorState;
        this.actionService = useService("action");
        this.idleWatcher = useService("guapante_picking_idle_watcher");
    }

    // Mismo flujo que preparation_picking_badge_patch.js: parar el
    // watchdog antes de limpiar la sesión evita una carrera donde el
    // poll de los 30s alcanza a dispararse entre el clearOperator() y
    // el doAction de vuelta al NIP.
    async onLogout() {
        this.idleWatcher.stopWatching();
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
            clearBreadcrumbs: true,
        });
    }
}
