import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { formatDuration } from "./preparation_picking_time_format";

// Pantalla A (PDS Operación) — Tech Lead, plan aprobado 2026-11-06.
// Solo lectura: sin acciones, sin ranking de personas (salvo el
// operario asignado por tarjeta, igual que Nivel 1). Mismo canal de
// bus que ya usa Nivel 1 (guapante_preparation_day-<sessionId>) y los
// mismos eventos de contenido (picking_claim_updated/reload); se le
// agrega el manejo de "reconnect" del propio bus_service (gap
// identificado en el análisis — ningún componente existente lo
// atendía) más un refresco de respaldo periódico, que también
// reevalúa a qué jornada corresponde mostrar (ajuste 2 de Tech Lead:
// _picking_session_date, no _current_session_date — ver
// get_pds_operacion_board_data en preparation_pds.py).

const STATUS_ORDER = ["pending", "in_progress", "stopped", "done"];
const STATUS_LABELS = {
    pending: "Por hacer",
    in_progress: "En progreso",
    stopped: "Detenido",
    done: "Terminado",
};

const BACKUP_REFRESH_MS = 30000;
const UPDATED_LABEL_TICK_MS = 1000;
const SESSION_EXPIRED_EXCEPTION = "odoo.http.SessionExpiredException";

export class PdsOperacionDisplay extends Component {
    static template = "ist_preparation_day_picking.PdsOperacionDisplay";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.statusOrder = STATUS_ORDER;
        this.statusLabels = STATUS_LABELS;
        this.state = useState({
            loaded: false,
            sessionExpired: false,
            hasSession: false,
            sessionId: null,
            sessionDate: null,
            totalLines: 0,
            doneLines: 0,
            pendingLines: 0,
            globalProgressPct: 0,
            columns: { pending: [], in_progress: [], stopped: [], done: [] },
            lastUpdatedLabel: "",
            // Indicadores de tiempo (solo lectura): reloj del navegador
            // corregido con server_now; se actualiza en el tick de 1 s.
            nowMs: Date.now(),
            clockOffsetMs: 0,
            stoppedAlertS: 1800,
        });
        this.isDestroyed = false;
        this.channel = null;
        this._lastUpdatedPerfNow = null;
        this._backupIntervalId = null;
        this._labelTickIntervalId = null;
        this.onBusNotif = this.onBusNotif.bind(this);
        this.onBusReconnect = this.onBusReconnect.bind(this);

        onWillStart(async () => {
            await this.loadBoardData();
            this.busService.addEventListener("reconnect", this.onBusReconnect);
            this._backupIntervalId = window.setInterval(() => {
                this.loadBoardData();
            }, BACKUP_REFRESH_MS);
            this._labelTickIntervalId = window.setInterval(() => {
                this._refreshUpdatedLabel();
            }, UPDATED_LABEL_TICK_MS);
        });
        onWillUnmount(() => {
            this.isDestroyed = true;
            if (this._backupIntervalId) {
                window.clearInterval(this._backupIntervalId);
            }
            if (this._labelTickIntervalId) {
                window.clearInterval(this._labelTickIntervalId);
            }
            this.busService.removeEventListener("reconnect", this.onBusReconnect);
            this._unsubscribeChannel();
        });
    }

    _subscribeChannel() {
        if (!this.state.sessionId) {
            return;
        }
        this.channel = `guapante_preparation_day-${this.state.sessionId}`;
        this.busService.addChannel(this.channel);
        this.busService.subscribe("picking_claim_updated", this.onBusNotif);
        this.busService.subscribe("reload", this.onBusNotif);
    }

    _unsubscribeChannel() {
        if (!this.channel) {
            return;
        }
        this.busService.deleteChannel(this.channel);
        this.busService.unsubscribe("picking_claim_updated", this.onBusNotif);
        this.busService.unsubscribe("reload", this.onBusNotif);
        this.channel = null;
    }

    onBusNotif() {
        if (this.isDestroyed) {
            return;
        }
        this.loadBoardData();
    }

    // Gap identificado en el análisis de PDS (ningún componente
    // existente lo atendía): tras una reconexión real del bus (el
    // monitor se durmió, se perdió la red un rato), se fuerza una
    // recarga completa en vez de esperar al próximo evento de
    // contenido — que puede no llegar nunca si nada cambió mientras
    // estuvo desconectado.
    onBusReconnect() {
        if (this.isDestroyed) {
            return;
        }
        this.loadBoardData();
    }

    async loadBoardData() {
        let data;
        try {
            data = await this.orm.call(
                "guapante.preparation.day", "get_pds_operacion_board_data", [],
            );
        } catch (error) {
            if (this.isDestroyed) {
                return;
            }
            // Aviso propio en pantalla (punto explícito de Tech Lead:
            // no el diálogo genérico de Odoo) — al estar atrapado acá,
            // nunca llega a ser una promesa rechazada sin manejar, así
            // que el errorService global nunca abre su propio diálogo.
            if (error?.exceptionName === SESSION_EXPIRED_EXCEPTION) {
                this.state.sessionExpired = true;
                return;
            }
            throw error;
        }
        if (this.isDestroyed) {
            return;
        }
        this.state.sessionExpired = false;
        if (data.server_now) {
            this.state.clockOffsetMs = Date.parse(data.server_now) - Date.now();
        }
        if (data.stopped_alert_s) {
            this.state.stoppedAlertS = data.stopped_alert_s;
        }
        this.state.hasSession = data.has_session;
        this.state.sessionDate = data.session_date;
        if (data.has_session) {
            const previousSessionId = this.state.sessionId;
            this.state.sessionId = data.session_id;
            this.state.totalLines = data.total_lines;
            this.state.doneLines = data.done_lines;
            this.state.pendingLines = data.pending_lines;
            this.state.globalProgressPct = data.global_progress_pct;
            this.state.columns = data.columns;
            if (previousSessionId !== data.session_id) {
                // Cambio de jornada (corte de _picking_session_date) —
                // re-suscribe al canal de bus de la nueva sesión.
                this._unsubscribeChannel();
                this._subscribeChannel();
            }
        } else {
            this.state.columns = { pending: [], in_progress: [], stopped: [], done: [] };
        }
        this.state.loaded = true;
        this._lastUpdatedPerfNow = performance.now();
        this._refreshUpdatedLabel();
    }

    // Segundos transcurridos en el estado actual de la tarjeta (null si el
    // servidor no pudo determinar el inicio: nunca se inventa un tiempo).
    elapsedSeconds(card) {
        if (!card.status_since) {
            return null;
        }
        return Math.max(
            (this.state.nowMs + this.state.clockOffsetMs - Date.parse(card.status_since)) / 1000,
            0,
        );
    }

    elapsedLabel(card) {
        const seconds = this.elapsedSeconds(card);
        return seconds === null ? "" : formatDuration(seconds);
    }

    // Alerta de Detenido: lleva detenido más que el umbral del servidor.
    isStoppedAlert(card, status) {
        const seconds = this.elapsedSeconds(card);
        return status === "stopped" && seconds !== null && seconds > this.state.stoppedAlertS;
    }

    _refreshUpdatedLabel() {
        this.state.nowMs = Date.now();
        if (!this._lastUpdatedPerfNow) {
            this.state.lastUpdatedLabel = "";
            return;
        }
        const seconds = Math.floor((performance.now() - this._lastUpdatedPerfNow) / 1000);
        this.state.lastUpdatedLabel = `Actualizado hace ${seconds}s`;
    }
}

registry.category("actions").add("guapante_pds_operacion", PdsOperacionDisplay);
