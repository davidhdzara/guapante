/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import wSaleUtils from "@website_sale/js/website_sale_utils";

/**
 * Guapante Packaging Selector Widget
 * Handles packaging selection on product page
 * - Displays available packagings for selected variant
 * - Updates when variant changes
 * - Manages quantity +/- buttons
 * - Hides original Odoo controls
 * - AJAX Add to Cart (Stays on page)
 */
publicWidget.registry.GuapanteUnitSelector = publicWidget.Widget.extend({
    selector: '.guapante-unit-selector-container',
    events: {
        'change .packaging-option': '_onPackagingChange',
        'input .guapante-qty-input': '_updatePackagingInfo',
        'change .guapante-qty-input': '_updatePackagingInfo',
        'click .guapante-qty-plus': '_onQuantityPlus',
        'click .guapante-qty-minus': '_onQuantityMinus',
        'click .guapante-add-to-cart-btn': '_onAddToCart',
    },

    start: function () {
        // Initialize current packaging
        this.currentPackaging = this._getSelectedPackaging();
        
        this._updatePackagingInfo();
        
        // Hide original Odoo controls
        this._hideOriginalControls();
        
        // Listen for variant changes
        this._setupVariantListener();

        console.log('Guapante: Packaging selector initialized', this.currentPackaging);

        return this._super.apply(this, arguments);
    },

    /**
     * Setup listener for variant changes to reload packagings
     */
    _setupVariantListener: function () {
        const self = this;
        
        // Listen for when variant input changes (Odoo updates this automatically)
        $(document).on('change', 'input[name="product_id"]', function() {
            self._onVariantChange();
        });
    },

    /**
     * Reload packagings when variant changes
     */
    _onVariantChange: async function () {
        const productId = $('input[name="product_id"]').val();
        
        if (!productId) {
            return;
        }

        console.log('Guapante: Variant changed to product_id:', productId);

        try {
            // Fetch packagings for new variant
            const packagings = await this._fetchPackagings(productId);
            
            // Rebuild packaging selector UI
            this._rebuildPackagingSelector(packagings, productId);
            
            // Update current packaging reference
            this.currentPackaging = this._getSelectedPackaging();
            
            // Update info display
            this._updatePackagingInfo();
            
        } catch (error) {
            console.error('Guapante: Error loading packagings', error);
        }
    },

    /**
     * Fetch packagings for a product variant via AJAX
     */
    _fetchPackagings: async function (productId) {
        const response = await fetch(`/shop/product/packagings/${productId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch packagings');
        }
        return await response.json();
    },

    /**
     * Rebuild packaging selector HTML with new packagings
     */
    _rebuildPackagingSelector: function (packagings, productId) {
        const $container = this.$('.guapante-packaging-options');
        $container.empty();

        if (packagings && packagings.length > 0) {
            packagings.forEach((pkg, index) => {
                const isChecked = index === 0;
                const radioHtml = `
                    <input 
                        type="radio" 
                        class="btn-check packaging-option" 
                        name="packaging_selector_${productId}"
                        id="pkg_${pkg.id}_${productId}"
                        value="${pkg.id}"
                        data-packaging-name="${pkg.name}"
                        data-packaging-qty="${pkg.qty}"
                        ${isChecked ? 'checked' : ''}
                        autocomplete="off"
                    />
                    <label 
                        class="btn btn-outline-success" 
                        for="pkg_${pkg.id}_${productId}">
                        ${pkg.name}
                    </label>
                `;
                $container.append(radioHtml);
            });

            // Update hidden field
            if (packagings[0]) {
                $('input[name="product_packaging_id"]').val(packagings[0].id);
            }
        } else {
            // Fallback: No packagings
            const radioHtml = `
                <input 
                    type="radio" 
                    class="btn-check packaging-option" 
                    name="packaging_selector_${productId}"
                    id="pkg_default_${productId}"
                    value="0"
                    data-packaging-name="Unidad"
                    data-packaging-qty="1"
                    checked
                    autocomplete="off"
                />
                <label 
                    class="btn btn-outline-success" 
                    for="pkg_default_${productId}">
                    Unidad
                </label>
            `;
            $container.append(radioHtml);
            $('input[name="product_packaging_id"]').val(0);
        }
    },

    /**
     * Hide original Odoo controls
     */
    _hideOriginalControls: function () {
        // Hide original quantity selector
        $('#o_wsale_cta_wrapper .css_quantity').addClass('d-none');

        // Hide original add to cart button
        $('#add_to_cart').addClass('d-none');
    },

    /**
     * AJAX Add to Cart Handler
     * Prevents page reload and updates cart badge
     */
    _onAddToCart: async function (ev) {
        ev.preventDefault();

        var $btn = $(ev.currentTarget);

        // FETCH DYNAMIC PRODUCT ID (Handles Variants)
        var $productInput = $('input[name="product_id"]');
        var productId = $productInput.val() || this.$el.data('product-id');

        var quantity = this._getQuantity();
        var packagingId = this._getSelectedPackagingId();

        // Visual feedback: Loading state
        $btn.addClass('disabled').html('<i class="fa fa-spinner fa-spin me-2"></i> Agregando...');

        try {
            const data = await $.ajax({
                url: '/shop/cart/update_json',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        product_id: parseInt(productId),
                        add_qty: quantity,
                        product_packaging_id: packagingId,
                        display: false,
                    }
                })
            });

            console.log('Guapante: Cart response data:', data);

            // Update Cart Badge
            var itemCount = data.cart_lines_count || data.cart_quantity || 0;
            var $badges = $('.my_cart_quantity, .o_wsale_my_cart .badge, .btn-cart-guapante .badge');
            $badges.text(itemCount).removeClass('d-none');

            if (itemCount > 0) {
                $badges.show();
                $badges.parent().removeClass('d-none');
            }

            // Visual feedback: Success
            $btn.removeClass('disabled').addClass('btn-success')
                .html('<i class="fa fa-check me-2"></i> Agregado');

            // Restore button after delay
            setTimeout(() => {
                $btn.html('<i class="fa fa-shopping-cart me-2"></i> Agregar al Pedido');
            }, 2000);

        } catch (error) {
            console.error("Guapante: Error adding to cart", error);
            $btn.removeClass('disabled').html('<i class="fa fa-exclamation-triangle me-2"></i> Error');
        }
    },

    /**
     * Get currently selected packaging info
     */
    _getSelectedPackaging: function () {
        const $selected = this.$('.packaging-option:checked');
        if ($selected.length) {
            return {
                id: parseInt($selected.val()),
                name: $selected.data('packaging-name'),
                qty: parseFloat($selected.data('packaging-qty')) || 1
            };
        }
        return { id: 0, name: 'Unidad', qty: 1 };
    },

    /**
     * Get selected packaging ID
     */
    _getSelectedPackagingId: function () {
        return this._getSelectedPackaging().id;
    },

    /**
     * Get current quantity value
     */
    _getQuantity: function () {
        var qty = parseFloat(this.$('.guapante-qty-input').val()) || 1;
        return Math.max(qty, 0.01); // Minimum 0.01
    },

    /**
     * Set quantity value
     */
    _setQuantity: function (value) {
        value = Math.max(value, 0.01);
        this.$('.guapante-qty-input').val(value.toFixed(2));
        this._updatePackagingInfo();
    },

    /**
     * Handle quantity plus button
     */
    _onQuantityPlus: function () {
        var currentQty = this._getQuantity();
        this._setQuantity(currentQty + 1);
    },

    /**
     * Handle quantity minus button
     */
    _onQuantityMinus: function () {
        var currentQty = this._getQuantity();
        this._setQuantity(Math.max(0.01, currentQty - 1));
    },

    /**
     * Handle packaging change event
     */
    _onPackagingChange: function (ev) {
        var newPackaging = this._getSelectedPackaging();
        
        console.log('Guapante: Packaging changed to', newPackaging);
        
        this.currentPackaging = newPackaging;
        this._updateHiddenPackagingField(newPackaging.id);
        this._updatePackagingInfo();
    },

    /**
     * Update packaging info display
     */
    _updatePackagingInfo: function () {
        var packaging = this._getSelectedPackaging();
        var quantity = this._getQuantity();
        var $infoText = this.$('.packaging-info-text');

        if (packaging.qty > 1) {
            var totalUnits = (quantity * packaging.qty).toFixed(0);
            $infoText.text(`${quantity} ${packaging.name} = ${totalUnits} unidades`);
            this.$('.guapante-packaging-info').fadeIn(200);
        } else {
            this.$('.guapante-packaging-info').fadeOut(200);
        }
    },

    /**
     * Update hidden field value for backend submission
     */
    _updateHiddenPackagingField: function (packagingId) {
        var $hiddenField = this.$('input[name="product_packaging_id"]');
        if ($hiddenField.length) {
            $hiddenField.val(packagingId);
        }
    },
});
