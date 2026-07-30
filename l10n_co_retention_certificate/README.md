# CO - Certificado de Retenciones

Advanced accounting report module for Odoo 18 — Colombian localization.

## Overview

This module issues the **Certificado de Retenciones** (withholding certificate)
that a company delivers to its suppliers, grouped by **tax concept**
(`account.tax`) instead of by accounting account. This makes it independent
of how each client's chart of accounts (PUC) happens to be configured.

Covers all four Colombian withholding types in one certificate, each in its
own section with its corresponding legal note:
**Retención en la Fuente** (Art. 381 ET), **ReteIVA** (Art. 437-1/437-2 and
615 par. 2 ET), **ReteICA** (municipal statutes) and **contribuciones
parafiscales agropecuarias** (Ley 101 de 1993).

## Architecture

1. **Classifier** — `l10n_co_retention_type` on `account.tax`
   (retefuente/reteiva/reteica/parafiscal), auto-populated on install.
2. **Reporting engine** — an `account.report` with a custom handler,
   hierarchy Tercero → Tipo → Concepto, grouped by `tax_line_id` rather than
   by accounting account.
3. **Emission** — reuses the native `l10n_co_reports.retention_report.wizard`
   (expedition/declaration dates + article) unmodified; provider selection
   and which retentions to include are resolved by the report's own partner
   filter and unfold state, not by a dedicated wizard.
4. **PDF** — its own QWeb template on plain `web.external_layout`, so it
   respects each company's own Document Layout and logo. No branding is
   hardcoded — see "Client-specific branding" below.

### Classification rules (in this exact order)

1. **InSoTech concept** — if `insotech_account_colombia` is installed and an
   `insotech.retention.concept` links to the tax, use its `type`. Optional
   dependency: this module works standalone without that engine.
2. **Repartition account prefix** — `2367→reteiva`, `2368→reteica`,
   `2460→parafiscal`, `2365→retefuente`.
3. **Name pattern** — keyword match on the tax name, last resort.
4. **Unclassified** — left blank, logged as a warning for manual review.

Rule 1 must run before Rule 2 because some real-world tax configurations
route a given retention type through an accounting account that "belongs" to
a different range (e.g. ReteICA taxes posted to a 2365xx account instead of
2368xx). See `_l10n_co_compute_retention_type` in `models/account_tax.py`
for the full rationale.

## Dependencies

| Module | Source |
|--------|--------|
| `account_reports` | Odoo Enterprise |
| `l10n_co` | Odoo Community / Enterprise |
| `l10n_co_reports` | Odoo Enterprise |

`insotech_account_colombia` is an **optional runtime** dependency, not a
manifest dependency.

## Installation

1. Place this module in your Odoo addons path
2. Update the module list: `Settings → Technical → Update Apps List`
3. Search for **"Colombia - Certificado de Retenciones"** and install

## Usage

**Accounting → Reports → Colombian Statements → Certificado de Retenciones.**
Filter by partner and/or date range, unfold what you want included (folded
lines are excluded — everything is unfolded by default), then click **PDF**.

## Client-specific branding

This module deliberately ships with **no branding**: it uses
`web.external_layout` so the PDF automatically respects whatever Document
Layout and logo each installing company has configured. Do not hardcode a
specific client's colors, logo path, or custom header/footer into this
module — it is meant to be reused across clients as-is.

If a client needs a fully custom look (own color palette, hardcoded logo
asset, custom header/footer bypassing the standard layout), build a small
**separate extension module** that:
- `depends` on this module,
- inherits the `l10n_co_retention_certificate.document` template via two
  `xpath`s: one to swap the `t-call="web.external_layout"` target to the
  client's own layout template, one to `position="replace"` the `<style>`
  block with the client's palette (same `.rc-*` selectors, different
  values).

That extension module belongs in the **client's own deployment repository**,
never in this one.

## Reviewing the classification

**Accounting → Configuration → Taxes** — the new field is visible in the
list/form views, with a filter for "Retención sin clasificar (CO)" and a
"Tipo de Retención (CO)" group-by, so the accountant can audit and correct
the automatic classification.

## Testing

```bash
odoo-bin -d <database> -i l10n_co_retention_certificate --test-enable --stop-after-init
```

## License

LGPL-3.0 — See [LICENSE](https://www.gnu.org/licenses/lgpl-3.0.html)

## Author

**InSoTech** — Medellín, Colombia
