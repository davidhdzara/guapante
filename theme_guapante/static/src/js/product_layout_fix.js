/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteProductLayout = publicWidget.Widget.extend({
    selector: '.guapante-product-container',
    start: function () {
        var self = this;
        // Buscar el section#product_detail que está fuera (hermano siguiente o cercano)
        var $productDetail = $('#product_detail');
        var $targetColumn = this.$('.guapante-product-content');

        // Solo mover si ambos existen y el producto no está ya dentro
        if ($productDetail.length && $targetColumn.length && !$targetColumn.find('#product_detail').length) {
            // Mover el nodo
            $targetColumn.append($productDetail);
            // Mostrar el section (por si estaba oculto para evitar FOUC, opcional)
            $productDetail.removeClass('d-none');
            console.log('Guapante: Product Detail moved to Sidebar Layout successfully.');
        }
    },
});
