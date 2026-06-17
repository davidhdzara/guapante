/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);

        // Datos de la empresa para la sección DIAN del recibo
        const company = this.company || {};

        // Resolución DIAN y obligaciones fiscales
        result.dian_resolution_text = company.dian_resolution_text || '';
        result.dian_obligations_text = company.dian_obligations_text || '';
        result.dian_ciiu_code = company.company_registry || '';

        // CUFE y QR (si la orden ya fue facturada electrónicamente)
        result.dian_cufe = this.dian_cufe || false;
        result.dian_qr = this.dian_qr || false;

        // Forma y Medio de Pago DIAN (Anexo 1.9)
        result.dian_forma_pago = 'Contado';
        const medios = [];
        if (result.paymentlines && result.paymentlines.length > 0) {
            for (const line of result.paymentlines) {
                const name = (line.name || '').toLowerCase();
                if (name.includes('efectivo') || name.includes('cash')) {
                    medios.push('Efectivo');
                } else if (name.includes('transferencia') || name.includes('bank')) {
                    medios.push('Transferencia');
                } else {
                    medios.push('Tarjeta');
                }
            }
        } else {
            medios.push('Efectivo');
        }
        result.dian_medios_pago = [...new Set(medios)].join(' / ');

        return result;
    }
});
