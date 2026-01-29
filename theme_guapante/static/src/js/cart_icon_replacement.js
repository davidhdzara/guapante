/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Replace wishlist heart icon with cart icon in product cards
publicWidget.registry.GuapanteReplaceWishlistIcon = publicWidget.Widget.extend({
    selector: '.oe_product_card, .o_wsale_product_grid_wrapper',
    start: function () {
        var self = this;

        // Find all wishlist buttons and replace icon
        this.$('.o_add_wishlist').each(function () {
            var $button = $(this);

            // Replace the icon
            var $icon = $button.find('i');
            if ($icon.length) {
                $icon.removeClass('fa-heart fa-heart-o').addClass('fa-shopping-cart');
            }

            // Update attributes
            $button.attr('title', 'Agregar al carrito');
            $button.attr('aria-label', 'Agregar al carrito');
            $button.addClass('guapante-cart-icon');
        });

        console.log('Guapante: Wishlist icons replaced with cart icons.');

        return this._super.apply(this, arguments);
    },
});
