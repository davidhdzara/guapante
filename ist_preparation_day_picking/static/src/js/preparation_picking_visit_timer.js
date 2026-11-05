/** @odoo-module **/

import {
    Component, useState, onWillStart, onWillUpdateProps, onMounted, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { deserializeDateTime } from "@web/core/l10n/dates";

import { formatDuration } from "./preparation_picking_time_format";

const TICK_MS = 1000;
// Mismo valor que RELOAD_DEBOUNCE_MS en preparation_picking_level2_display.js
// (Tech Lead, 2026-11-02) — el canal es de toda la sesión, varios
// 'reload' seguidos no deben disparar varias resincronizaciones.
const RESYNC_DEBOUNCE_MS = 400;

// Cronómetro de "visita actual" (lote 2B, Tech Lead 2026-11-04) —
// componente separado embebido en la barra de Nivel 2, mismo patrón
// que PickingOperatorHeader (preparation_picking_operator_header.js):
// no vive dentro de PickingLinesDisplay, se monta junto a ella.
//
// "Visita actual" = el intervalo 'working' abierto por ESTE operario
// sobre ESTE claim — nunca el acumulado histórico del claim (eso ya
// lo muestra el contador L1 del pie de tarjeta en Nivel 1).
//
// B cliente (Tech Lead, 2026-11-04): "← Productos" ya NO cierra el
// intervalo (se quitó action_close_my_interval y su llamada) — es
// navegación pura. Si el operario vuelve al mismo producto, sigue
// siendo el MISMO intervalo abierto: este cronómetro NO vuelve a
// 00:00, sigue corriendo desde la primera entrada (incluye el tiempo
// que estuvo navegando fuera de Nivel 2). Solo vuelve a 00:00 cuando
// se abre un intervalo de verdad nuevo (cambio de producto, cierre de
// sesión, etc. — ver preparation_interval.py).
//
// Ancla anti-drift: get_my_open_interval() da start_dt + server_now
// del servidor en el MISMO instante — el elapsed inicial se calcula
// una sola vez con esos dos valores. De ahí en adelante, el tick
// local usa performance.now() (reloj monótono, inmune a que el
// usuario/el sistema ajuste la hora de la tablet) solo para medir el
// delta desde la última resincronización — nunca vuelve a comparar
// contra `new Date()` de la tablet. Cada resync (bus 'reload'
// relevante, o la pestaña vuelve a primer plano) repite la misma
// lectura de servidor y mueve el ancla, así que un drift acumulado
// nunca sobrevive más que el intervalo entre dos resyncs.
export class PickingVisitTimer extends Component {
    static template = "ist_preparation_day_picking.PickingVisitTimer";
    static props = { claimId: Number };

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.state = useState({ hasOpenInterval: false, elapsedSeconds: 0 });
        this.isDestroyed = false;
        this._anchorElapsedSeconds = 0;
        this._anchorPerfNow = 0;
        this._tickIntervalId = null;
        this._resyncDebounceTimer = null;
        this.onVisibilityChange = this.onVisibilityChange.bind(this);
        this.onBusReload = this.onBusReload.bind(this);

        onWillStart(() => this._resync());
        // Defensa adicional (Tech Lead, revisión de 2/4): el padre
        // monta este componente solo con t-if="state.claimId" (nunca
        // debería recibir un claimId distinto en vida, Nivel 2 se
        // remonta entero al cambiar de producto), pero si algún día
        // cambiara de todos modos, resincroniza en vez de quedarse con
        // el intervalo del claim anterior.
        onWillUpdateProps((nextProps) => {
            if (nextProps.claimId !== this.props.claimId) {
                return this._resync(nextProps.claimId);
            }
        });
        onMounted(() => {
            this._tickIntervalId = window.setInterval(() => this._tick(), TICK_MS);
            document.addEventListener("visibilitychange", this.onVisibilityChange);
            // Suscripción propia, sin tocar addChannel/deleteChannel
            // (eso lo maneja PickingLinesDisplay, el padre, y este
            // componente solo vive mientras el padre vive) — subscribe
            // es por nombre de evento, no por canal: cualquier
            // 'reload' que llegue a la pestaña (el canal ya abierto
            // por el padre) dispara también este callback. No filtra
            // por relevancia como el padre (_checkForRelevantReload):
            // un resync de más es barato (una lectura) y el debounce
            // ya colapsa varios seguidos.
            this.busService.subscribe("reload", this.onBusReload);
        });
        onWillUnmount(() => {
            this.isDestroyed = true;
            if (this._tickIntervalId) {
                window.clearInterval(this._tickIntervalId);
            }
            if (this._resyncDebounceTimer) {
                window.clearTimeout(this._resyncDebounceTimer);
            }
            document.removeEventListener("visibilitychange", this.onVisibilityChange);
            this.busService.unsubscribe("reload", this.onBusReload);
        });
    }

    _tick() {
        if (this.isDestroyed || !this.state.hasOpenInterval) {
            return;
        }
        const elapsedSincePerfAnchor = (performance.now() - this._anchorPerfNow) / 1000;
        this.state.elapsedSeconds = this._anchorElapsedSeconds + elapsedSincePerfAnchor;
    }

    onBusReload() {
        if (this.isDestroyed) {
            return;
        }
        this._debouncedResync();
    }

    onVisibilityChange() {
        if (document.visibilityState === "visible") {
            this._debouncedResync();
        }
    }

    _debouncedResync() {
        if (this._resyncDebounceTimer) {
            window.clearTimeout(this._resyncDebounceTimer);
        }
        this._resyncDebounceTimer = window.setTimeout(() => {
            this._resyncDebounceTimer = null;
            this._resync();
        }, RESYNC_DEBOUNCE_MS);
    }

    async _resync(claimId = this.props.claimId) {
        if (!claimId) {
            this.state.hasOpenInterval = false;
            this.state.elapsedSeconds = 0;
            return;
        }
        let result;
        try {
            result = await this.orm.call(
                "guapante.preparation.day.product.claim", "get_my_open_interval",
                [[claimId]],
            );
        } catch {
            // El cronómetro es dato secundario (mismo criterio que
            // _run_isolated en el servidor) — un fallo de red acá
            // nunca debe romper Nivel 2; se queda con el último valor
            // conocido hasta el próximo resync.
            return;
        }
        if (this.isDestroyed) {
            return;
        }
        if (!result.start_dt) {
            this.state.hasOpenInterval = false;
            this.state.elapsedSeconds = 0;
            return;
        }
        // deserializeDateTime (core de Odoo): interpreta el string
        // naive como UTC, igual que hace el ORM en todo el proyecto —
        // nunca un parseo manual de fechas acá.
        const startMs = deserializeDateTime(result.start_dt).toMillis();
        const serverNowMs = deserializeDateTime(result.server_now).toMillis();
        this._anchorElapsedSeconds = Math.max(0, (serverNowMs - startMs) / 1000);
        this._anchorPerfNow = performance.now();
        this.state.hasOpenInterval = true;
        this.state.elapsedSeconds = this._anchorElapsedSeconds;
    }

    get displayValue() {
        return formatDuration(this.state.elapsedSeconds);
    }
}
