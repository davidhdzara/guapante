# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Retención en la Fuente — Procedimiento 2 (Art. 384 ET), doc 8 del roadmap
comercial (`especificaciones_proximos_desarrollos.md` §8).

Hallazgo de diseño (2026-09-13): los campos ``procedure``/``percentage_
procedure2`` que ya existían en ``l10n.co.retefuente.uvt`` estaban a nivel
de AÑO+COMPAÑÍA (1 solo valor compartido por todos los empleados) -- forma
equivocada para lo que exige el Art. 384 ET, que es un porcentaje fijo
POR EMPLEADO, calculado sobre el promedio de SUS propios ingresos de los
últimos 12 meses. Este módulo mueve la selección del procedimiento a
``hr.contract`` (mismo lugar que las demás deducciones/retención propias
del contrato, ver ``hr_contract_deductions.py``) y agrega
``l10n.co.retefuente.procedure2`` como histórico real por contrato+semestre
-- a diferencia del bug de UVT corregido en doc 06 (que NO debía cachear),
aquí SÍ corresponde guardar un valor "congelado": la ley fija la tarifa
para todo el semestre aunque el ingreso cambie después.

Decisiones confirmadas por David (2026-09-12/13):
- El cambio de procedimiento (``l10n_co_ne_retention_procedure``) solo se
  puede escribir en junio o diciembre -- sin modelo de "solicitud
  pendiente", el cambio aplica de inmediato dentro de la ventana (Opción 2
  de la propuesta original).
- El cálculo del % fijo semestral lo dispara un botón manual que RRHH
  presiona cada semestre -- sin cron automático (Opción 2).
"""

from odoo import fields, models, _
from odoo.exceptions import UserError

_RETENTION_PROCEDURE_CHANGE_MONTHS = (6, 12)
_STRUCT_XMLID = 'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina'
_BASE_GROSS_CODE = 'CO_RETEFUENTE_BASE_GROSS'
_BASE_IBC_CODE = 'CO_RETEFUENTE_BASE_IBC'
_MAX_MONTHS_AVERAGE = 12


def _semester_start_for_date(d):
    """Devuelve el 1 de enero o el 1 de julio del semestre que contiene ``d``."""
    return d.replace(month=1, day=1) if d.month <= 6 else d.replace(month=7, day=1)


class HrContractRetefuenteProcedure(models.Model):
    """Selección del procedimiento de retención en la fuente por contrato."""

    _inherit = 'hr.contract'

    l10n_co_ne_retention_procedure = fields.Selection(
        selection=[
            ('1', 'Procedimiento 1 — Tabla Marginal Mensual (Art. 383 ET)'),
            ('2', 'Procedimiento 2 — Porcentaje Fijo Semestral (Art. 384 ET)'),
        ],
        string='Procedimiento de Retención',
        default='1',
        help='Procedimiento de retención en la fuente que aplica a este '
             'contrato. Por ley, solo puede cambiarse en junio o diciembre '
             '(Art. 384 ET) -- el cambio aplica de inmediato al guardar '
             'dentro de esa ventana, vigente para los payslips que se '
             'calculen desde ese momento.',
    )
    l10n_co_ne_retention_procedure2_ids = fields.One2many(
        comodel_name='l10n.co.retefuente.procedure2',
        inverse_name='contract_id',
        string='Histórico Procedimiento 2',
    )

    def write(self, vals):
        if 'l10n_co_ne_retention_procedure' in vals:
            today = fields.Date.context_today(self)
            if today.month not in _RETENTION_PROCEDURE_CHANGE_MONTHS:
                for contract in self:
                    if contract.l10n_co_ne_retention_procedure != vals['l10n_co_ne_retention_procedure']:
                        raise UserError(_(
                            'El procedimiento de retención en la fuente solo '
                            'puede cambiarse en junio o diciembre (Art. 384 '
                            'ET), para que el nuevo procedimiento quede '
                            'vigente desde el semestre correspondiente. '
                            'Contrato: %(name)s',
                            name=contract.name,
                        ))
        return super().write(vals)

    def action_calculate_retention_procedure2(self):
        """Calcula y guarda el % fijo del semestre siguiente (Art. 384 ET).

        Botón manual -- RRHH lo presiona cada junio/diciembre para los
        contratos en Procedimiento 2. Promedia el ingreso bruto/IBC de los
        últimos 12 payslips confirmados (o los que haya, si hay menos) de
        Nómina General, aplica la depuración + tabla marginal Art. 383
        sobre ese promedio (vía ``compute_retefuente(force_procedure='1')``,
        sin importar el procedimiento por defecto de la configuración
        anual) y guarda el % resultante como el fijo vigente para el
        semestre que arranca.
        """
        self.ensure_one()
        if self.l10n_co_ne_retention_procedure != '2':
            raise UserError(_(
                'Este contrato no está configurado en Procedimiento 2.'
            ))
        today = fields.Date.context_today(self)
        if today.month not in _RETENTION_PROCEDURE_CHANGE_MONTHS:
            raise UserError(_(
                'El cálculo del porcentaje fijo semestral solo puede '
                'hacerse en junio o diciembre (Art. 384 ET).'
            ))

        next_semester_start = (
            today.replace(year=today.year + 1, month=1, day=1)
            if today.month == 12
            else today.replace(month=7, day=1)
        )

        struct = self.env.ref(_STRUCT_XMLID)
        payslips = self.env['hr.payslip'].search([
            ('contract_id', '=', self.id),
            ('struct_id', '=', struct.id),
            ('state', '=', 'done'),
        ], order='date_from desc', limit=_MAX_MONTHS_AVERAGE)
        if not payslips:
            raise UserError(_(
                'No hay nóminas confirmadas de Nómina General para este '
                'contrato -- no se puede calcular el promedio de ingresos '
                'que exige el Art. 384 ET.'
            ))

        gross_values = []
        ibc_values = []
        for payslip in payslips:
            base_gross_line = payslip.line_ids.filtered(lambda l: l.code == _BASE_GROSS_CODE)
            base_ibc_line = payslip.line_ids.filtered(lambda l: l.code == _BASE_IBC_CODE)
            gross_values.append(base_gross_line.total if base_gross_line else 0.0)
            ibc_values.append(base_ibc_line.total if base_ibc_line else 0.0)

        months_considered = len(payslips)
        avg_gross = sum(gross_values) / months_considered
        avg_ibc = sum(ibc_values) / months_considered

        RetefuenteUvt = self.env['l10n.co.retefuente.uvt']
        rete_cfg = RetefuenteUvt.get_uvt_for_year(next_semester_start.year, self.company_id)
        result = rete_cfg.compute_retefuente(
            self.employee_id, avg_gross, avg_ibc, avg_ibc,
            self.company_id, contract=self, force_procedure='1',
        )
        base_uvt = result['base_uvt']
        if base_uvt > 0:
            fixed_percentage = (result['retencion_uvt'] / base_uvt) * 100
        else:
            fixed_percentage = 0.0

        Procedure2 = self.env['l10n.co.retefuente.procedure2']
        existing = Procedure2.search([
            ('contract_id', '=', self.id),
            ('semester_start', '=', next_semester_start),
        ], limit=1)
        vals = {
            'contract_id': self.id,
            'semester_start': next_semester_start,
            'months_considered': months_considered,
            'average_gross': avg_gross,
            'average_ibc': avg_ibc,
            'fixed_percentage': fixed_percentage,
            'computation_date': fields.Datetime.now(),
            'computed_by': self.env.user.id,
        }
        if existing:
            existing.write(vals)
        else:
            Procedure2.create(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Procedimiento 2 calculado'),
                'message': _(
                    'Porcentaje fijo para el semestre desde %(date)s: '
                    '%(pct).4f%% (promedio de %(months)d meses).',
                    date=next_semester_start,
                    pct=fixed_percentage,
                    months=months_considered,
                ),
                'type': 'success',
                'sticky': True,
            },
        }


class L10nCoRetefuenteProcedure2(models.Model):
    """Histórico del % fijo de Procedimiento 2 por contrato y semestre.

    1 registro por (contrato, semestre) -- la ley fija esta tarifa para
    todo el semestre (Art. 384 ET), por eso se guarda "congelada" en vez
    de recalcularse en cada payslip (a diferencia del UVT, doc 06, donde
    cachear un valor corregible era el bug).
    """

    _name = 'l10n.co.retefuente.procedure2'
    _description = 'Retención en la Fuente - Procedimiento 2 - Histórico Semestral'
    _order = 'semester_start desc'

    contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        related='contract_id.employee_id',
        string='Empleado',
        store=True,
    )
    company_id = fields.Many2one(
        related='contract_id.company_id',
        string='Compañía',
        store=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )
    semester_start = fields.Date(
        string='Inicio del Semestre',
        required=True,
        help='1 de enero o 1 de julio -- semestre para el que aplica el '
             'porcentaje fijo calculado.',
    )
    months_considered = fields.Integer(
        string='Meses Considerados',
        help='Cantidad de payslips confirmados usados para el promedio '
             '(hasta 12, o menos si el empleado lleva menos tiempo).',
    )
    average_gross = fields.Monetary(
        string='Ingreso Bruto Promedio',
        currency_field='currency_id',
    )
    average_ibc = fields.Monetary(
        string='IBC Promedio',
        currency_field='currency_id',
    )
    fixed_percentage = fields.Float(
        string='Porcentaje Fijo (%)',
        digits=(5, 4),
        help='Porcentaje fijo aplicado sobre la base gravable de cada '
             'payslip durante este semestre (Art. 384 ET).',
    )
    computation_date = fields.Datetime(
        string='Fecha de Cálculo',
        readonly=True,
    )
    computed_by = fields.Many2one(
        comodel_name='res.users',
        string='Calculado por',
        readonly=True,
    )

    _sql_constraints = [
        (
            'contract_semester_uniq',
            'UNIQUE(contract_id, semester_start)',
            'Ya existe un cálculo de Procedimiento 2 para este contrato '
            'en este semestre.',
        ),
    ]
