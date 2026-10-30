import { Component, useState, useRef, xml } from "@odoo/owl";

// Subcomponente aislado de cantidad/peso de Nivel 2 (especificación
// visual, punto 1 de Tech Lead; generalizado a unidades en el punto b,
// 2026-10-29): sin Record detrás (client action propio, no kanban) —
// input numérico propio + botón "Confirmar" visible, Enter dispara lo
// mismo. Dos modos por prop `integer`:
//   - false (default, kg): acepta coma o punto como ÚNICO separador
//     decimal (regla clara: nunca los dos juntos, nunca notación
//     científica).
//   - true (unidades): solo entero, sin separador — datos reales de
//     staging (2026-10-29) no muestran ninguna cantidad fraccionaria en
//     productos por unidad, así que se exige entero sin excepción.
// El widget de báscula real (scale_weight) queda para su propia fase —
// este input es el punto donde se enchufará después, sin tocar el
// resto de la tarjeta.
const DECIMAL_PATTERN = /^\d+([.,]\d+)?$/;
const INTEGER_PATTERN = /^\d+$/;

export class PickingWeightInput extends Component {
    static template = xml`
        <div class="d-flex flex-column flex-grow-1 me-2">
            <div class="d-flex gap-1">
                <input type="text"
                       t-att-inputmode="props.integer ? 'numeric' : 'decimal'"
                       class="form-control"
                       t-att-placeholder="props.placeholder || 'Peso (kg)'"
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
        integer: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
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
        // mismo evento es un no-op — un solo registro aunque el usuario
        // dispare el evento dos veces.
        if (this.state.submitting) {
            return;
        }
        const isInteger = Boolean(this.props.integer);
        const normalized = isInteger
            ? this.state.text.trim()
            : this.state.text.trim().replace(",", ".");
        const pattern = isInteger ? INTEGER_PATTERN : DECIMAL_PATTERN;
        if (!pattern.test(normalized)) {
            this.state.error = isInteger
                ? "Ingresa un número entero de unidades."
                : "Ingresa un peso válido (ej. 2.5 o 2,5).";
            if (this.weightInputRef.el) {
                this.weightInputRef.el.focus();
            }
            return;
        }
        const value = isInteger ? parseInt(normalized, 10) : parseFloat(normalized);
        if (value <= 0) {
            this.state.error = isInteger
                ? "Ingresa al menos 1 unidad."
                : "El peso debe ser mayor que cero.";
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
