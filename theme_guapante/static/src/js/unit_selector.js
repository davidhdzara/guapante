/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Guapante Unit Selector Widget
 * Handles unit of measure selection (Unidades/Kg/g) on product page
 * - Updates equivalence display when unit or quantity changes
 * - Syncs hidden field for backend submission
 */
publicWidget.registry.GuapanteUnitSelector = publicWidget.Widget.extend({
    selector: '#product_details',
    events: {
        'change .guapante-unit-selector input[type="radio"]': '_onUnitChange',
        'input input[name="add_qty"]': '_updateEquivalence',
        'change input[name="add_qty"]': '_updateEquivalence',
    },

    start: function () {
        this.$unitSelector = this.$('.guapante-unit-selector');

        if (this.$unitSelector.length) {
            this.conversions = this._getConversions();
            this._updateEquivalence();
            console.log('Guapante: Unit selector initialized', this.conversions);
        }

        return this._super.apply(this, arguments);
    },

    /**
     * Get conversion factors from data attributes
     */
    _getConversions: function () {
        return {
            kg_to_units: parseFloat(this.$unitSelector.data('kg-to-units')) || null,
            g_to_units: parseFloat(this.$unitSelector.data('g-to-units')) || null,
        };
    },

    /**
     * Get currently selected unit
     */
    _getSelectedUnit: function () {
        return this.$unitSelector.find('input[type="radio"]:checked').val() || 'unidades';
    },

    /**
     * Get current quantity value
     */
    _getQuantity: function () {
        var qty = parseFloat(this.$('input[name="add_qty"]').val()) || 1;
        return Math.max(qty, 0.01); // Minimum 0.01
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
        var $equivalence = this.$unitSelector.find('.guapante-unit-equivalence');
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
        var $hiddenField = this.$unitSelector.find('input[name="product_uom"]');
        if ($hiddenField.length) {
            $hiddenField.val(unit);
        }
    },
});
