import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { Component, useState, useRef, onMounted, onWillStart, onWillUnmount, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import {
    operatorState,
    ensureOperatorLoaded,
    identifyOperator,
} from "@ist_preparation_day/js/preparation_operator_state";
import { PickingInstallMenu } from "./preparation_picking_install_menu";

// Ícono de Picking servido como archivo estático del módulo — mismo
// archivo que usa /scoped_app para la página de instalación
// (_get_scoped_app_icons, web/controllers/webmanifest.py).
const ICON_URL = "/ist_preparation_day_picking/static/description/icon.svg";
// /logo.png: ruta nativa y pública (web/controllers/binary.py,
// company_logo) para el logo de la compañía activa — la misma que usa
// cualquier pantalla de login de Odoo, sin necesitar el id de la
// compañía ni autenticación.
const COMPANY_LOGO_URL = "/logo.png";

// No existe un client action nativo para "volver a la grilla de
// Aplicaciones" (la grilla es un overlay interno del Navbar, no hay
// servicio público para abrirla desde un componente ajeno) — una
// navegación completa a la raíz del backend es la salida nativa más simple
// y además la más apropiada para "Descartar": limpia todo el estado de la
// SPA, igual que se espera al salir de una app de tablet compartida.
const BACKEND_ROOT_URL = "/odoo";

export class GuapantePickingApp extends Component {
    // Especificación visual (David, 2026-10-23, punto 9): misma
    // estructura que la página de instalación del PWA
    // (web/static/src/core/install_scoped_app/install_scoped_app.xml) —
    // fondo o_home_menu_background, ícono en recuadro blanco
    // (rounded-4 p-4 bg-white shadow), título h1, botón redondeado como
    // el "Install" de esa página. Reloj/fecha arriba a la izquierda y
    // logo de la compañía arriba a la derecha, como
    // point_of_sale/.../login_screen.xml — sin reutilizar sus clases
    // CSS propias (login-overlay, o_attendance_background, timer-*):
    // reloj propio chico con solo clases Bootstrap, para no traer una
    // dependencia de estilos de otro módulo. Solo clases nativas, cero
    // CSS propio.
    static template = xml`
        <div class="o_home_menu_background h-100 w-100 d-flex flex-column user-select-none">
            <div class="d-flex justify-content-between align-items-start p-3">
                <div class="d-flex align-items-center gap-2">
                    <span class="fs-1" t-esc="clockState.time"/>
                    <div class="d-flex flex-column small">
                        <span t-esc="clockState.day"/>
                        <span t-esc="clockState.date"/>
                    </div>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <PickingInstallMenu/>
                    <img t-att-src="companyLogoUrl" style="height:40px;" alt="Logo"/>
                </div>
            </div>
            <t t-if="!operatorState.employeeName">
                <div class="flex-grow-1 d-flex align-items-center justify-content-center">
                    <div class="d-flex flex-column align-items-center justify-content-center gap-3 text-center">
                        <img style="height:100px;width:100px;" class="rounded-4 p-4 bg-white shadow" t-att-src="iconUrl" alt="Picking"/>
                        <h1 class="mb-0">Picking</h1>
                        <p class="text-muted mb-0">Ingresa tu NIP para identificarte</p>
                        <div style="width: min(320px, 90vw);">
                            <input type="password"
                                   inputmode="numeric"
                                   autocomplete="off"
                                   class="form-control form-control-lg text-center rounded-5 shadow-sm bg-white"
                                   t-ref="pinInput"
                                   t-model="state.pin"
                                   t-on-keydown="onKeydown"/>
                        </div>
                        <span t-if="state.error" class="text-danger small"><t t-esc="state.error"/></span>
                        <button class="btn btn-primary btn-lg rounded-5 shadow py-2 px-3" t-on-click="onConfirm">Confirmar</button>
                        <button class="btn btn-link btn-sm text-muted" t-on-click="onDiscard">Descartar</button>
                    </div>
                </div>
            </t>
            <t t-else="">
                <div class="flex-grow-1 d-flex align-items-center justify-content-center">
                    <span class="text-muted">Cargando Picking…</span>
                </div>
            </t>
        </div>
    `;
    static components = { PickingInstallMenu };
    static props = { "*": true };

    setup() {
        this.state = useState({ pin: "", error: "" });
        this.clockState = useState({ time: "", day: "", date: "" });
        this.operatorState = operatorState;
        this.pinInputRef = useRef("pinInput");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.idleWatcher = useService("guapante_picking_idle_watcher");
        this.iconUrl = ICON_URL;
        this.companyLogoUrl = COMPANY_LOGO_URL;

        onWillStart(async () => {
            // Solo carga datos acá (ensureOperatorLoaded es un RPC de
            // consulta) — Owl espera a que onWillStart resuelva antes del
            // primer render, así que para cuando se pinta la pantalla ya
            // se sabe si hay operario activo o no, sin parpadeo. Lo que NO
            // va acá es el handoff (doAction): hacerlo desde onWillStart es
            // reentrante con el action service, que todavía está montando
            // esta misma acción (hallazgo de Tech Lead) — el doAction real
            // se dispara en onMounted, una vez el componente ya montó.
            await ensureOperatorLoaded();
        });
        onMounted(() => {
            this._tickClock();
            this._clockTimer = browser.setInterval(() => this._tickClock(), 30000);
            if (operatorState.employeeName) {
                this.idleWatcher.startWatching();
                this.handoff();
            } else if (this.pinInputRef.el) {
                this.pinInputRef.el.focus();
            }
        });
        onWillUnmount(() => {
            if (this._clockTimer) {
                browser.clearInterval(this._clockTimer);
            }
        });
    }

    _tickClock() {
        const now = new Date();
        this.clockState.time = now.toLocaleTimeString("es-CO", {
            hour: "2-digit", minute: "2-digit",
        });
        this.clockState.day = now.toLocaleDateString("es-CO", { weekday: "long" });
        this.clockState.date = now.toLocaleDateString("es-CO", {
            day: "numeric", month: "long",
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
        //
        // El contexto de un client action NO llega como this.props.context
        // — los props de la acción son {...options.props, action, actionId}
        // (action_service.js, _getActionInfo), así que el contexto vive en
        // this.props.action.context (hallazgo de Tech Lead: con
        // this.props.context, picking_session_id nunca llegaba al servidor
        // y el botón del form siempre terminaba abriendo "hoy").
        // action_resolve_picking_handoff ahora devuelve directo el dict
        // de ir.actions.client de Nivel 1 (especificación visual,
        // 2026-10-23) — ya no hace falta pasar un xmlid string a
        // doAction() para forzar el camino de markup() de 'help': ese
        // bug era específico de un campo Html de ir.actions.act_window,
        // que un client action no tiene.
        const result = await this.orm.call(
            "guapante.preparation.day",
            "action_resolve_picking_handoff",
            [],
            { context: this.props.action?.context || {} },
        );
        await this.actionService.doAction(result, { clearBreadcrumbs: true });
    }

    onDiscard() {
        this.idleWatcher.stopWatching();
        browser.location.href = BACKEND_ROOT_URL;
    }
}

registry.category("actions").add("guapante_picking_app", GuapantePickingApp);
