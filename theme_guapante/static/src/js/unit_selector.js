/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import wSaleUtils from "@website_sale/js/website_sale_utils";

publicWidget.registry.GuapanteUnitSelector = publicWidget.Widget.extend({
    selector: '.guapante-unit-selector-container',
    events: {
        'change .uom-mode-option': '_onModeChange',
        'change .packaging-option': '_onPackagingChange',
        'input .guapante-qty-input': '_onQtyInput',
        'change .guapante-qty-input': '_onQtyChange',
        'click .guapante-qty-plus': '_onQuantityPlus',
        'click .guapante-qty-minus': '_onQuantityMinus',
        'click .guapante-add-to-cart-btn': '_onAddToCart',
    },

    start: function () {
        const rawWeight = this.$el.data('is-weight-uom');
        this.isWeightUom = (rawWeight === true || rawWeight === 'true');

        const rawPkg = this.$el.data('has-packaging');
        this.hasPackaging = (rawPkg === true || rawPkg === 'true');

        this.uomName = this.$el.data('uom-name') || 'Unidades';

        this.currentMode = 'kg';
        this.currentPackaging = this._getSelectedPackaging();

        this._initializeView();
        this._hideOriginalControls();
        this._setupVariantListener();

        // Bind add-to-cart using document-level delegation.
        // product_layout_fix.js moves #product_detail in the DOM,
        // which can break publicWidget's jQuery event bindings on $el.
        // Document-level delegation survives DOM moves.
        var self = this;
        this._onAddToCartDelegate = function (ev) {
            // Only handle clicks within OUR widget instance
            if ($.contains(self.$el[0], ev.target) || self.$el[0] === ev.target) {
                self._onAddToCart(ev);
            }
        };
        $(document).on('click.guapante_cart', '.guapante-add-to-cart-btn', this._onAddToCartDelegate);

        return this._super.apply(this, arguments);
    },

    destroy: function () {
        $(document).off('click.guapante_cart');
        this._super.apply(this, arguments);
    },

    _initializeView: function () {
        const $modeSelector = this.$('.guapante-uom-mode-selector');
        const $unitOption = this.$('#mode_unit').next('label');
        const $unitInput = this.$('#mode_unit');

        if (this.isWeightUom) {
            $modeSelector.removeClass('d-none');
            if (this.hasPackaging) {
                $unitInput.removeClass('d-none').prop('disabled', false);
                $unitOption.removeClass('d-none disabled btn-outline-secondary').addClass('btn-outline-success');
                this.$('#mode_kg').next('label').removeClass('guapante-force-first');
            } else {
                $unitInput.addClass('d-none').prop('disabled', true);
                $unitOption.addClass('d-none disabled btn-outline-secondary').removeClass('btn-outline-success');
                this.$('#mode_kg').next('label').addClass('guapante-force-first');
                if (this.currentMode === 'unit') this.currentMode = 'kg';
            }
            this.$(`input[name="uom_mode"][value="${this.currentMode}"]`).prop('checked', true);
        } else {
            $modeSelector.addClass('d-none');
            this.currentMode = 'unit';
        }
        this._updateUIBasedOnMode();
    },

    _hideOriginalControls: function () {
        $('#o_wsale_cta_wrapper .css_quantity').addClass('d-none');
        $('#add_to_cart').addClass('d-none');
    },

    _onModeChange: function (ev) {
        var previousMode = this.currentMode;
        this.currentMode = $(ev.currentTarget).val();


        var $qtyInput = this.$('.guapante-qty-input');
        var currentVal = this._parseValue($qtyInput.val());

        if (previousMode === 'kg' && this.currentMode === 'g') {
            $qtyInput.val(this._formatValue(Math.round(currentVal * 1000)));
        } else if (previousMode === 'g' && this.currentMode === 'kg') {
            var kgVal = currentVal / 1000;
            $qtyInput.val(this._formatValue(Math.max(0.1, parseFloat(kgVal.toFixed(2)))));
        } else if (this.currentMode === 'unit') {
            $qtyInput.val(this._formatValue(1));
        } else if (previousMode === 'unit' && this.currentMode === 'kg') {
            $qtyInput.val(this._formatValue(1));
        } else if (previousMode === 'unit' && this.currentMode === 'g') {
            $qtyInput.val(this._formatValue(500));
        }
        this._updateUIBasedOnMode();
    },

    _updateUIBasedOnMode: function () {
        const $qtyInput = this.$('.guapante-qty-input');
        const $packagingSelector = this.$('.guapante-unit-selector');
        const $packagingInfo = this.$('.guapante-packaging-info');
        const $modeInfo = this.$('.guapante-mode-info');

        // (#16) Ensure unit label exists next to qty input
        var $unitLabel = this.$('.guapante-qty-unit-label');
        if (!$unitLabel.length) {
            $qtyInput.after('<span class="input-group-text guapante-qty-unit-label"></span>');
            $unitLabel = this.$('.guapante-qty-unit-label');
        }
        switch (this.currentMode) {
            case 'kg':
                $qtyInput.attr('step', '0.01').attr('min', '0.1');
                if (this._parseValue($qtyInput.val()) < 0.1) $qtyInput.val(this._formatValue(1.0));
                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio por Kilogramo');
                $unitLabel.text('Kg').removeClass('d-none');
                break;
            case 'g':
                $qtyInput.attr('step', '50').attr('min', '50');
                let val = this._parseValue($qtyInput.val());
                if (val < 50) $qtyInput.val(this._formatValue(500));
                else $qtyInput.val(this._formatValue(Math.round(val)));
                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio calculado por peso (aprox)');
                $unitLabel.text('g').removeClass('d-none');
                break;
            case 'unit':
                $qtyInput.attr('step', '1').attr('min', '1');
                if (this._parseValue($qtyInput.val()) < 1) $qtyInput.val(this._formatValue(1));
                // Only show packaging selector if there are 2+ options
                var pkgCount = this.$('.packaging-option').length;
                if (this.isWeightUom) {
                    if (pkgCount > 1) {
                        $packagingSelector.removeClass('d-none');
                    } else {
                        $packagingSelector.addClass('d-none');
                    }
                    $modeInfo.text('Venta por Unidad / Paquete');
                } else {
                    if (this.hasPackaging && pkgCount > 1) {
                        $packagingSelector.removeClass('d-none');
                    } else {
                        $packagingSelector.addClass('d-none');
                    }
                    $modeInfo.text('Venta por Unidad');
                }
                this._updatePackagingInfo();
                $unitLabel.addClass('d-none');
                break;
        }
    },

    _onQtyInput: function () {
        if (this.currentMode === 'unit') {
            this._updatePackagingInfo();
        }
    },

    _onQtyChange: function () {
        let val = this._parseValue(this.$('.guapante-qty-input').val());
        const min = parseFloat(this.$('.guapante-qty-input').attr('min'));

        if (isNaN(val) || val < min) {
            val = min;
        }

        if (this.currentMode === 'g' || this.currentMode === 'unit') {
            val = Math.round(val);
        } else {
            val = parseFloat(val.toFixed(2));
        }

        this.$('.guapante-qty-input').val(this._formatValue(val));

        if (this.currentMode === 'unit') {
            this._updatePackagingInfo();
        }
    },

    _onQuantityPlus: function () {
        let val = this._parseValue(this.$('.guapante-qty-input').val());
        let step = 1;
        if (this.currentMode === 'kg') step = 0.5;
        if (this.currentMode === 'g') step = 50;

        this.$('.guapante-qty-input').val(this._formatValue(val + step)).trigger('change');
    },

    _onQuantityMinus: function () {
        let val = this._parseValue(this.$('.guapante-qty-input').val());
        let step = 1;
        if (this.currentMode === 'kg') step = 0.5;
        if (this.currentMode === 'g') step = 50;

        let newVal = val - step;
        const min = parseFloat(this.$('.guapante-qty-input').attr('min'));
        if (newVal < min) newVal = min;

        this.$('.guapante-qty-input').val(this._formatValue(newVal)).trigger('change');
    },

    _onPackagingChange: function (ev) {
        this.currentPackaging = this._getSelectedPackaging();
        $('input[name="product_packaging_id"]').val(this.currentPackaging.id);
        this._updatePackagingInfo();
    },

    _getSelectedPackaging: function () {
        const $selected = this.$('.packaging-option:checked');
        if ($selected.length) {
            return {
                id: parseInt($selected.val()),
                name: $selected.data('packaging-name'),
                qty: parseFloat($selected.data('packaging-qty')) || 1
            };
        }
        return { id: 0, name: 'Unidad', qty: 1 };
    },

    _updatePackagingInfo: function () {
        if (this.currentMode !== 'unit') return;

        const qty = this._parseValue(this.$('.guapante-qty-input').val());
        const pkg = this.currentPackaging;
        const $info = this.$('.guapante-packaging-info');
        const $text = this.$('.packaging-info-text');

        if (this.isWeightUom) {
            const totalKg = (qty * pkg.qty).toFixed(2);
            // Display formatted totalKg
            const formattedTotal = totalKg.toString().replace('.', ',');
            $text.text(`Peso aproximado de ${qty} ${pkg.name} x ${pkg.qty} kg = ${formattedTotal} kg Total`);
            $info.removeClass('d-none');
        } else {
            $info.addClass('d-none');
        }
    },

    _onAddToCart: async function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const productId = $('input[name="product_id"]').val() || this.$el.data('product-id');

        let qtyInput = this._parseValue(this.$('.guapante-qty-input').val());
        let finalQty = qtyInput;
        let uomMode = this.currentMode;
        let packagingId = 0;

        if (this.currentMode === 'g') {
            finalQty = qtyInput / 1000.0;
        } else if (this.currentMode === 'unit') {
            packagingId = this.currentPackaging.id;
            finalQty = qtyInput;
        } else {
            finalQty = qtyInput;
        }

        if (finalQty <= 0 || isNaN(finalQty)) {
            $btn.addClass('disabled').html('<i class="fa fa-exclamation-triangle me-2"></i> Cantidad Inválida');
            setTimeout(() => {
                $btn.removeClass('disabled').html('<i class="fa fa-shopping-cart me-2"></i> Agregar al Pedido');
            }, 2000);
            return;
        }

        finalQty = Math.round(finalQty * 1000) / 1000;

        $btn.addClass('disabled').html('<i class="fa fa-spinner fa-spin me-2"></i> Agregando...');

        try {
            const data = await $.ajax({
                url: '/shop/cart/update_json',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        product_id: parseInt(productId),
                        add_qty: finalQty,
                        product_packaging_id: packagingId,
                        uom_mode: uomMode,
                        display: false,
                    }
                })
            });

            const result = (data && data.result) ? data.result : data;
            var itemCount = result.cart_quantity != null ? result.cart_quantity : (result.cart_lines_count || 0);
            var $badges = $('.my_cart_quantity');
            if (itemCount > 0) {
                $badges.text(itemCount).removeClass('d-none').show();
            } else {
                $badges.text('').addClass('d-none');
            }

            $btn.removeClass('disabled').addClass('btn-success').html('<i class="fa fa-check me-2"></i> Agregado');
            setTimeout(() => {
                $btn.html('<i class="fa fa-shopping-cart me-2"></i> Agregar al Pedido').removeClass('btn-success');
            }, 2000);

        } catch (error) {
            console.error("Guapante: Error adding to cart", error);
            $btn.removeClass('disabled').html('<i class="fa fa-exclamation-triangle me-2"></i> Error');
        }
    },

    _setupVariantListener: function () {
        const self = this;

        // Odoo 18's _onChangeCombination does:
        //   $parent.find('.product_id').first().val(combination.product_id).trigger('change')
        // So we listen for 'change' on '.product_id' (class, not name attribute)
        $(document).on('change', '.product_id', function () {
            var newId = $(this).val();
            console.log('Guapante: variant changed, new product_id:', newId);
            if (newId && newId !== '0') {
                self._onVariantChange();
            }
        });
    },

    _onVariantChange: async function () {
        const productId = $('.product_id').first().val();
        if (!productId) return;
        try {
            const packagings = await this._fetchPackagings(productId);
            this.hasPackaging = (packagings && packagings.length > 0);
            this._initializeView();
            this._rebuildPackagingSelector(packagings, productId);
            this.currentPackaging = this._getSelectedPackaging();
            if (this.currentMode === 'unit') {
                this._updatePackagingInfo();
            }
        } catch (error) {
            console.error('Guapante: Error updating variant', error);
        }
    },

    _fetchPackagings: async function (productId) {
        const data = await $.ajax({
            url: `/shop/product/packagings/${productId}`,
            method: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {},
            }),
        });
        const result = (data && data.result) ? data.result : data;
        return result || [];
    },

    _rebuildPackagingSelector: function (packagings, productId) {
        const $container = this.$('.guapante-packaging-options');
        $container.empty();
        if (packagings && packagings.length > 0) {
            packagings.forEach((pkg, index) => {
                const isChecked = index === 0;
                const radioHtml = `
                    <input type="radio" class="btn-check packaging-option" name="packaging_selector_${productId}"
                        id="pkg_${pkg.id}_${productId}" value="${pkg.id}" data-packaging-name="${pkg.name}"
                        data-packaging-qty="${pkg.qty}" ${isChecked ? 'checked' : ''} autocomplete="off" />
                    <label class="btn btn-outline-success" for="pkg_${pkg.id}_${productId}">${pkg.name}</label>
                `;
                $container.append(radioHtml);
            });
            $('input[name="product_packaging_id"]').val(packagings[0].id);
        } else {
            // No packaging options to show
            $('input[name="product_packaging_id"]').val(0);
        }
    },

    _formatValue: function (val) {
        if (typeof val === 'number') {
            return parseFloat(val.toFixed(3)).toString();
        }
        return val;
    },

    _parseValue: function (val) {
        if (typeof val === 'string') {
            val = val.replace(/\s/g, '').replace(',', '.');
        }
        return parseFloat(val) || 0;
    },
});
