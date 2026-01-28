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

// Apply maturity level colors by injecting color circles
publicWidget.registry.GuapanteMaturityColors = publicWidget.Widget.extend({
    selector: '.js_product',
    start: function () {
        var self = this;

        // Find the "Grado de Madurez" attribute section
        var $maturitySection = this.$('li[data-attribute_name="Grado de Madurez"]');

        if ($maturitySection.length) {
            // Iterate through each value in this attribute
            $maturitySection.find('.js_attribute_value').each(function () {
                var $item = $(this);
                var $label = $item.find('label');
                var $input = $label.find('input');
                var valueName = $input.data('value_name') || '';
                var title = $input.attr('title') || '';
                var searchText = (valueName + ' ' + title).toLowerCase();

                // Determine maturity level
                var maturityLevel = '';
                var colorStyle = '';

                if (searchText.includes('verde') && !searchText.includes('pintón') && !searchText.includes('pinton') && !searchText.includes('maduro')) {
                    maturityLevel = 'verde';
                    colorStyle = 'background: #10B981;'; // Solid green
                } else if (searchText.includes('pinton-maduro') || searchText.includes('pintón-maduro')) {
                    maturityLevel = 'pinton-maduro';
                    colorStyle = 'background: linear-gradient(90deg, #10B981 0%, #10B981 33%, #FBBF24 33%, #FBBF24 66%, #F59E0B 66%, #F59E0B 100%);';
                } else if ((searchText.includes('pintón') || searchText.includes('pinton')) && !searchText.includes('maduro')) {
                    maturityLevel = 'pinton';
                    colorStyle = 'background: linear-gradient(90deg, #10B981 0%, #10B981 50%, #FBBF24 50%, #FBBF24 100%);';
                } else if (searchText.includes('maduro') && !searchText.includes('pintón') && !searchText.includes('pinton')) {
                    maturityLevel = 'maduro';
                    colorStyle = 'background: #FBBF24;'; // Solid yellow
                }

                if (maturityLevel) {
                    // Create color circle indicator
                    var $colorCircle = $('<span>', {
                        class: 'guapante-maturity-indicator',
                        'data-maturity': maturityLevel,
                        style: colorStyle + ' width: 16px; height: 16px; border-radius: 50%; display: inline-block; margin-right: 8px; vertical-align: middle; border: 1.5px solid #E5E7EB;'
                    });

                    // Find the span with the text and prepend the circle
                    var $textSpan = $label.find('.radio_input_value span, .form-check-label span').first();

                    if ($textSpan.length) {
                        // Check if circle doesn't already exist
                        if (!$textSpan.prev('.guapante-maturity-indicator').length) {
                            $textSpan.before($colorCircle);
                        }
                    }

                    // Add data attribute to label for CSS targeting
                    $label.attr('data-maturity', maturityLevel);
                }
            });

            console.log('Guapante: Maturity color indicators injected.');
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
