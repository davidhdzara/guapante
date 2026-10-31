import { Component, xml } from "@odoo/owl";
import { isDisplayStandalone } from "@web/core/browser/feature_detection";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

const SCOPED_APP_INSTALL_URL =
    "/scoped_app?app_id=ist_preparation_day_picking&path=scoped_app/picking&app_name=Picking";

// Menú de hamburguesa con "Instalar aplicación" — especificación visual,
// punto 10 de Tech Lead: mismo patrón que point_of_sale/static/src/app/
// navbar/navbar.xml (Dropdown + fa-bars + DropdownItem, visible solo si
// !isDisplayStandalone()), no un enlace suelto. Compartido entre la
// pantalla de NIP y los dos niveles — un solo componente, tres puntos de
// montaje.
export class PickingInstallMenu extends Component {
    static template = xml`
        <Dropdown t-if="!isStandalone">
            <button type="button" class="btn btn-light fa fa-bars" title="Menú"/>
            <t t-set-slot="content">
                <DropdownItem onSelected="onInstall">Instalar aplicación</DropdownItem>
            </t>
        </Dropdown>
    `;
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.isStandalone = isDisplayStandalone();
    }

    onInstall() {
        window.open(SCOPED_APP_INSTALL_URL, "_blank");
    }
}
