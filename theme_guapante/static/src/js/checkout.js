/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteCheckout = publicWidget.Widget.extend({
    selector: '.guapante-checkout-wrapper',
    events: {
        'change select[name="shipping_id"]': '_onShippingChange',
    },

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);
        console.log("[GuapanteCheckout] Widget started.");
        // Initialize state based on current value
        this._onShippingChange();
        return Promise.resolve();
    },

    /**
     * Handles the change event of the shipping address dropdown.
     * Shows/hides the new address form AND toggles 'required' attributes
     * so HTML5 validation does not block form submission.
     */
    _onShippingChange: function () {
        console.log("[GuapanteCheckout] _onShippingChange called.");

        const $select = this.$('select[name="shipping_id"]');
        if ($select.length === 0) {
            console.log("[GuapanteCheckout] No shipping_id select found, keeping form visible.");
            return;
        }

        const value = $select.val();
        console.log("[GuapanteCheckout] Selected value:", value);

        const $newAddressForm = this.$('.guapante-new-address-form');
        if ($newAddressForm.length === 0) {
            console.warn("[GuapanteCheckout] WARNING: .guapante-new-address-form not found!");
            return;
        }

        // Fields that are required only when entering a NEW address
        const $requiredFields = $newAddressForm.find('input[name="street"], input[name="city"], select[name="state_id"]');

        const intValue = parseInt(value, 10);

        // Logic:
        // -1: "Otra dirección..." -> Show form, enable required
        //  0: Placeholder "Escoge una dirección..." -> Show form, enable required
        // >0: Existing Address -> Hide form, disable required
        if (intValue > 0) {
            console.log("[GuapanteCheckout] Hiding new address form, removing required.");
            $newAddressForm.addClass('d-none');
            $requiredFields.removeAttr('required');
        } else {
            console.log("[GuapanteCheckout] Showing new address form, adding required.");
            $newAddressForm.removeClass('d-none');
            $requiredFields.attr('required', 'required');
        }
    },
});
