/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Main widget: Creates sidebar layout and moves product detail
publicWidget.registry.GuapanteProductSidebarLayout = publicWidget.Widget.extend({
    selector: '#product_detail',
    start: function () {
        var self = this;

        // Don't run in edit mode (Odoo Studio/Customization)
        if (window.location.href.indexOf('enable_editor') !== -1 ||
            $('body').hasClass('editor_enable') ||
            $('body').hasClass('o_web_studio_client_action')) {
            console.log('Guapante: Editor mode detected, skipping sidebar layout.');
            return this._super.apply(this, arguments);
        }

        var $productDetail = this.$el;

        // Check if sidebar layout already exists
        if ($productDetail.closest('.guapante-product-container').length) {
            console.log('Guapante: Sidebar layout already applied.');
            return this._super.apply(this, arguments);
        }

        // Create wrapper structure
        var $container = $('<div>', {
            class: 'container guapante-product-container mt-4'
        });

        var $row = $('<div>', { class: 'row' });

        // Create sidebar (Left column)
        var $sidebar = $('<aside>', {
            id: 'products_grid_before',
            class: 'col-lg-3 d-none d-lg-block'
        });

        // Create product content column (Right column)
        var $productColumn = $('<div>', {
            class: 'col-12 col-lg-9 guapante-product-content'
        });

        // Apply white card styles to product detail
        $productDetail.addClass('guapante-card bg-white shadow-sm rounded-4 p-4');

        // Insert wrapper before product detail
        $productDetail.before($container);

        // Build the structure
        $row.append($sidebar);
        $row.append($productColumn);
        $container.append($row);

        // Move product detail into the column
        $productColumn.append($productDetail);

        console.log('Guapante: Sidebar layout created via JavaScript.');

        // Load categories from controller context
        this._loadCategoriesFromContext($sidebar);

        return this._super.apply(this, arguments);
    },

    _loadCategoriesFromContext: function ($sidebar) {
        var self = this;

        // Categories should be available from the shop controller
        // We'll make an AJAX call to get them
        $.ajax({
            url: '/shop',
            method: 'GET',
            data: { 'category': 0 }, // Shop root
            success: function (html) {
                // Extract the categories sidebar from the shop page
                var $temp = $('<div>').html(html);
                var $categories = $temp.find('#o_shop_collapse_category').parent();

                if ($categories.length) {
                    $sidebar.html($categories.html());
                    console.log('Guapante: Categories loaded into sidebar.');
                } else {
                    // Fallback: show a placeholder
                    $sidebar.html('<h6 class="mb-3">Categorías</h6><p class="text-muted small">Ver todas en <a href="/shop">la tienda</a></p>');
                }
            },
            error: function () {
                $sidebar.html('<p class="text-muted">No hay categorías disponibles</p>');
            }
        });
    }
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

// Clean up stray text nodes - ejecutar DESPUÉS de que todo cargue
$(document).ready(function () {
    setTimeout(function () {
        // Remove the stray "s" from body
        $('body').contents().filter(function () {
            return this.nodeType === 3 && $.trim($(this).text()) === 's';
        }).remove();

        console.log('Guapante: Stray text cleanup completed.');
    }, 500);
});
