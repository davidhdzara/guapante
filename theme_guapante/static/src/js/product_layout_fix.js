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

            return this._super.apply(this, arguments);
        }

        var $productDetail = this.$el;

        // Check if sidebar layout already exists
        if ($productDetail.closest('.guapante-product-container').length) {

            return this._super.apply(this, arguments);
        }

        // Create wrapper structure
        var $container = $('<div>', {
            class: 'container guapante-product-container mt-2'
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

        // Remove Odoo's 'container' class from #product_detail to avoid
        // nested .container > .container (double max-width / padding).
        // The outer .guapante-product-container already provides the container.
        $productDetail.removeClass('container');

        // Insert wrapper before product detail
        $productDetail.before($container);

        // Build the structure
        $row.append($sidebar);
        $row.append($productColumn);
        $container.append($row);

        // Move product detail into the column
        $productColumn.append($productDetail);

        // ─── Fix ancestor overflow that breaks position: sticky ───
        // Odoo 18's #wrapwrap has overflow-x: hidden which creates a new
        // scroll context and completely breaks position: sticky on descendants.
        // Using overflow: clip preserves the clipping behavior without
        // creating a scroll context.
        $('#wrapwrap').css('overflow', 'clip');

        // ─── Strip Odoo's sticky from carousel AND section ───
        var $carousel = $productDetail.find('#o-carousel-product');
        if ($carousel.length) {
            $carousel.removeClass('position-sticky');
            $carousel.css({ 'position': 'relative', 'top': 'auto' });

            // Odoo's carousel JS re-applies position: sticky on EVERY scroll
            // event via inline styles. A MutationObserver nukes them instantly.
            var carouselEl = $carousel[0];
            var observer = new MutationObserver(function (mutations) {
                mutations.forEach(function (m) {
                    if (m.attributeName === 'style') {
                        var pos = carouselEl.style.position;
                        if (pos === 'sticky' || pos === '-webkit-sticky') {
                            carouselEl.style.position = 'relative';
                            carouselEl.style.top = 'auto';
                        }
                    }
                });
            });
            observer.observe(carouselEl, { attributes: true, attributeFilter: ['style'] });
        }
        $productDetail.removeClass('position-sticky');
        $productDetail.css({ 'position': '', 'top': '' });

        // Load categories from the hidden XML source
        this._loadCategoriesFromXML($sidebar);

        // ─── Fix breadcrumb separator (#7): / → > ───
        this._fixBreadcrumbSeparator();

        // ─── Add "Precio sujeto a cotización final" text below button (#18) ───
        var $addBtn = $productDetail.find('.guapante-add-to-cart-btn');
        if ($addBtn.length && !$addBtn.next('.guapante-disclaimer').length) {
            $addBtn.after('<p class="guapante-disclaimer">Precio sujeto a cotización final</p>');
        }

        return this._super.apply(this, arguments);
    },

    _fixBreadcrumbSeparator: function () {
        // Replace "/" separators with ">" in the breadcrumb
        var $breadcrumb = $('ol.breadcrumb, nav.breadcrumb, .breadcrumb');
        if ($breadcrumb.length) {
            // Odoo uses .breadcrumb-item with CSS ::before for separators
            // Override via CSS is cleaner, but also handle text separators
            $breadcrumb.find('.breadcrumb-item + .breadcrumb-item').each(function () {
                // The ::before content is set by Bootstrap CSS, override it
                $(this).css('--bs-breadcrumb-divider', '">"');
            });
        }
        // Also handle plain text separators in non-bootstrap breadcrumbs
        $('nav[aria-label="breadcrumb"]').contents().filter(function () {
            return this.nodeType === 3 && this.textContent.includes('/');
        }).each(function () {
            this.textContent = this.textContent.replace(/\s*\/\s*/g, ' > ');
        });
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

            // ─── Post-process sidebar (#1): Change header to "Filtros" ───
            this._refineSidebar($sidebar);
        } else {
            // Fallback message
            $sidebar.html('<p class="text-muted">No hay categorías disponibles</p>');
            console.warn('Guapante: Category source not found.');
        }
    },

    _refineSidebar: function ($sidebar) {
        // First pass: Remove ALL 'Categorías'/'Categorias' headers
        $sidebar.find('h5, h4, h3, b, strong').each(function () {
            var text = $(this).text().trim().toLowerCase();
            if (text === 'categorias' || text === 'categorías') {
                $(this).remove();
            }
        });

        // Ensure 'Filtros' header exists at the top
        var $header = $sidebar.find('.guapante-sidebar-header h5').first();
        if ($header.length) {
            $header.text('Filtros');
        } else {
            // Prepend header if missing
            $sidebar.prepend(
                '<div class="guapante-sidebar-header mb-2">' +
                '<h5 class="fw-bold mb-0">Filtros</h5>' +
                '<p class="text-muted small mb-3">Refinar catálogo</p>' +
                '</div>'
            );
        }

        // Remove 'Todos los productos' link
        $sidebar.find('a').each(function () {
            var text = $(this).text().trim().toLowerCase();
            if (text === 'todos los productos' || text === 'all products') {
                $(this).closest('li').length ? $(this).closest('li').remove() : $(this).remove();
            }
        });
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
                    // Smooth gradient: green → yellow → orange
                    colorStyle = 'background: linear-gradient(135deg, #10B981 0%, #34D399 20%, #FBBF24 50%, #F59E0B 80%, #F59E0B 100%);';
                } else if ((searchText.includes('pintón') || searchText.includes('pinton')) && !searchText.includes('maduro')) {
                    maturityLevel = 'pinton';
                    // Smooth gradient: green → yellow
                    colorStyle = 'background: linear-gradient(135deg, #10B981 0%, #34D399 30%, #FBBF24 70%, #FBBF24 100%);';
                } else if (searchText.includes('maduro') && !searchText.includes('pintón') && !searchText.includes('pinton')) {
                    maturityLevel = 'maduro';
                    colorStyle = 'background: #FBBF24;'; // Solid yellow
                } else if (searchText.includes('cascara negra') || searchText.includes('cáscara negra')) {
                    maturityLevel = 'cascara-negra';
                    // Gradient: almost black → dark brown → beige/yellow
                    colorStyle = 'background: linear-gradient(135deg, #27272A 0%, #451A03 50%, #D97706 85%, #FBBF24 100%);';
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

            // (#12) Add "Guía de maduración" link after the maturity section
            if (!$maturitySection.find('.guapante-maturity-guide').length) {
                var $guideLink = $('<a>', {
                    href: '#',
                    class: 'guapante-maturity-guide text-muted small d-flex align-items-center mt-1',
                    html: '<i class="fa fa-info-circle me-1"></i> Guía de maduración'
                });
                $guideLink.css({
                    'font-size': '0.75rem',
                    'text-decoration': 'none',
                    'color': '#9CA3AF'
                });
                $maturitySection.append($guideLink);
            }
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
            return this.nodeType === 3 && this.textContent.trim() === 's';
        }).remove();


    }, 500);
});
