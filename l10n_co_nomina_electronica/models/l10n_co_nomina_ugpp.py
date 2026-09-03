# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Modelo para generación de reportes UGPP – Storm User.

La UGPP (Unidad de Gestión Pensional y Parafiscales) requiere que las
empresas presenten información periódica sobre sus aportes a seguridad
social. Este modelo genera el archivo Excel con 3 hojas que alimenta
el aplicativo Storm User:

1. **nomina-aportante**: Información general del aportante (empresa).
2. **nomina-conceptos de pago**: Mapeo de reglas salariales a conceptos
   de pago UGPP con sus cuentas contables.
3. **nomina**: Detalle consolidado por empleado de los valores de nómina
   del período, con desglose de IBC y aportes.

Referencia: Manual Storm User – UGPP.
"""

import base64
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
except ImportError:
    openpyxl = None
    _logger.warning(
        'La librería openpyxl no está instalada. No se podrán generar '
        'los reportes UGPP en formato Excel.'
    )

# ──────────────────────────────────────────────────────────────────────────
# Constantes UGPP
# ──────────────────────────────────────────────────────────────────────────
# SMMLV – valor de respaldo si no está configurado en la empresa.


# Mapeo de tipo de documento DIAN → código corto UGPP
_DOC_TYPE_UGPP_MAP = {
    '13': 'CC',
    '22': 'CE',
    '12': 'TI',
    '41': 'PA',
    '11': 'RC',
    '21': 'TE',
    '31': 'NIT',
    '42': 'DIE',
    '47': 'PEP',
    '48': 'PPT',
    '50': 'NITP',
    '91': 'NUIP',
}


class L10nCoNominaUgpp(models.Model):
    """Generador de reportes UGPP para Storm User."""

    _name = 'l10n_co_nomina.ugpp'
    _description = 'Reporte UGPP – Storm User'
    _order = 'year desc, month desc'

    # ──────────────────────────────────────────────────────────────────
    # Campos principales
    # ──────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        help='Nombre descriptivo del reporte UGPP.',
    )
    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.today().year,
        help='Año del período a reportar.',
    )
    month = fields.Selection(
        selection=[
            ('1', 'Enero'),
            ('2', 'Febrero'),
            ('3', 'Marzo'),
            ('4', 'Abril'),
            ('5', 'Mayo'),
            ('6', 'Junio'),
            ('7', 'Julio'),
            ('8', 'Agosto'),
            ('9', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        help='Mes del período a reportar.',
    )
    date_from = fields.Date(
        string='Fecha Inicio',
        required=True,
        help='Fecha de inicio del período de reporte.',
    )
    date_to = fields.Date(
        string='Fecha Fin',
        required=True,
        help='Fecha de fin del período de reporte.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        help='Empresa para la que se genera el reporte UGPP.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('generated', 'Generado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        help='Estado del reporte. Cambia a "Generado" cuando se crea '
             'el archivo Excel exitosamente.',
    )
    excel_file = fields.Binary(
        string='Archivo Excel',
        readonly=True,
        help='Archivo Excel generado con las 3 hojas del reporte UGPP.',
    )
    excel_filename = fields.Char(
        string='Nombre Archivo Excel',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # SQL Constraints
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_period_company',
            'UNIQUE(year, month, company_id)',
            'Ya existe un reporte UGPP para este período y empresa.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Campos computados
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'month', 'company_id')
    def _compute_name(self):
        """Genera nombre descriptivo: 'UGPP - Empresa - Mes Año'."""
        month_names = dict(self._fields['month'].selection)
        for record in self:
            company_name = record.company_id.name or ''
            month_name = month_names.get(record.month, '')
            record.name = 'UGPP - %s - %s %s' % (
                company_name, month_name, record.year or ''
            )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Valida que la fecha inicio sea anterior a la fecha fin."""
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from > record.date_to:
                    raise UserError(_(
                        'La fecha de inicio debe ser anterior o igual a '
                        'la fecha de fin.'
                    ))

    # ══════════════════════════════════════════════════════════════════
    # ACCIÓN PRINCIPAL: Generar reporte Excel
    # ══════════════════════════════════════════════════════════════════

    def action_generate_report(self):
        """
        Genera el archivo Excel UGPP con 3 hojas para Storm User.

        Flujo:
        1. Busca las nóminas confirmadas del período.
        2. Genera la hoja 'nomina-aportante' con datos de la empresa.
        3. Genera la hoja 'nomina-conceptos de pago' con el mapeo de
           reglas salariales a conceptos UGPP.
        4. Genera la hoja 'nomina' con el detalle consolidado por
           empleado.
        5. Guarda el archivo Excel en el campo binario.
        """
        self.ensure_one()

        if not openpyxl:
            raise UserError(_(
                'La librería openpyxl no está instalada. Ejecute: '
                'pip install openpyxl'
            ))

        # Buscar nóminas del período
        payslips = self.env['hr.payslip'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done'),
        ])

        if not payslips:
            raise UserError(_(
                'No se encontraron nóminas confirmadas para el período '
                '%s - %s en la empresa %s.',
                self.date_from, self.date_to, self.company_id.name,
            ))

        # Crear workbook
        wb = openpyxl.Workbook()

        # Estilos
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(
            start_color='4472C4', end_color='4472C4', fill_type='solid'
        )
        header_alignment = Alignment(
            horizontal='center', vertical='center', wrap_text=True
        )
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )

        # ── Hoja 1: nomina-aportante ─────────────────────────────────
        ws_aportante = wb.active
        ws_aportante.title = 'nomina-aportante'
        self._generate_sheet_aportante(
            ws_aportante, header_font, header_fill,
            header_alignment, thin_border,
        )

        # ── Hoja 2: nomina-conceptos de pago ─────────────────────────
        ws_conceptos = wb.create_sheet('nomina-conceptos de pago')
        self._generate_sheet_conceptos(
            ws_conceptos, header_font, header_fill,
            header_alignment, thin_border,
        )

        # ── Hoja 3: nomina ───────────────────────────────────────────
        ws_nomina = wb.create_sheet('nomina')
        self._generate_sheet_nomina(
            ws_nomina, payslips, header_font, header_fill,
            header_alignment, thin_border,
        )

        # Guardar en memoria
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Almacenar archivo
        month_names = dict(self._fields['month'].selection)
        filename = 'UGPP_%s_%s_%s.xlsx' % (
            (self.company_id.vat or 'NIT').replace('-', ''),
            month_names.get(self.month, self.month),
            self.year,
        )

        self.write({
            'excel_file': base64.b64encode(output.read()),
            'excel_filename': filename,
            'state': 'generated',
        })

        _logger.info(
            'Reporte UGPP generado: %s (%d nóminas procesadas)',
            filename, len(payslips),
        )

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/excel_file/%s?download=true' % (
                self._name.replace('.', '_'), self.id, filename,
            ),
            'target': 'new',
        }

    # ══════════════════════════════════════════════════════════════════
    # GENERACIÓN DE HOJAS INDIVIDUALES
    # ══════════════════════════════════════════════════════════════════

    def _generate_sheet_aportante(
        self, ws, header_font, header_fill, header_alignment, thin_border
    ):
        """
        Genera la hoja 'nomina-aportante' con información de la empresa.

        Columnas:
        - Tipo Documento, Número Documento, Razón Social
        - Naturaleza Jurídica, Tipo Aportante
        - Dirección, Municipio, Departamento, Teléfono, Correo
        - Autorretención Especial
        """
        headers = [
            'Tipo Documento',
            'Número Documento',
            'DV',
            'Razón Social',
            'Naturaleza Jurídica',
            'Tipo Aportante',
            'Dirección',
            'Municipio',
            'Departamento',
            'Teléfono',
            'Correo Electrónico',
            'Autorretención Especial',
            'Período Año',
            'Período Mes',
        ]

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        company = self.company_id

        # Mapeo de naturaleza jurídica
        nature_map = {
            'publica': 'Pública',
            'privada': 'Privada',
            'mixta': 'Mixta',
            'otra': 'Otra',
        }
        contrib_map = {
            'empleador': 'Empleador',
            'independiente': 'Independiente',
            'cooperativa': 'Cooperativa de Trabajo Asociado',
        }

        row_data = [
            'NIT',  # Tipo Documento
            (company.vat or '').replace('-', ''),
            '',  # DV - se puede computar
            company.name or '',
            nature_map.get(company.l10n_co_ugpp_legal_nature, ''),
            contrib_map.get(company.l10n_co_ugpp_contributor_type, ''),
            company.street or '',
            company.city or '',
            company.state_id.name if company.state_id else '',
            company.phone or '',
            company.email or '',
            'Sí' if company.l10n_co_ugpp_special_autoretention else 'No',
            self.year,
            dict(self._fields['month'].selection).get(self.month, ''),
        ]

        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=2, column=col_num, value=value)
            cell.border = thin_border

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 40)
            )

    def _get_ugpp_salary_rules(self):
        """Retorna las reglas salariales con tipo de pago UGPP, ordenadas."""
        return self.env['hr.salary.rule'].search([
            ('l10n_co_ugpp_payment_type', '!=', False),
        ], order='sequence, code')

    def _generate_sheet_conceptos(
        self, ws, header_font, header_fill, header_alignment, thin_border
    ):
        """
        Genera la hoja 'nomina-conceptos de pago' según UGPP V-20.1.

        Columnas:
        1. Concepto (auto-numerado)
        2. Nombre concepto
        3. Cuenta contable
        4. Tipo pago
        5. Clasificación TP NO SALARIAL
        """
        headers = [
            'Concepto',
            'Nombre concepto',
            'Cuenta contable',
            'Tipo pago',
            'Clasificación TP NO SALARIAL',
        ]

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Buscar reglas salariales con tipo de pago UGPP configurado
        salary_rules = self._get_ugpp_salary_rules()

        payment_type_map = dict(
            self.env['hr.salary.rule']._fields[
                'l10n_co_ugpp_payment_type'
            ].selection
        )
        non_salary_map = dict(
            self.env['hr.salary.rule']._fields[
                'l10n_co_ugpp_non_salary_class'
            ].selection
        )

        for idx, rule in enumerate(salary_rules, 1):
            tp_label = payment_type_map.get(
                rule.l10n_co_ugpp_payment_type, ''
            )
            ns_label = (
                non_salary_map.get(rule.l10n_co_ugpp_non_salary_class, '')
                if rule.l10n_co_ugpp_payment_type == 'tp_no_salarial'
                else ''
            )
            row_data = [
                idx,                                  # Concepto (auto-numbered)
                rule.name or '',                      # Nombre concepto
                rule.l10n_co_ugpp_accounts or '',     # Cuenta contable
                tp_label,                             # Tipo pago
                ns_label,                             # Clasificación TP NO SALARIAL
            ]
            row_num = idx + 1
            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.border = thin_border

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 50)
            )

    # ──────────────────────────────────────────────────────────────────
    # IBC Calculation
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_ibc(total_salarial, total_no_salarial, contract, smmlv,
                      factor_integral_salary=0.70):
        """Calcula el IBC según normativa colombiana.

        - Art. 132 CST: Salario integral → IBC = factor_integral_salary
          del salario (Parámetros Anuales, 70% por defecto).
        - Art. 127/128 CST + Art. 30 Ley 1393/2010: pagos no salariales
          se excluyen hasta el 40% de la remuneración total.
        - Decreto 780/2016: piso 1 SMMLV, techo 25 SMMLV.
        """
        if contract and contract.l10n_co_ne_integral_salary:
            ibc = contract.wage * factor_integral_salary
        else:
            total_remuneracion = total_salarial + total_no_salarial
            limite_no_salarial = total_remuneracion * 0.40
            exceso_no_salarial = max(0, total_no_salarial - limite_no_salarial)
            ibc = total_salarial + exceso_no_salarial

        ibc = max(ibc, smmlv)       # Piso: 1 SMMLV
        ibc = min(ibc, smmlv * 25)  # Techo: 25 SMMLV
        return ibc

    # ──────────────────────────────────────────────────────────────────
    # Hoja 3: nomina – UGPP Storm User V-20.1
    # ──────────────────────────────────────────────────────────────────

    def _generate_sheet_nomina(
        self, ws, payslips, header_font, header_fill,
        header_alignment, thin_border
    ):
        """
        Genera la hoja 'nomina' según la guía UGPP Storm User V-20.1.

        Estructura de columnas:
        - 33 columnas fijas (datos del cotizante, novedades, días, fechas)
        - N columnas dinámicas (una por regla salarial con tipo UGPP)
        - 4 columnas IBC (Salud, Pensión, ARL, CCF)
        """
        # ── Columnas fijas ───────────────────────────────────────────
        fixed_headers = [
            'Tipo cotizante',                           # 1
            'Subtipo cotizante',                        # 2
            'Condición especial empresa',               # 3
            'Extranjero no obligado pensión',           # 4
            'Colombiano en el exterior',                # 5
            'Actividad alto riesgo pensión',            # 6
            'Tipo documento cotizante',                 # 7
            'Número documento cotizante',               # 8
            'Nombre cotizante',                         # 9
            'Cargo del trabajador',                     # 10
            'Año',                                      # 11
            'Mes',                                      # 12
            'Salario integral',                         # 13
            'Novedad incapacidad',                      # 14
            'Novedad licencia mat o pat',               # 15
            'Novedad permiso o licencia remunerada',    # 16
            'Novedad de suspensión',                    # 17
            'Novedad vacaciones',                       # 18
            'Número días trabajados',                   # 19
            'Número días incapacidades',                # 20
            'Número días licencia mat o pat',           # 21
            'Número días permiso o lic remuneradas',    # 22
            'Número días suspensión/lic no remunerada', # 23
            'Número días vacaciones',                   # 24
            'Número días huelga',                       # 25
            'Total días reportados',                    # 26
            'Ingreso',                                  # 27
            'Fecha ingreso',                            # 28
            'Retiro',                                   # 29
            'Fecha retiro',                             # 30
            'Fecha inicio vacaciones',                  # 31
            'Fecha terminación vacaciones',             # 32
            'Observaciones aportante',                  # 33
        ]

        # ── Columnas dinámicas (conceptos de pago) ───────────────────
        ugpp_rules = self._get_ugpp_salary_rules()
        concept_headers = [rule.name or rule.code or '' for rule in ugpp_rules]

        # ── Columnas IBC ─────────────────────────────────────────────
        ibc_headers = ['IBC Salud', 'IBC Pensión', 'IBC ARL', 'IBC CCF']

        all_headers = fixed_headers + concept_headers + ibc_headers

        for col_num, header in enumerate(all_headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # ── Preparar mapeos ──────────────────────────────────────────
        from ..services import dian_utils

        params = self.company_id._get_co_payroll_params(self.date_from)
        smmlv = params.smmlv
        period_start = self.date_from
        period_end = self.date_to

        # ── Iterar nóminas ───────────────────────────────────────────
        row_num = 2
        for payslip in payslips.sorted(
            key=lambda p: (p.employee_id.name, p.number or '')
        ):
            employee = payslip.employee_id
            contract = payslip.contract_id

            # -- Totales por tipo de pago UGPP -------------------------
            total_salarial = 0.0
            total_no_salarial = 0.0

            # Acumular monto por regla salarial (rule.id → total)
            rule_totals = {}
            for line in payslip.line_ids:
                rule = line.salary_rule_id
                ugpp_type = rule.l10n_co_ugpp_payment_type
                if ugpp_type:
                    rule_totals[rule.id] = (
                        rule_totals.get(rule.id, 0.0) + line.total
                    )
                    if ugpp_type == 'tp_salarial':
                        total_salarial += line.total
                    elif ugpp_type == 'tp_no_salarial':
                        total_no_salarial += line.total
                    elif ugpp_type in (
                        'tp_compensacion_ord', 'tp_compensacion_ext',
                    ):
                        # Compensaciones son salariales para IBC
                        total_salarial += line.total

            # -- Días por tipo UGPP ------------------------------------
            # Simplificación: se toma quantity de las líneas de nómina
            # cuya regla tiene el tipo UGPP correspondiente.
            days_by_type = {}
            for line in payslip.line_ids:
                ugpp_type = line.salary_rule_id.l10n_co_ugpp_payment_type
                if ugpp_type and line.quantity:
                    days_by_type[ugpp_type] = (
                        days_by_type.get(ugpp_type, 0.0) + line.quantity
                    )

            dias_incapacidad = int(days_by_type.get('tp_incapacidad', 0))
            dias_licencia_mat = int(days_by_type.get('tp_licencia_mat_pat', 0))
            dias_lic_remunerada = int(
                days_by_type.get('tp_licencia_remunerada', 0)
            )
            dias_vacaciones = int(
                days_by_type.get('tp_vacaciones', 0)
                + days_by_type.get('tp_vacaciones_terminacion', 0)
                + days_by_type.get('tp_descanso_anual', 0)
            )

            # Días trabajados (WORK100)
            dias_trabajados = int(sum(
                wd.number_of_days
                for wd in payslip.worked_days_line_ids
                if wd.work_entry_type_id.code == 'WORK100'
            ) or 30)

            dias_suspension = 0
            dias_huelga = 0

            total_dias = min(
                dias_trabajados + dias_incapacidad + dias_licencia_mat
                + dias_lic_remunerada + dias_suspension + dias_vacaciones
                + dias_huelga,
                30,
            )

            # -- Novedades (X / vacío) ---------------------------------
            nov_incapacidad = 'X' if dias_incapacidad > 0 else ''
            nov_lic_mat = 'X' if dias_licencia_mat > 0 else ''
            nov_lic_rem = 'X' if dias_lic_remunerada > 0 else ''
            nov_suspension = 'X' if dias_suspension > 0 else ''
            nov_vacaciones = 'X' if dias_vacaciones > 0 else ''

            # -- Nombre: APELLIDO1 APELLIDO2 NOMBRE1 NOMBRE2 -----------
            name_parts = dian_utils.split_name(employee.name)
            nombre_cotizante = ' '.join(filter(None, [
                name_parts.get('primer_apellido', ''),
                name_parts.get('segundo_apellido', ''),
                name_parts.get('primer_nombre', ''),
                name_parts.get('otros_nombres', ''),
            ]))

            # -- Tipo documento → código corto UGPP --------------------
            tipo_doc_ugpp = _DOC_TYPE_UGPP_MAP.get(
                employee.l10n_co_ne_document_type or '', ''
            )

            # -- Ingreso / Retiro en el período ------------------------
            es_ingreso = False
            fecha_ingreso = ''
            if contract and contract.date_start:
                if period_start <= contract.date_start <= period_end:
                    es_ingreso = True
                    fecha_ingreso = contract.date_start.strftime('%d/%m/%Y')

            es_retiro = False
            fecha_retiro = ''
            if contract and contract.date_end:
                if period_start <= contract.date_end <= period_end:
                    es_retiro = True
                    fecha_retiro = contract.date_end.strftime('%d/%m/%Y')

            # -- Vacaciones: fechas (simplificado) ---------------------
            fecha_ini_vac = ''
            fecha_fin_vac = ''
            # Futuro: extraer de hr.leave si se requiere detalle.

            # -- Cargo del trabajador ----------------------------------
            cargo = (
                employee.job_title
                or (employee.job_id.name if employee.job_id else '')
                or ''
            )

            # -- Salario integral --------------------------------------
            integral = (
                'X'
                if contract and contract.l10n_co_ne_integral_salary
                else ''
            )

            # ═════════════════════════════════════════════════════════
            # Construir fila de datos fijos (33 columnas)
            # ═════════════════════════════════════════════════════════
            fixed_data = [
                employee.l10n_co_ne_worker_type or '',              # 1
                employee.l10n_co_ne_worker_subtype or '',           # 2
                '',                                                 # 3  Condición especial empresa
                'X' if employee.l10n_co_ne_foreigner_no_pension else '',  # 4
                'X' if employee.l10n_co_ne_colombian_abroad else '',      # 5
                'X' if employee.l10n_co_ne_high_risk_pension else '',     # 6
                tipo_doc_ugpp,                                      # 7
                employee.identification_id or '',                   # 8
                nombre_cotizante,                                   # 9
                cargo,                                              # 10
                self.year,                                          # 11
                int(self.month),                                    # 12
                integral,                                           # 13
                nov_incapacidad,                                    # 14
                nov_lic_mat,                                        # 15
                nov_lic_rem,                                        # 16
                nov_suspension,                                     # 17
                nov_vacaciones,                                     # 18
                dias_trabajados,                                    # 19
                dias_incapacidad,                                   # 20
                dias_licencia_mat,                                  # 21
                dias_lic_remunerada,                                # 22
                dias_suspension,                                    # 23
                dias_vacaciones,                                    # 24
                dias_huelga,                                        # 25
                total_dias,                                         # 26
                'X' if es_ingreso else '',                          # 27
                fecha_ingreso,                                      # 28
                'X' if es_retiro else '',                           # 29
                fecha_retiro,                                       # 30
                fecha_ini_vac,                                      # 31
                fecha_fin_vac,                                      # 32
                '',                                                 # 33 Observaciones
            ]

            # ═════════════════════════════════════════════════════════
            # Columnas dinámicas: monto por regla salarial UGPP
            # ═════════════════════════════════════════════════════════
            concept_data = [
                rule_totals.get(rule.id, 0.0) for rule in ugpp_rules
            ]

            # ═════════════════════════════════════════════════════════
            # Columnas IBC
            # ═════════════════════════════════════════════════════════
            ibc = self._compute_ibc(
                total_salarial, total_no_salarial, contract, smmlv,
                factor_integral_salary=params.factor_integral_salary,
            )
            ibc_data = [ibc, ibc, ibc, ibc]

            # ═════════════════════════════════════════════════════════
            # Escribir fila completa
            # ═════════════════════════════════════════════════════════
            row_data = fixed_data + concept_data + ibc_data

            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.border = thin_border
                if isinstance(value, float):
                    cell.number_format = '#,##0.00'

            row_num += 1

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 40)
            )

        _logger.info(
            'Hoja "nomina" generada con %d filas (%d columnas: '
            '%d fijas + %d conceptos + 4 IBC)',
            row_num - 2,
            len(all_headers),
            len(fixed_headers),
            len(concept_headers),
        )
