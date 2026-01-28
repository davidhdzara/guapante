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

        // Load categories from the hidden XML source
        this._loadCategoriesFromXML($sidebar);

        return this._super.apply(this, arguments);
    },

    _loadCategoriesFromXML: function ($sidebar) {
        // Find the hidden div with categories injected by XML
        var $sidebarSource = $('#guapante_sidebar_source');

        if ($sidebarSource.length) {
            // Clone the content and show it in the sidebar
            var $categoriesContent = $sidebarSource.children().clone();
            $sidebar.html($categoriesContent);

            // Remove the hidden source
            $sidebarSource.remove();

            console.log('Guapante: Categories loaded from XML template.');
        } else {
            // Fallback message
            $sidebar.html('<p class="text-muted">No hay categorías disponibles</p>');
            console.warn('Guapante: Category source not found.');
        }
    }
});

// Apply maturity level colors to variant circles
publicWidget.registry.GuapanteMaturityColors = publicWidget.Widget.extend({
    selector: '.js_product',
    start: function () {
        var self = this;

        // Find all color attribute labels (circles)
        this.$('label.css_attribute_color').each(function () {
            var $label = $(this);
            var title = $label.attr('title') || '';
            var valueName = $label.find('input').data('value_name') || '';
            var searchText = (title + ' ' + valueName).toLowerCase();

            // Determine maturity level and apply data attribute
            if (searchText.includes('verde') && !searchText.includes('pintón') && !searchText.includes('pinton') && !searchText.includes('maduro')) {
                $label.attr('data-maturity', 'verde');
            } else if (searchText.includes('pintón-maduro') || searchText.includes('pinton-maduro')) {
                $label.attr('data-maturity', 'pinton-maduro');
            } else if ((searchText.includes('pintón') || searchText.includes('pinton')) && !searchText.includes('maduro')) {
                $label.attr('data-maturity', 'pinton');
            } else if (searchText.includes('maduro') && !searchText.includes('pintón') && !searchText.includes('pinton')) {
                $label.attr('data-maturity', 'maduro');
            }
        });

        console.log('Guapante: Maturity colors applied.');

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
