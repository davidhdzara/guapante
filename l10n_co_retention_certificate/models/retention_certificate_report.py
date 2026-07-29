# -*- coding: utf-8 -*-
import json

from odoo import models, _
from odoo.tools import SQL
from odoo.tools.translate import _lt

# _lt (traducción perezosa), no _ : este dict se evalúa una sola vez al
# importar el módulo, sin contexto de idioma/request todavía. Usar _()
# aquí generaba un warning ("no translation language detected") y
# congelaba el valor en el idioma que hubiera en ese instante. _lt()
# devuelve un objeto que se traduce cada vez que se usa (str(...)),
# ya con el idioma real del usuario.
RETENTION_TYPE_LABELS = {
    'retefuente': _lt('Retención en la Fuente'),
    'reteiva': _lt('Retención de IVA'),
    'reteica': _lt('Retención de ICA'),
    'parafiscal': _lt('Contribución Parafiscal'),
}

# Orden de presentación de las secciones dentro del certificado, tal como
# quedó acordado en la ESPEC (§4 Fase 4): Fuente -> ReteIVA -> ReteICA ->
# Parafiscales. Se usa aquí también para ordenar el nivel 2 del reporte.
RETENTION_TYPE_ORDER = ['retefuente', 'reteiva', 'reteica', 'parafiscal']


class RetentionCertificateReportHandler(models.AbstractModel):
    """Handler para el reporte 'Certificado de Retenciones'.

    Estructura del reporte:
        Nivel 1 (foldable):  Tercero (nombre + NIT) con totales
          Nivel 2 (foldable):  Tipo de retención (Fuente/IVA/ICA/Parafiscal)
            Nivel 3:           Concepto (impuesto): base y retenido
        Nivel 1:               Gran Total

    A diferencia del certificado nativo de l10n_co_reports (que agrupa por
    rango de cuenta contable), este reporte agrupa por account.tax vía
    account_move_line.tax_line_id, usando l10n_co_retention_type (ver
    models/account_tax.py) para clasificar cada impuesto. Esto lo hace
    inmune a cómo esté configurado el PUC de cada cliente.

    Sigue el mismo patrón arquitectónico que
    l10n_co_accounting_reports/models/account_partner_balance.py (mismo
    repo, mismo autor): odoo.tools.SQL, report._get_report_query(),
    _dynamic_lines_generator + expand_function + batch data generator.
    """

    _name = 'l10n_co.retention.certificate.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Certificado de Retenciones - Handler'

    # =================================================================
    # OPTIONS
    # =================================================================

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if options.get('export_mode') == 'print' and not options.get('unfolded_lines'):
            # Estado por defecto: todo desplegado (matiz D2 #2 — "todas las
            # líneas nacen marcadas"). Si el usuario ya plegó algo a mano
            # (unfolded_lines no vacío), se respeta esa selección: plegar
            # una línea es el acto consciente de excluirla del certificado.
            options['unfold_all'] = True

        # Reprograma el botón nativo "PDF" para que abra el wizard de
        # fechas/artículo en lugar del export genérico, igual que hace el
        # certificado nativo (l10n_co.report.handler, l10n_co_reports).
        for button in options['buttons']:
            if button['name'] == 'PDF':
                button['action'] = 'print_pdf'

    def print_pdf(self, options, action_param):
        """Abre el wizard reutilizado de l10n_co_reports (fechas de
        expedición/declaración + artículo) para generar el certificado en
        PDF a partir de lo que esté desplegado en este reporte en este
        momento. Ver wizard/retention_certificate_wizard.py: el wizard
        detecta que fue abierto desde ESTE reporte y redirige a nuestra
        propia plantilla en vez de a la nativa.
        """
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'l10n_co_reports.retention_report.wizard',
            'views': [(
                self.env.ref('l10n_co_reports.retention_report_wizard_form').id,
                'form',
            )],
            'view_id': self.env.ref('l10n_co_reports.retention_report_wizard_form').id,
            'target': 'new',
            'context': {'options': options},
            'data': {'options': json.dumps(options), 'output_format': 'pdf'},
        }

    # =================================================================
    # DYNAMIC LINES GENERATOR (Nivel 1 - Terceros)
    # =================================================================

    def _dynamic_lines_generator(
        self, report, options,
        all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        company_currency = self.env.company.currency_id

        totals_by_col_group = {
            col_group: {'tax_base_amount': 0.0, 'balance': 0.0}
            for col_group in options['column_groups']
        }

        partner_results = self._get_partner_results(report, options)

        for partner, values_by_col_group in partner_results:
            has_values = False

            for col_group, values in values_by_col_group.items():
                if not company_currency.is_zero(values.get('balance', 0.0)):
                    has_values = True
                totals_by_col_group[col_group]['tax_base_amount'] += values.get('tax_base_amount', 0.0)
                totals_by_col_group[col_group]['balance'] += values.get('balance', 0.0)

            if has_values:
                lines.append(
                    self._get_partner_line(report, options, partner, values_by_col_group)
                )

        for col_totals in totals_by_col_group.values():
            for key in col_totals:
                col_totals[key] = company_currency.round(col_totals[key])

        lines.append(self._get_total_line(report, options, totals_by_col_group))

        return [(0, line) for line in lines]

    # =================================================================
    # EXPAND / UNFOLD — Nivel 2 (Tipo de retención, dentro de un tercero)
    # =================================================================

    def _report_expand_unfoldable_line_l10n_co_retention_type(
        self, line_dict_id, groupby, options,
        progress, offset, unfold_all_batch_data=None
    ):
        report = self.env['account.report'].browse(options['report_id'])
        model, partner_id = report._get_model_info_from_id(line_dict_id)
        if model != 'res.partner':
            raise ValueError(
                "Wrong ID for retention certificate line to expand: %s" % line_dict_id
            )

        if unfold_all_batch_data and 'type_data' in unfold_all_batch_data:
            type_list = unfold_all_batch_data['type_data'].get(partner_id, [])
        else:
            type_list = self._get_type_results(report, options, [partner_id]).get(partner_id, [])

        lines = []
        for type_data in type_list:
            lines.append(
                self._get_type_line(report, options, type_data, line_dict_id)
            )

        return {
            'lines': lines,
            'offset_increment': 0,
            'has_more': False,
        }

    def _custom_unfold_all_batch_data_generator(
        self, report, options, lines_to_expand_by_function
    ):
        """Pre-carga en batch los datos de Nivel 2 (tipo de retención) para
        todos los terceros a expandir de una vez (Unfold All / Imprimir /
        Exportar).

        El Nivel 3 (concepto) no se pre-carga en batch: se resuelve con una
        consulta individual por (tercero, tipo) al expandirse, igual que
        hace el reporte nativo de Odoo cuando no hay batch data disponible.
        Es una simplificación deliberada — el volumen de líneas de Nivel 2
        por tercero es bajo (máximo 4 tipos de retención), así que el
        costo de no *también* batchear el Nivel 3 es marginal.
        """
        expand_key = '_report_expand_unfoldable_line_l10n_co_retention_type'
        partner_ids = []
        for line_dict in lines_to_expand_by_function.get(expand_key, []):
            model, model_id = report._get_model_info_from_id(line_dict['id'])
            if model == 'res.partner':
                partner_ids.append(model_id)

        return {
            'type_data': (
                self._get_type_results(report, options, partner_ids)
                if partner_ids else {}
            ),
        }

    # =================================================================
    # EXPAND / UNFOLD — Nivel 3 (Concepto, dentro de tercero + tipo)
    # =================================================================

    def _report_expand_unfoldable_line_l10n_co_retention_concept(
        self, line_dict_id, groupby, options,
        progress, offset, unfold_all_batch_data=None
    ):
        report = self.env['account.report'].browse(options['report_id'])
        partner_id, retention_type = self._parse_type_line_id(report, line_dict_id)

        concept_results = self._get_concept_results(report, options, [(partner_id, retention_type)])
        concept_list = concept_results.get((partner_id, retention_type), [])

        lines = []
        for concept_data in concept_list:
            lines.append(
                self._get_concept_line(report, options, concept_data, line_dict_id)
            )

        return {
            'lines': lines,
            'offset_increment': 0,
            'has_more': False,
        }

    def _parse_type_line_id(self, report, line_dict_id):
        """Extrae (partner_id, retention_type) de un line_dict_id de Nivel 2.

        La línea de Nivel 2 no tiene modelo propio (es un markup, igual que
        el agrupamiento por cuenta del reporte nativo l10n_co.fuente); el
        tipo va codificado en el markup del propio segmento
        (report._get_markup) y el tercero se busca en toda la cadena de la
        línea con report._get_res_id_from_line_id (no existe un
        "_get_parent_line_id" en el framework; este es el método real).
        """
        markup = report._get_markup(line_dict_id)
        retention_type = markup.split('type_', 1)[1] if markup and markup.startswith('type_') else False
        partner_id = report._get_res_id_from_line_id(line_dict_id, 'res.partner')
        return partner_id, retention_type

    # =================================================================
    # SQL: NIVEL 1 — TOTALES POR TERCERO
    # =================================================================

    def _get_partner_results(self, report, options):
        """Obtiene sumas agregadas por tercero, en todas las cuentas cuyo
        impuesto de retención (tax_line_id) esté clasificado.

        Returns:
            Lista de tuplas (partner_record, values_by_col_group) ordenada
            por nombre de tercero.
        """
        data = {}

        for col_group_key, col_group_options in (
            report._split_options_per_column_group(options).items()
        ):
            domain = self._get_base_domain()
            query = report._get_report_query(col_group_options, 'strict_range', domain=domain)
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.partner_id AS partner_id,
                    SUM(%(balance)s) AS balance,
                    SUM(%(tax_base_amount)s) AS tax_base_amount
                FROM %(tables)s
                %(currency_join)s
                WHERE %(where)s
                GROUP BY account_move_line.partner_id
                """,
                balance=report._currency_table_apply_rate(
                    SQL("account_move_line.credit - account_move_line.debit")
                ),
                tax_base_amount=report._currency_table_apply_rate(
                    self._tax_base_amount_case_sql()
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(col_group_options),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                data.setdefault(row['partner_id'], {})[col_group_key] = {
                    'balance': row['balance'] or 0.0,
                    'tax_base_amount': row['tax_base_amount'] or 0.0,
                }

        if not data:
            return []

        partners = self.env['res.partner'].browse(list(data.keys())).sorted(key=lambda p: p.name or '')

        result = []
        for partner in partners:
            values_by_col_group = {}
            for col_group_key in options['column_groups']:
                values = data.get(partner.id, {}).get(col_group_key, {})
                values_by_col_group[col_group_key] = {
                    'balance': values.get('balance', 0.0),
                    'tax_base_amount': values.get('tax_base_amount', 0.0),
                }
            result.append((partner, values_by_col_group))

        return result

    # =================================================================
    # SQL: NIVEL 2 — TOTALES POR TIPO DE RETENCIÓN (batch por terceros)
    # =================================================================

    def _get_type_results(self, report, options, partner_ids):
        """Obtiene, para un conjunto de terceros, el desglose por
        l10n_co_retention_type.

        Returns:
            Dict {partner_id: [type_data, ...]} donde type_data =
            {'retention_type': str, 'values': {col_group_key: {...}}}
        """
        if not partner_ids:
            return {}

        data = {}

        for col_group_key, col_group_options in (
            report._split_options_per_column_group(options).items()
        ):
            domain = self._get_base_domain() + [('partner_id', 'in', partner_ids)]
            query = report._get_report_query(col_group_options, 'strict_range', domain=domain)
            account_tax_alias = query.left_join(
                lhs_alias='account_move_line', lhs_column='tax_line_id',
                rhs_table='account_tax', rhs_column='id', link='l10n_co_retention_certificate_tax',
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.partner_id AS partner_id,
                    %(retention_type)s AS retention_type,
                    SUM(%(balance)s) AS balance,
                    SUM(%(tax_base_amount)s) AS tax_base_amount
                FROM %(tables)s
                %(currency_join)s
                WHERE %(where)s
                GROUP BY account_move_line.partner_id, %(retention_type)s
                """,
                retention_type=SQL.identifier(account_tax_alias, 'l10n_co_retention_type'),
                balance=report._currency_table_apply_rate(
                    SQL("account_move_line.credit - account_move_line.debit")
                ),
                tax_base_amount=report._currency_table_apply_rate(
                    self._tax_base_amount_case_sql()
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(col_group_options),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                key = (row['partner_id'], row['retention_type'])
                data.setdefault(key, {})[col_group_key] = {
                    'balance': row['balance'] or 0.0,
                    'tax_base_amount': row['tax_base_amount'] or 0.0,
                }

        result = {}
        for (partner_id, retention_type), values_by_col_group_raw in data.items():
            values_by_col_group = {}
            for col_group_key in options['column_groups']:
                values = values_by_col_group_raw.get(col_group_key, {})
                values_by_col_group[col_group_key] = {
                    'balance': values.get('balance', 0.0),
                    'tax_base_amount': values.get('tax_base_amount', 0.0),
                }
            result.setdefault(partner_id, []).append({
                'retention_type': retention_type,
                'values': values_by_col_group,
            })

        for partner_id, type_list in result.items():
            type_list.sort(key=lambda t: (
                RETENTION_TYPE_ORDER.index(t['retention_type'])
                if t['retention_type'] in RETENTION_TYPE_ORDER else 99
            ))

        return result

    # =================================================================
    # SQL: NIVEL 3 — TOTALES POR CONCEPTO (impuesto), dado tercero + tipo
    # =================================================================

    def _get_concept_results(self, report, options, partner_retention_pairs):
        """Obtiene, para pares (partner_id, retention_type), el desglose
        por impuesto (concepto).

        Returns:
            Dict {(partner_id, retention_type): [concept_data, ...]} donde
            concept_data = {'tax_id': int, 'concept_name': str,
                             'values': {col_group_key: {...}}}
        """
        if not partner_retention_pairs:
            return {}

        partner_ids = list({pair[0] for pair in partner_retention_pairs})
        retention_types = list({pair[1] for pair in partner_retention_pairs})

        data = {}

        for col_group_key, col_group_options in (
            report._split_options_per_column_group(options).items()
        ):
            domain = self._get_base_domain() + [
                ('partner_id', 'in', partner_ids),
                ('tax_line_id.l10n_co_retention_type', 'in', retention_types),
            ]
            query = report._get_report_query(col_group_options, 'strict_range', domain=domain)
            account_tax_alias = query.left_join(
                lhs_alias='account_move_line', lhs_column='tax_line_id',
                rhs_table='account_tax', rhs_column='id', link='l10n_co_retention_certificate_concept_tax',
            )
            self._cr.execute(SQL(
                """
                SELECT
                    account_move_line.partner_id AS partner_id,
                    %(retention_type)s AS retention_type,
                    account_move_line.tax_line_id AS tax_id,
                    SUM(%(balance)s) AS balance,
                    SUM(%(tax_base_amount)s) AS tax_base_amount
                FROM %(tables)s
                %(currency_join)s
                WHERE %(where)s
                GROUP BY account_move_line.partner_id, %(retention_type)s, account_move_line.tax_line_id
                """,
                retention_type=SQL.identifier(account_tax_alias, 'l10n_co_retention_type'),
                balance=report._currency_table_apply_rate(
                    SQL("account_move_line.credit - account_move_line.debit")
                ),
                tax_base_amount=report._currency_table_apply_rate(
                    self._tax_base_amount_case_sql()
                ),
                tables=query.from_clause,
                currency_join=report._currency_table_aml_join(col_group_options),
                where=query.where_clause,
            ))
            for row in self._cr.dictfetchall():
                key = (row['partner_id'], row['retention_type'])
                data.setdefault(key, {}).setdefault(row['tax_id'], {})[col_group_key] = {
                    'balance': row['balance'] or 0.0,
                    'tax_base_amount': row['tax_base_amount'] or 0.0,
                }

        all_tax_ids = {
            tax_id
            for by_tax in data.values()
            for tax_id in by_tax.keys()
        }
        concept_names = self._get_concept_names(list(all_tax_ids))

        result = {}
        for key, by_tax in data.items():
            concept_list = []
            for tax_id, values_by_col_group_raw in by_tax.items():
                values_by_col_group = {}
                for col_group_key in options['column_groups']:
                    values = values_by_col_group_raw.get(col_group_key, {})
                    values_by_col_group[col_group_key] = {
                        'balance': values.get('balance', 0.0),
                        'tax_base_amount': values.get('tax_base_amount', 0.0),
                    }
                concept_list.append({
                    'tax_id': tax_id,
                    'concept_name': concept_names.get(tax_id, ''),
                    'values': values_by_col_group,
                })
            concept_list.sort(key=lambda c: c['concept_name'])
            result[key] = concept_list

        return result

    # =================================================================
    # LINE BUILDERS
    # =================================================================

    def _get_partner_line(self, report, options, partner, values_by_col_group):
        line_id = report._get_generic_line_id('res.partner', partner.id)
        column_values = self._build_amount_columns(report, options, values_by_col_group)

        return {
            'id': line_id,
            'name': self._format_partner_name(partner),
            'columns': column_values,
            'level': 1,
            'unfoldable': True,
            'unfolded': (
                line_id in options.get('unfolded_lines', [])
                or options.get('unfold_all')
            ),
            'expand_function': '_report_expand_unfoldable_line_l10n_co_retention_type',
        }

    def _get_type_line(self, report, options, type_data, parent_line_id):
        retention_type = type_data['retention_type']
        line_id = report._get_generic_line_id(
            None, None,
            markup='type_%s' % (retention_type or 'sin_clasificar'),
            parent_line_id=parent_line_id,
        )
        column_values = self._build_amount_columns(report, options, type_data['values'])

        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': str(RETENTION_TYPE_LABELS.get(retention_type, _('Sin Clasificar'))),
            'columns': column_values,
            'level': 2,
            'unfoldable': True,
            'unfolded': (
                line_id in options.get('unfolded_lines', [])
                or options.get('unfold_all')
            ),
            'expand_function': '_report_expand_unfoldable_line_l10n_co_retention_concept',
        }

    def _get_concept_line(self, report, options, concept_data, parent_line_id):
        line_id = report._get_generic_line_id(
            'account.tax', concept_data['tax_id'], parent_line_id=parent_line_id
        )
        column_values = self._build_amount_columns(
            report, options, concept_data['values'], concept_name=concept_data['concept_name']
        )

        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': concept_data['concept_name'],
            'columns': column_values,
            'level': 3,
        }

    def _get_total_line(self, report, options, totals_by_col_group):
        column_values = self._build_amount_columns(report, options, totals_by_col_group)

        return {
            'id': report._get_generic_line_id(None, None, markup='total'),
            'name': _('Total'),
            'level': 1,
            'class': 'total',
            'columns': column_values,
        }

    def _build_amount_columns(self, report, options, values_by_col_group, concept_name=None):
        column_values = []
        for column in options['columns']:
            col_expr = column['expression_label']
            col_group = column['column_group_key']
            values = values_by_col_group.get(col_group, {})

            if col_expr == 'concept_name':
                column_values.append(
                    report._build_column_dict(concept_name, column)
                )
            elif col_expr in ('tax_base_amount', 'balance'):
                value = values.get(col_expr, 0.0)
                column_values.append(
                    report._build_column_dict(value, column, options=options)
                )
            else:
                column_values.append(report._build_column_dict(None, column))
        return column_values

    # =================================================================
    # HELPERS
    # =================================================================

    def _get_base_domain(self):
        """Dominio común a los tres niveles: solo líneas con un impuesto
        de retención de compra clasificado. La condición sobre
        tax_line_id.l10n_co_retention_type ya excluye implícitamente las
        líneas sin tax_line_id (los asientos de consignación a la DIAN,
        que no tienen impuesto asociado) — ver ESPEC §2.3 y §4 Fase 2.
        """
        return [
            ('partner_id', '!=', False),
            ('tax_line_id', '!=', False),
            ('tax_line_id.type_tax_use', '=', 'purchase'),
            ('tax_line_id.l10n_co_retention_type', '!=', False),
        ]

    def _tax_base_amount_case_sql(self):
        """Normaliza el signo de tax_base_amount igual que el reporte
        nativo l10n_co.fuente.report.handler: positivo si la retención
        quedó en el crédito (factura de proveedor), negativo si quedó en
        el débito (nota crédito / reverso).
        """
        return SQL(
            """
            CASE
                WHEN account_move_line.credit > 0 THEN account_move_line.tax_base_amount
                WHEN account_move_line.debit > 0 THEN account_move_line.tax_base_amount * -1
                ELSE 0
            END
            """
        )

    def _format_partner_name(self, partner):
        """'Nombre (NIT formateado)', o solo el nombre si no tiene NIT."""
        if not partner.vat:
            return partner.display_name
        vat_clean = ''.join(c for c in str(partner.vat) if c.isdigit())
        if len(vat_clean) > 1:
            id_type = partner.l10n_latam_identification_type_id.name or ''
            is_nit = 'nit' in id_type.lower()
            if is_nit:
                main_part, dv = vat_clean[:-1], vat_clean[-1]
                try:
                    formatted = '{:,}'.format(int(main_part)).replace(',', '.')
                    return '%s (NIT %s-%s)' % (partner.display_name, formatted, dv)
                except ValueError:
                    pass
        return '%s (NIT %s)' % (partner.display_name, partner.vat)

    def _get_concept_names(self, tax_ids):
        """Nombre a mostrar por impuesto: el de account.tax por defecto,
        o el de insotech.retention.concept si hay uno vinculado (más
        legible para el contador). Ver ESPEC §4 Fase 2.
        """
        if not tax_ids:
            return {}

        taxes = self.env['account.tax'].browse(tax_ids)
        names = {tax.id: tax.name for tax in taxes}

        if 'insotech.retention.concept' in self.env:
            concepts = self.env['insotech.retention.concept'].search([
                '|',
                ('purchase_tax_id', 'in', tax_ids),
                ('tax_id', 'in', tax_ids),
            ])
            for concept in concepts:
                if concept.purchase_tax_id.id in tax_ids:
                    names[concept.purchase_tax_id.id] = concept.name
                if concept.tax_id.id in tax_ids:
                    names.setdefault(concept.tax_id.id, concept.name)

        return names
