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
export class PreparationDayProductosEmbedder extends Component {
    static template = "ist_preparation_day_picking.PreparationDayProductosEmbedder";
    static components = { View };
    static props = ["*"];

    get viewProps() {
        return {
            type: "list",
            resModel: "guapante.preparation.day.line",
            domain: [["wizard_id", "=", this.props.record.resId]],
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
