/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Guapante Search Overlay — Rappi-style full-screen product search.
 *
 * Lifecycle:
 *   1. User taps search icon → overlay slides up
 *   2. Categories + recent searches shown
 *   3. User types → debounced 300 ms → calls /shop/search/products
 *   4. Results rendered as cards with inline add-to-cart
 *   5. + button expands mini UoM/qty selector → confirms add to cart
 */
publicWidget.registry.GuapanteSearchOverlay = publicWidget.Widget.extend({
    selector: '#guapante_search_overlay',

    events: {
        'input #guapante_search_input': '_onSearchInput',
        'click #guapante_search_cancel': '_close',
        'click #guapante_search_clear': '_onClearInput',
        'click #guapante_clear_recents': '_onClearRecents',
        'click .guapante-recent-chip': '_onRecentClick',
        'click .guapante-quick-add-btn': '_onQuickAdd',
        'click .guapante-mini-uom-btn': '_onMiniUomChange',
        'click .guapante-mini-qty-btn': '_onMiniQtyBtn',
        'input .guapante-mini-qty-input': '_onMiniQtyInput',
        'click .guapante-mini-add-confirm': '_onMiniAddConfirm',
        'keydown #guapante_search_input': '_onSearchKeydown',
    },

    init: function () {
        this._super.apply(this, arguments);
        this._debounceTimer = null;
        this._currentQuery = '';
        this._categoriesLoaded = false;
    },

    start: function () {
        this._super.apply(this, arguments);

        // ─ Cache DOM references ─
        this.$overlay = this.$el;
        this.$input = this.$('#guapante_search_input');
        this.$clearBtn = this.$('#guapante_search_clear');
        this.$emptyState = this.$('#guapante_search_empty');
        this.$loading = this.$('#guapante_search_loading');
        this.$noResults = this.$('#guapante_search_no_results');
        this.$results = this.$('#guapante_search_results');
        this.$recentsSection = this.$('#guapante_search_recents');
        this.$recentsList = this.$('#guapante_recents_list');
        this.$categoriesGrid = this.$('#guapante_categories_grid');

        // ─ Bind the trigger button ─
        $(document).on('click.guapanteSearch', '#guapante_search_trigger', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            this._open();
        });

        // ─ ESC to close ─
        $(document).on('keydown.guapanteSearch', (ev) => {
            if (ev.key === 'Escape' && this.$overlay.hasClass('active')) {
                this._close();
            }
        });

        this._renderRecents();
    },

    destroy: function () {
        $(document).off('.guapanteSearch');
        this._super.apply(this, arguments);
    },

    // ═══════════════════════════════════════════
    // Open / Close
    // ═══════════════════════════════════════════

    _open: function () {
        this.$overlay.addClass('active');
        // Prevent body scroll
        $('body').css('overflow', 'hidden');
        // Focus input with a small delay for the animation
        setTimeout(() => {
            this.$input.trigger('focus');
        }, 100);
        // Load categories on first open
        if (!this._categoriesLoaded) {
            this._loadCategories();
        }
        this._showState('empty');
        this._renderRecents();
    },

    _close: function () {
        this.$overlay.removeClass('active');
        $('body').css('overflow', '');
        this.$input.val('').trigger('blur');
        this.$clearBtn.addClass('d-none');
        this._currentQuery = '';
        if (this._debounceTimer) {
            clearTimeout(this._debounceTimer);
        }
    },

    // ═══════════════════════════════════════════
    // State Management
    // ═══════════════════════════════════════════

    _showState: function (state) {
        this.$emptyState.toggleClass('d-none', state !== 'empty');
        this.$loading.toggleClass('d-none', state !== 'loading');
        this.$noResults.toggleClass('d-none', state !== 'no-results');
        this.$results.toggleClass('d-none', state !== 'results');
    },

    // ═══════════════════════════════════════════
    // Search
    // ═══════════════════════════════════════════

    _onSearchInput: function () {
        var query = this.$input.val().trim();

        // Toggle clear button
        this.$clearBtn.toggleClass('d-none', query.length === 0);

        // Debounce
        if (this._debounceTimer) {
            clearTimeout(this._debounceTimer);
        }

        if (query.length < 2) {
            this._showState('empty');
            this._currentQuery = '';
            return;
        }

        this._showState('loading');
        this._debounceTimer = setTimeout(() => {
            this._executeSearch(query);
        }, 300);
    },

    _onSearchKeydown: function (ev) {
        if (ev.key === 'Escape') {
            this._close();
        }
    },

    _onClearInput: function () {
        this.$input.val('').trigger('focus');
        this.$clearBtn.addClass('d-none');
        this._showState('empty');
        this._currentQuery = '';
    },

    _executeSearch: async function (query) {
        this._currentQuery = query;

        try {
            var data = await $.ajax({
                url: '/shop/search/products',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: { query: query, limit: 12 },
                }),
            });

            // Check if query changed while waiting
            if (query !== this._currentQuery) return;

            // Handle JSON-RPC error responses
            if (data && data.error) {
                console.error('Guapante Search: server error', data.error);
                this._showState('no-results');
                return;
            }

            var result = (data && data.result) ? data.result : data;

            // Surface server-side errors returned in the result
            if (result && result.error) {
                console.error('Guapante Search: endpoint error', result.error);
            }

            var products = result.products || [];

            if (products.length === 0) {
                this._showState('no-results');
            } else {
                this._renderResults(products);
                this._showState('results');
                this._saveRecentSearch(query);
            }
        } catch (err) {
            console.error('Guapante Search: error', err);
            this._showState('no-results');
        }
    },

    // ═══════════════════════════════════════════
    // Render Results
    // ═══════════════════════════════════════════

    _renderResults: function (products) {
        var html = '';
        products.forEach(function (p) {
            var uomLabel = p.is_weight_uom ? 'por Kg' : p.uom_name;

            // Build mini UoM toggle
            var uomToggle = '';
            if (p.is_weight_uom) {
                // Weight products: show Kg / Gramos / Unidad toggle
                uomToggle = '<div class="guapante-mini-uom-toggle">'
                    + '<button class="guapante-mini-uom-btn active" data-mode="kg">Kg</button>'
                    + '<button class="guapante-mini-uom-btn" data-mode="g">Gramos</button>';
                if (p.has_packaging) {
                    uomToggle += '<button class="guapante-mini-uom-btn" data-mode="unit">Unidad</button>';
                }
                uomToggle += '</div>';
            } else {
                // SEARCH-01 FIX: Non-weight products get a static "Unidades" label
                uomToggle = '<div class="guapante-mini-uom-label">'
                    + '<span class="guapante-mini-uom-badge">Unidades</span>'
                    + '</div>';
            }

            // Build packaging selector (for unit mode)
            var pkgSelector = '';
            if (p.has_packaging && p.packagings.length > 1) {
                pkgSelector = '<div class="guapante-mini-pkg-select d-none">';
                p.packagings.forEach(function (pkg, idx) {
                    pkgSelector += '<button class="guapante-mini-uom-btn'
                        + (idx === 0 ? ' active' : '')
                        + '" data-pkg-id="' + pkg.id
                        + '" data-pkg-qty="' + pkg.qty
                        + '" data-pkg-name="' + pkg.name + '">'
                        + pkg.name + '</button>';
                });
                pkgSelector += '</div>';
            }

            // Default qty and step based on UoM
            var defaultQty = '1';
            var step = p.is_weight_uom ? '0.5' : '1';
            var minVal = p.is_weight_uom ? '0.1' : '1';

            html += '<div class="guapante-result-card"'
                + ' data-product-id="' + p.id + '"'
                + ' data-tmpl-id="' + p.product_tmpl_id + '"'
                + ' data-is-weight="' + (p.is_weight_uom ? '1' : '0') + '"'
                + ' data-has-pkg="' + (p.has_packaging ? '1' : '0') + '"'
                + ' data-packagings=\'' + JSON.stringify(p.packagings || []) + '\''
                + '>'
                // Image + quick add
                + '<div class="guapante-result-img-wrap">'
                + '<a href="/shop/product/' + p.product_tmpl_id + '">'
                + '<img src="' + p.image_url + '" alt="' + p.name + '" loading="lazy"/>'
                + '</a>'
                + '<button type="button" class="guapante-quick-add-btn" title="Agregar">'
                + '<i class="fa fa-plus"></i>'
                + '</button>'
                + '</div>'
                // Info
                + '<div class="guapante-result-info">'
                + '<div class="guapante-result-name">'
                + '<a href="/shop/product/' + p.product_tmpl_id + '">' + p.name + '</a>'
                + '</div>'
                + '<p class="guapante-result-uom">' + uomLabel + '</p>'
                + '</div>'
                // Expandable cart controls
                + '<div class="guapante-result-cart-expand">'
                + uomToggle
                + pkgSelector
                + '<div class="guapante-mini-qty-row">'
                + '<button type="button" class="guapante-mini-qty-btn" data-action="minus">'
                + '<i class="fa fa-minus"></i>'
                + '</button>'
                + '<input type="text" class="guapante-mini-qty-input"'
                + ' value="' + defaultQty + '"'
                + ' data-step="' + step + '"'
                + ' data-min="' + minVal + '"'
                + ' inputmode="decimal" />'
                + '<button type="button" class="guapante-mini-qty-btn" data-action="plus">'
                + '<i class="fa fa-plus"></i>'
                + '</button>'
                + '</div>'
                + '<button type="button" class="guapante-mini-add-confirm">'
                + '<i class="fa fa-shopping-cart"></i> Agregar'
                + '</button>'
                + '</div>'
                + '</div>';
        });

        this.$results.html(html);
    },

    // ═══════════════════════════════════════════
    // Quick Add (expand card)
    // ═══════════════════════════════════════════

    _onQuickAdd: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var $card = $(ev.currentTarget).closest('.guapante-result-card');
        var $expand = $card.find('.guapante-result-cart-expand');

        // Close any other expanded cards
        this.$('.guapante-result-cart-expand.active').not($expand).removeClass('active');

        // Toggle this card
        $expand.toggleClass('active');
    },

    // ═══════════════════════════════════════════
    // Mini UoM Toggle
    // ═══════════════════════════════════════════

    _onMiniUomChange: function (ev) {
        ev.preventDefault();
        var $btn = $(ev.currentTarget);
        var $card = $btn.closest('.guapante-result-card');
        var $toggle = $btn.closest('.guapante-mini-uom-toggle');
        var mode = $btn.data('mode');

        // Update active state
        $toggle.find('.guapante-mini-uom-btn').removeClass('active');
        $btn.addClass('active');

        // Update qty input defaults
        var $qtyInput = $card.find('.guapante-mini-qty-input');
        var $pkgSelect = $card.find('.guapante-mini-pkg-select');

        switch (mode) {
            case 'kg':
                $qtyInput.val('1').attr('data-step', '0.5').attr('data-min', '0.1');
                $pkgSelect.addClass('d-none');
                break;
            case 'g':
                $qtyInput.val('500').attr('data-step', '50').attr('data-min', '50');
                $pkgSelect.addClass('d-none');
                break;
            case 'unit':
                $qtyInput.val('1').attr('data-step', '1').attr('data-min', '1');
                $pkgSelect.removeClass('d-none');
                break;
        }
    },

    // ═══════════════════════════════════════════
    // Mini Qty Controls
    // ═══════════════════════════════════════════

    _onMiniQtyBtn: function (ev) {
        ev.preventDefault();
        var $btn = $(ev.currentTarget);
        var $input = $btn.closest('.guapante-mini-qty-row').find('.guapante-mini-qty-input');
        var step = parseFloat($input.attr('data-step')) || 1;
        var min = parseFloat($input.attr('data-min')) || 0.1;
        var val = this._parseNum($input.val());

        if ($btn.data('action') === 'plus') {
            val += step;
        } else {
            val = Math.max(min, val - step);
        }

        // SEARCH-02 FIX: Round to avoid floating-point drift, display plain number
        val = Math.round(val * 1000) / 1000;
        $input.val(this._formatNum(val));
    },

    _onMiniQtyInput: function (ev) {
        // Allow free text input, will be parsed on add
    },

    // ═══════════════════════════════════════════
    // Add to Cart (confirm)
    // ═══════════════════════════════════════════

    _onMiniAddConfirm: async function (ev) {
        ev.preventDefault();
        var $btn = $(ev.currentTarget);
        var $card = $btn.closest('.guapante-result-card');
        var productId = parseInt($card.data('product-id'));
        var isWeight = $card.data('is-weight') === 1 || $card.data('is-weight') === '1';

        // Determine current UoM mode
        var $activeMode = $card.find('.guapante-mini-uom-toggle .guapante-mini-uom-btn.active');
        var mode = $activeMode.length ? $activeMode.data('mode') : (isWeight ? 'kg' : 'unit');

        // Get quantity
        var qtyInput = this._parseNum($card.find('.guapante-mini-qty-input').val());
        var finalQty = qtyInput;
        var packagingId = 0;

        if (mode === 'g') {
            finalQty = qtyInput / 1000.0;
        } else if (mode === 'unit') {
            var $activePkg = $card.find('.guapante-mini-pkg-select .guapante-mini-uom-btn.active');
            if ($activePkg.length) {
                packagingId = parseInt($activePkg.data('pkg-id')) || 0;
                var pkgQty = parseFloat($activePkg.data('pkg-qty')) || 1;
                if (isWeight) {
                    finalQty = qtyInput * pkgQty;
                }
            }
        }

        if (finalQty <= 0 || isNaN(finalQty)) return;
        finalQty = Math.round(finalQty * 1000) / 1000;

        // Button loading state
        $btn.addClass('loading').html('<i class="fa fa-spinner fa-spin"></i> Agregando...');

        try {
            var data = await $.ajax({
                url: '/shop/cart/update_json',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        product_id: productId,
                        add_qty: finalQty,
                        product_packaging_id: packagingId,
                        uom_mode: mode,
                        display: false,
                    },
                }),
            });

            var result = (data && data.result) ? data.result : data;
            // SEARCH-03 FIX: Prefer cart_quantity (total items) over cart_lines_count (line count)
            var itemCount = result.cart_quantity != null ? result.cart_quantity : (result.cart_lines_count || 0);

            // Update cart badges everywhere
            var $badges = $('.my_cart_quantity');
            if (itemCount > 0) {
                $badges.text(itemCount).removeClass('d-none').show();
            } else {
                $badges.text('').addClass('d-none');
            }

            // Success feedback
            $btn.removeClass('loading').addClass('success')
                .html('<i class="fa fa-check"></i> Agregado');
            var $quickBtn = $card.find('.guapante-quick-add-btn');
            $quickBtn.addClass('added').html('<i class="fa fa-check"></i>');

            setTimeout(() => {
                $btn.removeClass('success').html('<i class="fa fa-shopping-cart"></i> Agregar');
                $quickBtn.removeClass('added').html('<i class="fa fa-plus"></i>');
                // Collapse the expansion
                $card.find('.guapante-result-cart-expand').removeClass('active');
            }, 1500);

        } catch (err) {
            console.error('Guapante Search: add to cart error', err);
            $btn.removeClass('loading').html('<i class="fa fa-exclamation-triangle"></i> Error');
            setTimeout(() => {
                $btn.html('<i class="fa fa-shopping-cart"></i> Agregar');
            }, 2000);
        }
    },

    // ═══════════════════════════════════════════
    // Categories
    // ═══════════════════════════════════════════

    _loadCategories: async function () {
        try {
            var data = await $.ajax({
                url: '/shop/search/categories',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {},
                }),
            });

            var result = (data && data.result) ? data.result : data;
            if (!Array.isArray(result) || result.length === 0) return;

            var html = '';
            result.forEach(function (cat) {
                var imgHtml = cat.has_image && cat.image_url
                    ? '<img src="' + cat.image_url + '" alt="' + cat.name + '"/>'
                    : '<span class="guapante-categ-icon-fallback"><i class="fa fa-leaf"></i></span>';

                html += '<a href="' + cat.url + '" class="guapante-category-chip">'
                    + imgHtml
                    + '<span>' + cat.name + '</span></a>';
            });

            this.$categoriesGrid.html(html);
            this._categoriesLoaded = true;
        } catch (err) {
            console.error('Guapante Search: load categories error', err);
        }
    },

    // ═══════════════════════════════════════════
    // Recent Searches (localStorage)
    // ═══════════════════════════════════════════

    _getRecents: function () {
        try {
            return JSON.parse(localStorage.getItem('guapante_recent_searches') || '[]');
        } catch (_e) {
            return [];
        }
    },

    _saveRecentSearch: function (query) {
        var recents = this._getRecents();
        // Remove duplicate
        recents = recents.filter(function (r) { return r.toLowerCase() !== query.toLowerCase(); });
        // Add to front
        recents.unshift(query);
        // Keep max 10
        recents = recents.slice(0, 10);
        try {
            localStorage.setItem('guapante_recent_searches', JSON.stringify(recents));
        } catch (_e) { /* quota exceeded or private mode */ }
    },

    _renderRecents: function () {
        var recents = this._getRecents();
        if (recents.length === 0) {
            this.$recentsSection.addClass('d-none');
            return;
        }
        this.$recentsSection.removeClass('d-none');
        var html = '';
        recents.forEach(function (term) {
            html += '<button type="button" class="guapante-recent-chip">'
                + '<i class="fa fa-clock-o"></i>'
                + '<span>' + $('<span>').text(term).html() + '</span>'
                + '</button>';
        });
        this.$recentsList.html(html);
    },

    _onRecentClick: function (ev) {
        var term = $(ev.currentTarget).find('span').text().trim();
        this.$input.val(term);
        this.$clearBtn.removeClass('d-none');
        this._showState('loading');
        this._executeSearch(term);
    },

    _onClearRecents: function () {
        try {
            localStorage.removeItem('guapante_recent_searches');
        } catch (_e) { /* ignore */ }
        this.$recentsSection.addClass('d-none');
        this.$recentsList.empty();
    },

    // ═══════════════════════════════════════════
    // Helpers
    // ═══════════════════════════════════════════

    _parseNum: function (val) {
        if (typeof val === 'string') {
            // SEARCH-02 FIX: Accept both comma and period as decimal separator
            val = val.replace(/\s/g, '').replace(',', '.');
        }
        return parseFloat(val) || 0;
    },

    _formatNum: function (val) {
        // SEARCH-02 FIX: Use plain numbers (no locale formatting) to avoid
        // parse confusion. The input is for machine processing, not display.
        if (typeof val === 'number') {
            // Remove trailing zeros for cleaner display (1.0 → 1, 0.500 → 0.5)
            return parseFloat(val.toFixed(3)).toString();
        }
        return val;
    },
});
