import { Component, xml } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

// Engranaje de la tarjeta de Nivel 1 (Detener/Liberar/Desechar) —
// componente simple ahora que Nivel 1 es un client action propio (ya no
// hace falta el truco de widget-de-campo-ancla sobre un kanban Record).
// Mismo Dropdown/DropdownItem nativo que usa el kanban por dentro.
// "Desechar" (Fase D) abre el diálogo nativo de stock.scrap.
export class PickingClaimGearMenu extends Component {
    static template = xml`
        <Dropdown>
            <button type="button" class="btn btn-light fa fa-gear" title="Más acciones"/>
            <t t-set-slot="content">
                <DropdownItem onSelected="() => this.props.onScrap()">Desechar</DropdownItem>
                <DropdownItem onSelected="() => this.props.onStop()">Detener</DropdownItem>
                <DropdownItem onSelected="() => this.props.onRelease()">Liberar</DropdownItem>
            </t>
        </Dropdown>
    `;
    static components = { Dropdown, DropdownItem };
    static props = {
        onScrap: Function,
        onStop: Function,
        onRelease: Function,
    };
}
