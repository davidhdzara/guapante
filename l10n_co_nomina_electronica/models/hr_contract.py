# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.contract para Nómina Electrónica DIAN.

Agrega los campos requeridos por el nodo ``<Trabajador>`` del XML de nómina
electrónica que dependen del contrato laboral: tipo de contrato y si el
salario es integral.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, sección 6.2.8, atributos TipoContrato y SalarioIntegral.
"""

from odoo import fields, models


class HrContract(models.Model):
    """Campos del contrato laboral para Nómina Electrónica DIAN."""

    _inherit = 'hr.contract'

    # ──────────────────────────────────────────────────────────────────
    # Tipo de Contrato (codificación DIAN)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_contract_type = fields.Selection(
        selection=[
            ('1', 'Término Fijo'),
            ('2', 'Término Indefinido'),
            ('3', 'Obra o Labor'),
            ('4', 'Aprendizaje'),
            ('5', 'Prácticas o Pasantía'),
        ],
        string='Tipo de Contrato DIAN',
        default='2',
        help='Tipo de contrato laboral según la codificación del anexo '
             'técnico de nómina electrónica de la DIAN.\n'
             '• 1 - Término Fijo: con fecha de terminación definida.\n'
             '• 2 - Término Indefinido: sin fecha de terminación.\n'
             '• 3 - Obra o Labor: duración atada a una obra específica.\n'
             '• 4 - Aprendizaje: contrato de aprendizaje SENA.\n'
             '• 5 - Prácticas o Pasantía: vinculación por práctica académica.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Salario Integral
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_integral_salary = fields.Boolean(
        string='Salario Integral',
        default=False,
        help='Indica si el trabajador devenga salario integral '
             '(Art. 132 CST). El salario integral incluye el factor '
             'prestacional y no genera derecho a auxilio de transporte, '
             'cesantías, intereses a las cesantías ni prima de servicios.\n'
             'Se refleja en el atributo SalarioIntegral del nodo '
             '<Trabajador> del XML.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Periodo de Nómina
    # ──────────────────────────────────────────────────────────────────
    l10n_co_payroll_period = fields.Selection(
        selection=[
            ('7', 'Semanal (7 días)'),
            ('10', 'Decenal (10 días)'),
            ('14', 'Catorcenal (14 días)'),
            ('15', 'Quincenal (15 días)'),
            ('30', 'Mensual (30 días)'),
        ],
        string='Periodo de Nómina',
        default='30',
        help='Periodo de pago de nómina. Afecta el cálculo del básico y '
             'auxilio de transporte. Las horas extra, incapacidades, '
             'licencias y vacaciones siempre se calculan sobre base mensual.',
    )

    # ──────────────────────────────────────────────────────────────────
    # PILA — Datos de Cotización
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pila_tipo_cotizante = fields.Selection(
        selection=[
            ('01', '01 - Dependiente'),
            ('02', '02 - Servicio Doméstico'),
            ('03', '03 - Independiente'),
            ('04', '04 - Madre Comunitaria'),
            ('12', '12 - Aprendiz del SENA en etapa lectiva'),
            ('19', '19 - Aprendiz del SENA en etapa productiva'),
            ('21', '21 - Estudiante (Ley 789/2002)'),
            ('22', '22 - Profesor de establecimiento particular'),
            ('30', '30 - Dependiente entidades o universidades públicas'),
            ('31', '31 - Cooperado o precooperativa'),
            ('51', '51 - Trabajador de tiempo parcial'),
        ],
        string='Tipo Cotizante',
        default='01',
        help='Tipo de cotizante según tabla PILA.',
    )
    l10n_co_pila_subtipo_cotizante = fields.Selection(
        selection=[
            ('00', '00 - No aplica'),
            ('01', '01 - Dependiente pensionado por vejez activo'),
            ('02', '02 - Independiente pensionado por vejez activo'),
        ],
        string='Subtipo Cotizante',
        default='00',
    )
    l10n_co_pila_salario_variable = fields.Boolean(
        string='Salario Variable',
        default=False,
        help='Marcar si el trabajador tiene salario variable.',
    )
    l10n_co_pila_clase_riesgo = fields.Selection(
        selection=[
            ('1', 'I - Riesgo Mínimo'),
            ('2', 'II - Riesgo Bajo'),
            ('3', 'III - Riesgo Medio'),
            ('4', 'IV - Riesgo Alto'),
            ('5', 'V - Riesgo Máximo'),
        ],
        string='Clase de Riesgo ARL',
        default='1',
    )
    l10n_co_pila_centro_trabajo = fields.Char(
        string='Centro de Trabajo',
        help='Código del centro de trabajo para ARL.',
    )
    l10n_co_pila_actividad_economica = fields.Char(
        string='Actividad Económica ARL',
        help='Código CIIU de la actividad económica para ARL.',
    )
    l10n_co_pila_indicador_alto_riesgo = fields.Boolean(
        string='Alto Riesgo Pensional',
        default=False,
        help='Indica si el empleado aplica para pensión de alto riesgo.',
    )
    l10n_co_pila_tarifa_especial_afp = fields.Char(
        string='Tarifa Especial AFP',
        help='Tarifa especial de AFP si aplica.',
    )
