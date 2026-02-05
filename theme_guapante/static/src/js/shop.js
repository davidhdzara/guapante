/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteShopRefine = publicWidget.Widget.extend({
    selector: '.guapante-shop-header',
    start: function () {
        // Only run if we're actually on a shop page (selector matched)
        if (!this.$el || this.$el.length === 0) {
            return this._super.apply(this, arguments);
        }

        // Move the Sorter (o_sortby_dropdown) to our custom header
        const $sorter = $('.o_sortby_dropdown');
        const $target = this.$el.find('.justify-content-between'); // The container with Title

        if ($sorter.length && $target.length) {
            // Append sorter to the flex container (it will sit on the right)
            $sorter.appendTo($target);
            $sorter.addClass('ms-auto'); // Push to right if not flex-between
        }

        // Safety: Ensure Price hiding persists (sometimes JS re-renders prices)
        const $prices = $('.product_price');
        if ($prices.length) {
            $prices.addClass('d-none');
        }

        return this._super.apply(this, arguments);
    }
});

// De Temporada Toggle Handler
publicWidget.registry.GuapanteSeasonalToggle = publicWidget.Widget.extend({
    selector: '#seasonalToggle',
    events: {
        'change': '_onToggleChange',
    },

    start: function () {
        this._super.apply(this, arguments);
        // Check if we're on a seasonal filtered page
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('is_seasonal') === '1') {
            this.el.checked = true;
        }
    },

    _onToggleChange: function (ev) {
        const isChecked = ev.currentTarget.checked;
        const url = new URL(window.location.href);

        if (isChecked) {
            // Add is_seasonal filter
            url.searchParams.set('is_seasonal', '1');
        } else {
            // Remove is_seasonal filter
            url.searchParams.delete('is_seasonal');
        }

        // Redirect to filtered URL
        window.location.href = url.toString();
    }
});
