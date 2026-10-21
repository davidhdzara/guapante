import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { Component, xml, useState, onWillUnmount } from "@odoo/owl";

// Puerto por convención fija (Backend/Tech Lead, Fase 8 del proyecto Guapante Scale Agent) — el
// Agent solo escucha en 127.0.0.1, sin puerto público. No hay ir.config_parameter para esto:
// la decisión de Fase 9 fue no persistir nada de básculas del lado de Odoo.
const SCALE_AGENT_URL = "http://127.0.0.1:8787";
// 15s, no 3s: la primera vez por sesión de Chrome, el fetch queda pendiente hasta que el
// operario acepta el prompt nativo de "Local Network Access" — confirmado en staging_dev real
// (David, 2026-08-24). Un timeout corto cortaba ese fetch como si fuera un error.
const FETCH_TIMEOUT_MS = 15000;
const LIVE_POLL_INTERVAL_MS = 1000;
// Cuántas lecturas seguidas e iguales hacen falta para considerar el peso "quieto" y
// auto-guardar. Aplica igual a básculas que sí reportan estabilidad (CPB9) y a las que no
// (HY918, ver criterio en _poll()) — evita comprometerse a la primera lectura por si es un
// frame espurio.
const STABLE_READS_REQUIRED = 2;

const ERROR_MESSAGE =
    "No se pudo leer la báscula. Verifica que el Agent esté corriendo y que el " +
    "navegador tenga permiso de red local.";
const TRACKING_MESSAGE = "Leyendo en vivo — deja el producto quieto para que se guarde solo.";
const FIRST_USE_HINT =
    "La primera vez, Chrome puede pedir permiso de acceso a la red local — acéptalo " +
    "para que funcione.";

class ScaleWeightField extends Component {
    static template = xml`
        <div class="o_field_scale_weight">
            <div class="d-flex align-items-center gap-1">
                <div class="flex-grow-1 text-truncate">
                    <FloatField t-props="floatFieldProps"/>
                </div>
                <button type="button"
                        t-attf-class="btn btn-sm p-1 {{ state.status === 'tracking' ? 'btn-primary' : 'btn-outline-secondary' }}"
                        t-att-disabled="props.readonly"
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
        this.trackingMessage = TRACKING_MESSAGE;
        this.firstUseHint = FIRST_USE_HINT;
        this._pollTimer = null;
        this._lastWeight = null;
        this._stableReads = 0;
        onWillUnmount(() => this._stopPolling());
    }

    get floatFieldProps() {
        return {
            ...this.props,
            readonly: this.props.readonly || this.state.status === "tracking",
        };
    }

    onToggleTracking() {
        if (this.state.status === "tracking") {
            this._stopPolling();
            this.state.status = "idle";
            return;
        }

        this.state.hasAttempted = true;
        this.state.status = "tracking";
        this.state.message = "";
        this._lastWeight = null;
        this._stableReads = 0;

        this._poll();
        this._pollTimer = setInterval(() => this._poll(), LIVE_POLL_INTERVAL_MS);
    }

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

        // stable === "STABLE" (ej. CPB9) o "UNKNOWN" (ej. HY918, que no reporta estabilidad):
        // en ambos casos, la única señal honesta de "se quedó quieto" es que el valor no haya
        // cambiado entre lecturas consecutivas — no se inventa estabilidad que el hardware no
        // entrega (mismo principio que WeightStability en Fase 3).
        if (this._lastWeight !== null && reading.weight === this._lastWeight) {
            this._stableReads += 1;
        } else {
            this._stableReads = 1;
        }
        this._lastWeight = reading.weight;

        await this.props.record.update({ [this.props.name]: reading.weight });

        if (this._stableReads >= STABLE_READS_REQUIRED) {
            this._stopPolling();
            // Mismo camino de guardado que el tecleo manual + Enter en la lista editable:
            // dispara write() -> PreparationDayLine.write() -> action_save_line_weight(), con
            // todo el blindaje ya existente (is_weight_confirmed, propagación, gate de
            // validación).
            await this.props.record.save();
            this.state.status = "idle";
            this.state.message = "";
        }
    }

    _setError() {
        this._stopPolling();
        this.state.status = "error";
        this.state.message = ERROR_MESSAGE;
    }

    _stopPolling() {
        if (this._pollTimer !== null) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
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
