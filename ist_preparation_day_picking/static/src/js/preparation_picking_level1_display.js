import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import {
    clearOperator,
    ensureOperatorLoaded,
    operatorState,
} from "@ist_preparation_day/js/preparation_operator_state";
import { PickingOperatorHeader } from "./preparation_picking_operator_header";
import { PickingInstallMenu } from "./preparation_picking_install_menu";
import { PickingClaimGearMenu } from "./preparation_picking_claim_menu";
import { normalizeSearchText } from "./preparation_picking_search_utils";
import { formatDuration } from "./preparation_picking_time_format";

// Contadores L1 (lote 2B, Tech Lead 2026-11-04): un único reloj
// compartido para TODAS las tarjetas, no un setInterval por tarjeta
// (podrían ser decenas tiqueando a la vez). tickCount vive en
// state solo para que las tarjetas que lo leen (getLiveCounterLabel)
// vuelvan a renderizar cada segundo — su valor no se usa para nada
// más que esa dependencia reactiva.
const L1_COUNTER_TICK_MS = 1000;

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

const STATUS_ORDER = ["pending", "in_progress", "stopped", "done"];
const STATUS_LABELS = {
    pending: "Pendiente",
    in_progress: "En progreso",
    stopped: "Detenido",
    done: "Terminado",
};
// orm.searchRead() de un campo Selection devuelve la clave cruda
// ('sin_stock'), no la etiqueta — a diferencia del <field> de kanban,
// que la traducía solo (bug real encontrado en la verificación de
// navegador, David 2026-10-23: la tarjeta de Detenido mostraba
// "sin_stock" en vez de "Sin stock"). Mismas claves que STOP_REASONS
// en preparation_day_product_claim.py.
const STOP_REASON_LABELS = {
    sin_stock: "Sin stock",
    mal_estado: "Producto en mal estado",
    esperando_proveedor: "Esperando proveedor",
    otro: "Otro",
};

// Nivel 1 de Picking como client action propio (especificación visual,
// David 2026-10-23 — decisión final tras dos rondas con un kanban
// nativo + t-inherit que nunca igualó la tarjeta/barra de Taller real:
// el envoltorio o_kanban_record del kanban no se podía quitar). Mismo
// Layout/slots que ya se habían validado para la barra; la tarjeta
// copia la ESTRUCTURA de mrp_workorder.MrpDisplayRecord (sin copiar
// archivos — licencia OEEL-1, mrp_workorder solo se agrega a depends
// para reusar sus clases/SCSS).
//
// La lógica de servidor (Fase A-C: claims, ownership, bus) no cambia —
// este componente lee con orm.searchRead/orm.read y llama los MISMOS
// métodos Python que ya existían, interpretando yo el resultado en vez
// de que lo haga el framework de kanban.
export class PickingClaimsDisplay extends Component {
    static template = "ist_preparation_day_picking.PickingClaimsDisplay";
    static components = { PickingOperatorHeader, PickingInstallMenu, PickingClaimGearMenu };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.busService = useService("bus_service");
        this.pwaService = useService("pwa");
        this.dialog = useService("dialog");
        this.statusOrder = STATUS_ORDER;
        this.statusLabels = STATUS_LABELS;
        this.stopReasonLabels = STOP_REASON_LABELS;
        this.state = useState({
            wizardId: null,
            hasLines: false,
            claims: [],
            // Terminado y Detenido empiezan plegados (Tech Lead,
            // 2026-11-02 — un Detenido escondido sin pista de que
            // existe sería un riesgo operativo, por eso el encabezado
            // SIEMPRE muestra el contador "Detenido (N)" con el mismo
            // chevron clickeable, plegado o no). Pendiente/En progreso
            // nunca entran acá — toggleGroup() las deja siempre
            // expandidas porque el objeto solo trae estas dos claves.
            foldedGroups: { done: true, stopped: true },
            searchText: "",
            // "Mis productos + Pendientes" / "Todos" (E3, David/Tech
            // Lead, 2026-11-02 — reemplaza el toggle anterior
            // "Mis productos"/"Todos"): arranca en la vista restringida
            // (false) — a diferencia del toggle viejo, ESTA vista nunca
            // deja la pantalla vacía (los Pendientes siempre entran), así
            // que ya no hace falta arrancar en "Todos" para que el
            // operario pueda tomar un producto sin tocar nada. "Todos"
            // (true) muestra TODO sin filtrar, incluido En progreso ajeno,
            // sin atenuar — nadie tiene nada que no pueda ver (E1/E3). No
            // se recuerda entre sesiones — siempre arranca restringida.
            showAllClaims: false,
            loaded: false,
            tickCount: 0,
        });
        // Punto (a), heredado de la implementación kanban: nunca tocar
        // el estado tras desmontar.
        this.isDestroyed = false;
        this.channel = null;
        this.onBusNotif = this.onBusNotif.bind(this);
        this.onOperationFinished = this.onOperationFinished.bind(this);
        // Ancla del reloj compartido: performance.now() en el instante
        // en que state.claims se llenó por última vez (loadRecords) —
        // nunca el reloj de la tablet. getLiveCounterLabel() suma el
        // delta desde esta ancla a claim.time_working_s/time_stopped_s
        // (ya calculados por el servidor hasta ESE instante).
        this._claimsLoadedPerfNow = performance.now();
        this._tickIntervalId = null;

        onWillStart(async () => {
            // Punto 3 (Tech Lead, 2026-10-31): sin operario identificado
            // (sesión vencida, "Cerrar" en otra pestaña, F5 directo a
            // esta URL) no se monta Nivel 1 — se vuelve a la pantalla de
            // NIP de una vez, sin esperar los 30s del idle watcher.
            // doAction a OTRA acción (guapante_picking_app, no esta
            // misma) desde onWillStart no es reentrante — mismo patrón
            // ya probado en _backToLevel1() de Nivel 2.
            await ensureOperatorLoaded();
            if (!operatorState.employeeName) {
                await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
                    clearBreadcrumbs: true,
                });
                return;
            }
            await this._resolveWizard();
            await this.loadRecords();
            if (this.state.wizardId) {
                this.channel = `guapante_preparation_day-${this.state.wizardId}`;
                await this.busService.addChannel(this.channel);
                this.busService.subscribe("picking_claim_updated", this.onBusNotif);
                this.busService.subscribe("reload", this.onBusNotif);
                this.busService.subscribe("picking_operation_finished", this.onOperationFinished);
            }
        });
        onMounted(() => {
            this._tickIntervalId = window.setInterval(() => {
                this.state.tickCount++;
            }, L1_COUNTER_TICK_MS);
        });
        onWillUnmount(() => {
            this.isDestroyed = true;
            if (this._tickIntervalId) {
                window.clearInterval(this._tickIntervalId);
            }
            if (this.channel) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe("picking_claim_updated", this.onBusNotif);
                this.busService.unsubscribe("reload", this.onBusNotif);
                this.busService.unsubscribe("picking_operation_finished", this.onOperationFinished);
            }
        });
    }

    // F5 en Nivel 1 (especificación visual, punto 2 de Tech Lead): el
    // wizard_id dinámico llega por additionalContext al hacer doAction
    // desde el NIP — eso NO sobrevive un refresco de página (la URL de
    // un client action solo trae lo guardado en el registro de la
    // acción, no lo dinámico del doAction original). Si falta, se
    // vuelve a resolver con el MISMO método que usa el NIP
    // (action_resolve_picking_handoff) — F5 recupera el estado de
    // verdad, no solo evita el error.
    async _resolveWizard() {
        let wizardId = this.props.action?.context?.wizard_id;
        if (!wizardId) {
            const result = await this.orm.call(
                "guapante.preparation.day", "action_resolve_picking_handoff", [], {},
            );
            wizardId = result?.context?.wizard_id || null;
        }
        this.state.wizardId = wizardId || null;
    }

    async loadRecords() {
        if (!this.state.wizardId) {
            this.state.loaded = true;
            return;
        }
        const lineCount = await this.orm.searchCount(
            "guapante.preparation.day.line", [["wizard_id", "=", this.state.wizardId]],
        );
        this.state.hasLines = lineCount > 0;
        // Plan f1 (Tech Lead, 2026-10-31): get_claims_for_level1_display
        // en vez de orm.searchRead directo — el filtro de "no ves lo que
        // tomó otro operario" vive en el servidor (ver su docstring en
        // preparation_day_product_claim.py), nunca acá.
        const claims = await this.orm.call(
            "guapante.preparation.day.product.claim",
            "get_claims_for_level1_display",
            [this.state.wizardId],
        );
        for (const claim of claims) {
            claim.assigned_employee_name = claim.assigned_employee_id
                ? claim.assigned_employee_id[1] : "";
            claim.stopped_by_employee_name = claim.stopped_by_employee_id
                ? claim.stopped_by_employee_id[1] : "";
            // "Detenido por mí" (E3, 2026-11-02) — igual que "Asignado a
            // mí", comparado contra el operario YA identificado en esta
            // estación (operatorState, cargado en onWillStart), no un
            // campo nuevo del servidor: el servidor ya manda el id real
            // en stopped_by_employee_id, alcanza con compararlo acá.
            claim.stopped_by_me = Boolean(
                claim.stopped_by_employee_id
                && claim.stopped_by_employee_id[0] === operatorState.employeeId
            );
        }
        this.state.claims = claims;
        this._claimsLoadedPerfNow = performance.now();
        this.state.loaded = true;
    }

    // Contadores L1: in_progress -> time_working_s; stopped ->
    // time_stopped_s (ambos ya calculados por get_claims_for_level1_
    // display, sección "contadores L1" de 4/7). Se lee state.tickCount
    // sin usarlo para nada más que registrar la dependencia reactiva —
    // es lo que hace que esta tarjeta vuelva a pintarse cada segundo.
    //
    // Simplificación conocida (E3): si DOS operarios tienen 'working'
    // abierto sobre el MISMO claim a la vez, el total real sube al
    // doble de rápido entre refrescos — este tick local solo suma a
    // ritmo de 1x hasta el próximo loadRecords() (bus), que corrige el
    // valor exacto. Visual únicamente, nunca el dato que se reporta.
    getLiveCounterLabel(claim) {
        void this.state.tickCount;
        const elapsedSincePerfLoad = (performance.now() - this._claimsLoadedPerfNow) / 1000;
        if (claim.status === "in_progress") {
            return formatDuration((claim.time_working_s || 0) + elapsedSincePerfLoad);
        }
        if (claim.status === "stopped") {
            return formatDuration((claim.time_stopped_s || 0) + elapsedSincePerfLoad);
        }
        return "";
    }

    get groupedClaims() {
        const groups = { pending: [], in_progress: [], stopped: [], done: [] };
        // E6 (David/Tech Lead, 2026-11-02): busca por producto O cliente
        // (customer_names_summary, calculado en el servidor — ver
        // get_claims_for_level1_display), sin distinguir acentos.
        const search = normalizeSearchText(this.state.searchText);
        for (const claim of this.state.claims) {
            if (search) {
                const haystack = normalizeSearchText(
                    claim.product_tmpl_name + " " + (claim.customer_names_summary || "")
                );
                if (!haystack.includes(search)) {
                    continue;
                }
                // Con texto de búsqueda, el buscador ignora "Mis
                // productos + Pendientes" (preferencia de David, vía
                // Tech Lead) — busca en TODO para no esconder una
                // coincidencia real detrás del filtro.
            } else if (
                !this.state.showAllClaims
                && !claim.touched_by_me
                && claim.status !== "pending"
            ) {
                // "Mis productos + Pendientes" (E3, 2026-11-02): vista
                // por defecto — lo que YO toqué (touched_by_me,
                // calculado en el servidor) MÁS todos los Pendientes
                // (de nadie todavía, le sirven a cualquiera). "Todos"
                // (showAllClaims) no filtra nada — ya no hay ninguna
                // regla de privacidad que aplicar, el servidor manda
                // todo sin filtrar (E1/E3).
                continue;
            }
            groups[claim.status].push(claim);
        }
        return groups;
    }

    // E6: un grupo plegable (done/stopped) se despliega SOLO mientras
    // haya texto de búsqueda y tenga coincidencias — nunca se escribe
    // en state.foldedGroups al buscar, así que al borrar el texto el
    // grupo vuelve exactamente al plegado/desplegado que el usuario
    // había elegido antes de buscar (preferencia intacta, no hay nada
    // que "restaurar" porque nunca se tocó).
    isGroupFolded(status) {
        if (!(status in this.state.foldedGroups)) {
            return false;
        }
        if (
            normalizeSearchText(this.state.searchText)
            && this.groupedClaims[status].length
        ) {
            return false;
        }
        return this.state.foldedGroups[status];
    }

    onBusNotif() {
        if (this.isDestroyed) {
            return;
        }
        this.loadRecords();
    }

    async onOperationFinished() {
        if (this.isDestroyed) {
            return;
        }
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, { clearBreadcrumbs: true });
    }

    onClickRefresh() {
        this.loadRecords();
    }

    async onClickClose() {
        // Punto 1 (Tech Lead, 2026-10-31): "Cerrar" cierra también la
        // identificación de esta estación (clearOperator() ya llama al
        // servidor y limpia guapante_prep_employee_id de la sesión, no
        // solo el estado local) y vuelve a la pantalla de NIP — antes
        // solo abría la grilla de Apps, dejando al operario identificado
        // para quien tomara el tablet después.
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
            clearBreadcrumbs: true,
        });
    }

    toggleGroup(status) {
        this.state.foldedGroups[status] = !this.state.foldedGroups[status];
    }

    async _callClaim(method, claimId, args = []) {
        try {
            return await this.orm.call(
                "guapante.preparation.day.product.claim", method, [[claimId], ...args],
            );
        } catch (error) {
            await this._handleError(error);
            return null;
        }
    }

    async _handleError(error) {
        const message = error?.data?.message || error?.message || "Ocurrió un error.";
        await new Promise((resolve) => {
            this.dialog.add(AlertDialog, {
                title: "No se pudo completar",
                body: message,
                confirm: () => resolve(),
            });
        });
        if (/NIP|sesión de operario expiró/i.test(message)) {
            await this.actionService.doAction(PICKING_APP_ACTION_XMLID, { clearBreadcrumbs: true });
        } else {
            await this.loadRecords();
        }
    }

    async onAssign(claim) {
        const result = await this._callClaim("action_assign", claim.id);
        if (result) {
            await this.actionService.doAction(result);
        }
    }

    async onResume(claim) {
        const result = await this._callClaim("action_resume", claim.id);
        if (result) {
            await this.actionService.doAction(result);
        }
    }

    // Doble entrada desde E3 (2026-11-02): el botón "Continuar" (solo
    // En progreso + mía) Y el click en CUALQUIER parte de la tarjeta,
    // de cualquier estado — mismo método, mismo action_open_lines_
    // kanban() sin ningún chequeo de dueño del lado servidor, así que
    // no hace falta distinguir de dónde vino la llamada.
    async onContinue(claim) {
        const result = await this._callClaim("action_open_lines_kanban", claim.id);
        if (result) {
            await this.actionService.doAction(result);
        }
    }

    async onRelease(claim) {
        const ok = await this._callClaim("action_release", claim.id);
        if (ok !== null) {
            await this.loadRecords();
        }
    }

    async onUnstop(claim) {
        // Igual que onRelease: queda en Nivel 1 (vuelve a Pendiente,
        // sin dueño), no abre ninguna acción — solo recarga.
        const ok = await this._callClaim("action_unstop", claim.id);
        if (ok !== null) {
            await this.loadRecords();
        }
    }

    async onScrap(claim) {
        // Fase D — el diálogo nativo de stock.scrap se cierra solo tras
        // Validar y no toca líneas/claims (solo descuenta stock): no
        // hace falta loadRecords() al volver, Nivel 1 queda como estaba.
        const result = await this._callClaim("action_open_scrap_wizard", claim.id);
        if (result) {
            await this.actionService.doAction(result);
        }
    }

    async onStop(claim) {
        // Mismo diálogo nativo (target=new) de siempre, sin cambios —
        // action_stop() ya llama _notify_bus(), y este componente ya
        // está suscrito al mismo canal: no hace falta loadRecords() acá.
        const result = await this._callClaim("action_open_stop_wizard", claim.id);
        if (result) {
            await this.actionService.doAction(result);
        }
    }
}

registry.category("actions").add("guapante_picking_level1", PickingClaimsDisplay);
