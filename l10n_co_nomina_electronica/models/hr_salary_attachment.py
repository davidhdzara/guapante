# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Extensión de hr.salary.attachment para embargos judiciales colombianos.

Reemplaza el modelo custom l10n.co.hr.embargo (ver doc 12 sección 7 y
correcciones_normativas_2026/16_diseno_embargo_hibrido_salary_attachment.md).
hr.salary.attachment (Enterprise, hr_payroll) ya resuelve ciclo de vida
(open/close/cancel), auditoría (mail.thread), multi-empleado y la
generación automática de hr.payslip.input por período -- lo único que no
provee es el cálculo con topes legales colombianos (Art. 155/156 CST) ni
la prioridad/piso jurisprudencial entre tipos de embargo concurrentes, que
sigue viviendo en la regla salarial CO_EMBARGO
(data/hr_payroll_structure_data.xml), no en este modelo.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_TOPE_CIVIL_CODE = 'L10N_CO_EMBARGO_CIVIL'
L10N_CO_LIBRANZA_CODE = 'L10N_CO_LIBRANZA'
L10N_CO_EMBARGO_CODES = (
    'L10N_CO_EMBARGO_ALIMENTOS', 'L10N_CO_EMBARGO_COOPERATIVA', 'L10N_CO_EMBARGO_CIVIL')


class HrSalaryAttachment(models.Model):
    """Extensión colombiana de Asignaciones Salariales (embargos)."""

    _inherit = 'hr.salary.attachment'

    l10n_co_company_country_code = fields.Char(
        related='company_id.country_id.code', string='País de la compañía',
        help='Solo para ocultar en la vista lo colombiano fuera de Colombia.')

    l10n_co_embargo_porcentaje = fields.Float(
        string='Porcentaje (%)',
        help='Porcentaje del salario neto a embargar. Si se deja en 0, se '
             'usa "Monto Mensual" como valor fijo. El monto real de cada '
             'nómina se recalcula dinámicamente (regla CO_EMBARGO) '
             'respetando los topes legales -- "Monto Mensual" aquí es solo '
             'un estimado para la vista de lista y el cálculo de fecha '
             'estimada de cierre, no el valor autoritativo.',
    )
    l10n_co_partner_id = fields.Many2one(
        'res.partner', string='Juzgado / Entidad', tracking=True,
        help='Contacto al que se le paga lo descontado: el juzgado o '
             'beneficiario del embargo, o la entidad de la libranza.',
    )
    l10n_co_embargo_juzgado = fields.Char(
        string='Juzgado / Entidad (texto legado)',
        help='Texto libre anterior al contacto. Solo se conserva para los '
             'registros que no pudieron enlazarse a un contacto; complete '
             '"Juzgado / Entidad" y deje este vacío.',
    )
    l10n_co_saldo_pendiente = fields.Monetary(
        string='Saldo Pendiente (no descontado)', readonly=True, copy=False,
        tracking=True,
        help='Libranza: valor que no se pudo descontar por el tope del 50% '
             'del neto de ley (Ley 1527/2012). No se pierde: se recupera en '
             'las nóminas siguientes, primero lo atrasado y luego la cuota '
             'del período, siempre respetando el tope.',
    )
    l10n_co_autoriza_liquidacion = fields.Boolean(
        string='Autoriza Descuento en Liquidación', tracking=True,
        help='El trabajador autorizó por escrito descontar el saldo de esta '
             'libranza de la liquidación final (Art. 149 CST; SL3208-2022). '
             'Exige adjuntar el documento. Sin autorización no se descuenta.',
    )
    l10n_co_alcanza_prestaciones = fields.Boolean(
        string='La Orden Alcanza Prestaciones', tracking=True,
        help='Embargo de alimentos o cooperativa: la orden judicial se '
             'extiende a las prestaciones sociales (Art. 344 CST, hasta el '
             '50%). Sin marcar, la liquidación no embarga prestaciones.',
    )
    l10n_co_alcanza_indemnizacion = fields.Boolean(
        string='La Orden Alcanza Indemnización', tracking=True,
        help='La orden judicial se extiende a la indemnización por despido. '
             'Sin marcar, la liquidación no embarga la indemnización.',
    )
    l10n_co_es_libranza = fields.Boolean(compute='_compute_l10n_co_tipo')
    l10n_co_es_embargo = fields.Boolean(compute='_compute_l10n_co_tipo')

    @api.depends('other_input_type_id.code')
    def _compute_l10n_co_tipo(self):
        for rec in self:
            code = rec.other_input_type_id.code
            rec.l10n_co_es_libranza = code == L10N_CO_LIBRANZA_CODE
            rec.l10n_co_es_embargo = code in L10N_CO_EMBARGO_CODES

    @api.constrains('employee_ids', 'other_input_type_id')
    def _check_l10n_co_libranza_un_empleado(self):
        for rec in self:
            if rec.other_input_type_id.code == L10N_CO_LIBRANZA_CODE \
                    and len(rec.employee_ids) > 1:
                raise ValidationError(_(
                    'La libranza "%s" debe tener un solo empleado: el saldo '
                    'pendiente y lo pagado se llevan por empleado.',
                    rec.display_name))

    @api.onchange('l10n_co_embargo_porcentaje')
    def _onchange_l10n_co_embargo_porcentaje(self):
        """Sugiere un monto mensual estimado al capturar un % de embargo.

        Editable después -- no es un compute+store, para no romper la
        edición manual nativa de `monthly_amount`. Solo una sugerencia
        inicial; la regla salarial CO_EMBARGO nunca confía en este valor
        para el descuento real, siempre recalcula con el salario neto del
        período.
        """
        if self.l10n_co_embargo_porcentaje and len(self.employee_ids) == 1:
            wage = self.employee_ids.contract_id.wage
            if wage:
                self.monthly_amount = wage * self.l10n_co_embargo_porcentaje / 100

    def _l10n_co_compute_embargo_amount(self, salario_neto, smmlv, fecha_nomina,
                                         factor_embargo_civil,
                                         pct_tope_embargo_alimentos):
        """Calcula el valor del embargo respetando topes legales.

        Reemplaza l10n.co.hr.embargo.compute_embargo_amount -- misma firma
        y misma lógica, solo cambia de dónde lee tipo/porcentaje/valor fijo
        (other_input_type_id.code / l10n_co_embargo_porcentaje /
        monthly_amount en vez de tipo_embargo / porcentaje / valor_fijo).

        Args:
            salario_neto: float - Salario neto del empleado (devengados - deducciones SS).
            smmlv: float - Salario minimo mensual legal vigente.
            fecha_nomina: date - Fecha del periodo de nómina (payslip.date_from)
                contra la que se valida la vigencia del embargo
                (date_start/date_end), independientemente de `state`.
            factor_embargo_civil: float - Fracción embargable del excedente
                sobre el SMMLV para embargos civiles (Art. 155 CST). Viene
                de hr.rule.parameter (l10n_co_factor_embargo_civil).
            pct_tope_embargo_alimentos: float - Porcentaje máximo del
                salario neto embargable por alimentos/cooperativa (Art. 156
                CST). Viene de hr.rule.parameter
                (l10n_co_pct_tope_embargo_alimentos).

        Returns:
            float - Valor a descontar, respetando topes legales.
        """
        self.ensure_one()
        if self.state != 'open':
            return 0.0
        if self.date_start and fecha_nomina < self.date_start:
            return 0.0
        if self.date_end and fecha_nomina > self.date_end:
            return 0.0

        code = self.other_input_type_id.code
        porcentaje = self.l10n_co_embargo_porcentaje
        valor_fijo = self.monthly_amount if not porcentaje else 0.0

        if code == _TOPE_CIVIL_CODE:
            # Art. 155 CST: máximo factor_embargo_civil del excedente sobre el SMMLV
            excedente = max(0, salario_neto - smmlv)
            tope = excedente * factor_embargo_civil
        else:
            # Alimentos/Cooperativa (Art. 156 CST): hasta pct_tope_embargo_alimentos%
            # del salario neto.
            tope = salario_neto * (pct_tope_embargo_alimentos / 100)

        if valor_fijo > 0:
            return min(valor_fijo, tope)
        elif porcentaje > 0:
            return min(salario_neto * (porcentaje / 100), tope)
        return 0.0

    @api.constrains('l10n_co_autoriza_liquidacion', 'attachment')
    def _check_l10n_co_autorizacion_documento(self):
        for rec in self:
            if rec.l10n_co_autoriza_liquidacion and not rec.attachment:
                raise ValidationError(_(
                    'La asignación "%s" autoriza el descuento en la '
                    'liquidación: adjunte el documento de autorización.',
                    rec.display_name))
