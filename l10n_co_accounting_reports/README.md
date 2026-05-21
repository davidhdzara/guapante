# CO - Balance por Terceros (Trial Balance by Partner)

Advanced accounting report module for Odoo 18 — Colombian localization.

## Overview

This module adds a **Trial Balance by Partner** report to the Odoo accounting
reports framework. It groups account balances by partner (third party) and
displays Colombian-specific information such as NIT (formatted with
verification digit), document type, and business name.

## Features

- **Hierarchical structure**: Account → Partner breakdown
- **7 columns**: Tipo Doc., NIT, Razón Social, Saldo Anterior, Débito, Crédito, Saldo Final
- **NIT formatting**: Automatic formatting with verification digit (900.123.456-7)
- **Fiscal year-aware**: Initial balances respect BS vs. P&L account rules
- **Lazy loading**: Partner data loaded on-demand for optimal performance
- **Standard filters**: Date range, journals, partners, analytic accounts
- **Export**: Excel (XLSX) and PDF via native framework
- **Multi-company & multi-currency**: Full support

## Dependencies

| Module | Source |
|--------|--------|
| `account_reports` | Odoo Enterprise |
| `l10n_co` | Odoo Community / Enterprise |

## Installation

1. Place this module in your Odoo addons path
2. Update the module list: `Settings → Technical → Update Apps List`
3. Search for **"Balance por Terceros"** and install

## Usage

Navigate to: **Accounting → Reports → Audit Reports → Balance por Terceros**

## Technical Details

- **Handler model**: `account.partner.balance.report.handler`
- **Report record**: `l10n_co_accounting_reports.partner_balance_report`
- **Architecture**: Custom handler inheriting `account.report.custom.handler`
- **SQL strategy**: Aggregation by `(account_id, partner_id)` with separate
  initial balance calculation respecting fiscal year boundaries

## Testing

```bash
odoo-bin -d <database> -i l10n_co_accounting_reports --test-enable --stop-after-init
```

## License

LGPL-3.0 — See [LICENSE](https://www.gnu.org/licenses/lgpl-3.0.html)

## Author

**InSoTech** — Medellín, Colombia
