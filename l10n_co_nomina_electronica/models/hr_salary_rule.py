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

    l10n_co_struct_country_code = fields.Char(
        related='struct_id.country_id.code', string='País de la estructura',
        help='Solo para ocultar en la vista lo colombiano fuera de Colombia.')

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

    # ──────────────────────────────────────────────────────────────────
    # Tercero del asiento contable (contacto al que se paga lo causado)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_tercero_origen = fields.Selection(
        selection=[
            ('employee_eps', 'EPS del empleado'),
            ('employee_afp', 'AFP del empleado'),
            ('employee_ccf', 'Caja de compensación del empleado'),
            ('company_arl', 'ARL de la compañía'),
            ('company_sena', 'SENA de la compañía'),
            ('company_icbf', 'ICBF de la compañía'),
            ('company_dian', 'DIAN (compañía)'),
            ('contract_sindicato', 'Sindicato del contrato'),
            ('contract_afc', 'Entidad AFC del contrato'),
            ('contract_pension_voluntaria', 'Fondo de pensión voluntaria del contrato'),
            ('contract_plan_complementario', 'Plan complementario del contrato'),
            ('contract_cooperativa', 'Cooperativa del contrato'),
            ('contract_educacion', 'Entidad de educación del contrato'),
            ('distribution', 'Reparto por asignación salarial (embargos, libranzas)'),
        ],
        string='Tercero del Asiento',
        help='De dónde sale el contacto (partner) de la línea del asiento '
             'contable en la cuenta por pagar de esta regla. Vacío: la línea '
             'se genera sin tercero.',
    )

    l10n_co_pila_origen_no_salarial = fields.Selection(
        selection=[
            ('naturaleza', 'Por naturaleza (nunca entra al IBC ni al 40%)'),
            ('pacto', 'Por pacto de desalarización (cuenta para el 40%)'),
        ],
        string='Origen del Pago No Salarial (IBC)',
        help='Solo para conceptos no salariales. Por naturaleza: auxilio de '
             'transporte, viáticos ocasionales, prestaciones, etc. -- nunca '
             'entran al IBC (Consejo de Estado, SU 25185 de 2021). Por pacto: '
             'alimentación, vivienda, bonificaciones habituales pactadas como '
             'no salariales -- cuentan para la regla del 40% (Ley 1393/2010 '
             'Art. 30) y su excedente suma al IBC. Los pagos por pacto exigen '
             'prueba del acuerdo (contrato u otrosí). La UGPP mira la realidad '
             'económica: un pago habitual que retribuye el servicio puede ser '
             'reincorporado al IBC aunque esté marcado como no salarial.',
    )

    _L10N_CO_ORIGEN_NO_SALARIAL_POR_CODIGO = {
        'CO_AUX_TRANS': 'naturaleza', 'CO_VIATICOS_NOSAL': 'naturaleza',
        'CO_DOTACION': 'naturaleza', 'CO_TELETRABAJO': 'naturaleza',
        'CO_INDEMNIZ': 'naturaleza', 'CO_LIQ_INDEMNIZACION': 'naturaleza',
        'CO_BONIF_RET': 'naturaleza',
        'CO_AUX_ALIM': 'pacto', 'CO_BONIF_NOSAL': 'pacto',
    }

    l10n_co_liq_tratamiento = fields.Selection(
        selection=[
            ('salario', 'Salario'),
            ('vacaciones', 'Vacaciones compensadas'),
            ('prestacion', 'Prestación social (prima, cesantías, intereses)'),
            ('indemnizacion', 'Indemnización'),
        ],
        string='Tratamiento en Liquidación',
        help='Clasifica el concepto de la liquidación para aplicar embargos y '
             'libranzas (CST arts. 154-156 y 344; Ley 1527/2012; SL3208-2022).',
    )

    _L10N_CO_LIQ_TRATAMIENTO_POR_CODIGO = {
        'CO_LIQ_SALARIOS': 'salario', 'CO_LIQ_VACACIONES': 'vacaciones',
        'CO_LIQ_PRIMA': 'prestacion', 'CO_LIQ_CESANTIAS': 'prestacion',
        'CO_LIQ_INT_CES': 'prestacion', 'CO_LIQ_INDEMNIZACION': 'indemnizacion',
        'CO_LIQ_VAC_DISFRUTADAS': 'salario', 'CO_LIQ_LIC_REM': 'salario',
    }

    # Codigo de regla (identificador interno del modulo, no un valor
    # normativo) -> origen del tercero. Solo se escribe donde el campo
    # esta vacio (no pisa lo que configure el usuario).
    _L10N_CO_TERCERO_ORIGEN_POR_CODIGO = {
        'CO_SALUD_EMP': 'employee_eps', 'CO_SALUD_CIA': 'employee_eps',
        'CO_PENSION_EMP': 'employee_afp', 'CO_PENSION_CIA': 'employee_afp',
        'CO_FSP': 'employee_afp',
        'CO_CCF_CIA': 'employee_ccf',
        'CO_ARL_CIA': 'company_arl',
        'CO_SENA_CIA': 'company_sena', 'CO_ICBF_CIA': 'company_icbf',
        'CO_RETEFUENTE': 'company_dian', 'CO_PRIMA_RETE': 'company_dian',
        'CO_LIQ_RETE': 'company_dian', 'CO_BON_RETE': 'company_dian',
        'CO_SINDICATO': 'contract_sindicato', 'CO_AFC': 'contract_afc',
        'CO_PENSION_VOL': 'contract_pension_voluntaria',
        'CO_PLAN_COMP': 'contract_plan_complementario',
        'CO_COOPERATIVA': 'contract_cooperativa',
        'CO_EDUCACION': 'contract_educacion',
        'CO_EMBARGO': 'distribution', 'CO_LIBRANZAS': 'distribution',
        'CO_LIQ_EMBARGO': 'distribution', 'CO_LIQ_LIBRANZAS': 'distribution',
        'CO_LIQ_SALUD': 'employee_eps', 'CO_LIQ_PENSION': 'employee_afp',
        'CO_LIQ_RETE': 'company_dian',
    }

    @api.model
    def _l10n_co_cargar_origen_tercero(self):
        """Asigna el origen del tercero a las reglas del modulo (todas las
        estructuras comparten codigo) que aun no lo tienen."""
        for code, origen in self._L10N_CO_TERCERO_ORIGEN_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_tercero_origen', '=', False),
            ]).write({'l10n_co_tercero_origen': origen})
        for code, origen in self._L10N_CO_ORIGEN_NO_SALARIAL_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_pila_origen_no_salarial', '=', False),
            ]).write({'l10n_co_pila_origen_no_salarial': origen})
        for code, trat in self._L10N_CO_LIQ_TRATAMIENTO_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_liq_tratamiento', '=', False),
            ]).write({'l10n_co_liq_tratamiento': trat})
        return True

    def _l10n_co_cuenta_pasivo(self):
        """Cuenta por pagar de la regla: account_credit si existe (aportes
        de empresa: gasto en debito, pasivo en credito); si no, account_debit
        (deducciones: el monto negativo hace caer el pasivo en credito)."""
        self.ensure_one()
        return self.account_credit or self.account_debit
