# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de res.company para Nómina Electrónica DIAN y reportes UGPP.

Agrega campos de configuración del software de nómina electrónica ante la DIAN,
selección del certificate.certificate nativo (compartido con facturación
electrónica) usado para firmar, y campos para la clasificación de empresa
ante la UGPP.

Todos los campos de nómina electrónica usan prefijo ``l10n_co_ne_`` y los
de UGPP usan ``l10n_co_ugpp_`` para evitar colisiones con facturación
electrónica.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Configuración de la empresa para Nómina Electrónica DIAN."""

    _inherit = 'res.company'

    # ──────────────────────────────────────────────────────────────────
    # Campos de Software DIAN – Nómina Electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_software_id = fields.Char(
        string='ID Software Nómina',
        help='Identificador del software asignado por la DIAN para '
             'nómina electrónica. Se obtiene en el portal de habilitación.',
    )
    l10n_co_ne_software_pin = fields.Char(
        string='PIN Software Nómina',
        help='PIN del software de nómina electrónica asignado por la DIAN.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Certificado Digital – reutiliza certificate.certificate nativo
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_certificate_id = fields.Many2one(
        comodel_name='certificate.certificate',
        string='Certificado Digital',
        check_company=True,
        domain="[('company_id', '=', id)]",
        help='Certificado digital usado para firmar los documentos de '
             'nómina electrónica (XAdES-BES). Reutiliza el mismo '
             'certificate.certificate nativo que usa Odoo para '
             'facturación electrónica -- no requiere cargar un .p12 '
             'independiente para nómina.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Ambiente y configuración de habilitación
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_environment = fields.Selection(
        selection=[
            ('1', 'Producción'),
            ('2', 'Habilitación (Pruebas)'),
        ],
        string='Ambiente Nómina Electrónica',
        default='2',
        required=True,
        help='Ambiente de operación ante la DIAN.\n'
             '• Producción: documentos con validez legal.\n'
             '• Habilitación: ambiente de pruebas para el proceso de '
             'habilitación ante la DIAN.',
    )
    l10n_co_ne_test_set_id = fields.Char(
        string='TestSetID',
        help='Identificador del set de pruebas asignado por la DIAN '
             'durante el proceso de habilitación. Solo aplica en '
             'ambiente de Habilitación (Pruebas).',
    )

    # ──────────────────────────────────────────────────────────────────
    # Prefijos de consecutivo para Nómina y Notas de Ajuste
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_payroll_prefix = fields.Char(
        string='Prefijo Nómina',
        default='NE',
        help='Prefijo utilizado en el consecutivo de documentos de '
             'nómina electrónica (ej: NE0001).',
    )
    l10n_co_ne_adjust_prefix = fields.Char(
        string='Prefijo Nota de Ajuste',
        default='NA',
        help='Prefijo utilizado en el consecutivo de notas de ajuste '
             'de nómina electrónica (ej: NA0001).',
    )
    l10n_co_ne_sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Secuencia Nómina Electrónica',
        default=lambda self: self.env.ref('l10n_co_nomina_electronica.seq_l10n_co_nomina_electronica', raise_if_not_found=False),
        domain="[('code', 'like', 'l10n_co_nomina.')]",
        help='Secuencia definitiva utilizada para generar los consecutivos de transmisión DIAN (ej: NE-00001).',
    )
    l10n_co_ne_pre_sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Secuencia Nómina Temporal',
        default=lambda self: self.env.ref('l10n_co_nomina_electronica.seq_l10n_co_nomina_temporal', raise_if_not_found=False),
        domain="[('code', 'like', 'l10n_co_nomina.')]",
        help='Secuencia temporal utilizada para borradores y nóminas pendientes de validación (ej: PRE-NOM-00001).',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos UGPP – Clasificación del aportante
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ugpp_legal_nature = fields.Selection(
        selection=[
            ('publica', 'Pública'),
            ('privada', 'Privada'),
            ('mixta', 'Mixta'),
            ('otra', 'Otra'),
        ],
        string='Naturaleza Jurídica',
        help='Naturaleza jurídica de la empresa según clasificación UGPP.',
    )
    l10n_co_ugpp_contributor_type = fields.Selection(
        selection=[
            ('empleador', 'Empleador'),
            ('independiente', 'Independiente'),
            ('cooperativa', 'Cooperativa de Trabajo Asociado'),
        ],
        string='Tipo de Aportante',
        help='Tipo de aportante al Sistema de Seguridad Social según UGPP.',
    )
    l10n_co_ugpp_special_autoretention = fields.Boolean(
        string='Autorretención Especial',
        default=False,
        help='Indica si la empresa tiene la calidad de autorretenedor '
             'especial ante la UGPP.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Parámetros de Nómina Colombiana
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_exoneration_1607 = fields.Boolean(
        string='Exoneración Ley 1607/2012',
        default=False,
        help='Si la empresa es persona jurídica del régimen contributivo, '
             'queda exonerada de aportes a SENA e ICBF para empleados '
             'con salario inferior a 10 SMMLV (Art. 114-1 ET).',
    )

    def _is_exonerado_parafiscales(self, ibc, date):
        """Determina si un IBC está exonerado de SENA/ICBF/Salud Empleador.

        Único criterio del Art. 114-1 ET (Ley 1607/2012): la compañía debe
        tener activada la exoneración (`l10n_co_ne_exoneration_1607`) y el
        IBC del empleado debe ser menor a `tope_exoneracion_smmlv` SMMLV
        del año de `date`.

        Antes de esto, este criterio estaba duplicado por separado en las
        reglas salariales de CO_SENA_CIA/CO_ICBF_CIA/CO_SALUD_CIA y el
        wizard de PILA tenía una cuarta versión desconectada (un booleano
        manual en el contrato) -- este método es ahora la única fuente de
        verdad, para que nómina y PILA no puedan divergir para el mismo
        empleado en el mismo periodo.

        SMMLV y el tope se leen del framework nativo hr.rule.parameter
        (doc 13, reemplaza l10n.co.payroll.annual.params).

        Args:
            ibc: float - IBC ya ajustado por el llamador (p.ej. con el
                factor de salario integral si aplica) -- este método no
                conoce el contrato, solo aplica el criterio de la norma.
            date: Fecha (date, datetime o string YYYY-MM-DD) que determina
                el SMMLV vigente.

        Returns:
            bool - True si el IBC está exonerado.
        """
        if not self.l10n_co_ne_exoneration_1607:
            return False
        RuleParameter = self.env['hr.rule.parameter']
        smmlv = RuleParameter._get_parameter_from_code('l10n_co_smmlv', date)
        tope = RuleParameter._get_parameter_from_code(
            'l10n_co_tope_exoneracion_smmlv', date)
        return ibc < smmlv * tope

    # ──────────────────────────────────────────────────────────────────
    # PILA — Datos del Aportante
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pila_tipo_aportante = fields.Selection(
        selection=[
            ('1', '1 - Empleador'),
            ('2', '2 - Independiente'),
            ('3', '3 - Entidad Beneficiaria del Sistema General de Participaciones'),
            ('4', '4 - Entidad Promotora de Salud'),
            ('5', '5 - Cooperativa/Precooperativa de Trabajo Asociado'),
            ('6', '6 - Misión Diplomática'),
            ('7', '7 - Organismo multilateral'),
            ('8', '8 - Institución Auxiliar del Cooperativismo'),
        ],
        string='Tipo Aportante PILA',
        default='1',
    )
    l10n_co_pila_arl_code = fields.Char(
        string='Código ARL',
        help='Código de la ARL según tabla de administradoras PILA (ej: 14-11).',
    )
    l10n_co_pila_forma_presentacion = fields.Selection(
        selection=[
            ('U', 'Único'),
            ('S', 'Sucursal'),
        ],
        string='Forma Presentación PILA',
        default='U',
    )
    l10n_co_pila_codigo_sucursal = fields.Char(
        string='Código Sucursal PILA',
    )
    l10n_co_pila_nombre_sucursal = fields.Char(
        string='Nombre Sucursal PILA',
    )
    l10n_co_pila_operador_code = fields.Char(
        string='Código Operador PILA',
        help='Código del operador de información PILA (ej: 89 para Enlace).',
    )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('l10n_co_ne_environment', 'l10n_co_ne_test_set_id')
    def _check_test_set_id(self):
        """Valida que TestSetID esté informado en ambiente de pruebas."""
        for company in self:
            if (
                company.l10n_co_ne_environment == '2'
                and company.l10n_co_ne_software_id
                and not company.l10n_co_ne_test_set_id
            ):
                raise ValidationError(_(
                    'Debe configurar el TestSetID para el ambiente de '
                    'Habilitación (Pruebas). Este valor se obtiene del '
                    'portal de la DIAN.'
                ))
