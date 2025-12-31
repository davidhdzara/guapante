{
    'name': 'Theme Guapante',
    'description': 'Tema personalizado para Comercializadora Guapante basado en Mockup React.',
    'category': 'Theme/eCommerce',
    'summary': 'eCommerce, Organic, Fresh',
    'version': '1.0.0',
    'depends': ['website', 'website_sale'],
    'data': [
        'views/layout/header.xml',
        'views/layout/footer.xml',
        'views/snippets/s_hero.xml',
        'views/snippets/s_features.xml',
        'views/snippets/s_categories.xml',
        'views/snippets/s_b2b.xml',
        'views/snippets/s_b2b.xml',
        'views/snippets/snippets.xml',
        'views/pages/home.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'theme_guapante/static/src/scss/primary_variables.scss',
            'theme_guapante/static/src/scss/theme.scss',
            'theme_guapante/static/src/scss/snippets/s_hero.scss',
            'theme_guapante/static/src/scss/snippets/s_features.scss',
            'theme_guapante/static/src/scss/snippets/s_categories.scss',
            'theme_guapante/static/src/scss/snippets/s_b2b.scss',
        ],
         'web._assets_primary_variables': [
            'theme_guapante/static/src/scss/primary_variables.scss',
        ],
    },
    'license': 'LGPL-3',
}