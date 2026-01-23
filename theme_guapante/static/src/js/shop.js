/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteShopRefine = publicWidget.Widget.extend({
    selector: '.guapante-shop-header',
    start: function () {
        // Move the Sorter (o_sortby_dropdown) to our custom header
        const $sorter = $('.o_sortby_dropdown');
        const $target = this.$el.find('.justify-content-between'); // The container with Title

        if ($sorter.length && $target.length) {
            // Append sorter to the flex container (it will sit on the right)
            $sorter.appendTo($target);
            $sorter.addClass('ms-auto'); // Push to right if not flex-between
        }

        // Safety: Ensure Price hiding persists (sometimes JS re-renders prices)
        $('.product_price').addClass('d-none');
    }
});
