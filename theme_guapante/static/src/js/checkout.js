/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteCheckout = publicWidget.Widget.extend({
    selector: '.guapante-checkout-wrapper',
    events: {
        'change select[name="shipping_id"]': '_onShippingChange',
        'click #guapante_confirm_btn': '_onConfirmClick',
    },

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);
        console.log("[GuapanteCheckout] Widget started.");
        this._onShippingChange();
        return Promise.resolve();
    },

    /**
     * Handle shipping address dropdown changes.
     * Shows/hides the new address form.
     */
    _onShippingChange: function () {
        const $select = this.$('select[name="shipping_id"]');
        if ($select.length === 0) {
            console.log("[GuapanteCheckout] No shipping_id select found.");
            return;
        }

        const value = parseInt($select.val(), 10);
        const $newAddressForm = this.$('.guapante-new-address-form');
        if ($newAddressForm.length === 0) return;

        if (value > 0) {
            // Existing address selected → hide new address form
            console.log("[GuapanteCheckout] Existing address selected, hiding form.");
            $newAddressForm.addClass('d-none');
        } else {
            // No address or "Other" → show form
            console.log("[GuapanteCheckout] Showing new address form.");
            $newAddressForm.removeClass('d-none');
        }
    },

    /**
     * Handle "Confirmar Pedido" button click.
     * Collects all field values and submits via a dynamically created form
     * to bypass the nested-form issue.
     */
    _onConfirmClick: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        console.log("[GuapanteCheckout] Confirm button clicked.");

        const $btn = this.$('#guapante_confirm_btn');

        // 1. Basic validation
        const shippingId = parseInt(this.$('select[name="shipping_id"]').val() || '0', 10);
        const isNewAddress = shippingId <= 0;

        if (isNewAddress) {
            // Validate address fields
            const street = this.$('input[name="street"]').val();
            const city = this.$('input[name="city"]').val();
            if (!street || !city) {
                alert('Por favor complete los campos de dirección (Dirección y Ciudad).');
                return;
            }
        }

        // 2. Disable button to prevent double-click
        $btn.prop('disabled', true);
        $btn.html('<i class="fa fa-spinner fa-spin me-2"></i> Procesando...');

        // 3. Create a dynamic form and submit it
        const $form = $('<form>', {
            method: 'POST',
            action: '/shop/address',
        });

        // Add CSRF token
        const csrfToken = this.$('#csrf_token').val() ||
            document.querySelector('input[name="csrf_token"]')?.value ||
            odoo.csrf_token;

        $form.append($('<input>', { type: 'hidden', name: 'csrf_token', value: csrfToken }));

        // 4. Collect all field values and add to form
        const fieldsToCollect = ['name', 'email', 'phone', 'shipping_id', 'street', 'state_id', 'city', 'comment'];
        fieldsToCollect.forEach((fieldName) => {
            const $field = this.$('[name="' + fieldName + '"]');
            if ($field.length > 0) {
                $form.append($('<input>', {
                    type: 'hidden',
                    name: fieldName,
                    value: $field.val() || ''
                }));
            }
        });

        // 5. Append form to body and submit
        $form.appendTo('body');
        console.log("[GuapanteCheckout] Submitting dynamic form to /shop/address");
        $form.submit();
    },
});
