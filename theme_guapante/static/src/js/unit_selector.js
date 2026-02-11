/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import wSaleUtils from "@website_sale/js/website_sale_utils";

/**
 * Guapante Unit Selector Widget
 * Handles UoM selection (Kg, Grams, Units) and Packagings
 */
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
        // 1. Read Configuration from DOM
        this.isWeightUom = this.$el.data('is-weight-uom'); // Boolean
        this.hasPackaging = this.$el.data('has-packaging'); // Boolean
        this.uomName = this.$el.data('uom-name') || 'Unidades';

        // 2. Initialize State
        this.currentMode = 'kg'; // Default
        this.currentPackaging = this._getSelectedPackaging();

        // 3. Setup Initial View
        this._initializeView();

        // 4. Hide original controls
        this._hideOriginalControls();

        // 5. Setup Listeners
        this._setupVariantListener();

        console.log('Guapante: Unit Selector initialized. WeightUom:', this.isWeightUom, 'HasPkg:', this.hasPackaging);

        return this._super.apply(this, arguments);
    },

    // --------------------------------------------------------------------------
    // Initialization & View Setup
    // --------------------------------------------------------------------------

    _initializeView: function () {
        const $modeSelector = this.$('.guapante-uom-mode-selector');
        const $unitOption = this.$('#mode_unit').next('label');
        const $unitInput = this.$('#mode_unit');

        if (this.isWeightUom) {
            // SHOW Mode Selector
            $modeSelector.removeClass('d-none');

            // Check if Unit mode should be enabled
            if (this.hasPackaging) {
                $unitInput.prop('disabled', false);
                $unitOption.removeClass('disabled btn-outline-secondary').addClass('btn-outline-success');
            } else {
                $unitInput.prop('disabled', true);
                $unitOption.addClass('disabled btn-outline-secondary').removeClass('btn-outline-success');
                // Ensure we are not in unit mode
                if (this.currentMode === 'unit') this.currentMode = 'kg';
            }

            // Set initial mode
            this.$(`input[name="uom_mode"][value="${this.currentMode}"]`).prop('checked', true);

        } else {
            // HIDE Mode Selector -> Force Unit Mode
            $modeSelector.addClass('d-none');
            this.currentMode = 'unit';
        }

        this._updateUIBasedOnMode();
    },

    _hideOriginalControls: function () {
        $('#o_wsale_cta_wrapper .css_quantity').addClass('d-none');
        $('#add_to_cart').addClass('d-none');
    },

    // --------------------------------------------------------------------------
    // Logic: Mode Switching
    // --------------------------------------------------------------------------

    _onModeChange: function (ev) {
        var previousMode = this.currentMode;
        this.currentMode = $(ev.currentTarget).val();
        console.log('Guapante: Switched from', previousMode, 'to:', this.currentMode);

        // Smart conversion of quantity between modes
        var $qtyInput = this.$('.guapante-qty-input');
        var currentVal = parseFloat($qtyInput.val()) || 1;

        if (previousMode === 'kg' && this.currentMode === 'g') {
            // Kg → g: multiply by 1000
            $qtyInput.val(Math.round(currentVal * 1000));
        } else if (previousMode === 'g' && this.currentMode === 'kg') {
            // g → Kg: divide by 1000
            var kgVal = currentVal / 1000;
            $qtyInput.val(Math.max(0.1, parseFloat(kgVal.toFixed(2))));
        } else if (this.currentMode === 'unit') {
            // Anything → Unidades: reset to 1 (avoid 500 units)
            $qtyInput.val(1);
        } else if (previousMode === 'unit' && this.currentMode === 'kg') {
            // Unidades → Kg: reset to 1
            $qtyInput.val(1);
        } else if (previousMode === 'unit' && this.currentMode === 'g') {
            // Unidades → g: reset to 500
            $qtyInput.val(500);
        }

        this._updateUIBasedOnMode();
    },

    _updateUIBasedOnMode: function () {
        const $qtyInput = this.$('.guapante-qty-input');
        const $packagingSelector = this.$('.guapante-unit-selector');
        const $packagingInfo = this.$('.guapante-packaging-info');
        const $modeInfo = this.$('.guapante-mode-info');

        // Reset Input constraints based on mode
        switch (this.currentMode) {
            case 'kg': // Kg
                $qtyInput.attr('step', '0.01').attr('min', '0.1');
                if ($qtyInput.val() < 0.1) $qtyInput.val(1.0);

                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio por Kilogramo');
                break;

            case 'g': // Gramos
                $qtyInput.attr('step', '50').attr('min', '50');
                // Convert current value if switching? For now just ensure integer > 50
                let val = parseInt($qtyInput.val());
                if (val < 50) $qtyInput.val(500);
                else $qtyInput.val(Math.round(val));

                $packagingSelector.addClass('d-none');
                $packagingInfo.addClass('d-none');
                $modeInfo.text('Precio calculado por peso (aprox)');
                break;

            case 'unit': // Unidad
                $qtyInput.attr('step', '1').attr('min', '1');
                if ($qtyInput.val() < 1) $qtyInput.val(1);

                // Show Packaging Selector ONLY if we have options, 
                // but actually if we are in unit mode implies we have packaging or it's a unit product
                if (this.isWeightUom) {
                    $packagingSelector.removeClass('d-none');
                    // If weight uom, unit mode means "Buying by piece/packaging"
                    $modeInfo.text('Venta por Unidad / Paquete');
                } else {
                    // Unit product - hide packaging selector unless strict requirement? 
                    // Existing logic showed it if packaging exists.
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

    // --------------------------------------------------------------------------
    // Logic: Quantity & Packaging
    // --------------------------------------------------------------------------

    _onQtyInput: function () {
        // Real-time validation could go here
        if (this.currentMode === 'unit') {
            this._updatePackagingInfo();
        }
    },

    _onQtyChange: function () {
        // Enforce min/step on blur/enter
        let val = parseFloat(this.$('.guapante-qty-input').val());
        const min = parseFloat(this.$('.guapante-qty-input').attr('min'));

        if (isNaN(val) || val < min) {
            val = min;
        }

        // Rounding
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
        let val = parseFloat(this.$('.guapante-qty-input').val()) || 0;
        let step = 1;

        if (this.currentMode === 'kg') step = 0.5; // UX: jumps of 0.5kg
        if (this.currentMode === 'g') step = 50;

        this.$('.guapante-qty-input').val(val + step).trigger('change');
    },

    _onQuantityMinus: function () {
        let val = parseFloat(this.$('.guapante-qty-input').val()) || 0;
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
        // Update hidden input
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

        const qty = parseFloat(this.$('.guapante-qty-input').val()) || 1;
        const pkg = this.currentPackaging;
        const $info = this.$('.guapante-packaging-info');
        const $text = this.$('.packaging-info-text');

        if (this.isWeightUom) {
            // Example: 3 Unidades (x 0.5kg) = 1.5 kg
            const totalKg = (qty * pkg.qty).toFixed(2);
            $text.text(`${qty} ${pkg.name} x ${pkg.qty} kg = ${totalKg} kg Total`);
            $info.removeClass('d-none');
        } else {
            // Unit product
            $info.addClass('d-none');
        }
    },

    // --------------------------------------------------------------------------
    // Backend Interaction: Add to Cart
    // --------------------------------------------------------------------------

    _onAddToCart: async function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);

        // 1. Prepare Data
        const $productInput = $('input[name="product_id"]');
        const productId = $productInput.val() || this.$el.data('product-id');
        let qtyInput = parseFloat(this.$('.guapante-qty-input').val());
        let finalQty = qtyInput;
        let uomMode = this.currentMode;
        let packagingId = 0;

        // 2. Transformations based on Mode
        if (this.currentMode === 'g') {
            // Grams to Kg
            finalQty = qtyInput / 1000.0;
        } else if (this.currentMode === 'unit') {
            packagingId = this.currentPackaging.id;
            // Native Odoo logic: if packaging is selected, it multiplies qty by packaging_qty?
            // Actually Odoo website_sale usually sends the packaging_id and the QTY OF PACKAGES.
            // But if we want to store KG in the line (standard behavior for weight products),
            // we should probably send the calculated quantity if we are bypassing standard logic.
            // HOWEVER, Odoo's cart_update_json handles line creation.

            // Standard Odoo behavior with packaging:
            // If packaging_id is set, the Qty passed is usually expected to be "Number of Packs" OR "Total UoM Qty" depending on implementation.
            // But Odoo 16/17+ standard flow: Input is usually UoM Qty.

            // DECISION: We will send the CALCULATED Total Kg for weight products to be safe and explicit.
            if (this.isWeightUom) {
                finalQty = qtyInput * this.currentPackaging.qty;
            } else {
                finalQty = qtyInput;
            }
        } else {
            // Kg Mode
            finalQty = qtyInput;
        }

        // Rounding to 3 decimals to avoid float issues
        finalQty = Math.round(finalQty * 1000) / 1000;

        // Visual Feedback
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
                        uom_mode: uomMode, // Custom field
                        display: false,
                    }
                })
            });

            // Update Badge
            var itemCount = data.cart_lines_count || data.cart_quantity || 0;
            var $badges = $('.my_cart_quantity, .o_wsale_my_cart .badge, .btn-cart-guapante .badge');
            $badges.text(itemCount).removeClass('d-none');
            if (itemCount > 0) {
                $badges.show(); $badges.parent().removeClass('d-none');
            }

            // Success Animation
            $btn.removeClass('disabled').addClass('btn-success').html('<i class="fa fa-check me-2"></i> Agregado');
            setTimeout(() => {
                $btn.html('<i class="fa fa-shopping-cart me-2"></i> Agregar al Pedido').removeClass('btn-success');
            }, 2000);

        } catch (error) {
            console.error("Guapante: Error adding to cart", error);
            $btn.removeClass('disabled').html('<i class="fa fa-exclamation-triangle me-2"></i> Error');
        }
    },

    // --------------------------------------------------------------------------
    // Variant Handling
    // --------------------------------------------------------------------------

    _setupVariantListener: function () {
        const self = this;
        $(document).on('change', 'input[name="product_id"]', function () {
            self._onVariantChange();
        });
    },

    _onVariantChange: async function () {
        const productId = $('input[name="product_id"]').val();
        if (!productId) return;

        console.log('Guapante: Variant changed to', productId);

        try {
            // Fetch Packagings
            const packagings = await this._fetchPackagings(productId);

            // Update hasPackaging State
            this.hasPackaging = (packagings && packagings.length > 0);

            // Re-Initialize View (updates "Unidad" button enable/disable)
            this._initializeView();

            // Rebuild Packaging Radio Buttons
            this._rebuildPackagingSelector(packagings, productId);

            // Update current selection
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
                    <input 
                        type="radio" 
                        class="btn-check packaging-option" 
                        name="packaging_selector_${productId}"
                        id="pkg_${pkg.id}_${productId}"
                        value="${pkg.id}"
                        data-packaging-name="${pkg.name}"
                        data-packaging-qty="${pkg.qty}"
                        ${isChecked ? 'checked' : ''}
                        autocomplete="off"
                    />
                    <label 
                        class="btn btn-outline-success" 
                        for="pkg_${pkg.id}_${productId}">
                        ${pkg.name}
                    </label>
                `;
                $container.append(radioHtml);
            });
            // Auto Select first
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
});
