# -*- coding: utf-8 -*-
# Part of l10n_co_accounting_reports.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api, _
from odoo.tools import SQL
from odoo.exceptions import UserError

from datetime import timedelta
from collections import defaultdict


class PartnerBalanceReportHandler(models.AbstractModel):
    """Handler para el reporte 'Balance de Prueba por Terceros'.

    Estructura del reporte:
        Nivel 1 (foldable):  Cuenta contable (código + nombre) con totales
          Nivel 3:           Tercero (Tipo Doc, NIT, Razón Social, saldos)
        Nivel 1:             Gran Total

    Hereda de account.report.custom.handler y sigue el mismo patrón
    arquitectónico del General Ledger de Odoo 18 (Enterprise).
    """

    _name = 'account.partner.balance.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Balance de Prueba por Terceros - Handler'

    # =================================================================
    # OPTIONS
    # =================================================================

    def _custom_options_initializer(self, report, options, previous_options):
        """Inicializa opciones del reporte."""
        super()._custom_options_initializer(report, options, previous_options)
        # FIX #1: Evitar líneas "Total" duplicadas debajo de cada sección
        options['ignore_totals_below_sections'] = True
        # Desplegar automáticamente en modo impresión
        if options.get('export_mode') == 'print' and not options.get('unfolded_lines'):
            options['unfold_all'] = True

    def _caret_options_initializer(self, report, options):
        """Configura el menú contextual (clic derecho) en las líneas.

        Permite al usuario navegar desde una línea del reporte hacia
        los asientos contables o el libro mayor filtrado.
        """
        options['caret_options'] = {
            'account.account': [
                {
                    'name': _('Libro Mayor'),
                    'action': 'caret_option_open_general_ledger',
                },
                {
                    'name': _('Asientos Contables'),
                    'action': 'caret_option_open_journal_items',
                },
            ],
            'res.partner': [
                {
                    'name': _('Libro Mayor del Tercero'),
                    'action': 'caret_option_open_partner_ledger',
                },
                {
                    'name': _('Asientos Contables'),
                    'action': 'caret_option_open_journal_items',
                },
            ],
        }

    # =================================================================
    # DYNAMIC LINES GENERATOR (Líneas de cuenta - nivel 1)
    # =================================================================

    def _dynamic_lines_generator(
        self, report, options,
        all_column_groups_expression_totals, warnings=None
    ):
        """Genera las líneas de nivel 1 (cuentas contables) con totales.

        Cada cuenta es una línea plegable. Al expandirla se muestran
        los terceros con sus saldos (via expand_function).
        """
        lines = []
        company_currency = self.env.company.currency_id

        totals_by_col_group = {
            col_group: {
                'initial_balance': 0.0,
                'debit': 0.0,
                'credit': 0.0,
                'balance': 0.0,
            }
            for col_group in options['column_groups']
        }

        # Obtener datos agregados a nivel de cuenta
        account_results = self._get_account_results(report, options)

        for account, values_by_col_group in account_results:
            has_values = False

            for col_group, values in values_by_col_group.items():
                initial = values.get('initial_balance', 0.0)
                debit = values.get('debit', 0.0)
                credit = values.get('credit', 0.0)
                balance = initial + debit - credit

                values['balance'] = balance

                if (
                    not company_currency.is_zero(debit)
                    or not company_currency.is_zero(credit)
                    or not company_currency.is_zero(initial)
                ):
                    has_values = True

                totals_by_col_group[col_group]['initial_balance'] += initial
                totals_by_col_group[col_group]['debit'] += debit
                totals_by_col_group[col_group]['credit'] += credit
                totals_by_col_group[col_group]['balance'] += balance

            if has_values:
                lines.append(
                    self._get_account_line(
                        report, options, account, values_by_col_group
                    )
                )

        # Redondear totales
        for col_totals in totals_by_col_group.values():
            for key in col_totals:
                col_totals[key] = company_currency.round(col_totals[key])

        # Línea de total general
        lines.append(
            self._get_total_line(report, options, totals_by_col_group)
        )

        return [(0, line) for line in lines]

    # =================================================================
    # EXPAND / UNFOLD (Líneas de tercero - nivel 3)
    # =================================================================

    def _report_expand_unfoldable_line_partner_balance(
        self, line_dict_id, groupby, options,
        progress, offset, unfold_all_batch_data=None
    ):
        """Expande una cuenta para mostrar sus terceros con saldos."""
        report = self.env['account.report'].browse(options['report_id'])
        model, account_id = report._get_model_info_from_id(line_dict_id)

        if model != 'account.account':
            raise UserError(
                _("Wrong ID for partner balance line to expand: %s",
                  line_dict_id)
            )

        # Usar datos pre-cargados (batch) o consultar individualmente
        if unfold_all_batch_data:
            partner_list = unfold_all_batch_data.get(
                'partner_data', {}
            ).get(account_id, [])
        else:
            partner_list = self._get_partner_results(
                report, options, [account_id]
            ).get(account_id, [])

        lines = []
        for partner_data in partner_list:
            lines.append(
                self._get_partner_line(
                    report, options, partner_data, line_dict_id
                )
            )

        return {
            'lines': lines,
            'offset_increment': 0,
            'has_more': False,
        }

    def _custom_unfold_all_batch_data_generator(
        self, report, options, lines_to_expand_by_function
    ):
        """Pre-carga datos de terceros para todas las cuentas (Unfold All).

        Optimiza el rendimiento cuando el usuario despliega todo el
        reporte o al exportar/imprimir.
        """
        expand_key = '_report_expand_unfoldable_line_partner_balance'
        account_ids = []
        for line_dict in lines_to_expand_by_function.get(expand_key, []):
            model, model_id = report._get_model_info_from_id(
                line_dict['id']
            )
            if model == 'account.account':
                account_ids.append(model_id)

        return {
            'partner_data': (
                self._get_partner_results(report, options, account_ids)
                if account_ids else {}
            ),
        }

    # =================================================================
    # SQL: DATOS A NIVEL DE CUENTA
    # =================================================================

    def _get_account_results(self, report, options):
        """Obtiene sumas agregadas por cuenta: período + saldo anterior.

        Returns:
            Lista de tuplas (account_record, values_by_col_group)
            donde values_by_col_group = {
                col_group_key: {
                    'debit': float,
                    'credit': float,
                    'initial_balance': float,
                }
            }
        """
        period_data = {}
        initial_data = {}

        for col_group_key, col_group_options in (
            report._split_options_per_column_group(options).items()
        ):
            # --- Sumas del período (strict_range) ---
            query = report._get_report_query(
                col_group_options, 'strict_range'
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.account_id AS account_id,
                    SUM(%(debit)s) AS debit,
                    SUM(%(credit)s) AS credit
                FROM %(tables)s
                %(currency_join)s
                WHERE %(where)s
                GROUP BY account_move_line.account_id
                """,
                debit=report._currency_table_apply_rate(
                    SQL("account_move_line.debit")
                ),
                credit=report._currency_table_apply_rate(
                    SQL("account_move_line.credit")
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(
                    col_group_options
                ),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                period_data.setdefault(
                    row['account_id'], {}
                )[col_group_key] = {
                    'debit': row['debit'],
                    'credit': row['credit'],
                }

            # --- Saldo anterior (initial balance) ---
            init_options = self._get_initial_balance_options(
                col_group_options
            )
            date_from = fields.Date.from_string(
                col_group_options['date']['date_from']
            )
            fiscal_dates = self.env.company.compute_fiscalyear_dates(
                date_from
            )
            domain = [
                '|',
                ('date', '>=', fiscal_dates['date_from']),
                ('account_id.include_initial_balance', '=', True),
            ]
            query = report._get_report_query(
                init_options, 'from_beginning', domain=domain
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.account_id AS account_id,
                    SUM(%(balance)s) AS initial_balance
                FROM %(tables)s
                %(currency_join)s
                WHERE %(where)s
                GROUP BY account_move_line.account_id
                """,
                balance=report._currency_table_apply_rate(
                    SQL("account_move_line.balance")
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(init_options),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                initial_data.setdefault(
                    row['account_id'], {}
                )[col_group_key] = row['initial_balance']

        # Combinar y devolver ordenado por código de cuenta
        all_account_ids = set(period_data.keys()) | set(initial_data.keys())
        if not all_account_ids:
            return []

        accounts = self.env['account.account'].browse(
            list(all_account_ids)
        ).sorted(key=lambda a: a.code)

        result = []
        for account in accounts:
            values_by_col_group = {}
            for col_group_key in options['column_groups']:
                period = period_data.get(
                    account.id, {}
                ).get(col_group_key, {})
                initial = initial_data.get(
                    account.id, {}
                ).get(col_group_key, 0.0)
                values_by_col_group[col_group_key] = {
                    'debit': period.get('debit', 0.0),
                    'credit': period.get('credit', 0.0),
                    'initial_balance': initial,
                }
            result.append((account, values_by_col_group))

        return result

    # =================================================================
    # SQL: DATOS A NIVEL DE TERCERO (por cuenta)
    # =================================================================

    def _get_partner_results(self, report, options, account_ids):
        """Obtiene datos de terceros dentro de cuentas específicas.

        Args:
            account_ids: Lista de IDs de account.account

        Returns:
            Dict {account_id: [partner_data_list]}
            donde partner_data = {
                'partner_id': int|None,
                'partner_vat': str (formateado),
                'partner_name': str,
                'doc_type': str,
                'values': {col_group_key: {initial_balance, debit,
                                           credit, balance}},
            }
        """
        if not account_ids:
            return {}

        # Lookup de tipos de identificación
        id_types = self.env['l10n_latam.identification.type'].search([])
        id_type_map = {t.id: t.name for t in id_types}
        nit_type_ids = {
            t.id for t in id_types
            if 'nit' in (t.name or '').lower()
        }

        # Estructura: {account_id: {partner_id: {col_group: {field: val}}}}
        data = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(float)
                )
            )
        )
        partner_info = {}

        for col_group_key, col_group_options in (
            report._split_options_per_column_group(options).items()
        ):
            # --- Sumas del período por tercero ---
            query = report._get_report_query(
                col_group_options, 'strict_range',
                domain=[('account_id', 'in', account_ids)]
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.account_id,
                    account_move_line.partner_id,
                    MIN(partner.vat) AS partner_vat,
                    MIN(partner.name) AS partner_name,
                    MIN(partner.l10n_latam_identification_type_id)
                        AS doc_type_id,
                    SUM(%(debit)s) AS debit,
                    SUM(%(credit)s) AS credit
                FROM %(tables)s
                %(currency_join)s
                LEFT JOIN res_partner partner
                    ON partner.id = account_move_line.partner_id
                WHERE %(where)s
                GROUP BY
                    account_move_line.account_id,
                    account_move_line.partner_id
                """,
                debit=report._currency_table_apply_rate(
                    SQL("account_move_line.debit")
                ),
                credit=report._currency_table_apply_rate(
                    SQL("account_move_line.credit")
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(
                    col_group_options
                ),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                acc_id = row['account_id']
                p_id = row['partner_id']
                data[acc_id][p_id][col_group_key]['debit'] = row['debit']
                data[acc_id][p_id][col_group_key]['credit'] = row['credit']

                if p_id is not None and p_id not in partner_info:
                    doc_type_id = row['doc_type_id']
                    partner_info[p_id] = {
                        'vat': row['partner_vat'] or '',
                        'name': row['partner_name'] or '',
                        'doc_type': id_type_map.get(doc_type_id, ''),
                        'is_nit': doc_type_id in nit_type_ids,
                    }

            # --- Saldo anterior por tercero ---
            init_options = self._get_initial_balance_options(
                col_group_options
            )
            date_from = fields.Date.from_string(
                col_group_options['date']['date_from']
            )
            fiscal_dates = self.env.company.compute_fiscalyear_dates(
                date_from
            )
            domain = [
                ('account_id', 'in', account_ids),
                '|',
                ('date', '>=', fiscal_dates['date_from']),
                ('account_id.include_initial_balance', '=', True),
            ]
            query = report._get_report_query(
                init_options, 'from_beginning', domain=domain
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.account_id,
                    account_move_line.partner_id,
                    MIN(partner.vat) AS partner_vat,
                    MIN(partner.name) AS partner_name,
                    MIN(partner.l10n_latam_identification_type_id)
                        AS doc_type_id,
                    SUM(%(balance)s) AS initial_balance
                FROM %(tables)s
                %(currency_join)s
                LEFT JOIN res_partner partner
                    ON partner.id = account_move_line.partner_id
                WHERE %(where)s
                GROUP BY
                    account_move_line.account_id,
                    account_move_line.partner_id
                """,
                balance=report._currency_table_apply_rate(
                    SQL("account_move_line.balance")
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(init_options),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                acc_id = row['account_id']
                p_id = row['partner_id']
                data[acc_id][p_id][col_group_key]['initial_balance'] = (
                    row['initial_balance']
                )

                if p_id is not None and p_id not in partner_info:
                    doc_type_id = row['doc_type_id']
                    partner_info[p_id] = {
                        'vat': row['partner_vat'] or '',
                        'name': row['partner_name'] or '',
                        'doc_type': id_type_map.get(doc_type_id, ''),
                        'is_nit': doc_type_id in nit_type_ids,
                    }

        # Construir resultado: {account_id: [partner_data_list]}
        result = {}
        for acc_id in data:
            partners = []
            for p_id, col_groups in data[acc_id].items():
                if p_id is not None:
                    info = partner_info.get(p_id, {
                        'vat': '', 'name': '', 'doc_type': '',
                        'is_nit': False,
                    })
                else:
                    info = {
                        'vat': '', 'name': _('Sin Tercero'),
                        'doc_type': '', 'is_nit': False,
                    }

                values_by_col_group = {}
                for col_group_key, values in col_groups.items():
                    initial = values.get('initial_balance', 0.0)
                    debit = values.get('debit', 0.0)
                    credit = values.get('credit', 0.0)
                    values_by_col_group[col_group_key] = {
                        'initial_balance': initial,
                        'debit': debit,
                        'credit': credit,
                        'balance': initial + debit - credit,
                    }

                partners.append({
                    'partner_id': p_id,
                    'partner_vat': self._format_partner_vat(
                        info['vat'], is_nit=info['is_nit']
                    ),
                    'partner_name': info['name'] or _('Sin Tercero'),
                    'doc_type': info['doc_type'],
                    'values': values_by_col_group,
                })

            # Ordenar: terceros con nombre primero, "Sin Tercero" al final
            partners.sort(
                key=lambda x: (
                    x['partner_id'] is None,
                    (x['partner_name'] or '').lower(),
                )
            )
            result[acc_id] = partners

        return result

    # =================================================================
    # LINE BUILDERS
    # =================================================================

    def _get_account_line(self, report, options, account, values_by_col_group):
        """Construye una línea de cuenta contable (nivel 1, plegable)."""
        line_id = report._get_generic_line_id(
            'account.account', account.id
        )
        column_values = []
        for column in options['columns']:
            col_expr = column['expression_label']
            col_group = column['column_group_key']
            values = values_by_col_group.get(col_group, {})

            if col_expr in ('doc_type', 'partner_vat', 'partner_name'):
                # Las columnas de tercero quedan vacías a nivel de cuenta
                column_values.append(
                    report._build_column_dict(None, column)
                )
            elif col_expr in (
                'initial_balance', 'debit', 'credit', 'balance'
            ):
                value = values.get(col_expr, 0.0)
                column_values.append(
                    report._build_column_dict(
                        value, column, options=options
                    )
                )
            else:
                column_values.append(
                    report._build_column_dict(None, column)
                )

        return {
            'id': line_id,
            'name': f'{account.code} {account.name}',
            'columns': column_values,
            'level': 1,
            'unfoldable': True,
            'unfolded': (
                line_id in options.get('unfolded_lines', [])
                or options.get('unfold_all')
            ),
            'expand_function': (
                '_report_expand_unfoldable_line_partner_balance'
            ),
            'caret_options': 'account.account',
        }

    def _get_partner_line(
        self, report, options, partner_data, parent_line_id
    ):
        """Construye una línea de tercero (nivel 3, dentro de cuenta)."""
        partner_id = partner_data['partner_id']

        if partner_id is not None:
            line_id = report._get_generic_line_id(
                'res.partner', partner_id,
                parent_line_id=parent_line_id
            )
        else:
            line_id = report._get_generic_line_id(
                'res.partner', None,
                parent_line_id=parent_line_id,
                markup='no_partner'
            )

        column_values = []
        values_by_col_group = partner_data.get('values', {})

        for column in options['columns']:
            col_expr = column['expression_label']
            col_group = column['column_group_key']

            if col_expr == 'doc_type':
                column_values.append(
                    report._build_column_dict(
                        partner_data.get('doc_type', ''), column
                    )
                )
            elif col_expr == 'partner_vat':
                column_values.append(
                    report._build_column_dict(
                        partner_data.get('partner_vat', ''), column
                    )
                )
            elif col_expr == 'partner_name':
                column_values.append(
                    report._build_column_dict(
                        partner_data.get('partner_name', ''), column
                    )
                )
            elif col_expr in (
                'initial_balance', 'debit', 'credit', 'balance'
            ):
                values = values_by_col_group.get(col_group, {})
                value = values.get(col_expr, 0.0)
                column_values.append(
                    report._build_column_dict(
                        value, column, options=options
                    )
                )
            else:
                column_values.append(
                    report._build_column_dict(None, column)
                )

        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': partner_data.get('partner_name', _('Sin Tercero')),
            'columns': column_values,
            'level': 3,
            'caret_options': 'res.partner',
        }

    def _get_total_line(self, report, options, totals_by_col_group):
        """Construye la línea de total general."""
        column_values = []
        for column in options['columns']:
            col_expr = column['expression_label']
            col_group = column['column_group_key']

            if col_expr in (
                'initial_balance', 'debit', 'credit', 'balance'
            ):
                value = totals_by_col_group.get(
                    col_group, {}
                ).get(col_expr, 0.0)
                column_values.append(
                    report._build_column_dict(
                        value, column, options=options
                    )
                )
            else:
                column_values.append(
                    report._build_column_dict(None, column)
                )

        return {
            'id': report._get_generic_line_id(
                None, None, markup='total'
            ),
            'name': _('Total'),
            'level': 1,
            'class': 'total',
            'columns': column_values,
        }

    # =================================================================
    # HELPERS
    # =================================================================

    def _get_initial_balance_options(self, options):
        """Crea opciones para calcular el saldo anterior (antes de date_from).

        Respeta el año fiscal:
        - Cuentas de balance (include_initial_balance=True):
          todo el histórico hasta date_from - 1
        - Cuentas de P&L (include_initial_balance=False):
          desde inicio del año fiscal hasta date_from - 1
        """
        new_options = {**options}
        new_options.pop('filter_search_bar', None)

        date_from = fields.Date.from_string(options['date']['date_from'])
        new_date_to = date_from - timedelta(days=1)
        fiscal_dates = self.env.company.compute_fiscalyear_dates(date_from)

        new_options['date'] = {
            **options['date'],
            'date_from': fields.Date.to_string(fiscal_dates['date_from']),
            'date_to': fields.Date.to_string(new_date_to),
        }
        return new_options

    @api.model
    def _format_partner_vat(self, vat, is_nit=False):
        """Formatea el NIT colombiano para visualización.

        Para NIT: 9001234567 → 900.123.456-7
        Para CC/CE: muestra tal cual
        """
        if not vat:
            return ''
        vat_clean = ''.join(c for c in str(vat) if c.isdigit())
        if not vat_clean:
            return str(vat)

        if is_nit and len(vat_clean) > 1:
            main_part = vat_clean[:-1]
            dv = vat_clean[-1]
            try:
                formatted = '{:,}'.format(int(main_part)).replace(',', '.')
                return f'{formatted}-{dv}'
            except ValueError:
                return vat_clean

        return vat_clean
