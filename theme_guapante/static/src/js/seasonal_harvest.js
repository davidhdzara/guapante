/** @odoo-module **/

/**
 * Seasonal Harvest — dynamic loader
 *
 * Looks for .s_seasonal_harvest_guapante on every page load and
 * populates it via /shop/seasonal-products.
 * LOW-04 FIX: Converted from IIFE to Odoo publicWidget pattern.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteSeasonalHarvest = publicWidget.Widget.extend({
    selector: '.s_seasonal_harvest_guapante',

    start: function () {
        var $grid = this.$('.row');
        if (!$grid.length) return this._super.apply(this, arguments);

        // Show spinner while loading
        $grid.html(
            '<div class="col-12 text-center py-4">' +
            '<i class="fa fa-spinner fa-spin text-muted fs-4"></i>' +
            '</div>'
        );

        fetch('/shop/seasonal-products')
            .then(function (r) { return r.text(); })
            .then(function (html) { $grid.html(html); })
            .catch(function () { $grid.html(''); });

        return this._super.apply(this, arguments);
    },
});
