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

from odoo import api, fields, models

_TOPE_CIVIL_CODE = 'L10N_CO_EMBARGO_CIVIL'


class HrSalaryAttachment(models.Model):
    """Extensión colombiana de Asignaciones Salariales (embargos)."""

    _inherit = 'hr.salary.attachment'

    l10n_co_embargo_porcentaje = fields.Float(
        string='Porcentaje (%)',
        help='Porcentaje del salario neto a embargar. Si se deja en 0, se '
             'usa "Monto Mensual" como valor fijo. El monto real de cada '
             'nómina se recalcula dinámicamente (regla CO_EMBARGO) '
             'respetando los topes legales -- "Monto Mensual" aquí es solo '
             'un estimado para la vista de lista y el cálculo de fecha '
             'estimada de cierre, no el valor autoritativo.',
    )
    l10n_co_embargo_juzgado = fields.Char(string='Juzgado / Entidad')

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
                                         factor_embargo_civil=0.20,
                                         pct_tope_embargo_alimentos=50.0):
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
