/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Guapante Cart Quantity Widget
 * Handles UoM-aware +/- quantity controls in the cart page
 */
publicWidget.registry.GuapanteCartQuantity = publicWidget.Widget.extend({
    selector: '.guapante-cart-qty-controls',
    events: {
        'click .guapante-cart-qty-plus': '_onPlus',
        'click .guapante-cart-qty-minus': '_onMinus',
        'change .guapante-cart-qty-input': '_onChange',
    },

    start: function () {
        this.lineId = parseInt(this.$el.data('line-id'));
        this.productId = parseInt(this.$el.data('product-id'));
        this.uomMode = this.$el.data('uom-mode') || 'unit';
        this.$input = this.$('.guapante-cart-qty-input');
        this._isUpdating = false;

        console.log('Guapante Cart: Qty controls init for line', this.lineId, 'mode:', this.uomMode);
        return this._super.apply(this, arguments);
    },

    // --------------------------------------------------------------------------
    // Event Handlers
    // --------------------------------------------------------------------------

    _onPlus: function (ev) {
        ev.preventDefault();
        if (this._isUpdating) return;

        let val = this._parseValue(this.$input.val());
        let step = this._getStep();
        let newVal = val + step;

        // Round to avoid float precision issues
        newVal = this._round(newVal);
        this._updateQuantity(newVal);
    },

    _onMinus: function (ev) {
        ev.preventDefault();
        if (this._isUpdating) return;

        let val = this._parseValue(this.$input.val());
        let step = this._getStep();
        let newVal = val - step;
        let min = this._getMin();

        if (newVal < min) {
            newVal = min;
        }

        newVal = this._round(newVal);
        this._updateQuantity(newVal);
    },

    _onChange: function (ev) {
        let val = this._parseValue($(ev.currentTarget).val());
        let min = this._getMin();

        if (val < min) {
            val = min;
        }

        val = this._round(val);
        this._updateQuantity(val);
    },

    _parseValue: function (val) {
        // Replace comma with dot for locales like ES/CO
        if (typeof val === 'string') {
            val = val.replace(',', '.');
        }
        return parseFloat(val) || 0;
    },

    // --------------------------------------------------------------------------
    // Logic
    // --------------------------------------------------------------------------

    _getStep: function () {
        switch (this.uomMode) {
            case 'kg': return 0.5;
            case 'g': return 50;
            default: return 1;
        }
    },

    _getMin: function () {
        switch (this.uomMode) {
            case 'kg': return 0.1;
            case 'g': return 50;
            default: return 1;
        }
    },

    _round: function (val) {
        if (this.uomMode === 'kg') {
            return Math.round(val * 100) / 100;
        }
        return Math.round(val);
    },

    _updateQuantity: async function (newQty) {
        this._isUpdating = true;
        const $controls = this.$el;
        const $buttons = $controls.find('button');

        // Visual feedback
        $buttons.prop('disabled', true);
        this.$input.val(newQty);

        // Calculate final qty in base UoM (always kg for weight products)
        let finalQty = newQty;
        if (this.uomMode === 'g') {
            finalQty = newQty / 1000.0;
        }

        try {
            await $.ajax({
                url: '/shop/cart/update_json',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        product_id: this.productId,
                        line_id: this.lineId,
                        set_qty: finalQty,
                        display: false,
                    }
                })
            });

            // Refresh the page to reflect changes
            window.location.reload();

        } catch (error) {
            console.error('Guapante Cart: Error updating quantity', error);
            // Revert input value
            this.$input.val(parseFloat(this.$input.val()) || 1);
        } finally {
            $buttons.prop('disabled', false);
            this._isUpdating = false;
        }
    },
});
