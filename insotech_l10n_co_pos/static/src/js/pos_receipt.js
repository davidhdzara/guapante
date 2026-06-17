/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    // Al cargar la orden desde el backend, guardamos nuestras variables DIAN
    setup() {
        super.setup(...arguments);
        this.dian_cufe = this.dian_cufe || false;
        this.dian_qr = this.dian_qr || false;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        if (json.dian_cufe) {
            this.dian_cufe = json.dian_cufe;
        }
        if (json.dian_qr) {
            this.dian_qr = json.dian_qr;
        }
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this.dian_cufe) {
            json.dian_cufe = this.dian_cufe;
        }
        if (this.dian_qr) {
            json.dian_qr = this.dian_qr;
        }
        return json;
    },

    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);
        
        // Asignar variables DIAN al root para que el XML las encuentre en props.data
        result.dian_cufe = this.dian_cufe || false;
        result.dian_qr = this.dian_qr || false;
        
        // Asegurar que result.headerData existe
        result.headerData = result.headerData || {};

        // También inyectar datos de la empresa desde el config de POS
        const posCompany = this.pos?.company || this.company || {};
        result.headerData.dian_resolution_text = posCompany.dian_resolution_text || '';
        result.headerData.dian_obligations_text = posCompany.dian_obligations_text || '';
        result.headerData.ciiu_code = posCompany.company_registry || '';
        
        // Lógica para desglosar Base Gravable e INC (Impuesto al Consumo)
        let base_gravable = 0.0;
        let inc_total = 0.0;
        
        if (result.tax_details && result.tax_details.length > 0) {
            for (let tax of result.tax_details) {
                if (tax.tax && tax.tax.name && (tax.tax.name.toUpperCase().includes('INC') || tax.tax.name.toUpperCase().includes('CONSUMO'))) {
                    inc_total += tax.amount;
                }
            }
            base_gravable = result.total_without_tax;
        }
        
        if (base_gravable > 0) {
            result.dian_base_gravable = base_gravable;
        }
        if (inc_total > 0) {
            result.dian_inc = inc_total;
        }
        
        // Forma y Medio de Pago DIAN (Anexo 1.9)
        result.dian_forma_pago = 'Contado';
        let medios_pago = [];
        if (result.paymentlines && result.paymentlines.length > 0) {
            for (let line of result.paymentlines) {
                let name = (line.name || '').toLowerCase();
                if (name.includes('efectivo') || name.includes('cash')) {
                    medios_pago.push('10 Efectivo');
                } else if (name.includes('transferencia') || name.includes('bank')) {
                    medios_pago.push('41 Transferencia');
                } else {
                    medios_pago.push('48 Tarjeta de Crédito/Débito');
                }
            }
        } else {
            medios_pago.push('10 Efectivo');
        }
        
        result.dian_medios_pago = [...new Set(medios_pago)].join(' / ');
        
        return result;
    }
});
