/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteSignup = publicWidget.Widget.extend({
    selector: '.OE_SIGNUP_FORM',
    events: {
        'change input[name="company_type"]': '_onCompanyTypeChange',
    },

    start: function () {
        this._onCompanyTypeChange();
        return this._super.apply(this, arguments);
    },

    _onCompanyTypeChange: function () {
        const type = this.$('input[name="company_type"]:checked').val();
        const $select = this.$('#l10n_latam_identification_type_id');
        const $options = $select.find('option');

        if (type === 'company') {
            // Show Company Labels & Placeholders
            this.$('.label-name').addClass('d-none');
            this.$('.label-company').removeClass('d-none');
            this.$('#name').attr('placeholder', 'Ej: Soluciones Tecnológicas S.A.S.');
            this.$('#vat').attr('placeholder', 'Ej: 900.123.456');

            // Filter Identification Types: Show ONLY NIT
            $options.each(function () {
                const name = $(this).data('name') || '';
                // Standard name for NIT in Colombia is "NIT"
                if (name.toUpperCase().includes('NIT')) {
                    $(this).removeClass('d-none');
                } else if ($(this).val()) { // Hide others, keep empty placeholder if needed or hide it
                    $(this).addClass('d-none');
                }
            });
            // Auto-select NIT if visible, or reset
            $select.val($select.find('option:not(.d-none):eq(1)').val());

        } else {
            // Show Person Labels & Placeholders
            this.$('.label-name').removeClass('d-none');
            this.$('.label-company').addClass('d-none');
            this.$('#name').attr('placeholder', 'Ej: María Rodríguez');
            this.$('#vat').attr('placeholder', 'Ej: 1020456789');

            // Filter Identification Types: Hide NIT, show others
            $options.each(function () {
                const name = $(this).data('name') || '';
                if (name.toUpperCase().includes('NIT')) {
                    $(this).addClass('d-none');
                } else {
                    $(this).removeClass('d-none');
                }
            });
            // Reset selection if hidden
            if ($select.find('option:selected').hasClass('d-none')) {
                $select.val('');
            }
        }
    },
});
