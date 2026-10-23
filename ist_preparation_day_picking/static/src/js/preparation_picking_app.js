import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { Component, useState, useRef, onMounted, onWillStart, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { isDisplayStandalone } from "@web/core/browser/feature_detection";

import {
    operatorState,
    ensureOperatorLoaded,
    identifyOperator,
    clearOperator,
} from "@ist_preparation_day/js/preparation_operator_state";

// app_id = nombre técnico real del módulo: la implementación base de
// _get_scoped_app_icons/_get_scoped_app_name (web/controllers/webmanifest.py)
// ya resuelve ícono y nombre a partir del manifest del módulo sin hacer
// falta override de WebManifest (a diferencia de mrp_workorder, que usa un
// app_id que no es un módulo real y por eso sí necesita el override).
const SCOPED_APP_INSTALL_URL =
    "/scoped_app?app_id=ist_preparation_day_picking&path=scoped_app/picking&app_name=Picking";

// No existe un client action nativo para "volver a la grilla de
// Aplicaciones" (la grilla es un overlay interno del Navbar, no hay
// servicio público para abrirla desde un componente ajeno) — una
// navegación completa a la raíz del backend es la salida nativa más simple
// y además la más apropiada para "Descartar": limpia todo el estado de la
// SPA, igual que se espera al salir de una app de tablet compartida.
const BACKEND_ROOT_URL = "/odoo";

export class GuapantePickingApp extends Component {
    static template = xml`
        <div class="h-100 d-flex flex-column">
            <t t-if="!operatorState.employeeName">
                <div class="d-flex flex-column align-items-center justify-content-center flex-grow-1 gap-3 text-center">
                    <h2 class="mb-0">Picking</h2>
                    <p class="text-muted mb-0">Ingresa tu NIP para identificarte</p>
                    <div style="width: min(320px, 90vw);">
                        <input type="password"
                               inputmode="numeric"
                               autocomplete="off"
                               class="form-control form-control-lg text-center"
                               t-ref="pinInput"
                               t-model="state.pin"
                               t-on-keydown="onKeydown"/>
                    </div>
                    <span t-if="state.error" class="text-danger small"><t t-esc="state.error"/></span>
                    <button class="btn btn-primary btn-lg" t-on-click="onConfirm">Confirmar</button>
                    <a t-if="!isStandalone" class="small" t-att-href="installUrl" target="_blank">
                        Instalar aplicación
                    </a>
                    <button class="btn btn-link btn-sm text-muted" t-on-click="onDiscard">Descartar</button>
                </div>
            </t>
            <t t-else="">
                <div class="d-flex align-items-center justify-content-between p-2 border-bottom">
                    <span>
                        <i class="fa fa-id-badge me-1"/>
                        <t t-esc="operatorState.employeeName"/>
                    </span>
                    <button class="btn btn-sm btn-outline-danger" t-on-click="onLogout">
                        Cerrar sesión
                    </button>
                </div>
                <div class="flex-grow-1 d-flex align-items-center justify-content-center">
                    <span class="text-muted">Cargando Picking…</span>
                </div>
            </t>
        </div>
    `;
    static props = { "*": true };

    setup() {
        this.state = useState({ pin: "", error: "" });
        this.operatorState = operatorState;
        this.pinInputRef = useRef("pinInput");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.idleWatcher = useService("guapante_picking_idle_watcher");
        this.isStandalone = isDisplayStandalone();
        this.installUrl = SCOPED_APP_INSTALL_URL;

        onWillStart(async () => {
            // refresh=False (current_operator es consulta): si ya había un
            // operario activo (ej. la pestaña se refrescó a mitad de
            // turno, todavía dentro de los 5 minutos), se salta la
            // pantalla de NIP y entra directo — el timeout es sobre
            // inactividad real, no sobre refrescar la página.
            await ensureOperatorLoaded();
            if (operatorState.employeeName) {
                this.idleWatcher.startWatching();
                await this.handoff();
            }
        });
        onMounted(() => {
            if (!operatorState.employeeName && this.pinInputRef.el) {
                this.pinInputRef.el.focus();
            }
        });
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
            if (this.pinInputRef.el) {
                this.pinInputRef.el.focus();
            }
            return;
        }
        this.state.error = "";
        this.idleWatcher.startWatching();
        await this.handoff();
    }

    async handoff() {
        // Resuelve a qué sesión entra: la del contexto (botón "Picking" del
        // form, sesión puntual) o la de hoy (ícono/menú de la app) — toda
        // la lógica vive en el método del modelo, acá solo se dispara.
        const action = await this.orm.call(
            "guapante.preparation.day",
            "action_resolve_picking_handoff",
            [],
            { context: this.props.context || {} },
        );
        await this.actionService.doAction(action, { clearBreadcrumbs: true });
    }

    async onLogout() {
        this.idleWatcher.stopWatching();
        await clearOperator();
    }

    onDiscard() {
        this.idleWatcher.stopWatching();
        browser.location.href = BACKEND_ROOT_URL;
    }
}

registry.category("actions").add("guapante_picking_app", GuapantePickingApp);
