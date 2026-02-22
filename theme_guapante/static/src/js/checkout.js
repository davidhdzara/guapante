/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteCheckout = publicWidget.Widget.extend({
    selector: '.guapante-checkout-wrapper',
    events: {
        'change #guapante_shipping_select': '_onShippingChange',
    },

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);

        return Promise.resolve();
    },

    /**
     * Handle shipping address dropdown changes.
     * Uses Odoo's native /shop/update_address JSON API to update
     * the order's partner_shipping_id, then reloads to show the
     * updated address details.
     */
    _onShippingChange: function (ev) {
        var partnerId = parseInt($(ev.currentTarget).val(), 10);
        if (!partnerId || partnerId <= 0) return;

        // Use $.ajax (frontend-compatible) instead of jsonrpc (backend-only)
        $.ajax({
            url: '/shop/update_address',
            method: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    partner_id: partnerId,
                    address_type: 'delivery',
                },
            }),
        }).then(function () {
            window.location.reload();
        }).catch(function (err) {
            console.error("[GuapanteCheckout] Error updating address:", err);
            var $wrapper = $('.guapante-checkout-wrapper');
            var $alert = $('<div class="alert alert-danger mt-2" role="alert">Error al actualizar la dirección. Por favor intente de nuevo.</div>');
            $wrapper.prepend($alert);
            setTimeout(function () { $alert.fadeOut(); }, 5000);
        });
    },
});
