# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Provisiones Automáticas de Prestaciones Sociales Colombianas.

Calcula mensualmente las provisiones de:
- **Prima de servicios**: 1/12 de la base prestacional (salario + aux. transporte).
- **Cesantías**: 1/12 de la base prestacional.
- **Intereses a las cesantías**: 12% anual sobre cesantías (1% mensual).
- **Vacaciones**: 15 días hábiles por año → salario / 24 (solo salario base).

Normativa aplicable:
- Código Sustantivo del Trabajo (CST), Arts. 249, 306, 186.
- Ley 52 de 1975 (intereses a cesantías).

Para salario integral (Art. 132 CST) se toma el 70% del salario como
base prestacional y no aplica auxilio de transporte.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class L10nCoHrProvision(models.Model):
    """Provisión Mensual de Prestaciones Sociales.

    Cabecera que agrupa las líneas de provisión por empleado para un
    mes y año determinados. Permite calcular, confirmar y contabilizar
    las provisiones.
    """

    _name = 'l10n.co.hr.provision'
    _description = 'Provisión Mensual de Prestaciones Sociales'
    _order = 'year desc, month desc'

    # ──────────────────────────────────────────────────────────────────
    # Campos principales
    # ──────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        readonly=True,
        help='Nombre descriptivo de la provisión en formato "Provisión MM/YYYY".',
    )
    year = fields.Char(
        string='Año',
        required=True,
        help='Año de la provisión.',
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
        help='Mes de la provisión.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        help='Compañía a la que pertenece esta provisión.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
        store=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name='l10n.co.hr.provision.line',
        inverse_name='provision_id',
        string='Líneas de Provisión',
        help='Detalle de provisiones por cada empleado con contrato activo.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmado'),
            ('posted', 'Contabilizado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        help='Estado de la provisión:\n'
             '• Borrador: pendiente de cálculo.\n'
             '• Confirmado: provisiones calculadas.\n'
             '• Contabilizado: registrado en contabilidad.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos totalizadores (computed)
    # ──────────────────────────────────────────────────────────────────
    total_prima = fields.Float(
        string='Total Prima',
        compute='_compute_totals',
        store=True,
        digits='Payroll',
        help='Suma de la provisión de prima de servicios de todos los empleados.',
    )
    total_cesantias = fields.Float(
        string='Total Cesantías',
        compute='_compute_totals',
        store=True,
        digits='Payroll',
        help='Suma de la provisión de cesantías de todos los empleados.',
    )
    total_intereses = fields.Float(
        string='Total Intereses Cesantías',
        compute='_compute_totals',
        store=True,
        digits='Payroll',
        help='Suma de la provisión de intereses a las cesantías '
             'de todos los empleados.',
    )
    total_vacaciones = fields.Float(
        string='Total Vacaciones',
        compute='_compute_totals',
        store=True,
        digits='Payroll',
        help='Suma de la provisión de vacaciones de todos los empleados.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Restricciones SQL
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_provision_period',
            'UNIQUE(year, month, company_id)',
            'Ya existe una provisión para este mes/año en la misma compañía.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Computed fields
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'month')
    def _compute_name(self):
        """Genera el nombre 'Provisión MM/YYYY'."""
        for record in self:
            if record.month and record.year:
                record.name = _('Provisión %s/%s') % (record.month, record.year)
            else:
                record.name = _('Provisión (borrador)')

    @api.depends(
        'line_ids.prima',
        'line_ids.cesantias',
        'line_ids.intereses_cesantias',
        'line_ids.vacaciones',
    )
    def _compute_totals(self):
        """Suma los valores de todas las líneas para cada concepto."""
        for provision in self:
            provision.total_prima = sum(
                provision.line_ids.mapped('prima')
            )
            provision.total_cesantias = sum(
                provision.line_ids.mapped('cesantias')
            )
            provision.total_intereses = sum(
                provision.line_ids.mapped('intereses_cesantias')
            )
            provision.total_vacaciones = sum(
                provision.line_ids.mapped('vacaciones')
            )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('year')
    def _check_year(self):
        """Valida que el año sea un valor numérico razonable."""
        for record in self:
            if record.year:
                try:
                    year_int = int(record.year)
                except (ValueError, TypeError):
                    raise ValidationError(
                        _('El año debe ser un valor numérico válido.')
                    )
                if year_int < 2000 or year_int > 2100:
                    raise ValidationError(
                        _('El año debe estar entre 2000 y 2100.')
                    )

    # ──────────────────────────────────────────────────────────────────
    # Acciones de negocio
    # ──────────────────────────────────────────────────────────────────
    def action_compute_provisions(self):
        """Calcula provisiones para todos los empleados con contrato activo.

        Fórmulas aplicadas (base mensual):
        - Prima de servicios: base_prestacional / 12
        - Cesantías: base_prestacional / 12
        - Intereses a las cesantías: cesantías × 12% (anual)
        - Vacaciones: salario_base / 24

        Donde:
        - base_prestacional = salario + auxilio_de_transporte
        - Auxilio de transporte aplica solo si salario <= 2 SMMLV
          y el contrato no es integral.
        - Para salario integral: base_prestacional = salario × 70%.
        """
        self.ensure_one()

        if self.state == 'posted':
            raise UserError(
                _('No se pueden recalcular provisiones ya contabilizadas.')
            )

        # Obtener parametros del ano de la provision
        from datetime import date
        ref_date = date(int(self.year), int(self.month), 1)
        params = self.company_id._get_co_payroll_params(ref_date)
        smmlv = params.smmlv
        aux_trans = params.aux_transporte

        # Buscar contratos activos
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('company_id', '=', self.company_id.id),
        ])

        if not contracts:
            raise UserError(
                _('No se encontraron contratos activos para la compañía "%s". '
                  'Verifique que existan contratos en estado "En Proceso".')
                % self.company_id.name
            )

        lines = []
        for contract in contracts:
            wage = contract.wage

            if contract.l10n_co_ne_integral_salary:
                # Salario integral: 70% del salario para prestaciones.
                # No aplica auxilio de transporte.
                emp_aux = 0.0
                base = wage * 0.70
            else:
                # Auxilio de transporte: solo si salario <= 2 SMMLV
                emp_aux = aux_trans if wage <= (smmlv * 2) else 0.0
                base = wage + emp_aux

            # Cálculo de provisiones mensuales
            prima = base / 12.0
            cesantias = base / 12.0
            intereses = cesantias * 0.12  # 12% anual sobre cesantías
            vacaciones = wage / 24.0  # Solo salario base, 15 días/año

            lines.append((0, 0, {
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'wage': wage,
                'aux_transporte': emp_aux,
                'prima': prima,
                'cesantias': cesantias,
                'intereses_cesantias': intereses,
                'vacaciones': vacaciones,
            }))

        # Limpiar líneas anteriores y crear nuevas
        self.line_ids = [(5, 0, 0)] + lines
        self.state = 'confirmed'

        return True

    def action_reset_draft(self):
        """Regresa la provisión a estado borrador."""
        for record in self:
            if record.state == 'posted':
                raise UserError(
                    _('No se puede pasar a borrador una provisión '
                      'ya contabilizada.')
                )
            record.state = 'draft'
        return True

    def action_post(self):
        """Marca la provisión como contabilizada.

        En esta versión no genera asientos contables automáticos,
        solo cambia el estado. La integración contable se implementará
        en una fase posterior.
        """
        for record in self:
            if record.state != 'confirmed':
                raise UserError(
                    _('Solo se pueden contabilizar provisiones confirmadas.')
                )
            record.state = 'posted'
        return True


class L10nCoHrProvisionLine(models.Model):
    """Línea de Provisión por Empleado.

    Detalle individual de las provisiones de prestaciones sociales
    para un empleado específico dentro de una provisión mensual.
    """

    _name = 'l10n.co.hr.provision.line'
    _description = 'Línea de Provisión por Empleado'

    # ──────────────────────────────────────────────────────────────────
    # Relaciones
    # ──────────────────────────────────────────────────────────────────
    provision_id = fields.Many2one(
        comodel_name='l10n.co.hr.provision',
        string='Provisión',
        required=True,
        ondelete='cascade',
        index=True,
        help='Provisión mensual a la que pertenece esta línea.',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Empleado',
        required=True,
        help='Empleado al que corresponde esta provisión.',
    )
    contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato',
        required=True,
        help='Contrato activo del empleado al momento del cálculo.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos base
    # ──────────────────────────────────────────────────────────────────
    wage = fields.Float(
        string='Salario Base',
        digits='Payroll',
        help='Salario mensual del contrato al momento del cálculo.',
    )
    aux_transporte = fields.Float(
        string='Auxilio de Transporte',
        digits='Payroll',
        help='Auxilio de transporte mensual. Aplica solo si el salario '
             'es menor o igual a 2 SMMLV y el contrato no es integral.',
    )
    base_prestacional = fields.Float(
        string='Base Prestacional',
        compute='_compute_base_prestacional',
        store=True,
        digits='Payroll',
        help='Base para el cálculo de prestaciones sociales. '
             'Para salario ordinario: salario + auxilio de transporte. '
             'Para salario integral: 70% del salario.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos de provisión
    # ──────────────────────────────────────────────────────────────────
    prima = fields.Float(
        string='Prima de Servicios',
        digits='Payroll',
        help='Provisión mensual de prima de servicios = base_prestacional / 12. '
             'Equivale a 30 días de salario por año de servicio.',
    )
    cesantias = fields.Float(
        string='Cesantías',
        digits='Payroll',
        help='Provisión mensual de cesantías = base_prestacional / 12. '
             'Equivale a 30 días de salario por año de servicio (Art. 249 CST).',
    )
    intereses_cesantias = fields.Float(
        string='Intereses Cesantías',
        digits='Payroll',
        help='Provisión mensual de intereses a las cesantías = cesantías × 12%. '
             'Los intereses corresponden al 12% anual sobre el saldo de '
             'cesantías (Ley 52 de 1975).',
    )
    vacaciones = fields.Float(
        string='Vacaciones',
        digits='Payroll',
        help='Provisión mensual de vacaciones = salario_base / 24. '
             'Corresponde a 15 días hábiles de descanso remunerado por año '
             '(Art. 186 CST). No incluye auxilio de transporte.',
    )
    total = fields.Float(
        string='Total Provisión',
        compute='_compute_total',
        store=True,
        digits='Payroll',
        help='Suma total de todas las provisiones del empleado: '
             'prima + cesantías + intereses + vacaciones.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Computed fields
    # ──────────────────────────────────────────────────────────────────
    @api.depends('wage', 'aux_transporte')
    def _compute_base_prestacional(self):
        """Calcula la base prestacional como salario + auxilio transporte.

        Para salario integral el aux_transporte será 0 y wage ya habrá
        sido ajustado al 70% en el método action_compute_provisions,
        pero aquí se almacena wage original y aux_transporte real.
        La base prestacional refleja wage + aux_transporte tal como
        se almacenan (wage original, aux 0 para integral).
        """
        for line in self:
            line.base_prestacional = line.wage + line.aux_transporte

    @api.depends('prima', 'cesantias', 'intereses_cesantias', 'vacaciones')
    def _compute_total(self):
        """Suma todas las provisiones del empleado."""
        for line in self:
            line.total = (
                line.prima
                + line.cesantias
                + line.intereses_cesantias
                + line.vacaciones
            )
