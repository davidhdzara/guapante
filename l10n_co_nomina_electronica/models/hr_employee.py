# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.employee para Nómina Electrónica DIAN.

Agrega los campos requeridos por el nodo ``<Trabajador>`` del XML de nómina
electrónica: tipo/subtipo de trabajador, tipo de documento según codificación
DIAN, lugar de trabajo (municipio DANE), indicadores de alto riesgo y
extranjería, así como información bancaria para el nodo ``<Pago>``.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, secciones 6.2.8 (Trabajador) y 6.2.9 (Pago).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    """Campos del trabajador para Nómina Electrónica DIAN."""

    _inherit = 'hr.employee'

    # ──────────────────────────────────────────────────────────────────
    # Tipo de documento de identidad (codificación DIAN)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_document_type = fields.Selection(
        selection=[
            ('11', 'Registro Civil'),
            ('12', 'Tarjeta de Identidad'),
            ('13', 'Cédula de Ciudadanía'),
            ('21', 'Tarjeta de Extranjería'),
            ('22', 'Cédula de Extranjería'),
            ('31', 'NIT'),
            ('41', 'Pasaporte'),
            ('42', 'Documento de Identificación Extranjero'),
            ('47', 'PEP – Permiso Especial de Permanencia'),
            ('48', 'PPT – Permiso de Protección Temporal'),
            ('50', 'NIT de otro país'),
            ('91', 'NUIP'),
        ],
        string='Tipo Documento DIAN',
        help='Tipo de documento de identidad del trabajador según la '
             'codificación oficial de la DIAN para nómina electrónica.\n'
             'Este valor se usa en el atributo TipoDocumento del nodo '
             '<Trabajador> del XML.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Tipo y Subtipo de Trabajador
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_worker_type = fields.Selection(
        selection=[
            ('01', '01 - Trabajador Dependiente'),
            ('02', '02 - Servicio Doméstico'),
            ('04', '04 - Madre Comunitaria'),
            ('12', '12 - Aprendiz del SENA en Etapa Lectiva'),
            ('19', '19 - Aprendiz del SENA en Etapa Productiva'),
            ('22', '22 - Profesor de Establecimiento Particular'),
            ('23', '23 - Estudiante de Práctica o Pasantía'),
            ('30', '30 - Dependiente de Entidad No Obligada a Cotizar SENA e ICBF'),
            ('31', '31 - Cooperado o Precooperativa de Trabajo Asociado'),
            ('51', '51 - Trabajador de Tiempo Parcial'),
        ],
        string='Tipo Trabajador',
        default='01',
        help='Tipo de trabajador según el anexo técnico de nómina '
             'electrónica de la DIAN. Determina las reglas de cotización '
             'a seguridad social.',
    )
    l10n_co_ne_worker_subtype = fields.Selection(
        selection=[
            ('00', '00 - No Aplica'),
            ('01', '01 - Dependiente Pensionado por Vejez Activo'),
            ('02', '02 - Dependiente Pensionado por Vejez – Alto Riesgo'),
        ],
        string='Subtipo Trabajador',
        default='00',
        help='Subtipo del trabajador. Aplica para pensionados activos '
             'y pensionados de alto riesgo.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Indicadores especiales del trabajador
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_high_risk_pension = fields.Boolean(
        string='Pensión Alto Riesgo',
        default=False,
        help='Indica si el trabajador cotiza al régimen de pensión de '
             'alto riesgo. Se refleja en el atributo AltoRiesgoPension '
             'del nodo <Trabajador>.',
    )
    l10n_co_ne_foreigner_no_pension = fields.Boolean(
        string='Extranjero No Obligado a Pensión',
        default=False,
        help='Indica si el trabajador es un extranjero no obligado a '
             'cotizar a pensión en Colombia, según convenios '
             'internacionales de seguridad social.',
    )
    l10n_co_ne_colombian_abroad = fields.Boolean(
        string='Colombiano en el Exterior',
        default=False,
        help='Indica si el trabajador es un colombiano que presta sus '
             'servicios desde el exterior.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Lugar de trabajo (codificación DANE)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_dane_city_id = fields.Many2one(
        comodel_name='res.city',
        string='Municipio Lugar de Trabajo',
        help='Municipio donde el trabajador presta sus servicios, '
             'codificado según el DANE. Se usa en los atributos '
             'LugarTrabajoDepartamentoEstado y LugarTrabajoMunicipioCiudad '
             'del nodo <Trabajador>.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Información de pago bancario
    # Nodo <Pago> del XML de nómina electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_payment_method = fields.Selection(
        selection=[
            ('1', 'Transferencia Bancaria'),
            ('2', 'Cheque'),
            ('10', 'Efectivo'),
        ],
        string='Método de Pago',
        default='1',
        help='Método de pago de la nómina al trabajador. Se refleja en '
             'el atributo Metodo del nodo <Pago> del XML.',
    )
    l10n_co_ne_bank_name = fields.Char(
        string='Nombre del Banco',
        help='Nombre de la entidad bancaria donde el trabajador tiene '
             'su cuenta de nómina.',
    )
    l10n_co_ne_bank_account_type = fields.Selection(
        selection=[
            ('ahorro', 'Cuenta de Ahorro'),
            ('corriente', 'Cuenta Corriente'),
        ],
        string='Tipo de Cuenta',
        help='Tipo de cuenta bancaria del trabajador.',
    )
    l10n_co_ne_bank_account = fields.Char(
        string='Número de Cuenta',
        help='Número de cuenta bancaria del trabajador para el pago '
             'de nómina.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Retención en la Fuente – Datos del trabajador
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_dependientes = fields.Boolean(
        string='Tiene Dependientes',
        default=False,
        help='Art. 387 ET: Si el trabajador tiene personas a cargo '
             '(hijos menores, cónyuge, padres dependientes), tiene '
             'derecho a deducir el 10%% del ingreso bruto mensual, '
             'con un máximo de 32.5 UVT por mes.',
    )
    l10n_co_ne_voluntary_pension = fields.Float(
        string='Aporte Voluntario Pensión',
        default=0,
        help='Aporte mensual voluntario a fondo de pensiones. '
             'Deducible hasta el 25%% del ingreso bruto mensual '
             '(Art. 126-1 ET).',
    )
    l10n_co_ne_afc = fields.Float(
        string='AFC Mensual',
        default=0,
        help='Ahorro mensual para Fomento de la Construcción (AFC). '
             'Deducible hasta el 30%% del ingreso bruto mensual '
             '(Art. 126-4 ET).',
    )

    # ──────────────────────────────────────────────────────────────────
    # PILA — Administradoras de Seguridad Social
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pila_eps_code = fields.Char(
        string='Código EPS',
        help='Código de la EPS según tabla de administradoras PILA.',
    )
    l10n_co_pila_afp_code = fields.Char(
        string='Código AFP',
        help='Código de la AFP (Fondo de Pensiones) según tabla PILA.',
    )
    l10n_co_pila_ccf_code = fields.Char(
        string='Código CCF',
        help='Código de la Caja de Compensación Familiar según tabla PILA.',
    )
    l10n_co_pila_afp_traslado = fields.Char(
        string='AFP Traslado',
        help='Código AFP destino en caso de traslado.',
    )
    l10n_co_pila_eps_traslado = fields.Char(
        string='EPS Traslado',
        help='Código EPS destino en caso de traslado.',
    )
    l10n_co_pila_colombiano_exterior = fields.Boolean(
        string='Colombiano en el Exterior (PILA)',
        default=False,
    )
    l10n_co_pila_fecha_radicacion_ext = fields.Date(
        string='Fecha Radicación Exterior',
    )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('l10n_co_ne_worker_type', 'l10n_co_ne_worker_subtype')
    def _check_worker_subtype_consistency(self):
        """Valida coherencia entre tipo y subtipo de trabajador."""
        for employee in self:
            if (
                employee.l10n_co_ne_worker_subtype in ('01', '02')
                and employee.l10n_co_ne_worker_type != '01'
            ):
                raise ValidationError(_(
                    'Los subtipos de trabajador "Pensionado por Vejez" solo '
                    'aplican para el tipo de trabajador "01 - Dependiente". '
                    'Empleado: %s',
                    employee.name,
                ))

    @api.constrains('l10n_co_ne_payment_method', 'l10n_co_ne_bank_account')
    def _check_bank_account_for_transfer(self):
        """Valida que la cuenta bancaria esté informada si el pago es por transferencia."""
        for employee in self:
            if (
                employee.l10n_co_ne_payment_method == '1'
                and not employee.l10n_co_ne_bank_account
            ):
                raise ValidationError(_(
                    'Debe informar el número de cuenta bancaria cuando el '
                    'método de pago es Transferencia Bancaria. '
                    'Empleado: %s',
                    employee.name,
                ))
