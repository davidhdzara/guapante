# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Liquidación Definitiva de Contrato de Trabajo – Colombia.

Implementa el cálculo automático de la liquidación definitiva que debe
pagarse al empleado cuando se termina su contrato laboral, de conformidad
con el Código Sustantivo del Trabajo (CST).

Conceptos liquidados:
    • Salario pendiente (días no pagados del último mes)
    • Prima de servicios proporcional (Art. 306–308 CST)
    • Cesantías proporcionales (Art. 249 CST)
    • Intereses sobre cesantías (Ley 52 de 1975, 12% anual)
    • Vacaciones proporcionales (Art. 186 CST)
    • Vacaciones pendientes (días acumulados no disfrutados)
    • Indemnización por despido sin justa causa (Art. 64 CST)
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class L10nCoHrLiquidacion(models.Model):
    """Liquidación Definitiva de Contrato – Colombia.

    Registro que consolida todos los conceptos que la ley colombiana
    exige pagar al trabajador al momento de la terminación del contrato
    laboral.  El flujo de estados es:

        borrador → calculado → aprobado → pagado
    """

    _name = 'l10n.co.hr.liquidacion'
    _description = 'Liquidación Definitiva de Contrato - Colombia'
    _order = 'date_end desc'

    # ──────────────────────────────────────────────────────────────────
    # Campos Principales
    # ──────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        help='Nombre descriptivo generado automáticamente: '
             '"Liquidación - [Nombre Empleado]".',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Empleado',
        required=True,
        help='Empleado cuyo contrato se está liquidando.',
    )
    contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato',
        required=True,
        help='Contrato laboral que se termina.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        related='contract_id.company_id',
        store=True,
        help='Compañía del contrato.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
        store=True,
        readonly=True,
    )
    date_start = fields.Date(
        string='Fecha Inicio Contrato',
        help='Fecha de inicio del contrato laboral. Se toma de '
             'contract_id.date_start si no se indica manualmente.',
    )
    date_end = fields.Date(
        string='Fecha de Retiro',
        required=True,
        help='Fecha efectiva de terminación del contrato laboral.',
    )
    cause = fields.Selection(
        selection=[
            ('justa_causa', 'Despido con Justa Causa'),
            ('sin_justa_causa', 'Despido sin Justa Causa'),
            ('renuncia', 'Renuncia Voluntaria'),
            ('mutuo_acuerdo', 'Mutuo Acuerdo'),
            ('fin_obra', 'Terminación de Obra o Labor'),
            ('muerte', 'Muerte del Trabajador'),
        ],
        string='Causa de Retiro',
        required=True,
        help='Causa de terminación del contrato laboral. Determina si '
             'procede indemnización (Art. 64 CST).',
    )
    contract_type = fields.Selection(
        selection=[
            ('fijo', 'Término Fijo'),
            ('indefinido', 'Término Indefinido'),
            ('obra', 'Obra o Labor'),
            ('aprendizaje', 'Aprendizaje'),
        ],
        string='Tipo de Contrato',
        required=True,
        default='indefinido',
        help='Tipo de contrato laboral. Afecta el cálculo de '
             'indemnización por despido sin justa causa (Art. 64 CST).',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('calculated', 'Calculado'),
            ('approved', 'Aprobado'),
            ('paid', 'Pagado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        copy=False,
        help='Estado de la liquidación:\n'
             '• Borrador: recién creada, pendiente de cálculo.\n'
             '• Calculado: se ejecutó el cálculo de todos los conceptos.\n'
             '• Aprobado: validada por el responsable de nómina.\n'
             '• Pagado: se realizó el pago al empleado.',
    )
    notes = fields.Text(
        string='Observaciones',
        help='Notas internas o comentarios sobre la liquidación.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos Calculados – Información Base
    # ──────────────────────────────────────────────────────────────────
    days_worked = fields.Integer(
        string='Días Laborados',
        compute='_compute_days_worked',
        store=True,
        help='Total de días calendario desde la fecha de inicio del '
             'contrato (o último corte) hasta la fecha de retiro.',
    )
    base_salary = fields.Float(
        string='Salario Mensual',
        digits='Account',
        help='Salario mensual base del contrato (wage).',
    )
    aux_transporte = fields.Float(
        string='Auxilio de Transporte',
        digits='Account',
        help='Auxilio de transporte mensual. Aplica si el salario '
             'no supera 2 SMMLV y no es salario integral.',
    )
    base_prestacional = fields.Float(
        string='Base Prestacional',
        compute='_compute_base_prestacional',
        store=True,
        digits='Account',
        help='Base para el cálculo de prestaciones sociales: '
             'salario mensual + auxilio de transporte.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Conceptos de Liquidación
    # ──────────────────────────────────────────────────────────────────
    salario_pendiente = fields.Float(
        string='Salario Pendiente',
        digits='Account',
        help='Días trabajados del último mes no pagados: '
             '(salario / dias_mes_comercial) × días_pendientes.',
    )
    prima_proporcional = fields.Float(
        string='Prima de Servicios Proporcional',
        digits='Account',
        help='Prima proporcional al semestre laborado: '
             'base_prestacional × días_semestre / dias_anio_comercial '
             '(Art. 306 CST). Divisor en Parámetros Anuales.',
    )
    cesantias_proporcionales = fields.Float(
        string='Cesantías Proporcionales',
        digits='Account',
        help='Cesantías proporcionales al tiempo laborado en el año: '
             'base_prestacional × días_año / dias_anio_comercial '
             '(Art. 249 CST). Divisor en Parámetros Anuales.',
    )
    intereses_cesantias = fields.Float(
        string='Intereses sobre Cesantías',
        digits='Account',
        help='Intereses anuales sobre cesantías proporcionales: '
             'cesantías × pct_intereses_cesantias × días_año / '
             'dias_anio_comercial (Ley 52/1975). % y divisor en '
             'Parámetros Anuales.',
    )
    vacaciones_proporcionales = fields.Float(
        string='Vacaciones Proporcionales',
        digits='Account',
        help='Vacaciones proporcionales: salario × días_laborados / '
             'divisor_vacaciones (Art. 186 CST: 15 días hábiles por año). '
             'Divisor en Parámetros Anuales.',
    )
    vacaciones_pendientes = fields.Float(
        string='Vacaciones Pendientes',
        digits='Account',
        help='Valor monetario de los días de vacaciones acumulados '
             'no disfrutados por el trabajador.',
    )
    indemnizacion = fields.Float(
        string='Indemnización',
        digits='Account',
        help='Indemnización por despido sin justa causa (Art. 64 CST). '
             'Solo aplica cuando la causa de retiro es "sin_justa_causa".',
    )
    total_liquidacion = fields.Float(
        string='Total Liquidación',
        compute='_compute_total_liquidacion',
        store=True,
        digits='Account',
        help='Suma de todos los conceptos de liquidación.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────
    @api.depends('employee_id', 'employee_id.name')
    def _compute_name(self):
        """Genera el nombre descriptivo de la liquidación."""
        for rec in self:
            if rec.employee_id:
                rec.name = _('Liquidación - %s', rec.employee_id.name)
            else:
                rec.name = _('Liquidación - Nuevo')

    @api.depends('date_start', 'date_end')
    def _compute_days_worked(self):
        """Calcula los días calendario laborados entre inicio y fin."""
        for rec in self:
            if rec.date_start and rec.date_end:
                delta = rec.date_end - rec.date_start
                rec.days_worked = max(delta.days, 0)
            else:
                rec.days_worked = 0

    @api.depends('base_salary', 'aux_transporte')
    def _compute_base_prestacional(self):
        """Calcula la base prestacional: salario + auxilio de transporte."""
        for rec in self:
            rec.base_prestacional = rec.base_salary + rec.aux_transporte

    @api.depends(
        'salario_pendiente',
        'prima_proporcional',
        'cesantias_proporcionales',
        'intereses_cesantias',
        'vacaciones_proporcionales',
        'vacaciones_pendientes',
        'indemnizacion',
    )
    def _compute_total_liquidacion(self):
        """Suma todos los conceptos de la liquidación."""
        for rec in self:
            rec.total_liquidacion = (
                rec.salario_pendiente
                + rec.prima_proporcional
                + rec.cesantias_proporcionales
                + rec.intereses_cesantias
                + rec.vacaciones_proporcionales
                + rec.vacaciones_pendientes
                + rec.indemnizacion
            )

    # ──────────────────────────────────────────────────────────────────
    # Onchange
    # ──────────────────────────────────────────────────────────────────
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Carga datos del contrato seleccionado."""
        if self.contract_id:
            contract = self.contract_id
            self.employee_id = contract.employee_id
            self.date_start = contract.date_start
            self.base_salary = contract.wage or 0.0
            # Determinar tipo de contrato a partir del campo DIAN
            type_map = {
                '1': 'fijo',
                '2': 'indefinido',
                '3': 'obra',
                '4': 'aprendizaje',
                '5': 'aprendizaje',
            }
            dian_type = contract.l10n_co_ne_contract_type
            if dian_type:
                self.contract_type = type_map.get(dian_type, 'indefinido')
            # Aux transporte: aplica si salario <= 2 SMMLV y no integral
            params = self.company_id._get_co_payroll_params(self.date_end or self.date_start)
            is_integral = contract.l10n_co_ne_integral_salary
            if not is_integral and (contract.wage or 0) <= params.smmlv * 2:
                self.aux_transporte = params.aux_transporte
            else:
                self.aux_transporte = 0.0

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Filtra contratos del empleado seleccionado."""
        if self.employee_id:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['open', 'close']),
            ], limit=1, order='date_start desc')
            if contract:
                self.contract_id = contract
            return {
                'domain': {
                    'contract_id': [
                        ('employee_id', '=', self.employee_id.id),
                    ],
                },
            }

    # ──────────────────────────────────────────────────────────────────
    # Constrains
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Valida que la fecha de retiro sea posterior al inicio."""
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    'La fecha de retiro (%s) no puede ser anterior '
                    'a la fecha de inicio del contrato (%s).',
                    rec.date_end, rec.date_start,
                ))

    # ──────────────────────────────────────────────────────────────────
    # Cálculo de Indemnización – Art. 64 CST
    # ──────────────────────────────────────────────────────────────────
    def _calculate_indemnizacion(self):
        """Calcula la indemnización por despido sin justa causa.

        Reglas según Art. 64 del Código Sustantivo del Trabajo:

        **Contrato a término fijo:**
            Salario correspondiente al tiempo que falte para cumplir
            el plazo estipulado, mínimo 15 días de salario.

        **Contrato a término indefinido:**
            • Salario < 10 SMMLV:
                - 30 días de salario por el primer año.
                - 20 días de salario por cada año adicional o proporción.
            • Salario ≥ 10 SMMLV:
                - 20 días de salario por el primer año.
                - 15 días de salario por cada año adicional o proporción.
        """
        for rec in self:
            if rec.cause != 'sin_justa_causa':
                rec.indemnizacion = 0.0
                continue

            salary = rec.base_salary
            params = rec.company_id._get_co_payroll_params(rec.date_end)
            smmlv = params.smmlv
            years = rec.days_worked / params.dias_anio_comercial

            dias_mes = params.dias_mes_comercial

            if rec.contract_type == 'fijo':
                # Contrato fijo: salario × días faltantes del contrato
                # Simplificación: mínimo 15 días de salario
                rec.indemnizacion = max(
                    salary / 2,
                    salary / dias_mes * 15,
                )
            elif rec.contract_type == 'indefinido':
                if salary < smmlv * 10:
                    # < 10 SMMLV: 30 días primer año + 20 días por año adicional
                    if years <= 1:
                        rec.indemnizacion = salary
                    else:
                        rec.indemnizacion = (
                            salary + (salary / dias_mes * 20 * (years - 1))
                        )
                else:
                    # ≥ 10 SMMLV: 20 días primer año + 15 días por año adicional
                    if years <= 1:
                        rec.indemnizacion = salary / dias_mes * 20
                    else:
                        rec.indemnizacion = (
                            (salary / dias_mes * 20)
                            + (salary / dias_mes * 15 * (years - 1))
                        )
            else:
                # Obra, aprendizaje u otros: sin indemnización estándar
                rec.indemnizacion = 0.0

    # ──────────────────────────────────────────────────────────────────
    # Cálculo General – Método Principal
    # ──────────────────────────────────────────────────────────────────
    def action_calculate(self):
        """Calcula todos los conceptos de la liquidación.

        Este método es invocado desde el botón "Calcular" de la vista.
        Actualiza todos los campos monetarios y transiciona el estado
        a 'calculated'.

        Fórmulas aplicadas (divisores y % desde Parámetros Anuales):
            • Salario pendiente = (salario / dias_mes) × días_pendientes_mes
            • Prima proporcional = base_prestacional × días_semestre / dias_anio
            • Cesantías proporcionales = base_prestacional × días_año / dias_anio
            • Intereses cesantías = cesantías × pct_intereses × días_año / dias_anio
            • Vacaciones proporcionales = salario × días_laborados / divisor_vacaciones
            • Indemnización: según Art. 64 CST
        """
        for rec in self:
            if not rec.date_start or not rec.date_end:
                raise UserError(_(
                    'Debe indicar la fecha de inicio del contrato y la '
                    'fecha de retiro antes de calcular la liquidación.'
                ))
            if not rec.base_salary:
                raise UserError(_(
                    'El salario mensual base no puede ser cero. '
                    'Verifique el contrato del empleado.'
                ))

            salary = rec.base_salary
            base = rec.base_prestacional
            date_start = rec.date_start
            date_end = rec.date_end
            days_worked = rec.days_worked
            params = rec.company_id._get_co_payroll_params(date_end)
            dias_mes = params.dias_mes_comercial
            dias_anio = params.dias_anio_comercial

            # ── Salario pendiente ──────────────────────────────────
            # Días del último mes que no se han pagado
            day_of_month = date_end.day
            rec.salario_pendiente = (salary / dias_mes) * day_of_month

            # ── Prima de servicios proporcional ────────────────────
            # Semestre: ene-jun o jul-dic
            if date_end.month <= 6:
                semester_start = date_end.replace(month=1, day=1)
            else:
                semester_start = date_end.replace(month=7, day=1)
            # Usar la fecha mayor: inicio contrato o inicio semestre
            effective_start = max(date_start, semester_start)
            days_semester = (date_end - effective_start).days
            days_semester = max(days_semester, 0)
            rec.prima_proporcional = base * days_semester / dias_anio

            # ── Cesantías proporcionales ───────────────────────────
            # Se liquidan desde el 1 de enero del año en curso (o inicio
            # del contrato si es posterior).
            year_start = date_end.replace(month=1, day=1)
            effective_year_start = max(date_start, year_start)
            days_year = (date_end - effective_year_start).days
            days_year = max(days_year, 0)
            rec.cesantias_proporcionales = base * days_year / dias_anio

            # ── Intereses sobre cesantías ──────────────────────────
            rec.intereses_cesantias = (
                rec.cesantias_proporcionales
                * (params.pct_intereses_cesantias / 100)
                * days_year / dias_anio
            )

            # ── Vacaciones proporcionales ──────────────────────────
            # Art. 186 CST: 15 días hábiles por año = salario / 24 / mes
            # Fórmula simplificada: salario × días_laborados / divisor_vacaciones
            rec.vacaciones_proporcionales = (
                salary * days_worked / params.divisor_vacaciones
            )

            # ── Vacaciones pendientes ──────────────────────────────
            # Se mantiene el valor ingresado manualmente si existe;
            # no se sobreescribe.

            # ── Indemnización ──────────────────────────────────────
            rec._calculate_indemnizacion()

            rec.state = 'calculated'

    # ──────────────────────────────────────────────────────────────────
    # Acciones de Flujo de Estado
    # ──────────────────────────────────────────────────────────────────
    def action_approve(self):
        """Marca la liquidación como aprobada."""
        for rec in self:
            if rec.state != 'calculated':
                raise UserError(_(
                    'Solo se pueden aprobar liquidaciones en estado '
                    '"Calculado". Estado actual: %s.',
                    dict(rec._fields['state'].selection).get(rec.state),
                ))
            rec.state = 'approved'

    def action_pay(self):
        """Marca la liquidación como pagada."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_(
                    'Solo se pueden pagar liquidaciones en estado '
                    '"Aprobado". Estado actual: %s.',
                    dict(rec._fields['state'].selection).get(rec.state),
                ))
            rec.state = 'paid'

    def action_draft(self):
        """Devuelve la liquidación a estado borrador."""
        for rec in self:
            if rec.state == 'paid':
                raise UserError(_(
                    'No se puede devolver a borrador una liquidación '
                    'que ya fue pagada.'
                ))
            rec.state = 'draft'
