import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillStart, onWillUnmount } from "@odoo/owl";

import { clearOperator } from "@ist_preparation_day/js/preparation_operator_state";
import { PickingOperatorHeader } from "./preparation_picking_operator_header";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

// Nivel 2 de Picking (Fase C): kanban de las cajas de UNA plantilla ya
// asignada. Dos responsabilidades propias de este controller, ninguna de
// las dos es "refrescar la lista" (eso ya lo hace el model nativo al
// guardar cada tarjeta):
//
// 1) Plegar por default el grupo "Terminado" al montar — group.toggle()
//    es la API pública real para esto (no hay un campo `fold` disponible
//    al agrupar por un Selection, solo existe para Many2one vía un campo
//    `fold` en el modelo relacionado). No verificado todavía en
//    navegador real — queda marcado para que David lo confirme primero
//    (Tech Lead, Fase C, punto 5).
//
// 2) Suscribirse al mismo canal de bus que Nivel 1 y, al recibir
//    picking_operation_finished, cerrar la sesión de operario en el
//    SERVIDOR (clearOperator(), no solo el estado local de JS — Tech
//    Lead, Fase C, punto 4) y volver a la pantalla de NIP. Sin esto, la
//    sesión de un tablet que no fue el que hizo el último pesaje seguiría
//    viva en el servidor hasta el timeout de 5 minutos.
class PickingLinesKanbanController extends KanbanController {
    static template = "ist_preparation_day_picking.PickingLinesKanbanView";
    static components = {
        ...KanbanController.components,
        PickingOperatorHeader,
    };

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.busService = useService("bus_service");
        this.channel = null;
        this.onOperationFinished = this.onOperationFinished.bind(this);

        onWillStart(async () => {
            const wizardId = this.props.context.picking_wizard_id;
            if (wizardId) {
                this.channel = `guapante_preparation_day-${wizardId}`;
                await this.busService.addChannel(this.channel);
                this.busService.subscribe(
                    "picking_operation_finished", this.onOperationFinished,
                );
            }
        });
        onWillUnmount(() => {
            if (this.channel) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe(
                    "picking_operation_finished", this.onOperationFinished,
                );
            }
        });

        onMounted(() => {
            const doneGroup = this.model.root.groups?.find(
                (group) => group.value === "done",
            );
            if (doneGroup && !doneGroup.isFolded) {
                doneGroup.toggle();
            }
        });
    }

    async onOperationFinished() {
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
            clearBreadcrumbs: true,
        });
    }
}

registry.category("views").add("guapante_picking_lines_kanban", {
    ...kanbanView,
    Controller: PickingLinesKanbanController,
});
