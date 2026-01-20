{
    'name': 'Guapante',
    'description': 'Modern, fresh theme for Guapante based on Odoo 18 best practices.',
    'category': 'Theme/eCommerce',
    'summary': 'Fresh, Organic, Modern',
    'version': '2.0.0',
    'images': [
        'static/description/guapante_preview.png',
        'static/description/icon.png',
    ],
    'depends': ['website', 'website_sale', 'auth_signup', 'l10n_co'],
    'data': [
        'views/layout/header.xml',
        'views/layout/footer.xml',
        'views/layout/bottom_nav.xml',
        'views/pages/home.xml',
        'views/shop/categories.xml',
        'views/shop/products_item.xml',
        'views/shop/layout.xml',
        'views/auth/login.xml',
        'views/auth/signup.xml',
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
            # Main SCSS file - imports all other SCSS files
            'theme_guapante/static/src/scss/theme.scss',
            # JavaScript files
            'theme_guapante/static/src/js/auth_signup.js',
            'theme_guapante/static/src/js/shop.js',
        ],
    },
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
