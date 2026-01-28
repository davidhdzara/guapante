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

        // Fetch and inject categories (we need to call the template)
        // For now, we'll load it via AJAX or use a simple placeholder
        // TODO: Need to fetch categories properly
        $sidebar.html('<h5>Categorías</h5><p class="text-muted small">Cargando...</p>');

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

        // Now fetch categories and populate sidebar
        this._loadCategories($sidebar);

        return this._super.apply(this, arguments);
    },

    _loadCategories: function ($sidebar) {
        // Fetch categories from the controller context
        // Since we're in frontend, we can access the categories from the page
        var $categoriesListOnPage = $('#o_shop_collapse_category');

        if ($categoriesListOnPage.length) {
            // Clone the existing categories list
            var $clonedCategories = $categoriesListOnPage.clone();
            $clonedCategories.removeAttr('id'); // Remove ID to avoid duplicates
            $sidebar.html($clonedCategories);
            console.log('Guapante: Categories loaded into sidebar.');
        } else {
            $sidebar.html('<p class="text-muted">No hay categorías disponibles</p>');
        }
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

// Clean up stray text nodes (like the "s" in body)
publicWidget.registry.GuapanteCleanupStrayText = publicWidget.Widget.extend({
    selector: 'body',
    start: function () {
        try {
            // Remove stray text nodes from body (direct children only)
            this.$el.contents().filter(function () {
                return this.nodeType === 3 && $(this).text().trim() !== '';
            }).remove();
        } catch (e) {
            // Silently fail if there's an issue - no need to log
        }

        return this._super.apply(this, arguments);
    },
});
