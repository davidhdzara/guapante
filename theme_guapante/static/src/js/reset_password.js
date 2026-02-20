/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Handles the password visibility toggle on the reset password page.
 */
publicWidget.registry.GuapantePasswordToggle = publicWidget.Widget.extend({
    selector: '.oe_reset_password_form',
    events: {
        'click .toggle-password': '_onTogglePassword',
    },

    _onTogglePassword: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const $input = $btn.closest('.position-relative').find('input');
        const $icon = $btn.find('i');

        if ($input.attr('type') === 'password') {
            $input.attr('type', 'text');
            $icon.removeClass('fa-eye').addClass('fa-eye-slash');
        } else {
            $input.attr('type', 'password');
            $icon.removeClass('fa-eye-slash').addClass('fa-eye');
        }
    },
});
