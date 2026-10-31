import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

import { OperatorIdentificationBadge } from "@ist_preparation_day/js/preparation_operator_badge";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

// El badge de identificación (preparation_operator_badge.js, genérico —
// también lo usa el wizard fuera de Picking) vive dentro del kanban al que
// se hace handoff, no en la pantalla de NIP, que ya se desmontó. Sin este
// patch, "Cerrar sesión" ahí limpia el operario pero no detiene el watchdog
// ni devuelve al tablet a la pantalla de NIP — el flujo del plan (Cerrar
// sesión → pantalla de NIP) quedaría roto (hallazgo de Tech Lead, Fase A).
//
// El parche solo actúa cuando el contexto de la acción activa trae
// 'guapante_picking_flow' — fuera de Picking (ej. el campo
// operator_identification del wizard) el badge se comporta exactamente
// igual que antes.
patch(OperatorIdentificationBadge.prototype, {
    setup() {
        super.setup();
        this.pickingActionService = useService("action");
        this.pickingIdleWatcher = useService("guapante_picking_idle_watcher");
    },

    async onLogout() {
        const inPickingFlow = Boolean(
            this.pickingActionService.currentController?.action?.context
                ?.guapante_picking_flow
        );
        await super.onLogout();
        if (inPickingFlow) {
            this.pickingIdleWatcher.stopWatching();
            await this.pickingActionService.doAction(PICKING_APP_ACTION_XMLID, {
                clearBreadcrumbs: true,
            });
        }
    },
});
