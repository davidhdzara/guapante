# -*- coding: utf-8 -*-
# Copyright 2024-2026 InSoTech (https://www.insotech.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    'name': 'Guapante Document Layouts',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Premium professional PDF report layouts with modern B2B typography, '
               'brand-aligned colors, and wkhtmltopdf-safe design.',
    'description': """
Guapante Document Layouts
===================================

A premium document layout for Odoo V18 that transforms your quotations,
invoices, and reports into professional B2B documents.

**Key Features:**

* 🎨 Modern typography: Montserrat (headings), Open Sans (body), JetBrains Mono (financial data)
* 📊 Premium zebra-striped tables with clear visual hierarchy
* 🎯 Section accent bars with brand-color integration
* 🔵 Automatically inherits your company colors (primary & secondary)
* 📄 wkhtmltopdf-safe (no flexbox, no CSS3 gradients — guaranteed PDF rendering)
* 📱 Clean, compact header with logo + company details
* 📋 LABEL/EYEBROW typography for metadata (dates, salesperson)
* 💰 JetBrains Mono for financial numbers (prices, totals, tax IDs)
* 🏢 Works with ANY Odoo company — not hardcoded to any brand

**How to activate:**

1. Install the module
2. Go to Settings → Configure Document Layout
3. Select "InSoTech" from the layout selector
4. Your company colors are applied automatically

**Compatibility:**

* Odoo V19 Community & Enterprise
* All standard reports (quotations, invoices, purchase orders, etc.)
* Compatible with sale_subscription, sale_management, account modules
    """,
    'author': 'InSoTech',
    'website': 'https://www.insotech.it',
    'support': 'proyectos@insotech.it',
    'depends': ['web', 'account'],
    'data': [
        'views/report_templates.xml',
        'views/report_invoice_inherit.xml',
        'data/report_layout.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'insotech_document_layouts/static/src/scss/layout_insotech.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
