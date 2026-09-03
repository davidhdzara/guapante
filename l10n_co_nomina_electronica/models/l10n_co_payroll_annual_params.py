# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Parametros Anuales de Nomina Colombiana.

Modelo centralizado para almacenar los valores legales que cambian cada
ano fiscal: SMMLV, Auxilio de Transporte y UVT.

Estos valores son utilizados por:
- Reglas salariales (auxilio de transporte, FSP)
- Calculo de retencion en la fuente (UVT)
- Provisiones (base prima, cesantias)
- Liquidacion de contrato

Referencia legal:
- Decreto anual de SMMLV (Gobierno Nacional, diciembre)
- Resolucion anual de UVT (DIAN)
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# Valores minimos razonables para validacion.
# El SMMLV mas bajo de Colombia fue $286,000 (2004).
# El auxilio mas bajo fue $37,500 (2004).
# La UVT mas baja fue $20,974 (2006).
_MIN_SMMLV = 200000
_MIN_AUX_TRANSPORTE = 30000
_MIN_UVT = 15000


class L10nCoPayrollAnnualParams(models.Model):
    _name = 'l10n.co.payroll.annual.params'
    _description = 'Parametros Anuales de Nomina Colombiana'
    _order = 'year desc'
    _rec_name = 'year'
    _sql_constraints = [
        ('unique_year_company',
         'unique(year, company_id)',
         'Solo puede existir un registro de parametros por ano y compania.'),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Campos
    # ──────────────────────────────────────────────────────────────────
    year = fields.Integer(
        string='Ano',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Ano fiscal al que aplican estos parametros.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
        help='Compania a la que pertenecen estos parametros.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )
    smmlv = fields.Monetary(
        string='SMMLV',
        required=True,
        currency_field='currency_id',
        help='Salario Minimo Mensual Legal Vigente para este ano. '
             'Decreto del Gobierno Nacional publicado en diciembre del ano anterior.',
    )
    aux_transporte = fields.Monetary(
        string='Auxilio de Transporte',
        required=True,
        currency_field='currency_id',
        help='Valor mensual del auxilio de transporte para este ano. '
             'Aplica a trabajadores con salario igual o inferior a 2 SMMLV.',
    )
    uvt = fields.Monetary(
        string='Valor UVT',
        required=True,
        currency_field='currency_id',
        help='Unidad de Valor Tributario vigente para este ano. '
             'Publicado por la DIAN mediante resolucion.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Seguridad Social
    # ──────────────────────────────────────────────────────────────────
    pct_salud_empleado = fields.Float(
        string='% Salud Empleado', required=True, default=4.0,
        help='Porcentaje de aporte a salud a cargo del trabajador.',
    )
    pct_salud_empleador = fields.Float(
        string='% Salud Empleador', required=True, default=8.5,
        help='Porcentaje de aporte a salud a cargo del empleador. '
             'Exonerable bajo Art. 114-1 ET.',
    )
    pct_salud_total = fields.Float(
        string='% Salud Total', compute='_compute_pct_totales', store=True,
        help='Suma de % salud empleado + empleador.',
    )
    pct_pension_empleado = fields.Float(
        string='% Pensión Empleado', required=True, default=4.0,
    )
    pct_pension_empleador = fields.Float(
        string='% Pensión Empleador', required=True, default=12.0,
    )
    pct_pension_total = fields.Float(
        string='% Pensión Total', compute='_compute_pct_totales', store=True,
        help='Suma de % pensión empleado + empleador.',
    )
    pct_arl_default = fields.Float(
        string='% ARL Clase I (default)', required=True, default=0.522,
        help='Porcentaje de ARL para riesgo Clase I. El nivel de riesgo '
             'real se ajusta por empresa/cargo cuando aplique.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Parafiscales
    # ──────────────────────────────────────────────────────────────────
    pct_ccf = fields.Float(
        string='% CCF', required=True, default=4.0,
        help='Caja de Compensación Familiar. Nunca se exonera.',
    )
    pct_sena = fields.Float(string='% SENA', required=True, default=2.0)
    pct_icbf = fields.Float(string='% ICBF', required=True, default=3.0)
    tope_exoneracion_smmlv = fields.Integer(
        string='Tope Exoneración (SMMLV)', required=True, default=10,
        help='Art. 114-1 ET: tope de salario, en múltiplos de SMMLV, '
             'hasta el cual aplica la exoneración de SENA/ICBF/Salud '
             'Empleador.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Prestaciones Sociales
    # ──────────────────────────────────────────────────────────────────
    pct_intereses_cesantias = fields.Float(
        string='% Intereses sobre Cesantías', required=True, default=12.0,
    )
    factor_integral_salary = fields.Float(
        string='Factor IBC Salario Integral', required=True, default=0.70,
        help='Fracción del salario integral que constituye el IBC para '
             'seguridad social y parafiscales.',
    )
    dias_mes_comercial = fields.Integer(
        string='Días Mes Comercial', required=True, default=30,
    )
    dias_anio_comercial = fields.Integer(
        string='Días Año Comercial', required=True, default=360,
    )
    divisor_vacaciones = fields.Integer(
        string='Divisor Vacaciones', required=True, default=720,
    )

    # ──────────────────────────────────────────────────────────────────
    # Incapacidades
    # ──────────────────────────────────────────────────────────────────
    dias_incapacidad_empleador = fields.Integer(
        string='Días Incapacidad a Cargo del Empleador', required=True,
        default=2,
    )
    pct_incapacidad_3_90 = fields.Float(
        string='% Incapacidad EPS Días 3-90', required=True, default=66.67,
    )
    pct_incapacidad_91_mas = fields.Float(
        string='% Incapacidad EPS Días 91+', required=True, default=50.0,
    )

    # ──────────────────────────────────────────────────────────────────
    # Embargos
    # ──────────────────────────────────────────────────────────────────
    pct_tope_embargo_alimentos = fields.Float(
        string='% Tope Embargo Alimentos', required=True, default=50.0,
    )
    factor_embargo_civil = fields.Float(
        string='Factor Embargo Civil', required=True, default=0.20,
        help='Fracción embargable del excedente sobre 1 SMMLV para '
             'embargos de origen civil (1/5 por defecto).',
    )

    # ──────────────────────────────────────────────────────────────────
    # Retención en la Fuente
    # ──────────────────────────────────────────────────────────────────
    pct_renta_exenta = fields.Float(
        string='% Renta Exenta', required=True, default=25.0,
    )
    max_renta_exenta_uvt = fields.Float(
        string='Máx. Renta Exenta (UVT/mes)', required=True, default=240.0,
    )
    pct_deduccion_dependientes = fields.Float(
        string='% Deducción Dependientes', required=True, default=10.0,
    )
    max_dependientes_uvt = fields.Float(
        string='Máx. Deducción Dependientes (UVT)', required=True,
        default=32.5,
    )
    max_vol_pension_pct = fields.Float(
        string='Máx. Aportes Vol. Pensión (%)', required=True, default=25.0,
    )
    max_afc_pct = fields.Float(
        string='Máx. AFC (%)', required=True, default=30.0,
    )

    # ──────────────────────────────────────────────────────────────────
    # Display name (Odoo 18: _compute_display_name, no name_get)
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'company_id', 'company_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%d - %s' % (rec.year, rec.company_id.name or '')

    @api.depends('pct_salud_empleado', 'pct_salud_empleador',
                 'pct_pension_empleado', 'pct_pension_empleador')
    def _compute_pct_totales(self):
        for rec in self:
            rec.pct_salud_total = rec.pct_salud_empleado + rec.pct_salud_empleador
            rec.pct_pension_total = rec.pct_pension_empleado + rec.pct_pension_empleador

    # ──────────────────────────────────────────────────────────────────
    # CRUD overrides: validar ANTES del INSERT para evitar errores SQL
    # ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Valida unicidad año+compania ANTES del INSERT.

        Esto evita que Odoo loguee un ERROR de SQL por duplicate key
        cuando el registro ya existe. La validacion ocurre en Python
        antes de llegar a la base de datos.
        """
        for vals in vals_list:
            year = vals.get('year', fields.Date.context_today(self).year)
            company_id = vals.get('company_id', self.env.company.id)
            existing = self.sudo().search([
                ('year', '=', year),
                ('company_id', '=', company_id),
            ], limit=1)
            if existing:
                raise ValidationError(
                    _('Ya existe un registro de parametros para el ano %(year)s '
                      'en la compania %(company)s. '
                      'Modifique el registro existente en lugar de crear uno nuevo.',
                      year=year,
                      company=existing.company_id.name)
                )
        return super().create(vals_list)

    def write(self, vals):
        """Valida unicidad si se modifica año o compania."""
        if 'year' in vals or 'company_id' in vals:
            for rec in self:
                new_year = vals.get('year', rec.year)
                new_company = vals.get('company_id', rec.company_id.id)
                existing = self.sudo().search([
                    ('year', '=', new_year),
                    ('company_id', '=', new_company),
                    ('id', '!=', rec.id),
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('Ya existe un registro de parametros para el ano %(year)s '
                          'en la compania %(company)s.',
                          year=new_year,
                          company=existing.company_id.name)
                    )
        return super().write(vals)

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(
                    _('El ano debe estar entre 2000 y 2100.')
                )

    @api.constrains('smmlv', 'aux_transporte', 'uvt')
    def _check_positive_values(self):
        """Valida que los valores monetarios sean razonables.

        No solo deben ser positivos; deben superar un minimo razonable
        para evitar datos erroneos (por ejemplo, SMMLV=$1.00).
        """
        for rec in self:
            if rec.smmlv < _MIN_SMMLV:
                raise ValidationError(
                    _('El SMMLV debe ser al menos %(min)s. '
                      'Valor ingresado: %(val)s.',
                      min='{:,.0f}'.format(_MIN_SMMLV),
                      val='{:,.0f}'.format(rec.smmlv))
                )
            if rec.aux_transporte < _MIN_AUX_TRANSPORTE:
                raise ValidationError(
                    _('El auxilio de transporte debe ser al menos %(min)s. '
                      'Valor ingresado: %(val)s.',
                      min='{:,.0f}'.format(_MIN_AUX_TRANSPORTE),
                      val='{:,.0f}'.format(rec.aux_transporte))
                )
            if rec.uvt < _MIN_UVT:
                raise ValidationError(
                    _('El valor UVT debe ser al menos %(min)s. '
                      'Valor ingresado: %(val)s.',
                      min='{:,.0f}'.format(_MIN_UVT),
                      val='{:,.0f}'.format(rec.uvt))
                )

    @api.constrains(
        'pct_salud_empleado', 'pct_salud_empleador', 'pct_pension_empleado',
        'pct_pension_empleador', 'pct_arl_default', 'pct_ccf', 'pct_sena',
        'pct_icbf', 'pct_intereses_cesantias', 'pct_incapacidad_3_90',
        'pct_incapacidad_91_mas', 'pct_tope_embargo_alimentos',
        'pct_renta_exenta', 'pct_deduccion_dependientes',
        'max_vol_pension_pct', 'max_afc_pct',
    )
    def _check_percentages_in_range(self):
        """Valida que los porcentajes esten en un rango 0-100 razonable."""
        pct_fields = [
            'pct_salud_empleado', 'pct_salud_empleador',
            'pct_pension_empleado', 'pct_pension_empleador',
            'pct_arl_default', 'pct_ccf', 'pct_sena', 'pct_icbf',
            'pct_intereses_cesantias', 'pct_incapacidad_3_90',
            'pct_incapacidad_91_mas', 'pct_tope_embargo_alimentos',
            'pct_renta_exenta', 'pct_deduccion_dependientes',
            'max_vol_pension_pct', 'max_afc_pct',
        ]
        for rec in self:
            for field_name in pct_fields:
                value = getattr(rec, field_name)
                if value < 0 or value > 100:
                    raise ValidationError(
                        _('%(field)s debe estar entre 0 y 100. '
                          'Valor ingresado: %(val)s.',
                          field=rec._fields[field_name].string,
                          val=value)
                    )

    @api.constrains('factor_integral_salary', 'factor_embargo_civil')
    def _check_factors_in_range(self):
        """Valida que los factores (fracciones 0-1) sean razonables."""
        for rec in self:
            for field_name in ('factor_integral_salary', 'factor_embargo_civil'):
                value = getattr(rec, field_name)
                if value <= 0 or value > 1:
                    raise ValidationError(
                        _('%(field)s debe estar entre 0 y 1. '
                          'Valor ingresado: %(val)s.',
                          field=rec._fields[field_name].string,
                          val=value)
                    )

    @api.constrains('dias_mes_comercial', 'dias_anio_comercial',
                     'divisor_vacaciones', 'dias_incapacidad_empleador',
                     'tope_exoneracion_smmlv')
    def _check_positive_integers(self):
        for rec in self:
            for field_name in ('dias_mes_comercial', 'dias_anio_comercial',
                                'divisor_vacaciones',
                                'dias_incapacidad_empleador',
                                'tope_exoneracion_smmlv'):
                value = getattr(rec, field_name)
                if value <= 0:
                    raise ValidationError(
                        _('%(field)s debe ser un valor positivo. '
                          'Valor ingresado: %(val)s.',
                          field=rec._fields[field_name].string,
                          val=value)
                    )
