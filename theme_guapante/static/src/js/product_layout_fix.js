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
        if ($productDetail.length && $targetColumn.length) {
            // Agregar clases de estilo al section (ya que XML no funciona)
            $productDetail.addClass('guapante-card bg-white shadow-sm rounded-4 p-4');

            if (!$targetColumn.find('#product_detail').length) {
                // Mover el nodo
                $targetColumn.append($productDetail);
                console.log('Guapante: Product Detail moved to Sidebar Layout.');
            }

            // SIEMPRE mostrar el section al finalizar, haya habido movimiento o si ya estaba allí.
            // Esto asegura que el contenido no quede oculto si el script corre dos veces o si hay caché.
            $productDetail.removeClass('d-none');
        }
    },
});
