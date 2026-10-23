import { Component, useState, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// Diálogo de "Agregar nota" del engrane de Nivel 2 (Fase D) — no hay
// widget nativo de "texto libre + chips de plantilla", así que se
// construye con el Dialog genérico de Odoo (mismo building block que
// usan AlertDialog/ConfirmationDialog por dentro), no un ir.actions.act_window
// propio. Los chips solo insertan texto en el textarea — el operario
// puede editarlo libre antes de guardar.
export class PickingNoteDialog extends Component {
    static template = xml`
        <Dialog title="'Agregar nota'">
            <div t-if="props.templates.length" class="d-flex flex-wrap gap-1 mb-2">
                <t t-foreach="props.templates" t-as="tpl" t-key="tpl.id">
                    <button type="button" class="btn btn-sm btn-outline-secondary"
                            t-on-click="() => this.onClickTemplate(tpl)">
                        <t t-esc="tpl.name"/>
                    </button>
                </t>
            </div>
            <textarea class="form-control" rows="4" placeholder="Escribe una nota…"
                      t-model="state.text"/>
            <t t-set-slot="footer">
                <button type="button" class="btn btn-primary" t-on-click="onConfirm">Guardar</button>
                <button type="button" class="btn btn-secondary" t-on-click="() => this.props.close()">Cancelar</button>
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        templates: Array,
        close: Function,
        onConfirm: Function,
    };

    setup() {
        this.state = useState({ text: "" });
    }

    onClickTemplate(tpl) {
        this.state.text = this.state.text
            ? `${this.state.text}\n${tpl.name}`
            : tpl.name;
    }

    onConfirm() {
        const text = this.state.text.trim();
        if (!text) {
            return;
        }
        this.props.onConfirm(text);
        this.props.close();
    }
}
