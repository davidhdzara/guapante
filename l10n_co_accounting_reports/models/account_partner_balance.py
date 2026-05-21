# -*- coding: utf-8 -*-
# Part of l10n_co_accounting_reports.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api, _
from odoo.tools import SQL
from odoo.exceptions import UserError

import io
import base64
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
        # Botón de exportación parafiscal
        options['buttons'].append({
            'name': _('Detalle Parafiscal'),
            'sequence': 50,
            'action': 'export_file',
            'action_param': 'export_parafiscal_xlsx',
            'file_export_type': _('XLSX'),
        })
        # Desplegar automáticamente en modo impresión
        if options.get('export_mode') == 'print' and not options.get('unfolded_lines'):
            options['unfold_all'] = True

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
    # EXPORT: PARAFISCAL XLSX
    # =================================================================

    def export_parafiscal_xlsx(self, options):
        """Genera un Excel con detalle extendido para reportes parafiscales.

        Columnas: NIT, DV, Razón Social, Dirección, Teléfono,
                  Departamento, Municipio, Producto, Kilos,
                  Valor Recaudado.

        Retorna dict con file_name, file_content, file_type
        compatible con el framework export_file de account.report.
        """
        import xlsxwriter

        report = self.env['account.report'].browse(options['report_id'])
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']

        # Obtener datos por (cuenta, tercero)
        rows = self._get_parafiscal_data(report, options)

        if not rows:
            raise UserError(_(
                'No se encontraron datos para exportar en el período '
                '%s a %s con los filtros seleccionados.',
                date_from, date_to,
            ))

        # Generar Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Detalle Parafiscal')

        # --- Formatos ---
        fmt_header = workbook.add_format({
            'bold': True,
            'bg_color': '#1a237e',
            'font_color': 'white',
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
            'font_size': 10,
        })
        fmt_text = workbook.add_format({
            'border': 1,
            'font_size': 9,
            'valign': 'vcenter',
        })
        fmt_number = workbook.add_format({
            'border': 1,
            'font_size': 9,
            'num_format': '#,##0.00',
            'valign': 'vcenter',
        })
        fmt_integer = workbook.add_format({
            'border': 1,
            'font_size': 9,
            'num_format': '#,##0',
            'valign': 'vcenter',
        })
        fmt_account = workbook.add_format({
            'bold': True,
            'bg_color': '#e3f2fd',
            'border': 1,
            'font_size': 10,
            'valign': 'vcenter',
        })

        # --- Encabezados ---
        headers = [
            ('NIT', 15),
            ('DV', 4),
            ('NOMBRE O RAZÓN SOCIAL', 35),
            ('DIRECCIÓN', 30),
            ('TELÉFONO', 14),
            ('DEPARTAMENTO', 16),
            ('MUNICIPIO', 16),
            ('PRODUCTO', 25),
            ('KILOS', 12),
            ('VALOR RECAUDADO', 18),
        ]

        for col, (name, width) in enumerate(headers):
            sheet.write(0, col, name, fmt_header)
            sheet.set_column(col, col, width)

        sheet.set_row(0, 30)
        sheet.freeze_panes(1, 0)

        # --- Datos ---
        row_idx = 1
        current_account = None

        for data in rows:
            # Separador por cuenta contable
            if data['account_code'] != current_account:
                current_account = data['account_code']
                account_label = '%s %s' % (
                    data['account_code'], data['account_name']
                )
                sheet.merge_range(
                    row_idx, 0, row_idx, len(headers) - 1,
                    account_label, fmt_account,
                )
                row_idx += 1

            # Fila del tercero
            sheet.write(row_idx, 0, data['nit'], fmt_text)
            sheet.write(row_idx, 1, data['dv'], fmt_text)
            sheet.write(row_idx, 2, data['partner_name'], fmt_text)
            sheet.write(row_idx, 3, data['address'], fmt_text)
            sheet.write(row_idx, 4, data['phone'], fmt_text)
            sheet.write(row_idx, 5, data['state'], fmt_text)
            sheet.write(row_idx, 6, data['city'], fmt_text)
            sheet.write(row_idx, 7, data['products'], fmt_text)
            sheet.write(row_idx, 8, data['kilos'], fmt_integer)
            sheet.write(row_idx, 9, data['amount'], fmt_number)
            row_idx += 1

        workbook.close()
        output.seek(0)

        # Retornar en formato compatible con export_file
        period = '%s_%s' % (
            date_from.replace('-', ''),
            date_to.replace('-', ''),
        )

        return {
            'file_name': 'detalle_parafiscal_%s' % period,
            'file_content': output.getvalue(),
            'file_type': 'xlsx',
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

    # =================================================================
    # PARAFISCAL: DATA HELPERS
    # =================================================================

    def _get_parafiscal_data(self, report, options):
        """Obtiene datos extendidos de terceros para exportación parafiscal.

        Combina:
        - Montos agrupados por (cuenta, tercero) del período
        - Datos extendidos del partner (dirección, teléfono, etc.)
        - Productos y kilos de las facturas relacionadas

        Returns:
            Lista de dicts ordenada por (cuenta, tercero) con todos
            los campos necesarios para el Excel.
        """
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']

        # Obtener cuentas con movimientos en el período
        account_results = self._get_account_results(report, options)
        if not account_results:
            return []

        # Aplicar filtro de búsqueda por cuenta (filter_search_bar)
        # El framework lo aplica a nivel de frontend; aquí lo replicamos
        search_term = options.get('filter_search_bar')
        if search_term:
            search_lower = search_term.strip().lower()
            account_results = [
                (acc, vals) for acc, vals in account_results
                if search_lower in (acc.code or '').lower()
                or search_lower in (acc.name or '').lower()
            ]
            if not account_results:
                return []

        account_ids = [a.id for a, _ in account_results]
        account_map = {
            a.id: {'code': a.code, 'name': a.name}
            for a, _ in account_results
        }

        # Lookup de tipos de identificación
        id_types = self.env['l10n_latam.identification.type'].search([])
        nit_type_ids = {
            t.id for t in id_types
            if 'nit' in (t.name or '').lower()
        }

        # Query principal: montos por (cuenta, tercero) + datos extendidos
        self._cr.execute(SQL(
            """
            SELECT
                aml.account_id,
                aml.partner_id,
                p.vat AS partner_vat,
                p.name AS partner_name,
                p.l10n_latam_identification_type_id AS doc_type_id,
                p.street AS address,
                p.phone AS phone,
                rs.name AS state_name,
                p.city AS city,
                SUM(aml.balance) AS amount
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            LEFT JOIN res_partner p ON p.id = aml.partner_id
            LEFT JOIN res_country_state rs ON rs.id = p.state_id
            WHERE aml.account_id = ANY(%(account_ids)s)
              AND aml.date >= %(date_from)s
              AND aml.date <= %(date_to)s
              AND am.state = 'posted'
              AND aml.partner_id IS NOT NULL
            GROUP BY
                aml.account_id,
                aml.partner_id,
                p.vat, p.name,
                p.l10n_latam_identification_type_id,
                p.street, p.phone,
                rs.name, p.city
            ORDER BY aml.account_id, p.name
            """,
            account_ids=account_ids,
            date_from=date_from,
            date_to=date_to,
        ))
        partner_rows = self._cr.dictfetchall()

        if not partner_rows:
            return []

        # Query productos/kilos: desde facturas relacionadas
        product_data = self._get_product_kilos_data(
            account_ids, date_from, date_to
        )

        # Construir resultado
        rows = []
        for row in partner_rows:
            acc_id = row['account_id']
            p_id = row['partner_id']
            vat = row['partner_vat'] or ''
            is_nit = row['doc_type_id'] in nit_type_ids

            # Separar NIT y DV
            vat_clean = ''.join(c for c in str(vat) if c.isdigit())
            if is_nit and len(vat_clean) > 1:
                nit = vat_clean[:-1]
                dv = vat_clean[-1]
            else:
                nit = vat_clean
                dv = ''

            # Productos y kilos del partner en esta cuenta
            prod_key = (acc_id, p_id)
            prod_info = product_data.get(prod_key, {})
            products = ', '.join(sorted(
                self._resolve_translated_field(p)
                for p in prod_info.get('products', set())
                if self._resolve_translated_field(p)
            ))
            kilos = prod_info.get('quantity', 0.0)

            acc_info = account_map.get(acc_id, {})
            rows.append({
                'account_code': acc_info.get('code', ''),
                'account_name': acc_info.get('name', ''),
                'nit': nit,
                'dv': dv,
                'partner_name': row['partner_name'] or '',
                'address': row['address'] or '',
                'phone': row['phone'] or '',
                'state': row['state_name'] or '',
                'city': row['city'] or '',
                'products': products,
                'kilos': kilos,
                'amount': abs(row['amount'] or 0.0),
            })

        return rows

    def _get_product_kilos_data(self, account_ids, date_from, date_to):
        """Obtiene productos y cantidades de facturas relacionadas.

        Para cada (cuenta, tercero), busca las facturas que tienen
        líneas en esa cuenta y extrae los productos y cantidades
        de las líneas de producto de esas facturas.

        Returns:
            Dict {(account_id, partner_id): {
                'products': set of product names,
                'quantity': total quantity,
            }}
        """
        self._cr.execute(SQL(
            """
            SELECT
                sub.account_id,
                sub.partner_id,
                sub.product_name,
                SUM(sub.total_qty) AS total_qty
            FROM (
                -- Patron A: Productos en el mismo asiento contable
                SELECT
                    aml_para.account_id,
                    aml_para.partner_id,
                    COALESCE(
                        pt.name->>'es_CO',
                        pt.name->>'en_US',
                        pt.name::text
                    ) AS product_name,
                    SUM(aml_prod.quantity * COALESCE(CASE WHEN uu.category_id != 2 AND pt.weight > 0 THEN pt.weight ELSE 1.0 END, 1.0)) AS total_qty
                FROM account_move_line aml_para
                JOIN account_move am
                    ON am.id = aml_para.move_id
                JOIN account_move_line aml_prod
                    ON aml_prod.move_id = am.id
                    AND aml_prod.product_id IS NOT NULL
                    AND aml_prod.display_type = 'product'
                JOIN product_product pp
                    ON pp.id = aml_prod.product_id
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                JOIN uom_uom uu
                    ON uu.id = pt.uom_id
                WHERE aml_para.account_id = ANY(%(account_ids)s)
                  AND aml_para.date >= %(date_from)s
                  AND aml_para.date <= %(date_to)s
                  AND am.state = 'posted'
                  AND aml_para.partner_id IS NOT NULL
                GROUP BY
                    aml_para.account_id,
                    aml_para.partner_id,
                    product_name

                UNION ALL

                -- Patron B1: Pagos Debito conciliados con Facturas Credito
                SELECT
                    aml_para.account_id,
                    aml_para.partner_id,
                    COALESCE(
                        pt.name->>'es_CO',
                        pt.name->>'en_US',
                        pt.name::text
                    ) AS product_name,
                    SUM(aml_prod.quantity * COALESCE(CASE WHEN uu.category_id != 2 AND pt.weight > 0 THEN pt.weight ELSE 1.0 END, 1.0)) AS total_qty
                FROM account_move_line aml_para
                JOIN account_move am
                    ON am.id = aml_para.move_id
                JOIN account_move_line aml_pay
                    ON aml_pay.move_id = am.id
                    AND aml_pay.account_id != aml_para.account_id
                JOIN account_partial_reconcile apr
                    ON apr.debit_move_id = aml_pay.id
                JOIN account_move_line aml_inv
                    ON aml_inv.id = apr.credit_move_id
                JOIN account_move_line aml_prod
                    ON aml_prod.move_id = aml_inv.move_id
                    AND aml_prod.product_id IS NOT NULL
                    AND aml_prod.display_type = 'product'
                JOIN product_product pp
                    ON pp.id = aml_prod.product_id
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                JOIN uom_uom uu
                    ON uu.id = pt.uom_id
                WHERE aml_para.account_id = ANY(%(account_ids)s)
                  AND aml_para.date >= %(date_from)s
                  AND aml_para.date <= %(date_to)s
                  AND am.state = 'posted'
                  AND aml_para.partner_id IS NOT NULL
                GROUP BY
                    aml_para.account_id,
                    aml_para.partner_id,
                    product_name

                UNION ALL

                -- Patron B2: Pagos Credito conciliados con Facturas Debito
                SELECT
                    aml_para.account_id,
                    aml_para.partner_id,
                    COALESCE(
                        pt.name->>'es_CO',
                        pt.name->>'en_US',
                        pt.name::text
                    ) AS product_name,
                    SUM(aml_prod.quantity * COALESCE(CASE WHEN uu.category_id != 2 AND pt.weight > 0 THEN pt.weight ELSE 1.0 END, 1.0)) AS total_qty
                FROM account_move_line aml_para
                JOIN account_move am
                    ON am.id = aml_para.move_id
                JOIN account_move_line aml_pay
                    ON aml_pay.move_id = am.id
                    AND aml_pay.account_id != aml_para.account_id
                JOIN account_partial_reconcile apr
                    ON apr.credit_move_id = aml_pay.id
                JOIN account_move_line aml_inv
                    ON aml_inv.id = apr.debit_move_id
                JOIN account_move_line aml_prod
                    ON aml_prod.move_id = aml_inv.move_id
                    AND aml_prod.product_id IS NOT NULL
                    AND aml_prod.display_type = 'product'
                JOIN product_product pp
                    ON pp.id = aml_prod.product_id
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                JOIN uom_uom uu
                    ON uu.id = pt.uom_id
                WHERE aml_para.account_id = ANY(%(account_ids)s)
                  AND aml_para.date >= %(date_from)s
                  AND aml_para.date <= %(date_to)s
                  AND am.state = 'posted'
                  AND aml_para.partner_id IS NOT NULL
                GROUP BY
                    aml_para.account_id,
                    aml_para.partner_id,
                    product_name
            ) sub
            GROUP BY
                sub.account_id,
                sub.partner_id,
                sub.product_name
            """,
            account_ids=account_ids,
            date_from=date_from,
            date_to=date_to,
        ))

        result = defaultdict(lambda: {'products': set(), 'quantity': 0.0})
        for row in self._cr.dictfetchall():
            key = (row['account_id'], row['partner_id'])
            product_name = row['product_name'] or ''
            # Resolver JSONB → string plano
            product_name = self._resolve_translated_field(product_name)
            if product_name:
                result[key]['products'].add(product_name)
            result[key]['quantity'] += row['total_qty'] or 0.0

        return dict(result)

    @api.model
    def _resolve_translated_field(self, value):
        """Convierte un campo traducible JSONB a string plano.

        En Odoo 18, los campos traducibles se almacenan como JSONB
        con estructura {'en_US': '...', 'es_CO': '...'}. psycopg2
        los deserializa como dict de Python.

        Prioridad: es_CO → en_US → primer valor disponible.
        """
        if not value:
            return ''
        if isinstance(value, dict):
            return (
                value.get('es_CO')
                or value.get('en_US')
                or next(iter(value.values()), '')
            )
        s = str(value)
        # Fallback: si es un string JSON (e.g. '{"en_US": "Batata"}')
        if s.startswith('{') and 'en_US' in s:
            try:
                import json
                d = json.loads(s)
                if isinstance(d, dict):
                    return (
                        d.get('es_CO')
                        or d.get('en_US')
                        or next(iter(d.values()), '')
                    )
            except (json.JSONDecodeError, ValueError):
                pass
        return s
