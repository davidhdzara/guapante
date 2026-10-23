import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { xml } from "@odoo/owl";

import { ScaleWeightField } from "@ist_preparation_day/js/preparation_list";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// Fase C, punto 1 y 5 de Tech Lead: dos extensiones al widget scale_weight
// ya existente (genérico — también lo usa la pestaña Productos fuera de
// Picking), ambas puestas acá en vez de en el módulo padre porque solo
// aplican dentro del flujo de Nivel 2.
//
// 1) Guardar con Enter (tecleo manual, sin báscula): el widget original
//    solo auto-guarda cuando LA BÁSCULA entrega una lectura estable — no
//    hay forma de confirmar con Enter un peso tecleado a mano. Odoo no
//    deja inyectar un t-on-keydown en un template ya definido sin
//    reescribirlo entero (las plantillas de componentes OWL no soportan
//    herencia tipo vista XML) — por eso se reasigna ScaleWeightField.template
//    completo acá, con un único cambio: t-on-keydown en el div raíz.
//
// 2) Alerta de peso sospechoso (punto 1): antes de guardar — por Enter O
//    por báscula estable, los dos caminos pasan por _confirmAndSave() —
//    si needs_weighing y la plantilla tiene historia suficiente
//    (expected_kg_per_unit > 0, calculado en el claim, Fase C), se pide
//    confirmación nativa cuando el peso cae fuera de [0.2x, 5x] del
//    esperado (estimated_kg * expected_kg_per_unit). Sin historia
//    suficiente no hay alerta — nunca un valor inventado.
//
// El keydown-guarda-con-Enter es justo el tipo de cosa que solo se ve en
// un navegador real (teclado físico/numérico del tablet, foco del
// input dentro de una tarjeta kanban) — no verificado todavía, señalado
// para que David lo pruebe primero (Tech Lead, punto 5).
ScaleWeightField.template = xml`
    <div class="o_field_scale_weight" t-on-keydown="onKeydown">
        <div class="d-flex align-items-center gap-1">
            <div class="flex-grow-1 text-truncate">
                <FloatField t-props="floatFieldProps"/>
            </div>
            <button type="button"
                    t-attf-class="btn btn-sm p-1 {{ state.status === 'tracking' ? 'btn-primary' : 'btn-outline-secondary' }}"
                    t-att-disabled="props.readonly || !operatorState.employeeId"
                    t-on-click="onToggleTracking"
                    title="Tomar peso de báscula">
                <i class="fa fa-balance-scale" role="img" aria-label="Tomar peso"/>
            </button>
        </div>
        <div class="small" style="min-height: 1.2em; line-height: 1.2em;">
            <span t-if="state.status === 'tracking'" class="text-info">
                <t t-esc="trackingMessage"/>
            </span>
            <span t-elif="state.status === 'error'" class="text-danger">
                <t t-esc="state.message"/>
            </span>
            <span t-elif="!operatorState.employeeId" class="text-warning">
                <t t-esc="notIdentifiedMessage"/>
            </span>
            <span t-elif="!state.hasAttempted" class="text-muted">
                <t t-esc="firstUseHint"/>
            </span>
        </div>
    </div>
`;

patch(ScaleWeightField.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
    },

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._confirmAndSave();
        }
    },

    async _confirmAndSave() {
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
        await record.save();
    },

    // Copia completa de _poll() del padre, con un solo cambio: el guardado
    // final pasa por _confirmAndSave() en vez de record.save() directo —
    // OWL no da un punto de inyección a mitad de método, así que no hay
    // forma de envolver solo esa línea llamando a super._poll().
    async _poll() {
        let readings;
        try {
            readings = await this._fetchScales();
        } catch (error) {
            this._setError();
            return;
        }

        const reading = readings && readings[0];
        if (
            !reading ||
            reading.connection_status !== "CONNECTED" ||
            reading.weight === null ||
            reading.weight <= 0
        ) {
            this._setError();
            return;
        }

        if (reading.stable === "UNSTABLE") {
            this._stableReads = 0;
            this._lastWeight = reading.weight;
            await this.props.record.update({ [this.props.name]: reading.weight });
            return;
        }

        if (this._lastWeight !== null && reading.weight === this._lastWeight) {
            this._stableReads += 1;
        } else {
            this._stableReads = 1;
        }
        this._lastWeight = reading.weight;

        await this.props.record.update({ [this.props.name]: reading.weight });

        if (this._stableReads >= 2) { // STABLE_READS_REQUIRED en preparation_list.js
            this._stopPolling();
            await this._confirmAndSave();
            this.state.status = "idle";
            this.state.message = "";
        }
    },
});
