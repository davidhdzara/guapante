/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

// PDS administrativo (Pantalla B), ENTREGA 2 — David/Tech Lead, 2026-11-10.
// Monta la View NATIVA de un reporte de Fase 2 (la acción que indica
// context.pds_action_xmlid: «Pickings por operario» o «Tiempo por
// operario») a pantalla completa y la re-monta cada N minutos (N lo da
// get_pds_admin_refresh_minutes, parámetro de sistema, mínimo 1). Solo
// lectura. Re-montar reinicia los filtros a los de la acción: es una
// pantalla de seguimiento, no de análisis.
//
// Cada vuelta llama a get_pds_admin_refresh_minutes: además de leer el
// intervalo vigente, sirve de sonda de sesión. Si el servidor responde
// SessionExpiredException se DETIENE el temporizador y se avisa — no se
// reintenta a ciegas. El temporizador se limpia siempre en onWillUnmount.

const SESSION_EXPIRED_EXCEPTION = "odoo.http.SessionExpiredException";

export class PdsAdminBoard extends Component {
    static template = "ist_preparation_day_picking.PdsAdminBoard";
    static components = { View };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loaded: false,
            sessionExpired: false,
            error: false,
            tick: 0,
            minutes: 5,
            updatedAt: "",
        });
        this._timerId = null;
        this._report = null;
        // La View hija no debe heredar el actionId/actionType de esta client
        // action (activaría entradas de cogMenu ajenas), igual que en
        // preparation_day_productos_embedder.js.
        useSubEnv({
            config: { ...this.env.config, actionId: false, actionType: false },
        });
        onWillStart(async () => {
            const xmlid = this.props.action?.context?.pds_action_xmlid;
            this._report = await this.actionService.loadAction(xmlid);
            this.state.minutes = await this.orm.call(
                "guapante.preparation.day", "get_pds_admin_refresh_minutes", [],
            );
            this._stamp();
            this.state.loaded = true;
        });
        onMounted(() => this._schedule());
        onWillUnmount(() => this._stop());
    }

    get viewProps() {
        const action = this._report;
        const viewType = action.views.find((v) => v[1] !== "search")[1];
        let groupBy = action.context?.group_by || [];
        if (typeof groupBy === "string") {
            groupBy = [groupBy];
        }
        return {
            type: viewType,
            resModel: action.res_model,
            views: action.views,
            context: action.context || {},
            domain: action.domain || [],
            groupBy,
            loadIrFilters: true,
            loadActionMenus: false,
            display: { mode: "fullscreen" },
        };
    }

    _stamp() {
        const now = new Date();
        this.state.updatedAt = now.toLocaleTimeString("es-CO", {
            hour: "2-digit", minute: "2-digit",
        });
    }

    _schedule() {
        this._stop();
        this._timerId = window.setInterval(() => this._refresh(), this.state.minutes * 60000);
    }

    _stop() {
        if (this._timerId !== null) {
            window.clearInterval(this._timerId);
            this._timerId = null;
        }
    }

    async _refresh() {
        try {
            const minutes = await this.orm.call(
                "guapante.preparation.day", "get_pds_admin_refresh_minutes", [],
            );
            this.state.error = false;
            this.state.tick += 1;
            this._stamp();
            if (minutes !== this.state.minutes) {
                this.state.minutes = minutes;
                this._schedule();
            }
        } catch (error) {
            if (error?.exceptionName === SESSION_EXPIRED_EXCEPTION) {
                this._stop();
                this.state.sessionExpired = true;
            } else {
                // Fallo transitorio (red, servidor): se conserva lo que ya
                // se ve y se reintenta en la siguiente vuelta.
                this.state.error = true;
            }
        }
    }
}

registry.category("actions").add("guapante_pds_admin", PdsAdminBoard);
