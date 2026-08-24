import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { Component, xml, useState } from "@odoo/owl";

// Puerto por convención fija (Backend/Tech Lead, Fase 8 del proyecto Guapante Scale Agent) — el
// Agent solo escucha en 127.0.0.1, sin puerto público. No hay ir.config_parameter para esto:
// la decisión de Fase 9 fue no persistir nada de básculas del lado de Odoo.
const SCALE_AGENT_URL = "http://127.0.0.1:8787";
// 15s, no 3s: la primera vez por sesión de Chrome, el fetch queda pendiente hasta que el
// operario acepta el prompt nativo de "Local Network Access" — confirmado en staging_dev real
// (David, 2026-08-24). Un timeout corto cortaba ese fetch como si fuera un error.
const FETCH_TIMEOUT_MS = 15000;
const ERROR_MESSAGE =
    "No se pudo leer la báscula. Verifica que el Agent esté corriendo y que el " +
    "navegador tenga permiso de red local.";
const FIRST_USE_HINT =
    "La primera vez, Chrome puede pedir permiso de acceso a la red local — acéptalo " +
    "para que funcione.";

class ScaleWeightField extends Component {
    static template = xml`
        <div class="o_field_scale_weight">
            <div class="d-flex align-items-center gap-1">
                <FloatField t-props="props"/>
                <button type="button"
                        class="btn btn-sm btn-outline-secondary p-1"
                        t-att-disabled="isButtonDisabled"
                        t-on-click="onTakeWeight"
                        title="Tomar peso de báscula">
                    <i class="fa fa-balance-scale" role="img" aria-label="Tomar peso"/>
                </button>
            </div>
            <div class="small" style="min-height: 1.2em; line-height: 1.2em;">
                <span t-if="state.message"
                      t-attf-class="{{ state.status === 'error' ? 'text-danger' : 'text-muted' }}">
                    <t t-esc="state.message"/>
                </span>
                <span t-elif="!state.hasAttempted" class="text-muted">
                    <t t-esc="firstUseHint"/>
                </span>
            </div>
        </div>
    `;
    static components = { FloatField };
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ status: "idle", message: "", hasAttempted: false });
        this.firstUseHint = FIRST_USE_HINT;
    }

    get isButtonDisabled() {
        return this.state.status === "loading" || this.props.readonly;
    }

    async onTakeWeight() {
        this.state.status = "loading";
        this.state.message = "";
        this.state.hasAttempted = true;

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
            this.state.status = "error";
            this.state.message = "El peso todavía no se estabiliza — espera e intenta de nuevo.";
            return;
        }

        // stable === "STABLE" o "UNKNOWN" (ej. HY918, que no reporta estabilidad) — aceptar.
        await this.props.record.update({ [this.props.name]: reading.weight });
        // Mismo camino de guardado que el tecleo manual + Enter en la lista editable:
        // dispara write() -> PreparationDayLine.write() -> action_save_line_weight(), con
        // todo el blindaje ya existente (is_weight_confirmed, propagación, gate de validación).
        await this.props.record.save();

        this.state.status = "idle";
        this.state.message = "";
    }

    _setError() {
        this.state.status = "error";
        this.state.message = ERROR_MESSAGE;
    }

    async _fetchScales() {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
        try {
            const response = await fetch(`${SCALE_AGENT_URL}/scales`, {
                method: "GET",
                mode: "cors",
                credentials: "omit",
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`Scale Agent respondió ${response.status}`);
            }
            return response.json();
        } finally {
            clearTimeout(timeout);
        }
    }
}

registry.category("fields").add("scale_weight", { ...floatField, component: ScaleWeightField });
