/**
 * Seasonal Harvest — dynamic loader
 *
 * Looks for .s_seasonal_harvest_guapante on every page load and
 * populates it via /shop/seasonal-products. Works regardless of
 * what HTML version the website builder has saved.
 */
(function () {
    'use strict';

    function loadSeasonalProducts() {
        var section = document.querySelector('.s_seasonal_harvest_guapante');
        if (!section) return;

        var grid = section.querySelector('.row');
        if (!grid) return;

        // Show spinner while loading
        grid.innerHTML =
            '<div class="col-12 text-center py-4">' +
            '<i class="fa fa-spinner fa-spin text-muted fs-4"></i>' +
            '</div>';

        fetch('/shop/seasonal-products')
            .then(function (r) { return r.text(); })
            .then(function (html) { grid.innerHTML = html; })
            .catch(function () { grid.innerHTML = ''; });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadSeasonalProducts);
    } else {
        loadSeasonalProducts();
    }
})();
