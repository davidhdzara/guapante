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
    # Display name (Odoo 18: _compute_display_name, no name_get)
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'company_id', 'company_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%d - %s' % (rec.year, rec.company_id.name or '')

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
