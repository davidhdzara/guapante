/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Guapante Unit Selector Widget
 * Handles unit of measure selection (Unidades/Kg/g) on product page
 * - Updates equivalence display when unit or quantity changes
 * - Syncs hidden field for backend submission
 * - Manages quantity +/- buttons
 */
publicWidget.registry.GuapanteUnitSelector = publicWidget.Widget.extend({
    selector: '.guapante-unit-selector-container',
    events: {
        'change .guapante-unit-selector input[type="radio"]': '_onUnitChange',
        'input .guapante-qty-input': '_updateEquivalence',
        'change .guapante-qty-input': '_updateEquivalence',
        'click .guapante-qty-plus': '_onQuantityPlus',
        'click .guapante-qty-minus': '_onQuantityMinus',
    },

    start: function () {
        this.conversions = this._getConversions();
        this._updateEquivalence();
        console.log('Guapante: Unit selector initialized', this.conversions);

        return this._super.apply(this, arguments);
    },

    /**
     * Get conversion factors from data attributes
     * Falls back to demo values for testing until backend is ready
     */
    _getConversions: function () {
        var kgToUnits = parseFloat(this.$el.data('kg-to-units'));
        var gToUnits = parseFloat(this.$el.data('g-to-units'));

        // Use demo values if backend hasn't provided conversion factors
        return {
            kg_to_units: kgToUnits || 5.6,    // Demo: 1 kg = 5.6 unidades
            g_to_units: gToUnits || 0.0056,   // Demo: 1 g = 0.0056 unidades
        };
    },

    /**
     * Get currently selected unit
     */
    _getSelectedUnit: function () {
        return this.$('.guapante-unit-selector input[type="radio"]:checked').val() || 'unidades';
    },

    /**
     * Get current quantity value
     */
    _getQuantity: function () {
        var qty = parseFloat(this.$('.guapante-qty-input').val()) || 1;
        return Math.max(qty, 0.01); // Minimum 0.01
    },

    /**
     * Set quantity value
     */
    _setQuantity: function (value) {
        value = Math.max(value, 0.01);
        this.$('.guapante-qty-input').val(value.toFixed(2));
        this._updateEquivalence();
    },

    /**
     * Handle quantity plus button
     */
    _onQuantityPlus: function () {
        var currentQty = this._getQuantity();
        var selectedUnit = this._getSelectedUnit();

        // Increment by different amounts depending on unit
        var increment = selectedUnit === 'g' ? 100 : (selectedUnit === 'kg' ? 0.5 : 1);
        this._setQuantity(currentQty + increment);
    },

    /**
     * Handle quantity minus button
     */
    _onQuantityMinus: function () {
        var currentQty = this._getQuantity();
        var selectedUnit = this._getSelectedUnit();

        // Decrement by different amounts depending on unit
        var decrement = selectedUnit === 'g' ? 100 : (selectedUnit === 'kg' ? 0.5 : 1);
        this._setQuantity(Math.max(0.01, currentQty - decrement));
    },

    /**
     * Handle unit change event
     */
    _onUnitChange: function (ev) {
        var selectedUnit = $(ev.currentTarget).val();
        this._updateHiddenUnitField(selectedUnit);
        this._updateEquivalence();
        console.log('Guapante: Unit changed to', selectedUnit);
    },

    /**
     * Update equivalence display based on selected unit and quantity
     */
    _updateEquivalence: function () {
        var selectedUnit = this._getSelectedUnit();
        var quantity = this._getQuantity();
        var $equivalence = this.$('.guapante-unit-equivalence');
        var $equivalenceText = $equivalence.find('.equivalence-text');

        // Calculate and display equivalence
        if (selectedUnit === 'kg' && this.conversions.kg_to_units) {
            var equivalentUnits = (quantity * this.conversions.kg_to_units).toFixed(1);
            $equivalenceText.text('≃ ' + equivalentUnits + ' uds');
            $equivalence.fadeIn(200);
        } else if (selectedUnit === 'g' && this.conversions.g_to_units) {
            var equivalentUnits = (quantity * this.conversions.g_to_units).toFixed(1);
            $equivalenceText.text('≃ ' + equivalentUnits + ' uds');
            $equivalence.fadeIn(200);
        } else {
            $equivalence.fadeOut(200);
        }
    },

    /**
     * Update hidden field value for backend submission
     */
    _updateHiddenUnitField: function (unit) {
        var $hiddenField = this.$('input[name="product_uom"]');
        if ($hiddenField.length) {
            $hiddenField.val(unit);
        }
    },
});
