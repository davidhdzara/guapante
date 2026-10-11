# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.employee para Nómina Electrónica DIAN.

Agrega los campos requeridos por el nodo ``<Trabajador>`` del XML de nómina
electrónica: tipo/subtipo de trabajador, indicadores de alto riesgo y
extranjería, así como información bancaria para el nodo ``<Pago>``. El lugar
de trabajo (LugarTrabajoPais/DepartamentoEstado/MunicipioCiudad/Direccion) NO
vive aquí -- sale del campo nativo ``address_id`` (Dirección de Trabajo) vía
``HrPayslip._ne_lugar_trabajo_partner()`` (H-018, 2026-10-11). El tipo de
documento de identidad (TipoDocumento del XML) tampoco vive aquí como
Selection propio -- sale de ``l10n_latam.identification.type`` vía
``work_contact_id`` (UX-02, 2026-10-11); ver
``l10n_co_ne_identification_type_id`` abajo y
``HrPayslip._ne_trabajador()``.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, secciones 6.2.8 (Trabajador) y 6.2.9 (Pago).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    """Campos del trabajador para Nómina Electrónica DIAN."""

    _inherit = 'hr.employee'

    # ──────────────────────────────────────────────────────────────────
    # Tipo de documento de identidad (UX-02, 2026-10-11, decisión de David +
    # Tech Lead): antes un Selection propio, duplicando el tipo de
    # identificación que Contactos ya guarda en work_contact_id (el mismo
    # partner que exige el dominio nativo de bank_account_id). El código
    # DIAN (TipoDocumento del nodo <Trabajador>) ahora sale de
    # l10n_latam.identification.type.l10n_co_ne_dian_document_code (dato del
    # módulo, data/l10n_latam_identification_type_dian_code_data.xml -- ver
    # HrPayslip._ne_trabajador()). El NÚMERO (identification_id) sigue siendo
    # el mismo Char nativo de siempre (sin cambiar su naturaleza ni los ~12
    # usos reales que ya tiene) -- lo que se agrega es sincronización
    # bidireccional con work_contact_id.vat, ver create()/write() más abajo
    # y models/res_partner.py (decisión de David, 2026-10-11: "que el
    # contacto y el empleado queden sincronizados en el número").
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_identification_type_id = fields.Many2one(
        comodel_name='l10n_latam.identification.type',
        string='Tipo de Documento',
        compute='_compute_l10n_co_ne_identification_type_id',
        inverse='_inverse_l10n_co_ne_identification_type_id',
        help='Tipo de documento de identidad del trabajador -- espejo '
             'editable de work_contact_id.l10n_latam_identification_type_id '
             '(el mismo dato de Contactos, mostrado aquí junto al número '
             'para no exigir 2 pestañas distintas).',
    )

    @api.depends('work_contact_id.l10n_latam_identification_type_id')
    def _compute_l10n_co_ne_identification_type_id(self):
        for employee in self:
            employee.l10n_co_ne_identification_type_id = (
                employee.work_contact_id.l10n_latam_identification_type_id)

    def _inverse_l10n_co_ne_identification_type_id(self):
        # El Internal User "RRHH" (hr.group_hr_user) no tiene de por sí
        # permiso de escritura en res.partner (access_res_partner_group_user:
        # perm_write=0 en la base de Odoo -- solo group_partner_manager lo
        # tiene) -- mismo caso que resuelve hr nativo con sudo() en
        # _inverse_work_contact_details() (hr_employee_base.py). sudo()
        # acotado a esta sola escritura, nunca a todo el registro.
        for employee in self:
            if employee.work_contact_id:
                employee.work_contact_id.sudo().write({
                    'l10n_latam_identification_type_id':
                        employee.l10n_co_ne_identification_type_id.id,
                })

    # ──────────────────────────────────────────────────────────────────
    # Sincronización del NÚMERO de identificación con Contactos (UX-02,
    # 2026-10-11, decisión de David: "que el contacto y el empleado queden
    # sincronizados en el número"). La dirección Contactos -> empleado vive
    # en models/res_partner.py (write() de res.partner, cuando cambia vat).
    #
    # Por qué un create()/write() explícitos y no un related/compute+store
    # en identification_id: ese campo es nativo de hr (Char, sin related) y
    # tiene ~12 usos reales en este módulo (NumeroDocumento del XML, UGPP,
    # PILA, la clave de idempotencia del wizard de certificación, y pruebas)
    # -- convertirlo en related cambiaría su naturaleza de almacenamiento,
    # más riesgo del necesario. Además hay un problema real de orden en la
    # creación (verificado contra hr/models/hr_employee.py::create()): para
    # un empleado SIN usuario vinculado (el caso típico), work_contact_id NO
    # existe todavía cuando super().create() procesa identification_id --
    # hr nativo lo crea DESPUÉS, en _create_work_contacts(), llamado tras
    # super().create(). Por eso la propagación debe hacerse DESPUÉS de que
    # el create() completo (incluida esa post-creación) haya terminado.
    #
    # Guards explícitos (Tech Lead, 2026-10-11): nunca propagar un valor
    # vacío/False en ninguna dirección (borraría el dato real del otro
    # lado), y comparar antes de escribir para no generar un ciclo
    # empleado->contacto->empleado->... (ver test_sin_bucle_infinito_entre_
    # employee_y_partner en test_identificacion_sincronizada.py).
    # ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for employee in employees:
            if (
                employee.identification_id
                and employee.work_contact_id
                and employee.work_contact_id.vat != employee.identification_id
            ):
                employee.work_contact_id.sudo().vat = employee.identification_id
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'identification_id' in vals:
            for employee in self:
                if (
                    employee.identification_id
                    and employee.work_contact_id
                    and employee.work_contact_id.vat != employee.identification_id
                ):
                    employee.work_contact_id.sudo().vat = employee.identification_id
        return res

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
    # Información de pago bancario (UX-02, 2026-10-11, decisión de David +
    # Tech Lead): Banco/TipoCuenta/NumeroCuenta ya NO son campos propios --
    # duplicaban la cuenta bancaria nativa del empleado (bank_account_id,
    # res.partner.bank, visible en "Información privada" > grupo "Contacto
    # privado"). Banco y NumeroCuenta salen de ahí
    # (HrPayslip._ne_pago()); TipoCuenta se omite del XML (es opcional en
    # el XSD -- no existe campo nativo real para Ahorro/Corriente, ver
    # docstring de _ne_pago()). Metodo sigue siendo el único campo propio
    # de esta sección: no tiene equivalente nativo verificado.
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
             'el atributo Metodo del nodo <Pago> del XML. La cuenta '
             'bancaria se elige en "Información privada" (Cuenta '
             'Bancaria).',
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
    # Nota (AUD-05, doc 32): l10n_co_ne_voluntary_pension/l10n_co_ne_afc que vivian
    # aqui se eliminaron -- eran una segunda fuente de datos desconectada de
    # contract.l10n_co_ne_pension_voluntaria/contract.l10n_co_ne_afc (la que
    # realmente alimenta la deduccion del payslip). Su unico consumidor era
    # hr_retefuente.py, que ahora lee del contrato -- misma fuente de verdad
    # que la deduccion real. Ningun empleado real tenia estos campos
    # configurados (verificado antes del cambio), no hace falta migracion de
    # datos.

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
    # Ficha Consolidada (doc 11) -- campos related de solo lectura, puro
    # passthrough para mostrar en la pestaña "Nómina Colombia" datos que
    # ya viven en el contrato/compañía (mismo patrón que
    # res_config_settings.py usa en todo el módulo: no son un dato nuevo,
    # solo un acceso de lectura conveniente).
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_contract_type_display = fields.Selection(
        related='contract_id.l10n_co_ne_contract_type',
        string='Tipo de Contrato',
        readonly=True,
    )
    l10n_co_ne_analytic_account_id = fields.Many2one(
        related='contract_id.analytic_account_id',
        string='Centro de Costo',
        readonly=True,
    )
    l10n_co_pila_clase_riesgo_display = fields.Selection(
        related='contract_id.l10n_co_pila_clase_riesgo',
        string='Clase de Riesgo ARL',
        readonly=True,
    )
    l10n_co_pila_arl_name_display = fields.Char(
        related='company_id.l10n_co_pila_arl_name',
        string='ARL',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # Habilitación DIAN (doc 39) — empleado emulado, no real
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_is_habilitacion_test = fields.Boolean(
        string='Empleado de Prueba Habilitación DIAN',
        default=False,
        help='Marca los empleados sintéticos creados por el wizard de '
             'habilitación DIAN (doc 34/39) para armar el set de pruebas '
             'sin depender de datos reales de la empresa. PILA y UGPP '
             'deben excluir estos registros de sus reportes reales -- '
             'nunca representan personal real ni deben contarse como tal.',
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

    @api.constrains('l10n_co_ne_payment_method', 'bank_account_id')
    def _check_bank_account_for_transfer(self):
        """Valida que la cuenta bancaria esté informada si el pago es por transferencia.

        UX-02 (2026-10-11): ahora mira el campo nativo bank_account_id en vez del
        propio l10n_co_ne_bank_account (retirado)."""
        for employee in self:
            if (
                employee.l10n_co_ne_payment_method == '1'
                and not employee.bank_account_id
            ):
                raise ValidationError(_(
                    'Debe informar la Cuenta Bancaria (Información privada) cuando '
                    'el método de pago es Transferencia Bancaria. '
                    'Empleado: %s',
                    employee.name,
                ))
