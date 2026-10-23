import { Component, useState, useRef, xml } from "@odoo/owl";

// Subcomponente aislado del peso de Nivel 2 (especificación visual,
// punto 1 de Tech Lead): sin Record detrás (client action propio, no
// kanban) — input numérico propio, Enter o "Confirmar" disparan
// onConfirm(valor). Acepta coma o punto decimal. El widget de báscula
// real (scale_weight) queda para su propia fase — este input es el
// punto donde se enchufará después, sin tocar el resto de la tarjeta.
export class PickingWeightInput extends Component {
    static template = xml`
        <div class="d-flex flex-column flex-grow-1 me-2">
            <input type="text"
                   inputmode="decimal"
                   class="form-control"
                   placeholder="Peso (kg)"
                   t-ref="weightInput"
                   t-model="state.text"
                   t-on-keydown="onKeydown"/>
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
        });
        this.weightInputRef = useRef("weightInput");
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.confirm();
        }
    }

    confirm() {
        const normalized = this.state.text.replace(",", ".").trim();
        const value = parseFloat(normalized);
        if (isNaN(value) || value <= 0) {
            this.state.error = "Ingresa un peso válido.";
            if (this.weightInputRef.el) {
                this.weightInputRef.el.focus();
            }
            return;
        }
        this.state.error = "";
        this.props.onConfirm(value);
    }
}
