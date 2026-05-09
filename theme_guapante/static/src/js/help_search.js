/**
 * Buscador JS para el Centro de Ayuda (Frontend-only)
 */
odoo.define('theme_guapante.help_search', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    // Base de datos "mock" de artículos de ayuda. 
    // En el futuro, el usuario puede agregar más artículos aquí, o podríamos inyectarlo vía QWeb.
    const HELP_ARTICLES = [
        { title: "¿Cómo realizo un pedido B2B?", category: "Pedidos", url: "/ayuda/pedidos" },
        { title: "¿Puedo modificar un pedido después de confirmado?", category: "Pedidos", url: "/ayuda/pedidos" },
        { title: "¿Cuáles son los métodos de pago aceptados?", category: "Pago y Facturación", url: "/ayuda/pagos" },
        { title: "¿Cómo descargo mi factura electrónica DIAN?", category: "Pago y Facturación", url: "/ayuda/pagos" },
        { title: "¿Cómo aplico retenciones a mi pago?", category: "Pago y Facturación", url: "/ayuda/pagos" },
        { title: "Tiempos de entrega y ventanas horarias", category: "Envío y Entrega", url: "/ayuda/envios" },
        { title: "¿Cómo rastreo mi pedido en tiempo real?", category: "Envío y Entrega", url: "/ayuda/envios" },
        { title: "¿Qué certificaciones de calidad tienen los productos?", category: "Productos", url: "/ayuda/productos" },
        { title: "¿Cómo funciona la cadena de frío?", category: "Productos", url: "/ayuda/productos" },
        { title: "Olvidé mi contraseña, ¿cómo la recupero?", category: "Mi Cuenta", url: "/ayuda/cuenta" },
        { title: "¿Cómo agrego una nueva dirección de envío?", category: "Mi Cuenta", url: "/ayuda/cuenta" },
        { title: "Política de devoluciones por frescura", category: "Devoluciones", url: "/ayuda/devoluciones" },
        { title: "¿Cómo reportar un problema con mi entrega?", category: "Devoluciones", url: "/ayuda/devoluciones" }
    ];

    publicWidget.registry.GuapanteHelpSearch = publicWidget.Widget.extend({
        selector: '.guapante-ayuda-hero',
        events: {
            'input #ayudaSearchInput': '_onSearchInput',
            'focus #ayudaSearchInput': '_onSearchFocus',
            'blur #ayudaSearchInput': '_onSearchBlur',
        },

        start: function () {
            this.$input = this.$('#ayudaSearchInput');
            this.$dropdown = this.$('#ayudaSearchResults');
            return this._super.apply(this, arguments);
        },

        _onSearchInput: function (e) {
            const query = $(e.currentTarget).val().toLowerCase().trim();
            
            if (query.length < 2) {
                this.$dropdown.removeClass('active').empty();
                return;
            }

            // Filtrar artículos que coincidan con la búsqueda
            const results = HELP_ARTICLES.filter(article => 
                article.title.toLowerCase().includes(query) || 
                article.category.toLowerCase().includes(query)
            );

            this._renderResults(results, query);
        },

        _renderResults: function (results, query) {
            this.$dropdown.empty();

            if (results.length === 0) {
                this.$dropdown.append(`
                    <div class="search-result-item" style="cursor: default; color: #6c757d;">
                        <div class="result-title">No se encontraron resultados para "${query}"</div>
                    </div>
                `);
            } else {
                results.forEach(article => {
                    this.$dropdown.append(`
                        <a href="${article.url}" class="search-result-item">
                            <div class="result-category">${article.category}</div>
                            <div class="result-title">${article.title}</div>
                        </a>
                    `);
                });
            }

            this.$dropdown.addClass('active');
        },

        _onSearchFocus: function () {
            if (this.$input.val().trim().length >= 2) {
                this.$dropdown.addClass('active');
            }
        },

        _onSearchBlur: function () {
            // Retraso para permitir hacer clic en los enlaces antes de ocultar
            setTimeout(() => {
                this.$dropdown.removeClass('active');
            }, 200);
        }
    });
});
