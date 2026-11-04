/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useSubEnv } from "@odoo/owl";
import { View } from "@web/views/view";

// Punto 5 (prototipo, David/Tech Lead, 2026-11-03): pestaña "Productos"
// con buscador/filtros/agrupar nativos, al estilo del desplegable de
// conciliación bancaria de Contabilidad (BankRecViewEmbedder, visto en
// account_accountant/static/src/components/bank_reconciliation/kanban.js
// y bank_rec_form.xml). Mismo mecanismo que ahí: <widget> embebe esta
// View SIN depender de un campo del form — recibe record vía
// widgetProps (ver web/static/src/views/widgets/widget.js), así que
// usamos record.resId para el domain. list_view_ref/search_view_ref en
// el context (confirmado leyendo _prepare_embedded_views_data en
// bank_rec_widget.py) es cómo Accounting apunta a una vista concreta
// por xmlid sin resolver el id numérico a mano en JS.
//
// Fix (David/Tech Lead, 2026-11-04): esta View vive dentro del form de
// guapante.preparation.day, así que hereda env.config.views de la
// ACCIÓN de sesiones — que ya trae sus propias entradas 'list'/'search'
// (para guapante.preparation.day, no para .line). Sin viewId/
// searchViewId explícitos, loadView() (web/static/src/views/view.js)
// reutiliza esas ids heredadas en vez de dejarlas en false, y el
// server devuelve el arch equivocado (campos name/date, que .line no
// tiene) -> OwlError "Unknown field name". BankRecViewEmbedder evita
// esto porque dispara su View desde un doAction() nuevo (config.views
// vacío); acá no hay doAction, así que viewId/searchViewId en false
// son el único mecanismo que fuerza a loadView() a honrar list_view_ref
// /search_view_ref del context en vez de la entrada heredada.
// Verificado por lectura de código + get_views() en shell: con
// viewId=false y searchViewId=false, list y search resuelven a
// view_preparation_day_line_list_picking (11121) y
// view_preparation_day_line_search (11118), no a las vistas del día.
// Fix 2 (David, 2026-11-04 — "el segundo engrane al lado del
// buscador no debería ir ahí", probado en navegador): el mismo
// mecanismo de herencia de env.config de arriba también filtraba
// env.config.actionId/actionType del action PADRE (Preparación del
// Día, un ir.actions.act_window real) hacia esta View hija — eso
// activa dos entradas del registro cogMenu que no tienen nada que
// ver con esta lista embebida: "insert-embedded-view-menu" (Knowledge,
// exige env.config.actionId truthy) y "spreadsheet-cog-menu"
// (exige env.config.actionType === "ir.actions.act_window"). La
// lista nativa que esto reemplaza nunca tuvo ninguna de las dos
// porque un field o2m embebido en un form jamás arma su propio
// control panel. useSubEnv con actionId/actionType reseteados a su
// default (ver getDefaultConfig() en web/static/src/views/view.js)
// apaga ambas sin tocar nada del resto del config heredado
// (searchMenuTypes, etc. siguen funcionando igual). export_xlsx se
// apaga aparte, por atributo de arch, en
// view_preparation_day_line_list_picking (no es un tema de
// env.config, es isDisplayed de export-all-menu leyendo el arch).
export class PreparationDayProductosEmbedder extends Component {
    static template = "ist_preparation_day_picking.PreparationDayProductosEmbedder";
    static components = { View };
    static props = ["*"];

    setup() {
        useSubEnv({
            config: {
                ...this.env.config,
                actionId: false,
                actionType: false,
            },
        });
    }

    get viewProps() {
        return {
            type: "list",
            resModel: "guapante.preparation.day.line",
            domain: [["wizard_id", "=", this.props.record.resId]],
            viewId: false,
            searchViewId: false,
            context: {
                list_view_ref:
                    "ist_preparation_day_picking.view_preparation_day_line_list_picking",
                search_view_ref:
                    "ist_preparation_day.view_preparation_day_line_search",
            },
            searchMenuTypes: ["filter", "groupBy"],
            allowSelectors: false,
            noBreadcrumbs: true,
        };
    }
}

registry.category("view_widgets").add("preparation_day_productos_embedder", {
    component: PreparationDayProductosEmbedder,
});
