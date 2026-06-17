/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);

        // En Odoo 18, los campos custom inyectados via _load_pos_data
        // están disponibles en company.raw (el dict original),
        // no como propiedades del modelo ORM reactivo.
        const company = this.company || {};
        const raw = company.raw || company;

        // --- Datos de la empresa para la sección DIAN ---
        result.dian_resolution_text = raw.dian_resolution_text || '';
        result.dian_obligations_text = raw.dian_obligations_text || '';
        result.dian_ciiu_code = raw.dian_ciiu_code || '';

        // --- Datos del cliente ---
        const partner = this.partner_id;
        if (partner) {
            result.dian_client = {
                name: partner.name || 'Consumidor Final',
                vat: partner.vat || '',
                id_type: partner.l10n_latam_identification_type_id
                    ? (partner.l10n_latam_identification_type_id.name ||
                       partner.l10n_latam_identification_type_id)
                    : 'NIT',
                street: partner.street || '',
                city: partner.city || '',
                phone: partner.phone || partner.mobile || '',
                email: partner.email || '',
            };
        } else {
            result.dian_client = {
                name: 'Consumidor Final',
                vat: '222222222222',
                id_type: 'NIT',
                street: '',
                city: '',
                phone: '',
                email: '',
            };
        }

        // --- CUFE y QR ---
        result.dian_cufe = this.dian_cufe || false;
        result.dian_qr = this.dian_qr || false;

        // --- Forma y Medio de Pago DIAN ---
        result.dian_forma_pago = 'Contado';
        const medios = [];
        if (result.paymentlines && result.paymentlines.length > 0) {
            for (const line of result.paymentlines) {
                const name = (line.name || '').toLowerCase();
                if (name.includes('efectivo') || name.includes('cash')) {
                    medios.push('Efectivo');
                } else if (name.includes('transferencia') || name.includes('bank')) {
                    medios.push('Transferencia Bancaria');
                } else if (name.includes('nequi')) {
                    medios.push('Nequi');
                } else if (name.includes('daviplata')) {
                    medios.push('Daviplata');
                } else {
                    medios.push('TC');
                }
            }
        } else {
            medios.push('Efectivo');
        }
        result.dian_medios_pago = [...new Set(medios)].join(' / ');

        return result;
    }
});
