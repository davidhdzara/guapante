import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

import { ScaleWeightField } from "@ist_preparation_day/js/preparation_list";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// Fase C, punto 1 de Tech Lead: el widget scale_weight es GENÉRICO — lo
// usa también la lista editable de Productos, fuera de Picking, donde
// Enter ya lo maneja la lista nativa (guarda y pasa a la fila siguiente).
// Por eso las dos extensiones de acá solo actúan cuando el record viene
// de Picking (record.context.guapante_picking_flow, la misma señal que
// ya usa el resto del proyecto) — fuera de Picking, onKeydown y
// _saveWeight se comportan exactamente como el no-op/guardado directo
// del padre, sin preventDefault ni interceptar nada.
//
// onKeydown y _saveWeight están separados en el padre (preparation_list.js)
// justo para esto: parchear solo esos dos métodos, nunca una copia de
// _poll() ni una reescritura del template completo — así este patch no
// se desincroniza si el padre cambia su lógica de báscula.
patch(ScaleWeightField.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
    },

    onKeydown(ev) {
        if (!this.props.record.context.guapante_picking_flow) {
            return super.onKeydown(ev);
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._saveWeight();
        }
    },

    async _saveWeight() {
        if (!this.props.record.context.guapante_picking_flow) {
            return super._saveWeight();
        }
        const record = this.props.record;
        const actualKg = record.data[this.props.name];
        const needsWeighing = record.data.needs_weighing;
        const expectedKgPerUnit = record.data.expected_kg_per_unit;
        if (needsWeighing && expectedKgPerUnit > 0) {
            const expectedWeight = record.data.estimated_kg * expectedKgPerUnit;
            const outOfRange = (
                actualKg > expectedWeight * 5 || actualKg < expectedWeight * 0.2
            );
            if (outOfRange) {
                const confirmed = await new Promise((resolve) => {
                    this.dialogService.add(ConfirmationDialog, {
                        title: "Peso fuera de lo usual",
                        body: (
                            `Para este producto se espera un peso cercano a ` +
                            `${expectedWeight.toFixed(3)} kg y se registraron ` +
                            `${actualKg.toFixed(3)} kg. ¿Confirmas que el peso ` +
                            `es correcto?`
                        ),
                        confirm: () => resolve(true),
                        cancel: () => resolve(false),
                    });
                });
                if (!confirmed) {
                    return;
                }
            }
        }
        await super._saveWeight();
    },
});
