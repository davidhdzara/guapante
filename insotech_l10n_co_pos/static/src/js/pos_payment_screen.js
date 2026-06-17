/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    
    /**
     * Interceptamos la validación de la orden antes de mandarla al servidor.
     * Si la orden requiere factura (to_invoice) y no tiene cliente,
     * buscamos al Consumidor Final (222222222222) en la sesión y se lo asignamos
     * para evitar que Odoo bloquee la transacción con un error en pantalla.
     */
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        
        if (order.is_to_invoice() && !order.get_partner()) {
            // Buscar Consumidor Final cargado en memoria (res.partner)
            const consumidorFinal = this.pos.db.get_partners_sorted(1000).find(
                (p) => p.vat === '222222222222'
            );
            
            if (consumidorFinal) {
                // Asignar silenciosamente y continuar
                order.set_partner(consumidorFinal);
            } else {
                // Si por alguna razón no está cacheado en el POS local, mostrar advertencia
                console.warn("Consumidor Final (222222222222) no encontrado en memoria POS.");
            }
        }
        
        // Continuar con el flujo nativo que ahora ya tiene el partner asignado
        return super.validateOrder(...arguments);
    }
});
