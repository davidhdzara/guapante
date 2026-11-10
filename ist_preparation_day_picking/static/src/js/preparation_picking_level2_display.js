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
import { PickingVisitTimer } from "./preparation_picking_visit_timer";
import { matchesLineSearch } from "./preparation_picking_search_utils";

const PICKING_APP_ACTION_XMLID = "ist_preparation_day_picking.action_picking_app";

const LINE_FIELDS = [
    "daily_sequence", "is_done", "needs_weighing", "estimated_kg",
    "expected_kg_per_unit", "actual_kg", "main_customer_name", "zone_name",
    "customer_qty_display", "customer_uom_label",
    "no_variant_attribute_value_ids", "qty_uom_label",
];

// Redondeo a 3 decimales antes de comparar (Tech Lead, 2026-10-29,
// punto b.1): evita falsos avisos de "despachas menos" por residuos de
// coma flotante (ej. 2.5 - 2.3 !== 0.2 exacto en JS).
const round3 = (n) => Math.round(n * 1000) / 1000;

// Debounce de 'reload' (Tech Lead, 2026-11-02): el canal es de toda la
// sesión — una renumeración + varias líneas nuevas pueden mandar varios
// 'reload' seguidos; colapsarlos evita varias verificaciones redundantes.
const RELOAD_DEBOUNCE_MS = 400;

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
    static components = {
        PickingOperatorHeader, PickingInstallMenu, PickingWeightInput, PickingVisitTimer,
    };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.busService = useService("bus_service");
        this.dialog = useService("dialog");
        this.state = useState({
            wizardId: null,
            productName: "",
            productTmplId: null,
            lines: [],
            foldedDone: true,
            searchText: "",
            loaded: false,
            noteTemplates: [],
        });
        this.isDestroyed = false;
        this.channel = null;
        this._reloadDebounceTimer = null;
        this.onOperationFinished = this.onOperationFinished.bind(this);
        this.onBusReload = this.onBusReload.bind(this);

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
            // Punto 2 (Tech Lead, 2026-11-02): este canal es de toda la
            // sesión — un pedido nuevo de CUALQUIER producto manda
            // 'reload' acá también, no solo a Nivel 1. onBusReload()
            // filtra por relevancia antes de tocar state.lines.
            this.busService.subscribe("reload", this.onBusReload);
        });
        onWillUnmount(() => {
            this.isDestroyed = true;
            if (this._reloadDebounceTimer) {
                clearTimeout(this._reloadDebounceTimer);
                this._reloadDebounceTimer = null;
            }
            if (this.channel) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe("picking_operation_finished", this.onOperationFinished);
                this.busService.unsubscribe("reload", this.onBusReload);
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
        let attrById = {};
        if (attrIds.length) {
            const attrs = await this.orm.read(
                "product.template.attribute.value", attrIds,
                ["name", "display_name", "guapante_chip_color"],
            );
            attrById = Object.fromEntries(attrs.map((a) => [a.id, a]));
        }
        // Color POR VALOR (David, 2026-11-10, punto 3): el `color` nativo de
        // product.template.attribute.value es aleatorio por producto (el
        // mismo «Verde» sale con 9 colores), así que NO se usa. El servidor
        // calcula `guapante_chip_color` desde el parámetro del sistema
        // ist_preparation_day_picking.attribute_chip_colors (nombre del
        // valor → clase nativa o_tag_color_N); sin mapear → 0 (neutro).
        // Texto (David, 2026-10-31): "Atributo: Valor" (display_name
        // nativo) cuando cabe sin alargar el chip — la columna de
        // Nivel 2 es angosta (w-25). Con los atributos reales de
        // Preparación, "Tamaño: Grande" (14) cabe bien pero "Grado de
        // Madurez: Pinton-Maduro" (31) no — ahí se deja solo el valor
        // ("Pinton-Maduro"). Umbral sobre el texto completo, no solo
        // sobre el nombre del atributo, para que decida igual sin
        // importar qué tan largo salga el valor.
        const MAX_CHIP_TEXT_LENGTH = 20;
        for (const line of lines) {
            line.attribute_chips = line.no_variant_attribute_value_ids.map((id) => {
                const attr = attrById[id];
                const fullText = attr?.display_name || "";
                return {
                    // id del valor como key (Tech Lead, 2026-10-31): dos
                    // chips con el mismo texto (p.ej. un valor "Grande"
                    // de dos atributos distintos) colisionarían con el
                    // texto como t-key.
                    id,
                    name: (
                        fullText && fullText.length <= MAX_CHIP_TEXT_LENGTH
                    ) ? fullText : (attr?.name || ""),
                    color: attr?.guapante_chip_color || 0,
                };
            });
        }
        this.state.lines = lines;
        this.state.loaded = true;
    }

    // E6 (David/Tech Lead, 2026-11-02): un solo buscador para Caja #
    // y cliente — ver matchesLineSearch() para la regla exacta de "#"
    // vs. número suelto vs. texto normal.
    _matchesSearch(line) {
        return matchesLineSearch(
            line.daily_sequence, line.main_customer_name, this.state.searchText,
        );
    }

    get pendingLines() {
        return this.state.lines.filter(
            (line) => !line.is_done && this._matchesSearch(line)
        );
    }

    get doneLines() {
        return this.state.lines.filter(
            (line) => line.is_done && this._matchesSearch(line)
        );
    }

    // Igual que isGroupFolded() en Nivel 1: el grupo "Terminado" se
    // despliega solo mientras haya coincidencias de la búsqueda ahí —
    // nunca se toca state.foldedDone al buscar, así que al borrar el
    // texto vuelve exactamente al plegado/desplegado que tenía antes.
    isDoneFolded() {
        if (this.state.searchText.trim() && this.doneLines.length) {
            return false;
        }
        return this.state.foldedDone;
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

    // Punto 2 (Tech Lead, 2026-11-02): "El Nivel 2 se actualiza solo" —
    // no se puede llamar loadLines() directo en cada 'reload' (ese canal
    // es de toda la sesión, dispara por pedidos de OTROS productos la
    // mayoría de las veces). Primero se filtra por relevancia
    // (_checkForRelevantReload) y recién ahí se reemplaza state.lines —
    // reemplazo que, además, ya es seguro hoy: onConfirmWeight hace
    // exactamente lo mismo en cada confirmación (Pendiente o Terminada,
    // E2) y no borra el
    // texto sin confirmar de las demás tarjetas (ver mensaje a Tech
    // Lead, 2026-11-02 — PickingWeightInput no resincroniza state.text
    // desde props tras el setup() inicial, y OWL reutiliza la instancia
    // mientras el t-key=line.id siga en la lista).
    onBusReload() {
        if (this.isDestroyed) {
            return;
        }
        if (this._reloadDebounceTimer) {
            clearTimeout(this._reloadDebounceTimer);
        }
        this._reloadDebounceTimer = setTimeout(() => {
            this._reloadDebounceTimer = null;
            this._checkForRelevantReload();
        }, RELOAD_DEBOUNCE_MS);
    }

    async _checkForRelevantReload() {
        if (this.isDestroyed) {
            return;
        }
        // Comparación por conjunto de ids, no por conteo (Tech Lead,
        // 2026-11-02): una reubicación + un pedido nuevo al mismo tiempo
        // deja el conteo igual pero cambia qué líneas corresponden —
        // un searchCount no lo detecta.
        const currentIds = await this.orm.search(
            "guapante.preparation.day.line",
            [
                ["wizard_id", "=", this.state.wizardId],
                ["product_id", "=", this.state.productTmplId],
            ],
        );
        if (this.isDestroyed) {
            return;
        }
        const knownIds = this.state.lines.map((line) => line.id);
        const sameSet = (
            currentIds.length === knownIds.length &&
            new Set(currentIds).size === new Set([...currentIds, ...knownIds]).size
        );
        if (!sameSet) {
            await this.loadLines();
        }
    }

    onClickRefresh() {
        this.loadLines();
    }

    toggleDoneGroup() {
        this.state.foldedDone = !this.state.foldedDone;
    }

    async onClickBackToLevel1() {
        await this._backToLevel1();
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

    // Campo de peso/cantidad SIEMPRE vacío y obligatorio (David,
    // corrección #7, 2026-10-31): ya no se precarga con estimated_kg —
    // el operario tiene que escribir un valor real para poder
    // confirmar la línea, aplique o no needs_weighing. is_qty_estimated
    // ya no se marca desde aquí; sigue existiendo en el modelo pero solo
    // la pone en True action_mark_line_ready() (botón "Marcar lista" /
    // RPC), nunca esta escritura.
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
        // E2 (David/Tech Lead, 2026-11-02 — Terminadas editables sin
        // botón Deshacer): mismo valor que ya estaba registrado (Enter
        // sin cambios sobre una Terminada, input precargado con
        // actual_kg) — no-op también en el cliente, antes de cualquier
        // alerta o viaje al servidor. El servidor ya lo trataría como
        // no-op (new_kg == old_kg no dispara corrección ni undo), pero
        // sin este corte temprano el operario vería "Despachas menos de
        // lo pedido" sobre un valor que en realidad no cambió.
        if (line.is_done && round3(value) === round3(line.actual_kg)) {
            return;
        }
        const wasPending = !line.is_done;
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
                    },
                },
            );
            await this.loadLines();
            if (this.isDestroyed) {
                return;
            }
            // Punto (a) (Tech Lead, 2026-10-31): si esta era la última
            // línea pendiente de ESTE producto, volver solo a Nivel 1 —
            // salvo que este mismo guardado también haya cerrado la
            // OPERACIÓN completa (todas las líneas de la sesión, no solo
            // las de este producto). wasPending (E2, 2026-11-02): una
            // corrección sobre una línea que YA estaba Terminada nunca
            // navega sola — sin esto, corregir el peso de la única línea
            // de un producto que ya no tenía pendientes volvía a Nivel 1
            // aunque nada nuevo se hubiera completado. El write() de
            // arriba, cuando es la última línea pendiente de TODA la
            // sesión, ya deja self.state = 'done' en el servidor dentro
            // de la misma
            // transacción (action_save_line_weight → action_mark_done),
            // antes de que esta llamada retorne — así que leer el estado
            // acá es una señal confiable, no una carrera contra el bus.
            // Si la operación sí se cerró, el bus
            // ('picking_operation_finished' → onOperationFinished) se
            // encarga de volver al NIP; encadenar _backToLevel1() encima
            // duplicaría la navegación.
            if (wasPending && this.pendingLines.length === 0) {
                const [wizard] = await this.orm.read(
                    "guapante.preparation.day", [this.state.wizardId], ["state"],
                );
                if (!this.isDestroyed && wizard.state !== "done") {
                    await this._backToLevel1();
                }
            }
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
