# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Asistente para generar Liquidación Definitiva de Contrato.

Doc 20 (correcciones_normativas_2026/20_diseno_migracion_liquidacion.md):
migrado del modelo standalone `l10n.co.hr.liquidacion` a `hr.payslip` con
`struct_id=hr_payroll_structure_co_liquidacion`, siguiendo el patrón
Bélgica descrito en doc 14 §3 -- la estructura ya implementa los 10
conceptos legales completos como reglas salariales, el wizard solo
recolecta los datos que no tienen equivalente en `hr.contract` y crea el
payslip en borrador (no se llama `compute_sheet()` aquí: el usuario lo
calcula desde el propio payslip, igual que hacía "Calcular" en el modelo
viejo).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Tipos de contrato DIAN (hr.contract.l10n_co_ne_contract_type) para los
# que el Art. 64 CST calcula la indemnización con base en los días reales
# restantes del contrato (CO_LIQ_INDEMNIZACION, condition_python lee
# inputs.get('CO_LIQ_INDEMNIZ')) -- '1' fijo, '3' obra/labor.
_CONTRACT_TYPES_REQUIRE_DIAS_RESTANTES = ('1', '3')


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
        help='Motivo de la terminación del contrato. Determina si procede '
             'indemnización (Art. 64 CST): solo "Despido sin Justa Causa" '
             'la activa.',
    )
    requires_dias_restantes = fields.Boolean(
        compute='_compute_requires_dias_restantes',
        help='Técnico: controla la visibilidad de "Días Restantes de '
             'Contrato" -- true si el contrato es a término fijo u '
             'obra/labor (Art. 64 CST).',
    )
    dias_restantes_contrato = fields.Integer(
        string='Días Restantes de Contrato',
        help='Días que faltaban para cumplir el plazo pactado del '
             'contrato (fijo) o para terminar la obra/labor, al momento '
             'del retiro. Solo aplica a contrato a término fijo u '
             'obra/labor -- base del cálculo de indemnización del Art. 64 '
             'CST (salario_diario × días_restantes). Se ingresa manualmente '
             'porque Odoo no calcula por sí solo cuánto faltaba del plazo '
             'pactado.',
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

    @api.depends('contract_id', 'contract_id.l10n_co_ne_contract_type')
    def _compute_requires_dias_restantes(self):
        for wizard in self:
            wizard.requires_dias_restantes = (
                wizard.contract_id.l10n_co_ne_contract_type
                in _CONTRACT_TYPES_REQUIRE_DIAS_RESTANTES
            )

    def _prepare_input_line_ids(self):
        """Construye input_line_ids para el payslip de liquidación.

        Solo CO_LIQ_INDEMNIZ tiene equivalente aquí -- vacaciones
        pendientes (doc 20 §4.3) quedó deliberadamente fuera de alcance,
        ninguna regla ni input la consume, se resuelve a mano si el caso
        puntual se presenta.
        """
        self.ensure_one()
        lines = []
        if (
            self.cause == 'sin_justa_causa'
            and self.requires_dias_restantes
            and self.dias_restantes_contrato
        ):
            input_type = self.env.ref(
                'l10n_co_nomina_electronica.input_co_liq_indemniz')
            lines.append((0, 0, {
                'input_type_id': input_type.id,
                'amount': self.dias_restantes_contrato,
            }))
        return lines

    def action_create_liquidacion(self):
        """Crea el payslip de liquidación y abre su formulario.

        Deja el payslip en borrador -- el usuario lo calcula desde el
        propio formulario (botón nativo "Calcular"), igual que el modelo
        viejo requería el paso explícito "Calcular" después de crear el
        registro.
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
        struct = self.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')

        payslip = self.env['hr.payslip'].create({
            'name': _('Liquidación - %s', self.employee_id.name),
            'employee_id': self.employee_id.id,
            'contract_id': contract.id,
            'struct_id': struct.id,
            'date_from': contract.date_start,
            'date_to': self.date_end,
            'l10n_co_ne_liquidacion_cause': self.cause,
            'input_line_ids': self._prepare_input_line_ids(),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'res_id': payslip.id,
            'view_mode': 'form',
            'target': 'current',
        }
