{
    'name': 'Guapante',
    'description': 'Modern, fresh theme for Guapante based on Odoo 18 best practices.',
    'category': 'Theme/eCommerce',
    'summary': 'Fresh, Organic, Modern',
    'version': '2.1.0',
    'images': [
        'static/description/guapante_preview.png',
        'static/description/icon.png',
    ],
    'depends': ['base', 'contacts', 'website', 'website_sale', 'auth_signup', 'l10n_co', 'stock', 'stock_picking_batch', 'fleet', 'account', 'sale', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_config.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'report/sale_report_templates.xml',
        'report/purchase_report_templates.xml',
        'views/preparation_day_views.xml',
        'views/stock_picking_views.xml',
        'views/shop/order_status.xml',
        'views/product_template_view.xml',
        'views/product_packaging_views.xml',
        'views/layout/header.xml',
        'views/layout/footer.xml',
        'views/layout/bottom_nav.xml',
        'views/layout/search_modal.xml',
        'views/pages/home.xml',
        'views/shop/categories.xml',
        'views/shop/products_item.xml',
        'views/shop/product.xml',
        'views/shop/layout.xml',
        'views/shop/cart.xml',
        'views/shop/checkout.xml',
        'views/portal/portal_layout.xml', # Custom Portal Layout
        'views/portal/my_orders.xml', # Custom My Orders View
        'views/portal/my_invoices.xml', # Custom My Invoices View
        'views/portal/my_profile.xml', # Custom Mi Perfil View
        'views/portal/my_addresses.xml', # Custom Mis Direcciones View
        'views/auth/login.xml',
        'views/auth/signup.xml',
        'views/auth/reset_password.xml',
        'views/snippets/s_hero.xml',
        'views/snippets/s_features.xml',
        'views/snippets/s_categories.xml',
        'views/snippets/s_seasonal_harvest.xml',
        'views/snippets/s_b2b.xml',
        'views/snippets/s_about_hero.xml',
        'views/snippets/s_about_history.xml',
        'views/snippets/s_about_mission_vision.xml',
        'views/snippets/s_about_pillars.xml',
        'views/snippets/s_about_cta.xml',
        'views/snippets/snippets.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            'theme_guapante/static/src/scss/primary_variables.scss',
        ],
        'web.assets_frontend': [
            # Base theme styles
            'theme_guapante/static/src/scss/theme.scss',
            # Layout components
            'theme_guapante/static/src/scss/layout/_header.scss',
            'theme_guapante/static/src/scss/layout/_bottom_nav.scss',
            'theme_guapante/static/src/scss/layout/_footer.scss',
            'theme_guapante/static/src/scss/layout/_search_modal.scss',
            # Page-specific styles
            'theme_guapante/static/src/scss/pages/_auth.scss',
            'theme_guapante/static/src/scss/pages/_shop.scss',
            'theme_guapante/static/src/scss/pages/_shop_grid.scss',  # Product cards premium style
            'theme_guapante/static/src/scss/pages/_cart.scss',  # Cart page styles
            'theme_guapante/static/src/scss/pages/_checkout.scss',  # Checkout page styles
            'theme_guapante/static/src/scss/pages/_order_status.scss',  # Order status page styles
            'theme_guapante/static/src/scss/pages/_portal_orders.scss', # Portal / My Orders styles
            'theme_guapante/static/src/scss/pages/_portal_profile.scss', # Portal / Mi Perfil styles
            'theme_guapante/static/src/scss/pages/_portal_addresses.scss', # Portal / Mis Direcciones styles
            # Snippets
            'theme_guapante/static/src/scss/snippets/_s_hero.scss',
            'theme_guapante/static/src/scss/snippets/_s_features.scss',
            'theme_guapante/static/src/scss/snippets/_s_categories.scss',
            'theme_guapante/static/src/scss/snippets/_s_seasonal_harvest.scss',
            'theme_guapante/static/src/scss/snippets/_s_b2b.scss',
            'theme_guapante/static/src/scss/snippets/_s_about_hero.scss',
            'theme_guapante/static/src/scss/snippets/_s_about_history.scss',
            'theme_guapante/static/src/scss/snippets/_s_about_mission_vision.scss',
            'theme_guapante/static/src/scss/snippets/_s_about_pillars.scss',
            'theme_guapante/static/src/scss/snippets/_s_about_cta.scss',
            # JavaScript files
            'theme_guapante/static/src/js/auth_signup.js',
            'theme_guapante/static/src/js/reset_password.js',
            'theme_guapante/static/src/js/shop.js',
            'theme_guapante/static/src/js/product_layout_fix.js',  # Layout Fix JS
            'theme_guapante/static/src/js/cart_icon_replacement.js',  # Replace wishlist with cart
            'theme_guapante/static/src/js/unit_selector.js',  # Unit selector (Unidades/Kg/g)
            'theme_guapante/static/src/js/cart_quantity.js',  # Cart quantity controls
            'theme_guapante/static/src/js/address_error_fix.js',  # Fix address errors
            'theme_guapante/static/src/js/checkout.js',  # Checkout interaction
            'theme_guapante/static/src/js/seasonal_harvest.js',  # Seasonal products dynamic loader
            'theme_guapante/static/src/js/search_modal.js',  # Full-screen search overlay
        ],
        'web.assets_backend': [
            'theme_guapante/static/src/js/preparation_list.js',
        ],
    },
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
