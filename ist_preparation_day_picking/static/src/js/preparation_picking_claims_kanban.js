import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillUnmount } from "@odoo/owl";

import { clearOperator } from "@ist_preparation_day/js/preparation_operator_state";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

// Nivel 1 de Picking: kanban estándar (sin componente propio) agrupado por
// `status`. Un kanban nativo no se suscribe solo al bus — este js_class le
// agrega esa suscripción al controller, igual que LiveRefreshAnchor hace
// para el form de la sesión, pero a nivel de lista completa en vez de un
// campo-ancla. Con ~60 tarjetas como máximo (dato real de producción,
// Limón Tahity) un model.load() completo al recibir la notificación es
// más simple y suficientemente rápido — no vale la pena actualizar
// tarjeta por tarjeta (decisión de Tech Lead, Fase B).
class PickingClaimsKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.busService = useService("bus_service");
        this.channel = null;
        this.onBusNotif = this.onBusNotif.bind(this);
        this.onOperationFinished = this.onOperationFinished.bind(this);

        onWillStart(async () => {
            const wizardId = this.props.context.picking_wizard_id;
            if (wizardId) {
                this.channel = `guapante_preparation_day-${wizardId}`;
                await this.busService.addChannel(this.channel);
                this.busService.subscribe("picking_claim_updated", this.onBusNotif);
                this.busService.subscribe("reload", this.onBusNotif);
                // Fase C, punto 4 de Tech Lead: si la última caja de la
                // sesión se termina desde Nivel 2 mientras este tablet
                // sigue en Nivel 1, igual tiene que cerrar su sesión de
                // operario en el servidor y volver a la pantalla de NIP
                // — mismo manejo que preparation_picking_lines_kanban.js.
                this.busService.subscribe(
                    "picking_operation_finished", this.onOperationFinished,
                );
            }
        });
        onWillUnmount(() => {
            if (this.channel) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe("picking_claim_updated", this.onBusNotif);
                this.busService.unsubscribe("reload", this.onBusNotif);
                this.busService.unsubscribe(
                    "picking_operation_finished", this.onOperationFinished,
                );
            }
        });
    }

    onBusNotif() {
        this.model.load();
    }

    async onOperationFinished() {
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
            clearBreadcrumbs: true,
        });
    }
}

registry.category("views").add("guapante_picking_claims_kanban", {
    ...kanbanView,
    Controller: PickingClaimsKanbanController,
});
