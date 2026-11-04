/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
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
export class PreparationDayProductosEmbedder extends Component {
    static template = "ist_preparation_day_picking.PreparationDayProductosEmbedder";
    static components = { View };
    static props = ["*"];

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
