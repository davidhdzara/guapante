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
from odoo.tools.misc import str2bool


class ResCompany(models.Model):
    """Configuración de la empresa para Nómina Electrónica DIAN."""

    _inherit = 'res.company'

    # ──────────────────────────────────────────────────────────────────
    # Modo de Operación DIAN – Nómina Electrónica (doc 22 §1)
    # ──────────────────────────────────────────────────────────────────
    # Antes campos planos aqui mismo (l10n_co_ne_software_id/_pin/
    # _test_set_id) -- migrados a l10n.co.ne.operation_mode para replicar
    # visualmente la tabla "Modos de Operacion" de Facturacion Electronica
    # (CO). A diferencia de DIAN, siempre hay a lo sumo 1 fila por
    # compania (ver l10n_co_ne_operation_mode.py).
    l10n_co_ne_operation_mode_ids = fields.One2many(
        comodel_name='l10n.co.ne.operation_mode',
        inverse_name='company_id',
        string='Modos de Operación Nómina Electrónica',
    )

    # ──────────────────────────────────────────────────────────────────
    # Certificado Digital – reutiliza certificate.certificate nativo
    # ──────────────────────────────────────────────────────────────────
    # Antes había además un Many2one l10n_co_ne_certificate_id para elegir
    # explícitamente "cuál certificado usa nómina" (doc 22 §2, Opción B).
    # Retirado 2026-09-12: verificado el código real de Facturación
    # Electrónica (l10n_co_dian) -- NO tiene ningún campo de selección
    # explícita, toma siempre el último certificado de la lista
    # (certificates_sudo[-1]). El Many2one aparte era complejidad nuestra,
    # no paridad real con Facturación. _get_ne_certificate() reemplaza su
    # uso en el flujo de firma con el mismo criterio ("el último").
    l10n_co_ne_certificate_ids = fields.One2many(
        comodel_name='certificate.certificate',
        inverse_name='company_id',
        string='Certificados',
    )

    def _get_ne_certificate(self):
        """Certificado usado para firmar nómina electrónica.

        Mismo criterio que Facturación Electrónica (l10n_co_dian):
        el último certificado de la lista de la compañía, sin campo
        de selección explícita aparte.
        """
        self.ensure_one()
        return self.l10n_co_ne_certificate_ids[-1:]

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
    # Doc 22 §3: l10n_co_ne_environment (arriba) sigue siendo la UNICA
    # fuente de verdad real (Selection, sin cambios) -- hr_payslip.py la
    # sigue leyendo directo en sus 4 usos existentes. Este boolean es
    # puramente una traduccion computada+inversa para exponerla en
    # Ajustes > Nomina como 2 checkboxes (paridad con Facturacion
    # Electronica) sin duplicar el dato ni requerir migracion.
    l10n_co_ne_test_environment = fields.Boolean(
        string='Ambiente de Pruebas',
        compute='_compute_test_environment',
        inverse='_inverse_test_environment',
        help='Marque esta casilla si está probando flujos de nómina '
             'electrónica o si necesita activar el entorno de proceso '
             'de certificación.',
    )
    # Genuinamente nuevo, sin equivalente previo -- gatea
    # action_send_test_set() (hr_payslip.py) para que no quede decorativo
    # (doc 21 §3 senalaba justo ese riesgo si se copiaba el patron de
    # DIAN sin darle logica real detras).
    l10n_co_ne_certification_process = fields.Boolean(
        string='Activar Proceso de Certificación',
        default=False,
        help='Envía documentos de prueba de nómina electrónica con su '
             'certificado para lograr el estado "Habilitado" en el '
             'portal de la DIAN.',
    )
    # Doc 37: mismo patrón que l10n_co_dian_demo_mode nativo (Facturación
    # Electrónica, Enterprise) -- Boolean respaldado en ir.config_parameter
    # (no columna propia), mutuamente excluyente con "Ambiente de Pruebas".
    # Campo propio (no se reutiliza el flag de Facturación): Nómina y
    # Facturación son productos independientes con sus propias validaciones
    # (_validate_company_ne_config, etc.), compartir el flag los acoplaría
    # sin necesidad.
    l10n_co_ne_demo_mode = fields.Boolean(
        string='DIAN Modo Demo',
        compute='_compute_ne_demo_mode',
        inverse='_inverse_ne_demo_mode',
        help='Activa este modo para poder probar los flujos de nómina '
             'electrónica solo con validaciones internas, pero sin '
             'respuesta del entorno de la DIAN.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Habilitación DIAN (doc 34) -- metas de documentos a certificar
    # ──────────────────────────────────────────────────────────────────
    # Sin default fijo (doc 34 §5, corrección de David 2026-09-12): el
    # numero real lo exige el portal de habilitacion de la DIAN caso por
    # caso, no algo que este equipo pueda asumir. Lo consume el wizard
    # l10n.co.ne.certification.wizard como meta de progreso, no como
    # generador -- Opcion B confirmada en doc 34 §2 (usa el pipeline real
    # de hr.payslip, no un generador sintetico aparte).
    l10n_co_ne_num_nomina_certificar = fields.Integer(
        string='Cantidad de Nómina Electrónica a Certificar',
        help='Meta de documentos tipo Nómina Individual que deben quedar '
             'Aceptados por la DIAN durante el proceso de certificación. '
             'La define usted según lo que exija el portal de '
             'habilitación de la DIAN para esta empresa.',
    )
    l10n_co_ne_num_ajuste_certificar = fields.Integer(
        string='Cantidad de Nómina Electrónica de Ajuste a Certificar',
        help='Meta de documentos tipo Nota de Ajuste que deben quedar '
             'Aceptados por la DIAN durante el proceso de certificación. '
             'La define usted según lo que exija el portal de '
             'habilitación de la DIAN para esta empresa.',
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
    # Doc 11 (ficha consolidada): nombre legible de la ARL, a nivel de
    # compañía -- no por empleado. La afiliación a ARL en Colombia es de
    # toda la empresa, no individual (todos los empleados comparten la
    # misma ARL); duplicar un campo de nombre por cada ficha de empleado
    # obligaría a actualizar N registros si la empresa cambia de ARL.
    l10n_co_pila_arl_name = fields.Char(
        string='Nombre ARL',
        help='Nombre comercial de la Administradora de Riesgos Laborales '
             'de la empresa (ej: "Positiva ARL", "Sura ARL"). Complementa '
             'el Código ARL (código PILA) -- este campo es solo para '
             'mostrar un nombre legible en pantalla.',
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
    # Computes
    # ──────────────────────────────────────────────────────────────────
    @api.depends('l10n_co_ne_environment')
    def _compute_test_environment(self):
        for company in self:
            company.l10n_co_ne_test_environment = company.l10n_co_ne_environment == '2'

    def _inverse_test_environment(self):
        for company in self:
            company.l10n_co_ne_environment = (
                '2' if company.l10n_co_ne_test_environment else '1'
            )
            # Mutuamente excluyente con Modo Demo (mismo criterio que
            # _inverse_l10n_co_dian_test_environment nativo): activar el
            # ambiente de pruebas real de la DIAN apaga el Modo Demo local.
            if company.l10n_co_ne_test_environment:
                company.l10n_co_ne_demo_mode = False

    def _compute_ne_demo_mode(self):
        for company in self:
            company.l10n_co_ne_demo_mode = str2bool(
                self.env['ir.config_parameter'].sudo().get_param(
                    f'l10n_co_ne_demo_mode_{company.id}'
                )
            )

    def _inverse_ne_demo_mode(self):
        for company in self:
            self.env['ir.config_parameter'].sudo().set_param(
                f'l10n_co_ne_demo_mode_{company.id}',
                str(company.l10n_co_ne_demo_mode),
            )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('l10n_co_ne_environment', 'l10n_co_ne_operation_mode_ids')
    def _check_test_set_id(self):
        """Valida que TestSetID esté informado en ambiente de pruebas."""
        for company in self:
            mode = company.l10n_co_ne_operation_mode_ids
            if (
                company.l10n_co_ne_environment == '2'
                and mode
                and not mode.test_set_id
            ):
                raise ValidationError(_(
                    'Debe configurar el ID de Pruebas en el Modo de '
                    'Operación para el ambiente de Habilitación '
                    '(Pruebas). Este valor se obtiene del portal de la '
                    'DIAN.'
                ))
