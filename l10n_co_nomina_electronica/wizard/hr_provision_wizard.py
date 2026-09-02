# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Asistente para crear Provisiones de Prestaciones Sociales.

Permite seleccionar el año y mes, crea el registro de provisión y
redirige al formulario para ejecutar el cálculo.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nCoHrProvisionWizard(models.TransientModel):
    """Asistente para generar provisiones mensuales de prestaciones sociales.

    Este wizard simplifica la creación de provisiones permitiendo
    seleccionar el período (año/mes) y generando automáticamente
    el registro de provisión con el cálculo de las líneas.
    """

    _name = 'l10n.co.hr.provision.wizard'
    _description = 'Asistente para Crear Provisión de Prestaciones'

    year = fields.Char(
        string='Año',
        required=True,
        default=lambda self: str(fields.Date.context_today(self).year),
        help='Año para el cual se calculará la provisión.',
    )
    month = fields.Selection(
        selection=[
            ('01', 'Enero'),
            ('02', 'Febrero'),
            ('03', 'Marzo'),
            ('04', 'Abril'),
            ('05', 'Mayo'),
            ('06', 'Junio'),
            ('07', 'Julio'),
            ('08', 'Agosto'),
            ('09', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        default=lambda self: '%02d' % fields.Date.context_today(self).month,
        help='Mes para el cual se calculará la provisión.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        help='Compañía para la cual se generará la provisión.',
    )

    def action_create_provision(self):
        """Crea la provisión mensual y ejecuta el cálculo automáticamente.

        Returns:
            dict: Acción de ventana apuntando al formulario de la provisión
            creada con las líneas ya calculadas.

        Raises:
            UserError: Si ya existe una provisión para el período seleccionado.
        """
        self.ensure_one()

        if not self.year or not self.month:
            raise UserError(
                _('Debe seleccionar el año y el mes para generar la provisión.')
            )

        # Verificar si ya existe provisión para el período
        existing = self.env['l10n.co.hr.provision'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if existing:
            raise UserError(
                _('Ya existe una provisión para %s/%s en la compañía "%s". '
                  'Puede editarla directamente desde la lista de provisiones.')
                % (self.month, self.year, self.company_id.name)
            )

        # Crear la provisión
        provision = self.env['l10n.co.hr.provision'].create({
            'year': self.year,
            'month': self.month,
            'company_id': self.company_id.id,
        })

        # Ejecutar cálculo automático
        provision.action_compute_provisions()

        # Abrir el formulario de la provisión creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.co.hr.provision',
            'res_id': provision.id,
            'view_mode': 'form',
            'target': 'current',
        }
