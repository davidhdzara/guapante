import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, useRef, onMounted, onWillStart, xml } from "@odoo/owl";

import { operatorState, ensureOperatorLoaded, identifyOperator } from "./preparation_operator_state";

class OperatorPinDialog extends Component {
    static template = xml`
        <Dialog title="'Identifícate con tu PIN'" size="'sm'">
            <div class="d-flex flex-column gap-2">
                <input type="password"
                       inputmode="numeric"
                       class="form-control"
                       t-ref="pinInput"
                       t-model="state.pin"
                       t-on-keydown="onKeydown"/>
                <span t-if="state.error" class="text-danger small"><t t-esc="state.error"/></span>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary" t-on-click="onConfirm">Confirmar</button>
                <button class="btn btn-secondary" t-on-click="() => this.props.close()">Cancelar</button>
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = { close: Function };

    setup() {
        this.state = useState({ pin: "", error: "" });
        this.pinInputRef = useRef("pinInput");
        onMounted(() => this.pinInputRef.el && this.pinInputRef.el.focus());
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.onConfirm();
        }
    }

    async onConfirm() {
        const result = await identifyOperator(this.state.pin);
        if (!result.success) {
            this.state.error = result.error || "PIN no reconocido.";
            this.state.pin = "";
            return;
        }
        this.props.close();
    }
}

class OperatorIdentificationBadge extends Component {
    static template = xml`
        <div class="o_guapante_operator_badge">
            <t t-if="operatorState.employeeName">
                <span class="badge text-bg-success px-3 py-2 me-1" style="font-size: 0.85rem;">
                    <i class="fa fa-id-badge"/> <t t-esc="operatorState.employeeName"/>
                </span>
                <button type="button" class="btn btn-sm btn-outline-secondary" t-on-click="openDialog">
                    Cambiar operario
                </button>
            </t>
            <t t-else="">
                <button type="button" class="btn btn-sm btn-warning fw-bold" t-on-click="openDialog">
                    <i class="fa fa-id-badge"/> Identificarme con PIN
                </button>
            </t>
        </div>
    `;
    static props = { ...standardFieldProps };

    setup() {
        this.operatorState = operatorState;
        this.dialogService = useService("dialog");
        onWillStart(() => ensureOperatorLoaded());
    }

    openDialog() {
        this.dialogService.add(OperatorPinDialog);
    }
}

registry.category("fields").add("guapante_operator_badge", { component: OperatorIdentificationBadge });
