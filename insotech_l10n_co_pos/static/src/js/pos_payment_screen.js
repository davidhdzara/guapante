/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    
            } else {
                // Si por alguna razón no está cacheado en el POS local, mostrar advertencia
                console.warn("Consumidor Final (222222222222) no encontrado en memoria POS.");
            }
        }
        
        // Continuar con el flujo nativo que ahora ya tiene el partner asignado
        return super.validateOrder(...arguments);
    }
});
