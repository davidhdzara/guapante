import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, xml } from "@odoo/owl";

// Widget-ancla invisible: no muestra nada, solo se suscribe al canal de
// bus.bus de esta sesión mientras el formulario está abierto, y recarga el
// registro cuando el backend avisa (sale.order confirmada o
// stock.picking reprogramado con fecha dentro de esta sesión — ver
// _ensure_session_for_date en models/preparation_day.py).
class LiveRefreshAnchor extends Component {
    static template = xml`<span/>`;
    static props = { ...standardFieldProps };

    setup() {
        this.busService = useService("bus_service");
        this.channel = `guapante_preparation_day-${this.props.record.resId}`;
        this.onReload = this.onReload.bind(this);

        onWillStart(async () => {
            if (this.props.record.resId) {
                await this.busService.addChannel(this.channel);
                this.busService.subscribe("reload", this.onReload);
            }
        });
        onWillUnmount(() => {
            if (this.props.record.resId) {
                this.busService.deleteChannel(this.channel);
                this.busService.unsubscribe("reload", this.onReload);
            }
        });
    }

    onReload() {
        this.props.record.load();
    }
}

registry.category("fields").add("guapante_live_refresh", {
    component: LiveRefreshAnchor,
});
