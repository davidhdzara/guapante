# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.salary.rule para Nómina Electrónica DIAN y reportes UGPP.

Agrega el campo de mapeo ``l10n_co_ne_dian_concept`` que vincula cada regla
salarial con el concepto XML correspondiente del nodo ``<Devengados>`` o
``<Deducciones>`` del documento de nómina electrónica. Este mapeo es la pieza
clave que permite al sistema construir automáticamente el XML de nómina
a partir de las líneas de la nómina calculada.

También incluye campos para la clasificación UGPP del concepto, necesarios
para generar los reportes de Storm User.

Referencia: Anexo Técnico V1.0, secciones 6.2.12 (Devengados) y 6.2.13
(Deducciones).
"""

from odoo import api, fields, models

# ──────────────────────────────────────────────────────────────────────────
# Constantes: conceptos de deducción según el XML DIAN
# ──────────────────────────────────────────────────────────────────────────
DEDUCTION_CONCEPTS = {
    'Salud', 'FondoPension', 'FondoSP', 'Sindicato', 'Sancion',
    'Libranza', 'PagoTerceroDed', 'AnticipoDed', 'PensionVoluntaria',
    'RetencionFuente', 'AFC', 'Cooperativa', 'EmbargoFiscal',
    'PlanComplementarios', 'Educacion', 'Deuda', 'OtraDeduccion',
    'ReintegroDed',
}


class HrSalaryRule(models.Model):
    """Mapeo de reglas salariales a conceptos DIAN y clasificación UGPP."""

    _inherit = 'hr.salary.rule'

    # ──────────────────────────────────────────────────────────────────
    # Concepto DIAN para el XML de nómina electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_dian_concept = fields.Selection(
        selection=[
            # ── Devengados ──────────────────────────────────────────
            ('Sueldo', 'Sueldo Básico'),
            ('Transporte', 'Auxilio de Transporte'),
            ('ViaticoS', 'Viáticos Salariales'),
            ('ViaticoNS', 'Viáticos No Salariales'),
            ('HED', 'Hora Extra Diurna (HED)'),
            ('HEN', 'Hora Extra Nocturna (HEN)'),
            ('HRN', 'Hora Recargo Nocturno (HRN)'),
            ('HEDDF', 'Hora Extra Diurna Dom/Fest (HEDDF)'),
            ('HRDDF', 'Hora Recargo Diurno Dom/Fest (HRDDF)'),
            ('HENDF', 'Hora Extra Nocturna Dom/Fest (HENDF)'),
            ('HRNDF', 'Hora Recargo Nocturno Dom/Fest (HRNDF)'),
            ('VacacionesComunes', 'Vacaciones Comunes'),
            ('VacacionesCompensadas', 'Vacaciones Compensadas'),
            ('Primas', 'Prima de Servicios'),
            ('Cesantias', 'Cesantías'),
            ('InteresesCesantias', 'Intereses a las Cesantías'),
            ('Incapacidad', 'Incapacidad'),
            ('LicenciaMP', 'Licencia de Maternidad/Paternidad'),
            ('LicenciaR', 'Licencia Remunerada'),
            ('LicenciaNR', 'Licencia No Remunerada'),
            ('BonificacionS', 'Bonificación Salarial'),
            ('BonificacionNS', 'Bonificación No Salarial'),
            ('AuxilioS', 'Auxilio Salarial'),
            ('AuxilioNS', 'Auxilio No Salarial'),
            ('HuelgaLegal', 'Huelga Legal'),
            ('OtroConceptoS', 'Otro Concepto Salarial'),
            ('OtroConceptoNS', 'Otro Concepto No Salarial'),
            ('CompensacionO', 'Compensación Ordinaria'),
            ('CompensacionE', 'Compensación Extraordinaria'),
            ('BonoEPCTVS', 'Bono EPCTV Salarial'),
            ('BonoEPCTVNS', 'Bono EPCTV No Salarial'),
            ('BonoAlimS', 'Bono Alimentación Salarial'),
            ('BonoAlimNS', 'Bono Alimentación No Salarial'),
            ('Comision', 'Comisión'),
            ('PagoTercero', 'Pago a Terceros (Devengado)'),
            ('Anticipo', 'Anticipo (Devengado)'),
            ('Dotacion', 'Dotación'),
            ('ApoyoSost', 'Apoyo de Sostenimiento'),
            ('Teletrabajo', 'Teletrabajo'),
            ('BonifRetiro', 'Bonificación por Retiro'),
            ('Indemnizacion', 'Indemnización'),
            ('Reintegro', 'Reintegro (Devengado)'),
            # ── Deducciones ─────────────────────────────────────────
            ('Salud', 'Aporte Salud (Deducción)'),
            ('FondoPension', 'Aporte Fondo de Pensión (Deducción)'),
            ('FondoSP', 'Fondo de Solidaridad Pensional (Deducción)'),
            ('Sindicato', 'Sindicato (Deducción)'),
            ('Sancion', 'Sanción (Deducción)'),
            ('Libranza', 'Libranza (Deducción)'),
            ('PagoTerceroDed', 'Pago a Terceros (Deducción)'),
            ('AnticipoDed', 'Anticipo (Deducción)'),
            ('OtraDeduccion', 'Otra Deducción'),
            ('PensionVoluntaria', 'Pensión Voluntaria (Deducción)'),
            ('RetencionFuente', 'Retención en la Fuente'),
            ('AFC', 'AFC – Ahorro Fomento Construcción'),
            ('Cooperativa', 'Cooperativa (Deducción)'),
            ('EmbargoFiscal', 'Embargo Fiscal'),
            ('PlanComplementarios', 'Planes Complementarios de Salud'),
            ('Educacion', 'Educación (Deducción)'),
            ('ReintegroDed', 'Reintegro (Deducción)'),
            ('Deuda', 'Deuda (Deducción)'),
        ],
        string='Concepto DIAN Nómina',
        help='Concepto del anexo técnico de nómina electrónica al que '
             'se mapea esta regla salarial. Determina en qué nodo del '
             'XML (<Devengados> o <Deducciones>) se incluirá el valor '
             'calculado por esta regla.\n\n'
             'Si no se selecciona un concepto, la regla no se incluirá '
             'en el XML de nómina electrónica.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campo computado: ¿Es deducción?
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_is_deduction = fields.Boolean(
        string='Es Deducción DIAN',
        compute='_compute_is_deduction',
        store=True,
        help='Indica si el concepto DIAN corresponde a una deducción. '
             'Se calcula automáticamente a partir del concepto seleccionado.',
    )

    @api.depends('l10n_co_ne_dian_concept')
    def _compute_is_deduction(self):
        """Determina si el concepto DIAN es una deducción basándose en la lista oficial."""
        for rule in self:
            rule.l10n_co_ne_is_deduction = (
                rule.l10n_co_ne_dian_concept in DEDUCTION_CONCEPTS
                if rule.l10n_co_ne_dian_concept
                else False
            )

    # ──────────────────────────────────────────────────────────────────
    # Campos UGPP – Clasificación para Storm User
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ugpp_payment_type = fields.Selection(
        selection=[
            ('tp_salarial', 'TP Salarial'),
            ('tp_no_salarial', 'TP NO Salarial'),
            ('tp_compensacion_ord', 'TP Compensación ordinaria'),
            ('tp_compensacion_ext', 'TP Compensación extraordinaria'),
            ('tp_no_compensacion', 'TP No compensación'),
            ('tp_estudiantes', 'TP A Estudiantes o aprendices'),
            ('tp_incapacidad', 'TP Incapacidad'),
            ('tp_licencia_mat_pat', 'TP Licencia mat o pat'),
            ('tp_licencia_remunerada', 'TP Licencia remunerada'),
            ('tp_vacaciones', 'TP Vacaciones'),
            ('tp_vacaciones_terminacion', 'TP Vacaciones terminación de contrato'),
            ('tp_descanso_anual', 'TP Descanso anual'),
            ('tp_prestaciones', 'TP Prestaciones'),
        ],
        string='Tipo Pago UGPP',
        help='Clasificación del tipo de pago según la guía UGPP Storm User V-20.1. '
             'Los 13 tipos oficiales de la UGPP.',
    )
    l10n_co_ugpp_non_salary_class = fields.Selection(
        selection=[
            ('mera_liberalidad', 'Mera liberalidad'),
            ('pacto_colectivo', 'Pacto colectivo'),
            ('contrato', 'Contrato'),
            ('otrosi', 'Otrosí'),
        ],
        string='Clasificación TP NO SALARIAL',
        help='Subclasificación obligatoria cuando Tipo Pago = TP NO Salarial. '
             'Según guía UGPP Storm User V-20.1.',
    )
    l10n_co_ugpp_accounts = fields.Char(
        string='Cuentas UGPP (separadas por ;)',
        help='Cuentas contables asociadas al concepto para el reporte '
             'UGPP, separadas por punto y coma (;). Ejemplo: '
             '"510506;510527;520506".',
    )
