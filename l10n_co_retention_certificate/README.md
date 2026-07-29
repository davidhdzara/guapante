# CO - Certificado de Retenciones

Advanced accounting report module for Odoo 18 — Colombian localization.

## Overview

This module issues the **Certificado de Retenciones** (withholding certificate)
that a company delivers to its suppliers, grouped by **tax concept**
(`account.tax`) instead of by accounting account. This makes it independent
of how each client's chart of accounts (PUC) happens to be configured.

Status: **Phase 1 only** — the retention-type classifier. The reporting
engine, wizard and PDF template are specified but not yet implemented (see
`ESPEC_certificado_retenciones.md` in the Guapante project docs for the full
roadmap).

## Phase 1 — Classifier

Adds `l10n_co_retention_type` to `account.tax` (Selection:
`retefuente` / `reteiva` / `reteica` / `parafiscal`), auto-populated on
install for every purchase tax with `amount < 0`.

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
