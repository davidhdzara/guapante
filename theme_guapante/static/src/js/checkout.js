/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuapanteCheckout = publicWidget.Widget.extend({
    selector: '.guapante-checkout-wrapper',
    events: {
        'change #guapante_shipping_select': '_onShippingChange',
        'change #whatsappCheck': '_onWhatsappCheckChange',
        'click #guapante_confirm_btn': '_onConfirmOrder',
        'submit #appendOrderModal form': '_onConfirmFusion',
    },

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);

        // Si el checkbox ya está marcado al cargar (por caché o refresco)
        if ($('#whatsappCheck').is(':checked')) {
            $('#whatsappInputContainer').removeClass('d-none');
        }

        return Promise.resolve();
    },

    _onWhatsappCheckChange: function (ev) {
        var $container = $('#whatsappInputContainer');
        if ($(ev.currentTarget).is(':checked')) {
            $container.removeClass('d-none').hide().fadeIn(300);
        } else {
            $container.fadeOut(300, function() {
                $(this).addClass('d-none');
            });
        }
    },

    _onConfirmOrder: function (ev) {
        var isChecked = $('#whatsappCheck').is(':checked');
        var numberInput = $('#whatsappNumber').val() || '';
        var number = numberInput.trim();
        var $btn = $(ev.currentTarget);
        
        if (isChecked) {
            // Validacion: al menos 7 digitos
            var cleanNumber = number.replace(/\D/g, '');
            if (cleanNumber.length < 7) {
                $('#whatsappNumber').addClass('border-danger');
                $('#whatsapp_error').removeClass('d-none');
                return;
            }
            $('#whatsappNumber').removeClass('border-danger');
            $('#whatsapp_error').addClass('d-none');

            ev.preventDefault();
            $btn.html('<i class="fa fa-spinner fa-spin me-2"></i> Guardando...').addClass('disabled');
            
            $.ajax({
                url: '/shop/update_whatsapp',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        whatsapp_number: number,
                    },
                }),
            }).then(function () {
                window.location.href = $btn.attr('href') || '/shop/checkout/confirm';
            }).catch(function (err) {
                console.error("[GuapanteCheckout] Error al guardar número WhatsApp:", err);
                $btn.removeClass('disabled').html('<i class="fa fa-paper-plane me-2"></i> Confirmar Pedido');
                alert('Error al guardar el número de WhatsApp. Por favor intenta de nuevo.');
            });
        }
        // Si no está chequeado, el enlace <a> funciona normalmente (va a /shop/checkout/confirm)
    },

    _onConfirmFusion: function (ev) {
        var isChecked = $('#whatsappCheck').is(':checked');
        var number = ($('#whatsappNumber').val() || '').trim();
        var $form = $(ev.currentTarget);
        var $btn = $form.find('button[type="submit"]');

        if (isChecked && number) {
            ev.preventDefault();
            
            // Validacion rapida
            var cleanNumber = number.replace(/\D/g, '');
            if (cleanNumber.length < 7) {
                $('#whatsappNumber').addClass('border-danger');
                $('#whatsapp_error').removeClass('d-none');
                return;
            }

            $btn.html('<i class="fa fa-spinner fa-spin me-2"></i> Procesando...').addClass('disabled');

            $.ajax({
                url: '/shop/update_whatsapp',
                method: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        whatsapp_number: number,
                    },
                }),
            }).then(function () {
                $form.off('submit').submit();
            }).catch(function () {
                // Si falla el guardado, igual procedemos con la fusion
                $form.off('submit').submit();
            });
        }
    },

    /**
     * Handle shipping address dropdown changes.
     * Uses Odoo's native /shop/update_address JSON API to update
     * the order's partner_shipping_id, then reloads to show the
     * updated address details.
     */
    _onShippingChange: function (ev) {
        var partnerId = parseInt($(ev.currentTarget).val(), 10);
        if (!partnerId || partnerId <= 0) return;

        // Use $.ajax (frontend-compatible) instead of jsonrpc (backend-only)
        $.ajax({
            url: '/shop/update_address',
            method: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    partner_id: partnerId,
                    address_type: 'delivery',
                },
            }),
        }).then(function () {
            window.location.reload();
        }).catch(function (err) {
            console.error("[GuapanteCheckout] Error updating address:", err);
            var $wrapper = $('.guapante-checkout-wrapper');
            var $alert = $('<div class="alert alert-danger mt-2" role="alert">Error al actualizar la dirección. Por favor intente de nuevo.</div>');
            $wrapper.prepend($alert);
            setTimeout(function () { $alert.fadeOut(); }, 5000);
        });
    },
});
