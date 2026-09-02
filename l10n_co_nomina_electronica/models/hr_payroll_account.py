# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Configuración de cuentas contables para nómina colombiana.

Modelo que permite mapear cada regla salarial (hr.salary.rule) a las cuentas
contables de débito y crédito correspondientes. Esta configuración es la base
para la generación automática de asientos contables al confirmar una nómina.

Cada empresa puede tener su propia configuración de cuentas contables para
cada regla salarial, garantizando flexibilidad en empresas multicompañía.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class L10nCoPayrollAccountConfig(models.Model):
    """Configuración de mapeo entre reglas salariales y cuentas contables."""

    _name = 'l10n.co.payroll.account.config'
    _description = 'Configuracion Contable de Nomina Colombia'
    _order = 'salary_rule_id, company_id'

    # ──────────────────────────────────────────────────────────────────
    # Campos principales
    # ──────────────────────────────────────────────────────────────────
    salary_rule_id = fields.Many2one(
        comodel_name='hr.salary.rule',
        string='Regla Salarial',
        required=True,
        ondelete='cascade',
        help='Regla salarial a la que se asignan las cuentas contables. '
             'Al confirmar una nomina, las lineas con esta regla generaran '
             'asientos contables usando las cuentas aqui configuradas.',
    )
    debit_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Debito',
        required=True,
        help='Cuenta contable para el movimiento de debito del asiento '
             'generado por esta regla salarial.',
    )
    credit_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Credito',
        required=True,
        help='Cuenta contable para el movimiento de credito del asiento '
             'generado por esta regla salarial.',
    )
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Cuenta Analitica',
        help='Cuenta analitica opcional para distribucion de costos. '
             'Si se configura, se asignara a las lineas del asiento contable.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
        help='Empresa a la que pertenece esta configuracion contable.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Nombre visible
    # ──────────────────────────────────────────────────────────────────
    @api.depends('salary_rule_id', 'debit_account_id', 'credit_account_id')
    def _compute_display_name(self):
        """Nombre visible: Regla -> Debito / Credito."""
        for rec in self:
            rule_name = rec.salary_rule_id.name or _('Sin regla')
            debit_code = rec.debit_account_id.code or '?'
            credit_code = rec.credit_account_id.code or '?'
            rec.display_name = '%s [D: %s / C: %s]' % (
                rule_name, debit_code, credit_code,
            )

    # ──────────────────────────────────────────────────────────────────
    # Restricciones SQL
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'salary_rule_company_unique',
            'UNIQUE(salary_rule_id, company_id)',
            'Ya existe una configuracion contable para esta regla salarial '
            'en esta compania. Solo se permite una configuracion por regla '
            'y compania.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Validaciones Python (ANTES del INSERT - lección aprendida)
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('salary_rule_id', 'company_id')
    def _check_unique_rule_company(self):
        """Valida unicidad de regla+compañía antes del commit SQL."""
        for rec in self:
            domain = [
                ('salary_rule_id', '=', rec.salary_rule_id.id),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    'Ya existe una configuracion contable para la regla '
                    '"%s" en la compania "%s". No se permiten duplicados.',
                    rec.salary_rule_id.name,
                    rec.company_id.name,
                ))

    @api.constrains('debit_account_id', 'credit_account_id')
    def _check_different_accounts(self):
        """Valida que las cuentas de débito y crédito sean diferentes."""
        for rec in self:
            if rec.debit_account_id == rec.credit_account_id:
                raise ValidationError(_(
                    'La cuenta de debito y la de credito deben ser '
                    'diferentes para la regla "%s".',
                    rec.salary_rule_id.name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        """Valida duplicados antes del INSERT en la base de datos."""
        for vals in vals_list:
            salary_rule_id = vals.get('salary_rule_id')
            company_id = vals.get('company_id') or self.env.company.id
            if salary_rule_id:
                existing = self.search_count([
                    ('salary_rule_id', '=', salary_rule_id),
                    ('company_id', '=', company_id),
                ])
                if existing:
                    rule = self.env['hr.salary.rule'].browse(salary_rule_id)
                    company = self.env['res.company'].browse(company_id)
                    raise ValidationError(_(
                        'Ya existe una configuracion contable para la regla '
                        '"%s" en la compania "%s". No se permiten duplicados.',
                        rule.name,
                        company.name,
                    ))
        return super().create(vals_list)

    def write(self, vals):
        """Valida duplicados antes del UPDATE si cambian regla o compañía."""
        if 'salary_rule_id' in vals or 'company_id' in vals:
            for rec in self:
                new_rule = vals.get('salary_rule_id', rec.salary_rule_id.id)
                new_company = vals.get('company_id', rec.company_id.id)
                domain = [
                    ('salary_rule_id', '=', new_rule),
                    ('company_id', '=', new_company),
                    ('id', '!=', rec.id),
                ]
                if self.search_count(domain):
                    rule = self.env['hr.salary.rule'].browse(new_rule)
                    company = self.env['res.company'].browse(new_company)
                    raise ValidationError(_(
                        'Ya existe una configuracion contable para la regla '
                        '"%s" en la compania "%s". No se permiten duplicados.',
                        rule.name,
                        company.name,
                    ))
        return super().write(vals)

    # ──────────────────────────────────────────────────────────────────
    # Métodos de negocio
    # ──────────────────────────────────────────────────────────────────
    @api.model
    def get_accounts_for_rule(self, rule_id, company_id):
        """Obtiene las cuentas contables configuradas para una regla salarial.

        Args:
            rule_id (int): ID de la regla salarial (hr.salary.rule).
            company_id (int): ID de la compañía (res.company).

        Returns:
            dict: Diccionario con las claves 'debit_account_id',
                  'credit_account_id' y 'analytic_account_id'.
                  Retorna dict vacío si no existe configuración.
        """
        config = self.search([
            ('salary_rule_id', '=', rule_id),
            ('company_id', '=', company_id),
        ], limit=1)
        if not config:
            return {}
        return {
            'debit_account_id': config.debit_account_id.id,
            'credit_account_id': config.credit_account_id.id,
            'analytic_account_id': config.analytic_account_id.id if config.analytic_account_id else False,
        }
