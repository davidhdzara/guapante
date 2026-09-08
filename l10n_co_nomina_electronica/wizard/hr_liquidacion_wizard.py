# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Asistente para generar Liquidación Definitiva de Contrato.

Presenta un formulario simplificado al usuario para seleccionar el
empleado, la fecha de retiro y la causa de terminación, y crea
automáticamente el registro de liquidación con los datos precargados
del contrato vigente.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nCoHrLiquidacionWizard(models.TransientModel):
    """Asistente para crear una liquidación definitiva de contrato."""

    _name = 'l10n.co.hr.liquidacion.wizard'
    _description = 'Asistente Liquidación de Contrato - Colombia'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Empleado',
        required=True,
        help='Seleccione el empleado cuyo contrato se va a liquidar.',
    )
    contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato',
        help='Contrato a liquidar. Si no se selecciona, se usará el '
             'contrato vigente del empleado.',
    )
    date_end = fields.Date(
        string='Fecha de Retiro',
        required=True,
        default=fields.Date.context_today,
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
        help='Motivo de la terminación del contrato.',
    )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Busca el contrato vigente del empleado seleccionado."""
        self.contract_id = False
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

    def action_create_liquidacion(self):
        """Crea el registro de liquidación y abre el formulario.

        Valida que exista un contrato seleccionado, pre-carga los campos
        del contrato y devuelve la acción para abrir la liquidación
        creada en modo formulario.
        """
        self.ensure_one()

        if not self.contract_id:
            raise UserError(_(
                'No se encontró un contrato para el empleado %s. '
                'Por favor seleccione o cree un contrato antes de '
                'generar la liquidación.',
                self.employee_id.name,
            ))

        contract = self.contract_id

        # Determinar tipo de contrato
        type_map = {
            '1': 'fijo',
            '2': 'indefinido',
            '3': 'obra',
            '4': 'aprendizaje',
            '5': 'aprendizaje',
        }
        dian_type = contract.l10n_co_ne_contract_type
        contract_type = type_map.get(dian_type, 'indefinido') if dian_type else 'indefinido'

        # Determinar auxilio de transporte
        RuleParameter = self.env['hr.rule.parameter']
        smmlv = RuleParameter._get_parameter_from_code(
            'l10n_co_smmlv', self.date_end)
        is_integral = contract.l10n_co_ne_integral_salary
        aux_transporte = 0.0
        if not is_integral and (contract.wage or 0) <= smmlv * 2:
            aux_transporte = RuleParameter._get_parameter_from_code(
                'l10n_co_aux_transporte', self.date_end)

        liquidacion = self.env['l10n.co.hr.liquidacion'].create({
            'employee_id': self.employee_id.id,
            'contract_id': contract.id,
            'date_start': contract.date_start,
            'date_end': self.date_end,
            'cause': self.cause,
            'contract_type': contract_type,
            'base_salary': contract.wage or 0.0,
            'aux_transporte': aux_transporte,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.co.hr.liquidacion',
            'res_id': liquidacion.id,
            'view_mode': 'form',
            'target': 'current',
        }
