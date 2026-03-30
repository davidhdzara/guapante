/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

export class GuapantePreparationListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");

        onMounted(() => {
            // Escuchar el evento keydown de la tabla para capturar el Enter o Tab
            this.env.bus.addEventListener("keydown", this.onKeydown.bind(this));
        });
    }

    async onKeydown(ev) {
        if (ev.key === "Enter" || ev.key === "Tab") {
            const activeElement = document.activeElement;
            // Verificar si el Enter se presionó dentro de un input de "actual_kg"
            if (activeElement && activeElement.tagName === "INPUT" && activeElement.name === "actual_kg") {
                ev.preventDefault();
                ev.stopPropagation();

                // Encontrar el ID de la línea activa en la vista
                const row = activeElement.closest(".o_data_row");
                if (row) {
                    const recordId = row.dataset.id;
                    if (recordId) {
                        // Perder el foco para que Odoo actualice el estado del modelo local
                        activeElement.blur();
                        
                        // Guardar la vista superior (Wizard)
                        await this.model.root.save();
                        
                        // Opcional: Llamar la recarga del padre
                        this.actionService.doAction({ type: 'ir.actions.client', tag: 'reload' });
                    }
                }
            }
        }
    }
}

export const guapantePreparationListView = {
    ...listView,
    Controller: GuapantePreparationListController,
};

registry.category("views").add("guapante_preparation_list", guapantePreparationListView);
