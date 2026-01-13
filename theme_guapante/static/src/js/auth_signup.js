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

        if (type === 'company') {
            // Show Company Labels & Placeholders
            this.$('.label-name').addClass('d-none');
            this.$('.label-company').removeClass('d-none');
            this.$('#name').attr('placeholder', 'Ej: Soluciones Tecnológicas S.A.S.');
            this.$('#vat').attr('placeholder', 'Ej: 900.123.456');
        } else {
            // Show Person Labels & Placeholders
            this.$('.label-name').removeClass('d-none');
            this.$('.label-company').addClass('d-none');
            this.$('#name').attr('placeholder', 'Ej: María Rodríguez');
            this.$('#vat').attr('placeholder', 'Ej: 1020456789');
        }
    },
});
