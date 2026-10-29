import { Component, useState, useRef, xml } from "@odoo/owl";

// Subcomponente aislado del peso de Nivel 2 (especificación visual,
// punto 1 de Tech Lead): sin Record detrás (client action propio, no
// kanban) — input numérico propio + botón "Confirmar" visible, Enter
// dispara lo mismo. Acepta coma o punto como ÚNICO separador decimal
// (regla clara, Tech Lead 2026-10-29: nunca los dos juntos, nunca
// notación científica). El widget de báscula real (scale_weight) queda
// para su propia fase — este input es el punto donde se enchufará
// después, sin tocar el resto de la tarjeta.
const WEIGHT_PATTERN = /^\d+([.,]\d+)?$/;

export class PickingWeightInput extends Component {
    static template = xml`
        <div class="d-flex flex-column flex-grow-1 me-2">
            <div class="d-flex gap-1">
                <input type="text"
                       inputmode="decimal"
                       class="form-control"
                       placeholder="Peso (kg)"
                       t-ref="weightInput"
                       t-model="state.text"
                       t-att-disabled="state.submitting"
                       t-on-keydown="onKeydown"/>
                <button type="button"
                        class="btn btn-primary text-nowrap"
                        t-att-disabled="state.submitting"
                        t-on-click="confirm">Confirmar</button>
            </div>
            <span t-if="state.error" class="text-danger small"><t t-esc="state.error"/></span>
        </div>
    `;
    static props = {
        value: { type: Number, optional: true },
        onConfirm: Function,
    };

    setup() {
        this.state = useState({
            text: this.props.value ? String(this.props.value) : "",
            error: "",
            submitting: false,
        });
        this.weightInputRef = useRef("weightInput");
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.confirm();
        }
    }

    async confirm() {
        // Guarda contra doble Enter / doble clic (Tech Lead, 2026-10-29):
        // mientras un intento está en vuelo, cualquier otro disparo del
        // mismo evento es un no-op — un solo registro de peso aunque el
        // usuario dispare el evento dos veces.
        if (this.state.submitting) {
            return;
        }
        const normalized = this.state.text.trim().replace(",", ".");
        if (!WEIGHT_PATTERN.test(normalized)) {
            this.state.error = "Ingresa un peso válido (ej. 2.5 o 2,5).";
            if (this.weightInputRef.el) {
                this.weightInputRef.el.focus();
            }
            return;
        }
        const value = parseFloat(normalized);
        if (value <= 0) {
            this.state.error = "El peso debe ser mayor que cero.";
            if (this.weightInputRef.el) {
                this.weightInputRef.el.focus();
            }
            return;
        }
        this.state.error = "";
        this.state.submitting = true;
        try {
            await this.props.onConfirm(value);
        } finally {
            this.state.submitting = false;
        }
    }
}
