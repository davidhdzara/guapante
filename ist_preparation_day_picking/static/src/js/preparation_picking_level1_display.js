import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { clearOperator } from "@ist_preparation_day/js/preparation_operator_state";
import { PickingOperatorHeader } from "./preparation_picking_operator_header";
import { PickingInstallMenu } from "./preparation_picking_install_menu";
import { PickingClaimGearMenu } from "./preparation_picking_claim_menu";

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
const CLAIM_FIELDS = [
    "product_tmpl_id", "product_tmpl_name", "status", "assigned_employee_id",
    "stop_reason", "stopped_by_employee_id", "is_mine",
    "pending_line_count", "total_line_count",
];

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
        this.homeMenu = useService("home_menu");
        this.pwaService = useService("pwa");
        this.dialog = useService("dialog");
        this.statusOrder = STATUS_ORDER;
        this.statusLabels = STATUS_LABELS;
        this.stopReasonLabels = STOP_REASON_LABELS;
        this.state = useState({
            wizardId: null,
            hasLines: false,
            claims: [],
            foldedDone: true,
            searchText: "",
            loaded: false,
        });
        // Punto (a), heredado de la implementación kanban: nunca tocar
        // el estado tras desmontar.
        this.isDestroyed = false;
        this.channel = null;
        this.onBusNotif = this.onBusNotif.bind(this);
        this.onOperationFinished = this.onOperationFinished.bind(this);

        onWillStart(async () => {
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
        onWillUnmount(() => {
            this.isDestroyed = true;
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
        const claims = await this.orm.searchRead(
            "guapante.preparation.day.product.claim",
            [["wizard_id", "=", this.state.wizardId]],
            CLAIM_FIELDS,
        );
        for (const claim of claims) {
            claim.assigned_employee_name = claim.assigned_employee_id
                ? claim.assigned_employee_id[1] : "";
            claim.stopped_by_employee_name = claim.stopped_by_employee_id
                ? claim.stopped_by_employee_id[1] : "";
        }
        this.state.claims = claims;
        this.state.loaded = true;
    }

    get groupedClaims() {
        const groups = { pending: [], in_progress: [], stopped: [], done: [] };
        const search = this.state.searchText.trim().toLowerCase();
        for (const claim of this.state.claims) {
            if (search && !claim.product_tmpl_name.toLowerCase().includes(search)) {
                continue;
            }
            groups[claim.status].push(claim);
        }
        return groups;
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

    onClickClose() {
        this.homeMenu.toggle();
    }

    toggleDoneGroup() {
        this.state.foldedDone = !this.state.foldedDone;
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
