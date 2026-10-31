import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import {
    clearOperator,
    ensureOperatorLoaded,
    operatorState,
} from "@ist_preparation_day/js/preparation_operator_state";
import { PickingOperatorHeader } from "./preparation_picking_operator_header";
import { PickingInstallMenu } from "./preparation_picking_install_menu";
import { PickingWeightInput } from "./preparation_picking_weight_input";
import { PickingNoteDialog } from "./preparation_picking_note_dialog";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

const LINE_FIELDS = [
    "daily_sequence", "is_done", "needs_weighing", "estimated_kg",
    "expected_kg_per_unit", "actual_kg", "main_customer_name", "zone_name",
    "customer_qty_display", "customer_uom_label", "claim_is_mine",
    "no_variant_attribute_value_ids", "qty_uom_label",
];

// Redondeo a 3 decimales antes de comparar (Tech Lead, 2026-10-29,
// punto b.1): evita falsos avisos de "despachas menos" por residuos de
// coma flotante (ej. 2.5 - 2.3 !== 0.2 exacto en JS).
const round3 = (n) => Math.round(n * 1000) / 1000;

// Nivel 2 de Picking como client action propio (especificación visual,
// David 2026-10-23 — misma decisión final que Nivel 1, ver
// preparation_picking_level1_display.js). Llega acá SIEMPRE con
// claim_id en el contexto de la acción (action_open_lines_kanban del
// claim) — el componente resuelve wizard_id/product_tmpl_id leyendo
// ese claim, nunca los recibe sueltos, porque un F5 solo conserva lo
// guardado en el registro de la acción (acá, nada dinámico): si
// claim_id falta, se vuelve limpio a Nivel 1 en vez de intentar
// adivinar qué producto era.
export class PickingLinesDisplay extends Component {
    static template = "ist_preparation_day_picking.PickingLinesDisplay";
    static components = { PickingOperatorHeader, PickingInstallMenu, PickingWeightInput };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.busService = useService("bus_service");
        this.pwaService = useService("pwa");
        this.dialog = useService("dialog");
        this.state = useState({
            wizardId: null,
            productName: "",
            productTmplId: null,
            lines: [],
            foldedDone: true,
            loaded: false,
            noteTemplates: [],
        });
        this.isDestroyed = false;
        this.channel = null;
        this.onOperationFinished = this.onOperationFinished.bind(this);

        onWillStart(async () => {
            // Punto 3 (Tech Lead, 2026-10-31): mismo chequeo que Nivel 1
            // — sin operario identificado, directo a NIP, sin pasar por
            // Nivel 1 primero (que de todas formas rebotaría igual).
            await ensureOperatorLoaded();
            if (!operatorState.employeeName) {
                await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
                    clearBreadcrumbs: true,
                });
                return;
            }
            const resolved = await this._resolveClaim();
            if (!resolved) {
                await this._backToLevel1();
                return;
            }
            await this.loadLines();
            // Fase D — chips del diálogo de notas: lectura simple, sin
            // bloquear el resto de la pantalla si falla (no es crítico
            // para pesar/terminar cajas).
            this.orm.searchRead(
                "guapante.preparation.day.note.template", [], ["name"],
            ).then((templates) => { this.state.noteTemplates = templates; });
            this.channel = `guapante_preparation_day-${this.state.wizardId}`;
            await this.busService.addChannel(this.channel);
            this.busService.subscribe("picking_operation_finished", this.onOperationFinished);
        });
        onWillUnmount(() => {
            this.isDestroyed = true;
            if (this.channel) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe("picking_operation_finished", this.onOperationFinished);
            }
        });
    }

    async _resolveClaim() {
        const claimId = this.props.action?.context?.claim_id;
        if (!claimId) {
            return false;
        }
        const claims = await this.orm.read(
            "guapante.preparation.day.product.claim", [claimId],
            ["wizard_id", "product_tmpl_id", "product_tmpl_name"],
        );
        const claim = claims[0];
        if (!claim || !claim.wizard_id) {
            return false;
        }
        this.state.claimId = claimId;
        this.state.wizardId = claim.wizard_id[0];
        this.state.productTmplId = claim.product_tmpl_id[0];
        this.state.productName = claim.product_tmpl_name;
        return true;
    }

    async _backToLevel1() {
        // wizard_id explícito cuando ya se conoce (siempre, salvo el
        // fallback de F5 sin claim_id resuelto): sin esto, "← Productos"
        // vuelve a Nivel 1 con el context en blanco, y _resolveWizard()
        // de Nivel 1 lo interpreta como "sin contexto" y resuelve LA
        // SESIÓN DE HOY (action_resolve_picking_handoff) en vez de la
        // sesión real que se estaba trabajando — bug real encontrado en
        // la verificación de navegador (David, 2026-10-23: sesión de
        // prueba de ayer, "← Productos" aterrizaba en la de hoy, vacía).
        await this.actionService.doAction(
            {
                type: "ir.actions.client",
                tag: "guapante_picking_level1",
                target: "fullscreen",
                context: {
                    guapante_picking_flow: true,
                    wizard_id: this.state.wizardId || undefined,
                },
            },
            { clearBreadcrumbs: true },
        );
    }

    async loadLines() {
        const lines = await this.orm.searchRead(
            "guapante.preparation.day.line",
            [
                ["wizard_id", "=", this.state.wizardId],
                ["product_id", "=", this.state.productTmplId],
            ],
            LINE_FIELDS,
        );
        const attrIds = [...new Set(lines.flatMap((l) => l.no_variant_attribute_value_ids))];
        let attrNames = {};
        if (attrIds.length) {
            const attrs = await this.orm.read(
                "product.template.attribute.value", attrIds, ["name"],
            );
            attrNames = Object.fromEntries(attrs.map((a) => [a.id, a.name]));
        }
        for (const line of lines) {
            line.attribute_names = line.no_variant_attribute_value_ids.map(
                (id) => attrNames[id] || "",
            );
        }
        this.state.lines = lines;
        this.state.loaded = true;
    }

    get pendingLines() {
        return this.state.lines.filter((line) => !line.is_done);
    }

    get doneLines() {
        return this.state.lines.filter((line) => line.is_done);
    }

    onOperationFinished() {
        if (this.isDestroyed) {
            return;
        }
        this._closeAndReturnToNip();
    }

    async _closeAndReturnToNip() {
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, { clearBreadcrumbs: true });
    }

    onClickRefresh() {
        this.loadLines();
    }

    async onClickClose() {
        // Punto 1 (Tech Lead, 2026-10-31): mismo fix que Nivel 1.
        await clearOperator();
        await this.actionService.doAction(PICKING_APP_ACTION_XMLID, {
            clearBreadcrumbs: true,
        });
    }

    toggleDoneGroup() {
        this.state.foldedDone = !this.state.foldedDone;
    }

    onClickBackToLevel1() {
        this._backToLevel1();
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
            await this._closeAndReturnToNip();
        } else {
            await this.loadLines();
        }
    }

    // Sin pesaje real (Tech Lead, 2026-10-29, punto b — kg directo Y
    // unidades): el input se precarga con estimated_kg (ver template) —
    // si el operario confirma SIN tocar ese valor, se guarda tal cual
    // con guapante_qty_estimated=True (is_qty_estimated, informativo
    // para reportes de Fase 2); si lo edita, llega distinto y se guarda
    // en False. Nunca aplica a needs_weighing=True: ahí el valor nace en
    // 0, cualquier número que llegue es necesariamente un pesaje real.
    //
    // Dos alertas independientes, cada una en su propio caso, sin
    // tocarse entre sí:
    // 1) needs_weighing=True (Fase C, punto 1 de Tech Lead, SIN cambios)
    //    — mismo umbral y texto que tenía el patch del widget
    //    scale_weight (preparation_picking_scale_weight_patch.js,
    //    retirado con el kanban): fuera de [20%, 500%] del peso
    //    esperado (estimated_kg * expected_kg_per_unit, promedio
    //    histórico) pide confirmación, nunca bloquea.
    // 2) needs_weighing=False — kg directo o unidades (punto b.1): regla
    //    de David, lo normal es despachar >= lo pedido; solo pide
    //    confirmación si despacha MENOS (nunca por despachar más — eso
    //    reemplaza cualquier tope superior para este caso, no hay rango
    //    aquí como en el 1). Comparación redondeada a 3 decimales para
    //    no disparar por residuos de coma flotante.
    async onConfirmWeight(line, value) {
        const wasUnedited = !line.needs_weighing && value === line.estimated_kg;
        if (line.needs_weighing && line.expected_kg_per_unit > 0) {
            const expectedWeight = line.estimated_kg * line.expected_kg_per_unit;
            const outOfRange = (
                value > expectedWeight * 5 || value < expectedWeight * 0.2
            );
            if (outOfRange) {
                const confirmed = await new Promise((resolve) => {
                    this.dialog.add(ConfirmationDialog, {
                        title: "Peso fuera de lo usual",
                        body: (
                            `Para este producto se espera un peso cercano a ` +
                            `${expectedWeight.toFixed(3)} kg y se registraron ` +
                            `${value.toFixed(3)} kg. ¿Confirmas que el peso ` +
                            `es correcto?`
                        ),
                        confirm: () => resolve(true),
                        cancel: () => resolve(false),
                    });
                });
                if (!confirmed) {
                    return;
                }
            }
        } else if (!line.needs_weighing && round3(value) < round3(line.estimated_kg)) {
            const confirmed = await new Promise((resolve) => {
                this.dialog.add(ConfirmationDialog, {
                    title: "Despachas menos de lo pedido",
                    body: (
                        `Despachas menos de lo pedido: ${value} de ` +
                        `${line.estimated_kg} ${line.qty_uom_label}. ` +
                        `¿Confirmas?`
                    ),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                });
            });
            if (!confirmed) {
                return;
            }
        }
        try {
            // actual_kg bajo guapante_picking_flow dispara el pipeline
            // completo ya existente (write() de PreparationDayLine en
            // ist_preparation_day/ist_preparation_day_picking: ownership,
            // operario activo, action_save_line_weight, bus) — el mismo
            // que disparaba el widget scale_weight al guardar.
            await this.orm.write(
                "guapante.preparation.day.line", [line.id], { actual_kg: value },
                {
                    context: {
                        guapante_picking_flow: true,
                        guapante_qty_estimated: wasUnedited,
                    },
                },
            );
            await this.loadLines();
        } catch (error) {
            await this._handleError(error);
        }
    }

    async onUndo(line) {
        try {
            await this.orm.call(
                "guapante.preparation.day.line", "action_undo_line", [[line.id]],
                { context: { guapante_picking_flow: true } },
            );
            await this.loadLines();
        } catch (error) {
            await this._handleError(error);
        }
    }

    // Fase D — engrane de la tarjeta de la caja: diálogo propio (no hay
    // widget nativo de texto libre + chips), ownership/operario activo
    // los exige action_add_note() en el servidor. No hace falta
    // loadLines() al guardar — la nota no cambia ningún dato que la
    // tarjeta muestre.
    onAddNote(line) {
        this.dialog.add(PickingNoteDialog, {
            templates: this.state.noteTemplates,
            onConfirm: (text) => this._saveNote(line, text),
        });
    }

    async _saveNote(line, text) {
        try {
            await this.orm.call(
                "guapante.preparation.day.line", "action_add_note", [[line.id], text],
                { context: { guapante_picking_flow: true } },
            );
        } catch (error) {
            await this._handleError(error);
        }
    }
}

registry.category("actions").add("guapante_picking_level2", PickingLinesDisplay);
