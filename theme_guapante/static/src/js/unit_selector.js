/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import wSaleUtils from "@website_sale/js/website_sale_utils";

/**
 * Guapante Unit Selector Widget
 * Handles unit of measure selection (Unidades/Kg/g) on product page
 * - Updates equivalence display when unit or quantity changes
 * - Syncs hidden field for backend submission
 * - Manages quantity +/- buttons
 * - Hides original Odoo controls
 * - AJAX Add to Cart (Stays on page)
 */
publicWidget.registry.GuapanteUnitSelector = publicWidget.Widget.extend({
    selector: '.guapante-unit-selector-container',
    events: {
        'change .guapante-unit-selector input[type="radio"]': '_onUnitChange',
        'input .guapante-qty-input': '_updateEquivalence',
        'change .guapante-qty-input': '_updateEquivalence',
        'click .guapante-qty-plus': '_onQuantityPlus',
        'click .guapante-qty-minus': '_onQuantityMinus',
        'click .guapante-add-to-cart-btn': '_onAddToCart',
    },

    start: function () {
        this.conversions = this._getConversions();

        // Initialize current unit for conversion tracking
        this.currentUnit = this._getSelectedUnit();

        this._updateEquivalence();

        // Hide original Odoo controls
        this._hideOriginalControls();

        console.log('Guapante: Unit selector initialized', this.conversions);

        return this._super.apply(this, arguments);
    },

    /**
     * Hide original Odoo quantity selector and add to cart button
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
        // Odoo updates input[name="product_id"] when variants change.
        var $productInput = $('input[name="product_id"]');
        var productId = $productInput.val() || this.$el.data('product-id');

        var quantity = this._getQuantity();

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
                        display: false,
                    }
                })
            });

            // Update Cart Quantity Badge (Standard Odoo Selectors + Our Custom One)
            var newQty = data.cart_quantity || 0;

            // Update Headers/Footers
            $('.my_cart_quantity').text(newQty).parent().removeClass('d-none');
            // Update our custom badges (specifically checking the red badge span)
            $('a[href="/shop/cart"] .badge').text(newQty).removeClass('d-none');
            // If badge was hidden (count 0), show it (simple logic: just set text)
            if (newQty > 0) {
                $('a[href="/shop/cart"] .badge').show();
            }

            // Visual feedback: Success
            $btn.removeClass('disabled').addClass('btn-success').removeClass('btn-primary')
                .html('<i class="fa fa-check me-2"></i> Agregado');

            // Restore button after delay
            setTimeout(() => {
                $btn.html('<i class="fa fa-shopping-cart me-2"></i> Agregar al Pedido');
            }, 2000);

            // Optional: Animate product to cart (using standard Odoo util if available/desired)
            // For now, simpler button feedback is sufficient and robust.

        } catch (error) {
            console.error("Guapante: Error adding to cart", error);
            $btn.removeClass('disabled').html('<i class="fa fa-exclamation-triangle me-2"></i> Error');
        }
    },

    /**
     * Get conversion factors from data attributes
     * Falls back to demo values for testing until backend is ready
     */
    _getConversions: function () {
        var kgToUnits = parseFloat(this.$el.data('kg-to-units'));
        var gToUnits = parseFloat(this.$el.data('g-to-units'));

        // Use demo values if backend hasn't provided conversion factors
        return {
            kg_to_units: kgToUnits || 5.6,    // Demo: 1 kg = 5.6 unidades
            g_to_units: gToUnits || 0.0056,   // Demo: 1 g = 0.0056 unidades
        };
    },

    /**
     * Get currently selected unit
     */
    _getSelectedUnit: function () {
        return this.$('.guapante-unit-selector input[type="radio"]:checked').val() || 'unidades';
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
        this._updateEquivalence();
    },

    /**
     * Handle quantity plus button
     */
    _onQuantityPlus: function () {
        var currentQty = this._getQuantity();
        var selectedUnit = this._getSelectedUnit();

        // Increment by different amounts depending on unit
        var increment = selectedUnit === 'g' ? 100 : (selectedUnit === 'kg' ? 0.5 : 1);
        this._setQuantity(currentQty + increment);
    },

    /**
     * Handle quantity minus button
     */
    _onQuantityMinus: function () {
        var currentQty = this._getQuantity();
        var selectedUnit = this._getSelectedUnit();

        // Decrement by different amounts depending on unit
        var decrement = selectedUnit === 'g' ? 100 : (selectedUnit === 'kg' ? 0.5 : 1);
        this._setQuantity(Math.max(0.01, currentQty - decrement));
    },

    /**
     * Handle unit change event
     * Auto-converts quantity when switching between g/kg
     */
    _onUnitChange: function (ev) {
        var newUnit = $(ev.currentTarget).val();
        var previousUnit = this.currentUnit || 'unidades';
        var currentQty = this._getQuantity();

        // Auto-convert quantity when switching between weight units
        var convertedQty = this._convertQuantity(currentQty, previousUnit, newUnit);

        // Update quantity if conversion happened
        if (convertedQty !== currentQty) {
            this._setQuantity(convertedQty);
        }

        // Store current unit for next comparison
        this.currentUnit = newUnit;

        this._updateHiddenUnitField(newUnit);
        this._updateEquivalence();
        console.log('Guapante: Unit changed from', previousUnit, 'to', newUnit, '| Qty:', currentQty, '→', convertedQty);
    },

    /**
     * Convert quantity when switching between units
     * Rules:
     * - g → kg: divide by 1000
     * - kg → g: multiply by 1000
     * - g/kg → unidades: reset to 1
     * - unidades → g/kg: keep current value
     */
    _convertQuantity: function (qty, fromUnit, toUnit) {
        // g to kg
        if (fromUnit === 'g' && toUnit === 'kg') {
            return qty / 1000;
        }

        // kg to g
        if (fromUnit === 'kg' && toUnit === 'g') {
            return qty * 1000;
        }

        // From weight units to unidades: reset to 1
        if ((fromUnit === 'g' || fromUnit === 'kg') && toUnit === 'unidades') {
            return 1;
        }

        // From unidades to weight: keep current value
        if (fromUnit === 'unidades' && (toUnit === 'g' || toUnit === 'kg')) {
            return qty;
        }

        // No conversion needed
        return qty;
    },

    /**
     * Update equivalence display based on selected unit and quantity
     */
    _updateEquivalence: function () {
        var selectedUnit = this._getSelectedUnit();
        var quantity = this._getQuantity();
        var $equivalence = this.$('.guapante-unit-equivalence');
        var $equivalenceText = $equivalence.find('.equivalence-text');

        // Calculate and display equivalence
        if (selectedUnit === 'kg' && this.conversions.kg_to_units) {
            var equivalentUnits = (quantity * this.conversions.kg_to_units).toFixed(1);
            $equivalenceText.text('≃ ' + equivalentUnits + ' uds');
            $equivalence.fadeIn(200);
        } else if (selectedUnit === 'g' && this.conversions.g_to_units) {
            var equivalentUnits = (quantity * this.conversions.g_to_units).toFixed(1);
            $equivalenceText.text('≃ ' + equivalentUnits + ' uds');
            $equivalence.fadeIn(200);
        } else {
            $equivalence.fadeOut(200);
        }
    },

    /**
     * Update hidden field value for backend submission
     */
    _updateHiddenUnitField: function (unit) {
        var $hiddenField = this.$('input[name="product_uom"]');
        if ($hiddenField.length) {
            $hiddenField.val(unit);
        }
    },
});
