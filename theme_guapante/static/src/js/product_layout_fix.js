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

        return this._super.apply(this, arguments);
    },
});

// Fallback: Aplicar estilos directamente al section (por si el container no existe)
publicWidget.registry.GuapanteProductStylesFallback = publicWidget.Widget.extend({
    selector: '#product_detail',
    start: function () {
        var $section = this.$el;

        // Aplicar clases de estilo si no las tiene
        if (!$section.hasClass('guapante-card')) {
            $section.addClass('guapante-card bg-white shadow-sm rounded-4 p-4');
            console.log('Guapante: Fallback styles applied to product detail.');
        }

        return this._super.apply(this, arguments);
    },
});

// Hide zero prices - mejorado para capturar todas las variaciones
publicWidget.registry.GuapanteHideZeroPrices = publicWidget.Widget.extend({
    selector: '#product_details',
    start: function () {
        var self = this;

        // Buscar todos los elementos con precio
        this.$('.oe_currency_value').each(function () {
            var priceText = $(this).text().trim();

            // Si el precio es 0,00 o variaciones
            if (priceText === '0,00' || priceText === '0.00' || priceText === '0' || priceText === '0,0') {
                // Ocultar el h3 padre que contiene este precio
                $(this).closest('h3').hide();
                // También ocultar el contenedor product_price si existe
                $(this).closest('.product_price').hide();
            }
        });

        return this._super.apply(this, arguments);
    },
});

// Clean up stray text nodes (like the "s" in body)
publicWidget.registry.GuapanteCleanupStrayText = publicWidget.Widget.extend({
    selector: 'body',
    start: function () {
        // Remove stray text nodes from body (direct children only)
        this.$el.contents().filter(function () {
            return this.nodeType === 3 && $(this).text().trim() !== '';
        }).remove();

        return this._super.apply(this, arguments);
    },
});
