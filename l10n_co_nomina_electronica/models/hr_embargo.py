# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Gestion de embargos judiciales con topes legales (Art. 155 CST)."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nCoHrEmbargo(models.Model):
    """Registro de embargos judiciales vinculados a un empleado.

    Aplica automaticamente los topes legales del Art. 155 CST
    y Art. 594 CPC al calcular el descuento en nomina.
    """

    _name = 'l10n.co.hr.embargo'
    _description = 'Embargo Judicial'
    _order = 'employee_id, date_start desc'

    employee_id = fields.Many2one(
        'hr.employee', string='Empleado',
        required=True, ondelete='cascade',
    )
    name = fields.Char(
        string='Referencia del Proceso',
        required=True,
        help='Numero del proceso judicial o referencia del embargo.',
    )
    tipo_embargo = fields.Selection([
        ('civil', 'Civil / Comercial'),
        ('alimentos', 'Alimentos (Pension alimentaria)'),
        ('cooperativa', 'Cooperativa / Fondo'),
    ], string='Tipo de Embargo', required=True, default='civil')
    valor_fijo = fields.Float(
        string='Valor Fijo Mensual',
        help='Valor fijo mensual a descontar. Si es 0, se usa el porcentaje.',
    )
    porcentaje = fields.Float(
        string='Porcentaje',
        help='Porcentaje del salario a descontar (ej: 20 para 20%%).',
    )
    date_start = fields.Date(
        string='Fecha Inicio', required=True,
    )
    date_end = fields.Date(
        string='Fecha Fin',
        help='Dejar vacio si el embargo no tiene fecha de terminacion.',
    )
    state = fields.Selection([
        ('active', 'Activo'),
        ('suspended', 'Suspendido'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='active')
    juzgado = fields.Char(string='Juzgado / Entidad')
    notes = fields.Text(string='Observaciones')
    company_id = fields.Many2one(
        'res.company', string='Compania',
        default=lambda self: self.env.company,
    )

    def compute_embargo_amount(self, salario_neto, smmlv, fecha_nomina,
                                factor_embargo_civil=0.20,
                                pct_tope_embargo_alimentos=50.0):
        """Calcula el valor del embargo respetando topes legales.

        Args:
            salario_neto: float - Salario neto del empleado (devengados - deducciones SS).
            smmlv: float - Salario minimo mensual legal vigente.
            fecha_nomina: date - Fecha del periodo de nómina (payslip.date_from)
                contra la que se valida la vigencia del embargo
                (date_start/date_end), independientemente de `state`.
            factor_embargo_civil: float - Fraccion embargable del excedente
                sobre el SMMLV para embargos civiles (Art. 155 CST). Viene
                de Parámetros Anuales (`factor_embargo_civil`, 1/5 = 0.20
                por defecto).
            pct_tope_embargo_alimentos: float - Porcentaje máximo del
                salario neto embargable por alimentos/cooperativa. Viene de
                Parámetros Anuales (`pct_tope_embargo_alimentos`, 50.0 por
                defecto).

        Returns:
            float - Valor a descontar, respetando topes legales.
        """
        self.ensure_one()
        if self.state != 'active':
            return 0.0
        if self.date_start and fecha_nomina < self.date_start:
            return 0.0
        if self.date_end and fecha_nomina > self.date_end:
            return 0.0

        if self.tipo_embargo == 'civil':
            # Art. 155 CST: maximo factor_embargo_civil del excedente sobre el SMMLV
            excedente = max(0, salario_neto - smmlv)
            tope = excedente * factor_embargo_civil
            if self.valor_fijo > 0:
                return min(self.valor_fijo, tope)
            elif self.porcentaje > 0:
                return min(salario_neto * (self.porcentaje / 100), tope)
            return 0.0

        elif self.tipo_embargo == 'alimentos':
            # Pension alimentaria: hasta pct_tope_embargo_alimentos% del salario total
            tope = salario_neto * (pct_tope_embargo_alimentos / 100)
            if self.valor_fijo > 0:
                return min(self.valor_fijo, tope)
            elif self.porcentaje > 0:
                return min(salario_neto * (self.porcentaje / 100), tope)
            return 0.0

        elif self.tipo_embargo == 'cooperativa':
            # Cooperativa: mismo tope que alimentos
            tope = salario_neto * (pct_tope_embargo_alimentos / 100)
            if self.valor_fijo > 0:
                return min(self.valor_fijo, tope)
            elif self.porcentaje > 0:
                return min(salario_neto * (self.porcentaje / 100), tope)
            return 0.0

        return 0.0
