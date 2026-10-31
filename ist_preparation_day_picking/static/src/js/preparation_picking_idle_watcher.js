import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";

import { operatorState } from "@ist_preparation_day/js/preparation_operator_state";

// Cada cuánto se pregunta al servidor si el operario sigue activo. No es el
// timeout en sí (eso vive en el servidor, ver const_preparation.py) — es solo
// la frecuencia con la que el tablet se entera de que ya venció.
const POLL_INTERVAL_MS = 30000;

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

// Service (no componente): tiene que sobrevivir al cambio de acción dentro de
// Picking (de la pantalla de NIP al kanban, y más adelante entre nivel 1 y
// nivel 2) — un timer dentro del componente de la pantalla de NIP muere en
// cuanto ese componente se desmonta tras el handoff, justo cuando el
// operario empieza a trabajar (hallazgo de Tech Lead, Fase A).
export const pickingIdleWatcherService = {
    dependencies: ["action"],
    start(env, { action }) {
        let intervalId = null;

        function stopWatching() {
            if (intervalId) {
                browser.clearInterval(intervalId);
                intervalId = null;
            }
        }

        async function poll() {
            // refresh=False del lado del servidor (current_operator): esta
            // consulta es solo de lectura y no debe extender la ventana de
            // 5 minutos — si lo hiciera, el timeout nunca se cumpliría
            // mientras la pestaña siguiera preguntando.
            let result;
            try {
                result = await rpc(
                    "/web/guapante/preparation_day/current_operator", {},
                );
            } catch {
                // Wifi intermitente de bodega: un fallo de red acá no debe
                // abrir un diálogo de error cada 30s sobre el tablet — el
                // servidor sigue siendo la fuente de verdad del timeout,
                // así que simplemente se reintenta en el próximo ciclo
                // (hallazgo de Tech Lead).
                return;
            }
            if (!result.employee_id && operatorState.employeeId) {
                operatorState.employeeId = false;
                operatorState.employeeName = false;
                stopWatching();
                // Solo fuerza la vuelta a la pantalla de NIP si el operario
                // sigue dentro de Picking — si ya salió por otro lado
                // ("Descartar", navegación manual), no lo interrumpe en otra
                // pantalla del backend que esté usando. La marca de contexto
                // 'guapante_picking_flow' es la misma que usa write() en
                // ist_preparation_day para exigir operario activo — la
                // reutilizamos acá como señal de "sigo dentro de Picking"
                // porque cubre tanto la pantalla de NIP como el kanban (y,
                // en fases siguientes, nivel 1/nivel 2), a diferencia de
                // `action.tag`, que solo identifica la pantalla de NIP y ya
                // no aplica una vez hecho el handoff al kanban.
                const stillInPicking = Boolean(
                    action.currentController?.action?.context
                        ?.guapante_picking_flow
                );
                if (stillInPicking) {
                    action.doAction(PICKING_APP_ACTION_XMLID, {
                        clearBreadcrumbs: true,
                    });
                }
            }
        }

        return {
            startWatching() {
                if (!intervalId) {
                    intervalId = browser.setInterval(poll, POLL_INTERVAL_MS);
                }
            },
            stopWatching,
        };
    },
};

registry.category("services").add("guapante_picking_idle_watcher", pickingIdleWatcherService);
