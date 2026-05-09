/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Buscador JS para el Centro de Ayuda (Frontend-only)
 */
const HELP_ARTICLES = [
    { title: "¿Cómo realizar un pedido?", category: "Pedidos", url: "/ayuda/pedidos" },
    { title: "¿Puedo modificar un pedido después de confirmado?", category: "Pedidos", url: "/ayuda/pedidos" },
    { title: "Métodos de pago aceptados y Facturación DIAN", category: "Pago y Facturación", url: "/ayuda/pagos" },
    { title: "¿Cómo aplico retenciones a mi pago?", category: "Pago y Facturación", url: "/ayuda/pagos" },
    { title: "Tiempos de entrega y Zonas de Cobertura", category: "Envío y Entrega", url: "/ayuda/envios" },
    { title: "¿Cómo rastreo mi pedido en tiempo real?", category: "Envío y Entrega", url: "/ayuda/envios" },
    { title: "Garantía de Frescura e Inocuidad", category: "Productos", url: "/ayuda/productos" },
    { title: "¿Qué certificaciones de calidad tienen los productos?", category: "Productos", url: "/ayuda/productos" },
    { title: "Gestión de Cuenta Corporativa", category: "Mi Cuenta", url: "/ayuda/cuenta" },
    { title: "¿Cómo recuperar mi contraseña?", category: "Mi Cuenta", url: "/ayuda/cuenta" },
    { title: "¿Cómo agrego una nueva dirección de envío?", category: "Mi Cuenta", url: "/ayuda/cuenta" },
    { title: "Política de Reclamos y Garantía", category: "Devoluciones", url: "/ayuda/devoluciones" },
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
