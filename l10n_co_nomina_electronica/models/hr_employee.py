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

from odoo import api, fields, models, _, _lt
from odoo.exceptions import UserError, ValidationError

from ..services import dian_utils
from .res_company import NE_MEDIOS_PAGO

# H-F1-06 (doc 87): DÓNDE se completan las afiliaciones, en UN solo sitio (el consultor v19 lo porta sin rediseño). ``NE_EMPLEADO_PAGINA`` es el ``name`` de la página nativa de Nómina en la
# vista del empleado (v18: ``hr_payroll`` de ``hr_payroll``; lo usa el xpath de ``views/hr_employee_views.xml`` y una prueba compara los dos); ``NE_EMPLEADO_PESTANA`` y
# ``NE_EMPLEADO_GRUPO_AFILIACION`` son los textos que ve el usuario (el grupo es el ``string`` de esa vista; la misma prueba lo compara).
NE_EMPLEADO_PAGINA = 'hr_payroll'
NE_EMPLEADO_PESTANA = _lt('Nómina')                                       # traducibles en el momento de usarse (``_lt``: los mensajes los arman con ``%(...)s``)
NE_EMPLEADO_GRUPO_AFILIACION = _lt('PILA - Administradoras')
NE_UBICACION_AJUSTES_PILA = _lt('Nómina > Configuración > Ajustes, bloque PILA')


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
            contacto = employee.work_contact_id
            if contacto:
                anterior = contacto.l10n_latam_identification_type_id
                nuevo = employee.l10n_co_ne_identification_type_id
                contacto.sudo().write({'l10n_latam_identification_type_id': nuevo.id})
                if anterior != nuevo:
                    employee._ne_nota_cambio_tipo_documento(contacto, anterior, nuevo)

    def _ne_asientos_publicados_del_contacto(self, contacto):
        """Asientos publicados del contacto (el contacto del empleado los recibe desde la primera nomina)."""
        return self.env['account.move'].sudo().search_count([
            ('partner_id', '=', contacto.id), ('state', '=', 'posted')])

    def _ne_nota_cambio_tipo_documento(self, contacto, anterior, nuevo):
        """Constancia en el chatter del contacto: el cambio del tipo de documento desde la ficha del empleado NO se bloquea (el
        dato correcto del trabajador manda para la nomina electronica) pero tampoco es silencioso (doc 59 18.8, TL 2026-11-14;
        principio «sin defaults silenciosos» de David). Si el contacto tiene asientos publicados, la nota lo dice."""
        self.ensure_one()
        asientos = self._ne_asientos_publicados_del_contacto(contacto)
        cuerpo = _(
            'Tipo de documento cambiado de "%(antes)s" a "%(despues)s" desde la ficha del empleado %(empleado)s por %(usuario)s.',
            antes=anterior.name or _('(vacío)'), despues=nuevo.name or _('(vacío)'),
            empleado=self.display_name, usuario=self.env.user.name)
        if asientos:
            cuerpo += ' ' + _('El contacto tiene %(n)s asientos publicados.', n=asientos)
        contacto.sudo().message_post(
            body=cuerpo, message_type='comment', subtype_xmlid='mail.mt_note',
            author_id=self.env.user.partner_id.id)

    # ──────────────────────────────────────────────────────────────────
    # Nombres y apellidos (H-024). Odoo solo guarda ``name``; Colombia pide
    # 4 datos separados (XML DIAN, PILA, UGPP) y partir un texto libre es
    # ambiguo. Se prellenan SOLO los casos sin ambigüedad (ver
    # dian_utils.split_name) y el resto lo completa una persona.
    # ──────────────────────────────────────────────────────────────────
    l10n_co_primer_nombre = fields.Char(string='Primer Nombre')
    l10n_co_otros_nombres = fields.Char(string='Otros Nombres')
    l10n_co_primer_apellido = fields.Char(string='Primer Apellido')
    l10n_co_segundo_apellido = fields.Char(string='Segundo Apellido')

    _L10N_CO_CAMPOS_NOMBRE = {
        'primer_nombre': 'l10n_co_primer_nombre',
        'otros_nombres': 'l10n_co_otros_nombres',
        'primer_apellido': 'l10n_co_primer_apellido',
        'segundo_apellido': 'l10n_co_segundo_apellido',
    }

    @api.model
    def _l10n_co_prellenar_nombre(self, full_name):
        """Valores de los 4 campos prellenados desde ``full_name`` (vacíos si es ambiguo)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_co_nomina_electronica.particulas_nombre')
        if not raw:
            raise UserError(_(
                'Falta el parámetro del sistema "l10n_co_nomina_electronica.particulas_nombre" '
                '(palabras que vuelven ambiguo un nombre, separadas por coma). Créelo en '
                'Ajustes > Técnico > Parámetros del sistema.'))
        particulas = {p.strip().lower() for p in raw.split(',') if p.strip()}
        partes = dian_utils.split_name(full_name or '', particulas)
        return {campo: partes[clave] for clave, campo in self._L10N_CO_CAMPOS_NOMBRE.items()}

    def _ne_caja_compensacion(self):
        """Caja de Compensación efectiva (res.partner). Única fuente para el asiento por
        tercero y para PILA.

        Con "¿Maneja empleados en diferentes ciudades?" activa en la empresa, es la del empleado
        y es obligatoria (sin ella: error, sin caer a la general). Desactivada, es siempre la
        general de la empresa. Sin dato: UserError que nombra al empleado/empresa y el campo."""
        self.ensure_one()
        company = self.company_id
        if company.l10n_co_pila_ccf_por_empleado:
            if not self.l10n_co_pila_ccf_id:
                raise UserError(_(
                    'El empleado %(employee)s no tiene Caja de Compensación y la empresa '
                    '%(company)s maneja la caja por empleado. Complétela en la ficha del empleado, '
                    'pestaña %(pestana)s, grupo «%(grupo)s».',
                    employee=self.name, company=company.name, pestana=NE_EMPLEADO_PESTANA, grupo=NE_EMPLEADO_GRUPO_AFILIACION))
            return self.l10n_co_pila_ccf_id
        if not company.l10n_co_pila_ccf_id:
            raise UserError(_(
                'La empresa %(company)s no tiene Caja de Compensación general (%(ubicacion)s). '
                'Se necesita para el empleado %(employee)s.',
                company=company.name, employee=self.name, ubicacion=NE_UBICACION_AJUSTES_PILA))
        return company.l10n_co_pila_ccf_id

    def _ne_afiliaciones_no_exigidas(self, fecha):
        """Lista versionada ``[(tipo de cotizante, subtipo, entidad)]`` (``*`` = cualquiera) que el parametro ``l10n_co_afiliaciones_no_exigidas`` exceptua a ``fecha``. Sin el parametro, un error que lo
        nombra y dice que hacer: nunca se asume que todo se exige ni que nada."""
        self.ensure_one()
        try:
            return self.env['hr.rule.parameter']._get_parameter_from_code('l10n_co_afiliaciones_no_exigidas', fecha)
        except UserError:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Afiliaciones que No se Exigen por Tipo de Cotizante» (código l10n_co_afiliaciones_no_exigidas) para el %(fecha)s, que se necesita '
                'para revisar la afiliación a la seguridad social del empleado %(empleado)s. Actualice el módulo de nómina electrónica o créelo en Nómina > Configuración > Parámetros de reglas.',
                fecha=fecha, empleado=self.name)) from None

    def _ne_entidad_exigida(self, entidad, contrato, fecha, no_exigidas=None):
        """¿Se exige la afiliación Y la cotización a ``entidad`` (``'eps'``, ``'afp'``, ``'ccf'``, ``'arl'``) para el tipo y el subtipo de cotizante del CONTRATO a ``fecha``? Falso si el parámetro
        versionado ``l10n_co_afiliaciones_no_exigidas`` la exceptua. FUENTE ÚNICA (H-F1-06): la usan el aviso y el error de la afiliación (``_ne_afiliaciones_faltantes``) Y las reglas que calculan la
        cotización (pensión del empleado y de la empresa y FSP, vía ``HrPayslip._ne_no_cotiza_pension``): quitar la fila del parámetro vuelve a exigir la afiliación y a calcular la cotización,
        sin tocar código. Base del régimen por tipo de cotizante de H-F1-09 (aprendiz: lectiva = sin AFP). No mira lo que cotice otra entidad: el IBC de salud y de las demás no cambia."""
        self.ensure_one()
        if no_exigidas is None:
            no_exigidas = self._ne_afiliaciones_no_exigidas(fecha)
        tipo = contrato.l10n_co_pila_tipo_cotizante or ''
        subtipo = contrato.l10n_co_pila_subtipo_cotizante or ''
        return not any(
            clave_entidad == entidad and clave_tipo in ('*', tipo) and clave_subtipo in ('*', subtipo)
            for clave_tipo, clave_subtipo, clave_entidad in no_exigidas)

    def _ne_afiliaciones_faltantes(self, contrato, fecha):
        """H-F1-06 (doc 87): LO QUE FALTA de la afiliación a la seguridad social del empleado, como ``[(etiqueta, nivel)]`` (``nivel`` = ``'empleado'`` o ``'compañía'``); vacío si está completa.
        FUENTE ÚNICA del aviso del recibo, del error al confirmar y del mensaje del asiento; independiente de que las reglas tengan cuenta contable. Exige EPS y AFP del empleado, la Caja
        (la del empleado si la empresa la maneja por empleado, si no la general de la empresa) y la ARL de la compañía, SALVO lo que el parámetro versionado ``l10n_co_afiliaciones_no_exigidas``
        (``hr.rule.parameter``, lista de ``(tipo de cotizante, subtipo, entidad)`` con ``*`` de comodín) exceptúe para el tipo y el subtipo de cotizante del CONTRATO: nada de la norma está
        en el código. Los empleados de prueba de la habilitación DIAN no tienen afiliación real y no se validan."""
        self.ensure_one()
        if self.l10n_co_ne_is_habilitacion_test:
            return []
        no_exigidas = self._ne_afiliaciones_no_exigidas(fecha)

        def _exigida(entidad):
            return self._ne_entidad_exigida(entidad, contrato, fecha, no_exigidas)

        compania = self.company_id
        faltan = []
        if _exigida('eps') and not self.l10n_co_pila_eps_id:
            faltan.append((self._fields['l10n_co_pila_eps_id'].string, 'empleado'))
        if _exigida('afp') and not self.l10n_co_pila_afp_id:
            faltan.append((self._fields['l10n_co_pila_afp_id'].string, 'empleado'))
        if _exigida('ccf'):
            if compania.l10n_co_pila_ccf_por_empleado:
                if not self.l10n_co_pila_ccf_id:
                    faltan.append((self._fields['l10n_co_pila_ccf_id'].string, 'empleado'))
            elif not compania.l10n_co_pila_ccf_id:
                faltan.append((_('Caja de Compensación general de la empresa'), 'compañía'))
        if _exigida('arl') and not compania.l10n_co_pila_arl_id:
            faltan.append((compania._fields['l10n_co_pila_arl_id'].string, 'compañía'))
        return faltan

    def _ne_valor_obligatorio(self, campo):
        """Valor de un campo que el empleado debe tener para el XML: sin el, error claro."""
        self.ensure_one()
        valor = self[campo]
        if not valor:
            raise UserError(_(
                'El empleado %(empleado)s no tiene "%(campo)s" (pestaña Nómina). Elíjalo: nunca '
                'se asume un valor por defecto.',
                empleado=self.name, campo=self._fields[campo].string))
        return valor

    def _ne_medio_pago(self):
        """Medio de pago efectivo (código DIAN '1'/'2'/'10'): el del empleado y, si no tiene, el
        general de la empresa. Sin ninguno: UserError (nunca se asume Transferencia)."""
        self.ensure_one()
        metodo = self.l10n_co_ne_payment_method or self.company_id.l10n_co_ne_payment_method
        if not metodo:
            raise UserError(_(
                'No hay Medio de Pago para el empleado %(employee)s: ni el empleado ni la '
                'empresa %(company)s (Nómina > Configuración > Ajustes, bloque Parámetros '
                'Nómina Colombia) lo tienen configurado.',
                employee=self.name, company=self.company_id.name))
        return metodo

    def _l10n_co_nombre_dian(self):
        """Los 4 datos de nombre para XML/PILA/UGPP, desde los campos (única fuente).

        Primer nombre y primer apellido son obligatorios; el error nombra al empleado."""
        self.ensure_one()
        if not (self.l10n_co_primer_nombre and self.l10n_co_primer_apellido):
            raise UserError(_(
                'El empleado "%(employee)s" no tiene completos el Primer Nombre y el Primer '
                'Apellido. Complételos en la pestaña Nómina, grupo "Identificación DIAN", '
                'antes de continuar.', employee=self.name))
        return {clave: self[campo] or ''
                for clave, campo in self._L10N_CO_CAMPOS_NOMBRE.items()}

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
    def _ne_solo_colombia(self):
        """Los empleados de companias colombianas (ver res.company._ne_es_colombia)."""
        return self.filtered(lambda e: e.company_id._ne_es_colombia())

    @api.model
    def _ne_vals_son_colombia(self, vals):
        """La compania de unos valores de creacion (la del empleado o, sin ella, la activa)."""
        compania = self.env['res.company'].browse(
            vals.get('company_id') or self.env.company.id)
        return compania._ne_es_colombia()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._ne_vals_son_colombia(vals) and vals.get('name') and not any(
                    campo in vals for campo in self._L10N_CO_CAMPOS_NOMBRE.values()):
                vals.update(self._l10n_co_prellenar_nombre(vals['name']))
        employees = super().create(vals_list)
        for employee in employees._ne_solo_colombia():
            if (
                employee.identification_id
                and employee.work_contact_id
                and employee.work_contact_id.vat != employee.identification_id
            ):
                employee.work_contact_id.sudo().vat = employee.identification_id
        return employees

    def write(self, vals):
        # H-024: al renombrar se vuelve a prellenar solo a quien NO tenía los campos
        # editados a mano (iguales al prellenado de su nombre anterior, o vacíos).
        renombrar = {}
        if vals.get('name') and not any(
                campo in vals for campo in self._L10N_CO_CAMPOS_NOMBRE.values()):
            nuevos = self._l10n_co_prellenar_nombre(vals['name'])
            for employee in self._ne_solo_colombia():
                actuales = {c: employee[c] or '' for c in self._L10N_CO_CAMPOS_NOMBRE.values()}
                previos = self._l10n_co_prellenar_nombre(employee.name)
                if actuales == previos or not any(actuales.values()):
                    renombrar[employee.id] = nuevos
        res = super().write(vals)
        for employee_id, nuevos in renombrar.items():
            super(HrEmployee, self.browse(employee_id)).write(nuevos)
        if 'identification_id' in vals:
            for employee in self._ne_solo_colombia():
                if (
                    employee.identification_id
                    and employee.work_contact_id
                    and employee.work_contact_id.vat != employee.identification_id
                ):
                    employee.work_contact_id.sudo().vat = employee.identification_id
        return res

    # ──────────────────────────────────────────────────────────────────
    # Default del TIPO de identificación para empleados colombianos nuevos
    # (UX-02, 2026-10-11, decisión de David, punto 3 de la .93/.94). Hallazgo:
    # work_contact_id se crea en hr/models/hr_employee_base.py::
    # _create_work_contacts() con vals = {email, mobile, name, image_1920,
    # company_id} -- nunca incluye el tipo de identificación, así que el
    # campo cae siempre en su default de CLASE
    # (l10n_latam_base/models/res_partner.py:
    # default=lambda self: self.env.ref('l10n_latam_base.it_vat')), el tipo
    # genérico "VAT", que no tiene (a propósito) código DIAN. El
    # @api.onchange('country_id') de ese mismo archivo no ayuda: solo corre
    # en formularios UI (nunca en create() por ORM) y, aunque corriera,
    # elegiría NIT (l10n_co.rut, el único tipo colombiano con is_vat=True en
    # l10n_co/data/l10n_latam.identification.type.csv), no Cédula.
    #
    # David decidió que, en la práctica, casi todos los empleados
    # colombianos son Cédula de ciudadanía -- ese debe ser el valor INICIAL,
    # no "VAT" (que ni es un tipo de documento real). Es un default, no un
    # constraint: el usuario sigue pudiendo cambiarlo a mano después. Nunca
    # toca un contacto que ya tenga otro tipo -- este método solo procesa
    # contactos RECIÉN creados, nunca uno existente -- ver también el
    # backfill equivalente para los contactos que ya existían antes de este
    # cambio, en migrations/18.0.3.0.89/post-sync_identification_number.py.
    # ──────────────────────────────────────────────────────────────────
    def _create_work_contacts(self):
        super()._create_work_contacts()
        it_vat = self.env.ref('l10n_latam_base.it_vat', raise_if_not_found=False)
        cedula = self.env.ref('l10n_co.national_citizen_id', raise_if_not_found=False)
        if not it_vat or not cedula:
            return
        for employee in self:
            partner = employee.work_contact_id
            if not partner or employee.company_id.partner_id.country_id.code != 'CO':
                continue
            tipo_actual = partner.l10n_latam_identification_type_id
            if not tipo_actual or tipo_actual == it_vat:
                partner.sudo().l10n_latam_identification_type_id = cedula.id

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
        selection=NE_MEDIOS_PAGO,
        string='Método de Pago',
        help='Solo si este empleado se paga distinto al medio general de la empresa '
             '(Nómina > Configuración > Ajustes). Vacío: se usa el general. Se refleja en el '
             'atributo Metodo del nodo <Pago> del XML. La cuenta bancaria se elige en '
             '"Información privada" (Cuenta Bancaria).',
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
    # .302 (doc 76 §2.3): pactos de desalarización del empleado (modelo l10n.co.employee.pacto)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pacto_ids = fields.One2many(
        'l10n.co.employee.pacto', 'employee_id', string='Pactos de desalarización', copy=False,
        help='Pactos escritos de desalarización del empleado (art. 128 CST y art. 17 Ley 344/1996): uno por concepto no salarial pactado, con su fecha de firma, fecha de fin '
             'opcional y el documento firmado. Cubren los recibos cuyo «Hasta» cae entre la firma y el fin, aunque el contrato se renueve.')

    # ──────────────────────────────────────────────────────────────────
    # PILA — Administradoras de Seguridad Social
    # ──────────────────────────────────────────────────────────────────
    # H-F1-06 (doc 87): ``tracking=True`` en las tres afiliaciones: el chatter del empleado deja quién cambió cuál y cuándo.
    l10n_co_pila_eps_id = fields.Many2one(
        'res.partner', string='EPS',
        domain=[('l10n_co_entity_type', '=', 'eps')], tracking=True,
        help='Contacto de la EPS del empleado. El código PILA se toma del '
             'contacto.',
    )
    l10n_co_pila_afp_id = fields.Many2one(
        'res.partner', string='AFP',
        domain=[('l10n_co_entity_type', '=', 'afp')], tracking=True,
        help='Contacto del Fondo de Pensiones del empleado. También es el '
             'tercero del Fondo de Solidaridad Pensional.',
    )
    l10n_co_pila_ccf_id = fields.Many2one(
        'res.partner', string='Caja de Compensación',
        domain=[('l10n_co_entity_type', '=', 'ccf')], tracking=True,
        help='Contacto de la Caja de Compensación Familiar del empleado.',
    )
    l10n_co_pila_ccf_por_empleado = fields.Boolean(
        related='company_id.l10n_co_pila_ccf_por_empleado', string='Caja por empleado')
    l10n_co_pila_eps_code = fields.Char(
        string='Código EPS', related='l10n_co_pila_eps_id.l10n_co_pila_entity_code',
        help='Código PILA derivado del contacto de la EPS.',
    )
    l10n_co_pila_afp_code = fields.Char(
        string='Código AFP', related='l10n_co_pila_afp_id.l10n_co_pila_entity_code',
        help='Código PILA derivado del contacto de la AFP.',
    )
    l10n_co_pila_ccf_code = fields.Char(
        string='Código CCF', related='l10n_co_pila_ccf_id.l10n_co_pila_entity_code',
        help='Código PILA derivado del contacto de la Caja de Compensación.',
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

    # H-021 (2026-11-09): aquí vivía @api.constrains('l10n_co_ne_payment_method',
    # 'bank_account_id') (_check_bank_account_for_transfer). Corría en CADA guardado, incluido
    # el primero: como l10n_co_ne_payment_method tiene default '1' (Transferencia), un empleado
    # nuevo no podía guardarse sin cuenta bancaria. La cuenta solo hace falta para armar el
    # nodo <Pago> del XML, así que la exigencia vive donde se usa:
    # hr.payslip._ne_validar_cuenta_transferencia(), llamada desde _ne_pago() y desde
    # _validate_ne_prerequisites() (antes de gastar el consecutivo).
