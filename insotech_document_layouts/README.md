# InSoTech Premium Document Layouts

**Professional PDF report layouts for Odoo V19**

Transform your quotations, invoices, and reports into premium B2B documents with modern typography, brand-aligned colors, and a clean visual hierarchy.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Modern Typography** | Montserrat (headings), Open Sans (body), JetBrains Mono (financial data) — bundled locally |
| **Brand Color Integration** | Automatically inherits your company's primary & secondary colors |
| **Premium Tables** | Zebra-striped rows, section accent bars, uppercase column headers |
| **wkhtmltopdf-Safe** | Zero flexbox, zero CSS3 gradients — guaranteed PDF rendering |
| **Compact Header** | Logo + company details with accent separator |
| **Financial Typography** | JetBrains Mono for prices, totals, and tax IDs |
| **Universal Compatibility** | Works with quotations, invoices, purchase orders, and all standard reports |

## 📦 Installation

### As a Git Submodule (recommended)

```bash
# Add the repository as a submodule
git submodule add git@github.com:davidhdzara/insotech.git addons/insotech

# Or clone directly
git clone git@github.com:davidhdzara/insotech.git addons/insotech
```

Add the path to your Odoo addons and update:

```bash
odoo-bin -u insotech_document_layouts -d your_database
```

### Manual Installation

1. Download or clone this module into your Odoo addons directory
2. Restart Odoo
3. Go to **Apps** → Search for "InSoTech Premium Document Layouts"
4. Click **Install**

## 🚀 How to Activate

1. Go to **Settings → Configure Document Layout**
2. Select **"InSoTech"** from the layout selector
3. Choose your company **primary** and **secondary** colors
4. Done — all reports will use the new premium layout

## 🎨 Typography System

| Role | Font | Weights | Usage |
|------|------|---------|-------|
| Display / Headings | Montserrat | 600, 700, 800 | Document titles, section labels |
| Body Text | Open Sans | 400, 600, 700 | Descriptions, addresses, notes |
| Financial Data | JetBrains Mono | 400, 500 | Prices, totals, tax IDs, quantities |

All fonts are **bundled locally** — no external CDN dependencies.

## 🔧 Compatibility

- **Odoo Version:** 19.0 (Community & Enterprise)
- **PDF Engine:** wkhtmltopdf (all versions)
- **Compatible Modules:** `sale`, `sale_management`, `sale_subscription`, `account`, `purchase`, `stock`
- **Languages:** All (layout is language-independent)

## 📄 License

This module is licensed under the [LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html).

## 🏢 About InSoTech

**Infinity Solutions Technology S.A.S** — Reinventa · Automatiza · Evoluciona

- 🌐 [insotech.it](https://www.insotech.it)
- 📧 proyectos@insotech.it
- 📱 +57 302 852 2449
