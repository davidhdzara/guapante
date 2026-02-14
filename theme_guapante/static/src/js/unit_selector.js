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

        console.log('Guapante: Unit Selector initialized. WeightUom:', this.isWeightUom, 'HasPkg:', this.hasPackaging);
        return this._super.apply(this, arguments);
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
        console.log('Guapante: Switched from', previousMode, 'to:', this.currentMode);

        var $qtyInput = this.$('.guapante-qty-input');
        var currentVal = this._parseValue($qtyInput.val());

        if (previousMode === 'kg' && this.currentMode === 'g') {
            $qtyInput.val(Math.round(currentVal * 1000));
        } else if (previousMode === 'g' && this.currentMode === 'kg') {
            var kgVal = currentVal / 1000;
            $qtyInput.val(Math.max(0.1, parseFloat(kgVal.toFixed(2))));
        } else if (this.currentMode === 'unit') {
            $qtyInput.val(1);
        } else if (previousMode === 'unit' && this.currentMode === 'kg') {
            $qtyInput.val(1);
        } else if (previousMode === 'unit' && this.currentMode === 'g') {
            $qtyInput.val(500);
        }
        this._updateUIBasedOnMode();
    },

    _updateUIBasedOnMode: function () {
        const $qtyInput = this.$('.guapante-qty-input');
        const $packagingSelector = this.$('.guapante-unit-selector');
        const $packagingInfo = this.$('.guapante-packaging-info');
        const $modeInfo = this.$('.guapante-mode-info');

        switch (this.currentMode) {
            case 'kg':
                $qtyInput.attr('step', '0.01').attr('min', '0.1');
                if (this._parseValue($qtyInput.val()) < 0.1) $qtyInput.val(1.0);
                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio por Kilogramo');
                break;
            case 'g':
                $qtyInput.attr('step', '50').attr('min', '50');
                let val = this._parseValue($qtyInput.val());
                if (val < 50) $qtyInput.val(500);
                else $qtyInput.val(Math.round(val));
                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio calculado por peso (aprox)');
                break;
            case 'unit':
                $qtyInput.attr('step', '1').attr('min', '1');
                if (this._parseValue($qtyInput.val()) < 1) $qtyInput.val(1);
                if (this.isWeightUom) {
                    $packagingSelector.removeClass('d-none');
                    $modeInfo.text('Venta por Unidad / Paquete');
                } else {
                    if (this.hasPackaging) {
                        $packagingSelector.removeClass('d-none');
                    } else {
                        $packagingSelector.addClass('d-none');
                    }
                    $modeInfo.text('Venta por Unidad');
                }
                this._updatePackagingInfo();
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

        this.$('.guapante-qty-input').val(val);

        if (this.currentMode === 'unit') {
            this._updatePackagingInfo();
        }
    },

    _onQuantityPlus: function () {
        let val = this._parseValue(this.$('.guapante-qty-input').val());
        let step = 1;
        if (this.currentMode === 'kg') step = 0.5;
        if (this.currentMode === 'g') step = 50;

        this.$('.guapante-qty-input').val(val + step).trigger('change');
    },

    _onQuantityMinus: function () {
        let val = this._parseValue(this.$('.guapante-qty-input').val());
        let step = 1;
        if (this.currentMode === 'kg') step = 0.5;
        if (this.currentMode === 'g') step = 50;

        let newVal = val - step;
        const min = parseFloat(this.$('.guapante-qty-input').attr('min'));
        if (newVal < min) newVal = min;

        this.$('.guapante-qty-input').val(newVal).trigger('change');
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
            $text.text(`${qty} ${pkg.name} x ${pkg.qty} kg = ${totalKg} kg Total`);
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
            if (this.isWeightUom) {
                finalQty = qtyInput * this.currentPackaging.qty;
            } else {
                finalQty = qtyInput;
            }
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

            var itemCount = data.cart_lines_count || data.cart_quantity || 0;
            var $badges = $('.my_cart_quantity, .o_wsale_my_cart .badge, .btn-cart-guapante .badge');
            $badges.text(itemCount).removeClass('d-none');
            if (itemCount > 0) {
                $badges.show(); $badges.parent().removeClass('d-none');
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
        $(document).on('change', 'input[name="product_id"]', function () {
            self._onVariantChange();
        });
    },

    _onVariantChange: async function () {
        const productId = $('input[name="product_id"]').val();
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
        const response = await fetch(`/shop/product/packagings/${productId}`);
        if (!response.ok) throw new Error('Failed to fetch packagings');
        return await response.json();
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
            const radioHtml = `
                    <input type="radio" class="btn-check packaging-option" name="packaging_selector_${productId}"
                        id="pkg_default_${productId}" value="0" data-packaging-name="Unidad" data-packaging-qty="1" checked
                        autocomplete="off" />
                    <label class="btn btn-outline-success" for="pkg_default_${productId}">Unidad</label>
                `;
            $container.append(radioHtml);
            $('input[name="product_packaging_id"]').val(0);
        }
    },

    _parseValue: function (val) {
        if (typeof val === 'string') {
            val = val.replace(',', '.');
        }
        return parseFloat(val) || 0;
    },
});
