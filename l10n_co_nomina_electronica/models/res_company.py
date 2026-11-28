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
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import convert
from odoo.tools.misc import str2bool

from ..services import dian_utils, nomina_xml_builder

# Selecciones compartidas entre la empresa (valor general) y el contrato/empleado (excepción).
NE_CLASES_RIESGO = [
    ('1', 'I - Riesgo Mínimo'),
    ('2', 'II - Riesgo Bajo'),
    ('3', 'III - Riesgo Medio'),
    ('4', 'IV - Riesgo Alto'),
    ('5', 'V - Riesgo Máximo'),
]
NE_MEDIOS_PAGO = [
    ('1', 'Transferencia Bancaria'),
    ('2', 'Cheque'),
    ('10', 'Efectivo'),
]


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

    # Plantillas de las secuencias de nomina electronica (datos del modulo, company_id vacio): solo
    # se copian para crear la de cada compania; ninguna compania las usa directamente. El consecutivo
    # DIAN se autoriza por NIT, asi que cada compania colombiana lleva el suyo (M1, doc 51).
    _NE_SECUENCIAS = (
        ('l10n_co_ne_sequence_id', 'l10n_co_nomina_electronica.seq_l10n_co_nomina_electronica'),
        ('l10n_co_ne_pre_sequence_id', 'l10n_co_nomina_electronica.seq_l10n_co_nomina_temporal'),
        (None, 'l10n_co_nomina_electronica.seq_l10n_co_nomina_ajuste'),
    )

    def _ne_crear_secuencia_propia(self, plantilla, siguiente=1):
        """Copia propia de la plantilla para esta compania, con el siguiente numero indicado."""
        self.ensure_one()
        return self.env['ir.sequence'].sudo().create({
            'name': '%s (%s)' % (plantilla.name, self.name),
            'code': plantilla.code, 'implementation': plantilla.implementation,
            'prefix': plantilla.prefix, 'suffix': plantilla.suffix,
            'padding': plantilla.padding, 'number_increment': plantilla.number_increment,
            'number_next': siguiente, 'company_id': self.id})

    def _ne_asegurar_secuencias(self):
        """A cada compania colombiana sin secuencia de nomina electronica (consecutivo, temporal,
        ajuste) le crea la suya, empezando en 1. No toca las que ya tienen (ni crea nada para una
        compania de otro pais)."""
        for company in self:
            if not company._ne_es_colombia():
                continue
            for campo, xmlid in self._NE_SECUENCIAS:
                plantilla = self.env.ref(xmlid, raise_if_not_found=False)
                if not plantilla:
                    continue
                if campo:
                    if not company[campo]:
                        company.sudo()[campo] = company._ne_crear_secuencia_propia(plantilla)
                elif not self.env['ir.sequence'].sudo().search_count([
                        ('code', '=', plantilla.code), ('company_id', '=', company.id)]):
                    company._ne_crear_secuencia_propia(plantilla)

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._ne_asegurar_secuencias()
        return companies

    def _ne_valor_obligatorio(self, campo):
        """Valor de configuracion de la compania que se necesita para generar un archivo (PILA):
        sin el, error claro nombrando compania y campo (nunca un valor por defecto)."""
        self.ensure_one()
        valor = self[campo]
        if not valor:
            raise UserError(_(
                'La compañía "%(company)s" no tiene "%(campo)s" configurado (Nómina > '
                'Configuración > Ajustes, bloque PILA). Elíjalo antes de generar la planilla.',
                company=self.name, campo=self._fields[campo].string))
        return valor

    def _ne_en_produccion(self):
        """Producción real de nómina electrónica: ambiente 1 y sin proceso de certificación. Aquí se reporta por
        DOCUMENTO mensual; el ciclo por recibo solo sigue vivo en habilitación (doc 53 §27.1, D-5h)."""
        self.ensure_one()
        return self.l10n_co_ne_environment == '1' and not self.l10n_co_ne_certification_process

    def _ne_exigir_colombia(self):
        """Error claro si la compania no es colombiana: los asistentes de nomina colombiana (PILA,
        UGPP, habilitacion DIAN, consulta por CUNE) trabajan con la compania del registro y solo para
        companias de Colombia."""
        for company in self:
            if not company._ne_es_colombia():
                raise UserError(_(
                    'La compañía "%(company)s" no es colombiana: esta opción solo aplica a '
                    'compañías de Colombia. Cambie de compañía en el selector superior o '
                    'verifique el país de la compañía (Ajustes > Compañías).',
                    company=company.name))

    def _ne_es_colombia(self):
        """True si la compania es colombiana. Unica comprobacion de pais del modulo: lo propio de la
        nomina colombiana (numeracion, validaciones, sincronizacion de identificacion, IBC, piso
        integral) solo corre para companias de Colombia, de modo que una compania de otro pais
        (p. ej. Mexico) que comparta la base no se ve afectada."""
        self.ensure_one()
        return self.partner_id.country_id.code == 'CO'

    def _get_ne_certificate(self):
        """Certificado usado para firmar nómina electrónica.

        Mismo criterio que Facturación Electrónica (l10n_co_dian):
        el último certificado de la lista de la compañía (``certificates_sudo[-1]``), sin campo
        de selección explícita aparte.

        H-F2-03 (defecto previo, decisión del TL del 22-nov): se lee con ``sudo``, SOLO el de la compañía
        ``self``. ``certificate.certificate`` da permiso de acceso únicamente a ``base.group_system``
        (``addons/certificate/security/ir.model.access.csv``), así que sin ``sudo`` el administrador de nómina,
        que no es del sistema, no podía validar la configuración ni firmar. El ``sudo`` NO abre el modelo: nadie
        más lee ``certificate.certificate`` directamente (la prueba lo confirma). El registro se devuelve (con
        ``sudo``) únicamente a la validación de la configuración (``_l10n_co_ne_validar_config``) y a los
        cargadores de la llave para firmar (``xml_signer.load_from_certificate``, en el mixin del recibo y en el
        documento mensual): el método es privado (no se llama por RPC) y ningún campo, vista ni informe lo devuelve.
        Quién puede GENERAR o TRANSMITIR lo decide ``_ne_exigir_administrador_de_nomina``, no este permiso.
        """
        self.ensure_one()
        return self.sudo().l10n_co_ne_certificate_ids[-1:]

    def _l10n_co_ne_validar_config(self):
        """Valida la configuración de nómina electrónica DIAN de la compañía.

        Antes vivía en ``HrPayslip._validate_company_ne_config(company)`` (mixin del recibo) y solo
        usaba los datos de la compañía; el documento mensual la necesita sin depender del recibo
        (doc 53 §23.12-§23.13). El mixin conserva su nombre como envoltorio delgado que llama aquí:
        mismos chequeos, mismo orden y mismos mensajes.

        Raises:
            UserError: faltan datos (software, PIN, certificado), el certificado está vencido o la
                moneda no es COP.
        """
        self.ensure_one()
        company = self
        missing = []
        mode = company.l10n_co_ne_operation_mode_ids
        if not mode or not mode.software_id:
            missing.append(_('ID Software Nómina'))
        if not mode or not mode._ne_pin_del_software():
            missing.append(_('PIN Software Nómina'))
        if not company._get_ne_certificate():
            missing.append(_('Certificado Digital'))
        if missing:
            raise UserError(_(
                'Faltan los siguientes datos de configuración de nómina '
                'electrónica en la empresa %s:\n• %s',
                company.name,
                '\n• '.join(missing),
            ))

        certificate = company._get_ne_certificate()
        if certificate and certificate.date_end and certificate.date_end < fields.Datetime.now():
            raise UserError(_(
                'El certificado digital de la empresa %s está vencido '
                '(venció el %s). Cargue o seleccione un certificado '
                'vigente antes de continuar.',
                company.name,
                certificate.date_end,
            ))

        # AUD-DIAN-34 (2026-10-05): el Anexo Técnico (NIE030) es explícito -- "Para Colombia
        # se debe colocar 'COP'" en TipoMoneda, sin excepción. No se parametriza: es una
        # constante del Anexo (nomina_xml_builder.NE_TIPO_MONEDA), así que una compañía en
        # otra moneda debe fallar aquí, antes de generar un XML inválido, en vez de enviar
        # "COP" por encima de montos que en realidad están en otra moneda.
        if company.currency_id.name != nomina_xml_builder.NE_TIPO_MONEDA:
            raise UserError(_(
                'La compañía %(company)s tiene moneda "%(currency)s" configurada, pero la '
                'Nómina Electrónica DIAN exige TipoMoneda="%(cop)s" (Anexo Técnico, NIE030: '
                '"Para Colombia se debe colocar \'%(cop)s\'"). Configure la compañía en '
                'pesos colombianos antes de generar nómina electrónica.',
                company=company.name, currency=company.currency_id.name,
                cop=nomina_xml_builder.NE_TIPO_MONEDA,
            ))

    # ──────────────────────────────────────────────────────────────────
    # DIAN — URLs y tiempos configurables (AUD-DIAN-34, 2026-10-05)
    # ──────────────────────────────────────────────────────────────────
    # Único punto para que services/soap_client.py, services/dian_utils.py y este modelo
    # no mantengan cada uno su propia copia de las URL de la DIAN (antes repetidas en 3
    # sitios) ni de los tiempos fijos (SOAP_TIMEOUT, tick/timeout del motor de
    # habilitación). Los valores por defecto son los que ya estaban hardcodeados -- ningún
    # comportamiento cambia al instalar esto. Sobrescribibles vía ir.config_parameter
    # (Ajustes > Técnico > Parámetros del Sistema, valor inicial en data/ir_config_
    # parameter_dian_data.xml, noupdate=1) sin tocar código ni re-desplegar.

    def _ne_dian_endpoint(self, environment=None):
        """URL del servicio SOAP de la DIAN. ``environment`` por defecto es el de la
        compañía; se puede forzar (ej. envíos de set de pruebas, siempre habilitación)."""
        self.ensure_one()
        env = environment or self.l10n_co_ne_environment
        override = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_co_nomina_electronica.dian_soap_endpoint_%s' % env)
        return dian_utils.get_soap_endpoint(env, override=override)

    def _ne_dian_qr_host(self, environment=None):
        """Host del catálogo DIAN para la URL del CodigoQR (Anexo Técnico, sección QRCode)."""
        self.ensure_one()
        env = environment or self.l10n_co_ne_environment
        override = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_co_nomina_electronica.dian_qr_host_%s' % env)
        return dian_utils.get_qr_catalog_host(env, override=override)

    def _ne_config_int_param(self, key, default):
        """Lee un parámetro entero positivo de ir.config_parameter bajo ``key`` -- usado
        para los timeouts configurables (SOAP_TIMEOUT, tick/timeout de habilitación). Valor
        ausente o inválido -> ``default`` con un _logger.warning (ver dian_utils.
        parse_positive_int): una configuración mal escrita nunca debe reventar un envío."""
        raw = self.env['ir.config_parameter'].sudo().get_param(key)
        return dian_utils.parse_positive_int(raw, default, key)

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

    # Estado del proceso automático de habilitación DIAN (ver
    # models/l10n_co_ne_habilitacion.py). El avance por documento no se guarda
    # aquí: se calcula contando las nóminas del set (l10n_co_ne_hab_set_id).
    l10n_co_ne_hab_state = fields.Selection(
        selection=[
            ('idle', 'Sin iniciar'),
            ('running', 'En proceso'),
            ('done', 'Completada'),
            ('error', 'Detenida'),
        ],
        string='Estado de la habilitación DIAN',
        default='idle',
        copy=False,
    )
    l10n_co_ne_hab_message = fields.Char(string='Último mensaje de habilitación', copy=False)
    l10n_co_ne_hab_user_id = fields.Many2one(
        'res.users', string='Usuario que inició la habilitación', copy=False,
    )
    l10n_co_ne_hab_started = fields.Datetime(string='Inicio de la habilitación', copy=False)

    # ──────────────────────────────────────────────────────────────────
    # Localización nómina (.99, pedido de David): paquete de nómina
    # electrónica instalado, visible en Ajustes > Nómina como la
    # "Localización fiscal" de Contabilidad (chart_template). hr_payroll
    # no tiene un framework de plantillas equivalente al de account
    # (confirmado con Tech Lead contra el servidor) -- este campo calca
    # el PATRÓN VISUAL de Accounting, no reusa un mecanismo nativo de
    # Nómina que no existe.
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_payroll_package = fields.Selection(
        selection='_selection_l10n_co_ne_payroll_package',
        string='Paquete de Nómina',
        help='Localización de nómina electrónica instalada para este país.',
    )

    @api.model
    def _selection_l10n_co_ne_payroll_package(self):
        return [('l10n_co_nomina_electronica', _('Colombia'))]

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
        # AUD-DIAN-34 (2026-10-04): dominio restringido al código EXACTO
        # tras un bug real en producción (Guapante) -- el dominio amplio
        # "like 'l10n_co_nomina.'" permitía elegir por error la secuencia
        # de Notas de Ajuste (l10n_co_nomina.ajuste, prefijo NA) como si
        # fuera esta, generando nóminas individuales con consecutivo
        # NA-prefijado que la DIAN rechazó (NIE011/NIE012).
        domain="[('code', '=', 'l10n_co_nomina.electronica')]",
        help='Secuencia definitiva utilizada para generar los consecutivos de transmisión DIAN (ej: NE-00001).',
    )
    l10n_co_ne_pre_sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Secuencia Nómina Temporal',
        # AUD-DIAN-34 (2026-10-04): ver nota en l10n_co_ne_sequence_id --
        # mismo incidente real: esta quedó apuntando a la secuencia de
        # Notas de Ajuste (NA) en vez de la Temporal (PRE-NOM) en
        # producción y en staging.
        domain="[('code', '=', 'l10n_co_nomina.temporal')]",
        help='Secuencia temporal utilizada para borradores y nóminas pendientes de validación (ej: PRE-NOM-00001).',
    )

    # ──────────────────────────────────────────────────────────────────
    # .304 (doc 77, diseño del TL aprobado el 22-nov): protección de consecutivos de nómina electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_ultimo_nomina = fields.Integer(
        string='Último consecutivo de nómina que viajó (control manual)', default=0,
        help='Número (solo la parte numérica, sin el prefijo) del último documento de nómina electrónica que viajó a la DIAN en el ambiente actual de la compañía. 0 = sin control '
             'manual: solo cuenta lo que la base ya conoce. Es la única defensa tras restaurar una copia de la base: lo enviado DESPUÉS del respaldo no está en ella. Si la secuencia '
             'queda por debajo de este número o de cualquier número ya enviado, no se genera un consecutivo (la DIAN rechaza un número repetido con el veredicto viejo).')
    l10n_co_ne_ultimo_ajuste = fields.Integer(
        string='Último consecutivo de nota de ajuste que viajó (control manual)', default=0,
        help='Igual que el de nómina, para las notas de ajuste (otro prefijo, otra secuencia). 0 = sin control manual.')
    l10n_co_ne_consecutivos_usados = fields.Integer(string='Consecutivos usados', compute='_compute_ne_consecutivos_contadores')
    l10n_co_ne_consecutivos_rechazados = fields.Integer(string='Consecutivos rechazados', compute='_compute_ne_consecutivos_contadores')

    def _compute_ne_consecutivos_contadores(self):
        """Contadores informativos de Ajustes: números que viajaron a la DIAN en el ambiente actual y cuántos fueron rechazados (de ``l10n.co.ne.consecutivo``)."""
        Consecutivo = self.env['l10n.co.ne.consecutivo'].sudo()
        for compania in self:
            dominio = [('company_id', '=', compania.id), ('ambiente', '=', compania._ne_ambiente_consecutivos() if compania.id else 'habilitacion')]
            compania.l10n_co_ne_consecutivos_usados = Consecutivo.search_count(dominio) if compania.id else 0
            compania.l10n_co_ne_consecutivos_rechazados = Consecutivo.search_count(dominio + [('estado', '=', 'rechazado')]) if compania.id else 0

    def _ne_ambiente_consecutivos(self):
        """``'produccion'`` si la compañía reporta en producción real (``_ne_en_produccion``) y ``'habilitacion'`` en cualquier otro caso: los números de habilitación no
        cuentan contra los de producción (la DIAN los lleva por ambiente)."""
        self.ensure_one()
        return 'produccion' if self._ne_en_produccion() else 'habilitacion'

    def _ne_prefijo_consecutivo(self, es_ajuste):
        """Prefijo del consecutivo de la compañía: el de ajuste para una nota, el de nómina para un original. Sin prefijo es un error claro: no se inventa uno (antes caía en 'NE'
        o 'NA' en silencio, .304)."""
        self.ensure_one()
        prefijo = self.l10n_co_ne_adjust_prefix if es_ajuste else self.l10n_co_ne_payroll_prefix
        if not prefijo or not prefijo.strip():
            raise UserError(_(
                'La compañía "%(compania)s" no tiene prefijo de %(que)s. Configúrelo en Ajustes > Nómina (%(campo)s) antes de generar el documento.',
                compania=self.name, que=_('notas de ajuste') if es_ajuste else _('nómina electrónica'),
                campo=_('Prefijo Nota de Ajuste') if es_ajuste else _('Prefijo Nómina')))
        return prefijo

    def _ne_secuencia_consecutivo(self, es_ajuste):
        """Secuencia del consecutivo: la de notas de ajuste (código ``l10n_co_nomina.ajuste``, primero la de la compañía y luego la sin compañía) o la de nómina de la compañía.
        Sin secuencia es un error claro: no hay fallback silencioso (.304)."""
        self.ensure_one()
        if es_ajuste:
            secuencia = self.env['ir.sequence'].search([
                ('code', '=', 'l10n_co_nomina.ajuste'), '|', ('company_id', '=', self.id), ('company_id', '=', False)], order='company_id', limit=1)
            if not secuencia:
                raise UserError(_(
                    'La compañía "%(compania)s" no tiene secuencia de notas de ajuste de nómina electrónica (código l10n_co_nomina.ajuste). Configúrela antes de generar la nota.',
                    compania=self.name))
            return secuencia
        if not self.l10n_co_ne_sequence_id:
            raise UserError(_(
                'La compañía "%(compania)s" no tiene secuencia de nómina electrónica. Configúrela en Ajustes > Nómina antes de generar el documento.', compania=self.name))
        return self.l10n_co_ne_sequence_id

    def _ne_mayor_consecutivo_viajado(self, es_ajuste):
        """Mayor número (solo la parte numérica) con el prefijo de este tipo que YA VIAJÓ a la DIAN en el ambiente actual de la compañía (aceptado, rechazado, pendiente), según
        ``l10n.co.ne.consecutivo``, y el control manual de Ajustes; 0 si no hay ninguno. Los números de habilitación no cuentan en producción y los PRE-NOM temporales nunca viajan."""
        self.ensure_one()
        prefijo = self._ne_prefijo_consecutivo(es_ajuste)
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT COALESCE(MAX(valor), 0) FROM l10n_co_ne_consecutivo WHERE company_id = %s AND ambiente = %s AND prefijo = %s AND estado <> %s',
            (self.id, self._ne_ambiente_consecutivos(), prefijo, 'fallido'))
        de_la_base = self.env.cr.fetchone()[0] or 0
        manual = (self.l10n_co_ne_ultimo_ajuste if es_ajuste else self.l10n_co_ne_ultimo_nomina) or 0
        return max(de_la_base, manual)

    def _ne_mayor_consecutivo_asignado(self, es_ajuste):
        """Mayor número con el prefijo ASIGNADO a un recibo, nota o documento mensual de la compañía (haya viajado o no): para decir cuál es el siguiente disponible cuando el que
        da la secuencia ya está en uso. Los PRE-NOM no empiezan con este prefijo."""
        self.ensure_one()
        prefijo = self._ne_prefijo_consecutivo(es_ajuste)
        self.env.flush_all()
        self.env.cr.execute("""
            SELECT COALESCE(MAX(valor), 0) FROM (
                SELECT NULLIF(substring(l10n_co_ne_consecutive FROM '(\\d+)$'), '')::bigint AS valor
                  FROM hr_payslip WHERE company_id = %(c)s AND l10n_co_ne_consecutive LIKE %(p)s
                 UNION ALL
                SELECT NULLIF(substring(consecutive FROM '(\\d+)$'), '')::bigint AS valor
                  FROM l10n_co_ne_documento WHERE company_id = %(c)s AND consecutive LIKE %(p)s
            ) x""", {'c': self.id, 'p': prefijo.replace('%', '\\%').replace('_', '\\_') + '%'})
        return max(self.env.cr.fetchone()[0] or 0, self._ne_mayor_consecutivo_viajado(es_ajuste))

    def _ne_tomar_consecutivo(self, es_ajuste):
        """UNICA función que toma el siguiente consecutivo oficial de nómina electrónica (recibo, nota de ajuste y documento mensual; .304, doc 77 con las decisiones del TL):
        1. Sin secuencia o sin prefijo: error claro (C: no hay fallback).
        2. Control B: si el siguiente número de la secuencia es menor o igual al mayor que YA VIAJÓ a la DIAN en este ambiente (o al control manual de Ajustes), error que nombra
           la secuencia y el valor que debe tener; NO se corrige sola. La secuencia nunca vuelve a dar un número que viajó, también el rechazado (un documento mensual rechazado conserva el SUYO sin pasar
           por aquí: ``l10n.co.ne.documento._ne_numero_se_conserva``).
        3. Control A: el número que daría la secuencia no puede estar ya asignado a otro recibo, nota o documento de la compañía (error claro, no el IntegrityError de la restricción).
        Recién entonces consume la secuencia (no_gap: un fallo posterior la devuelve con el rollback)."""
        self.ensure_one()
        prefijo = self._ne_prefijo_consecutivo(es_ajuste)
        secuencia = self._ne_secuencia_consecutivo(es_ajuste)
        siguiente = self._ne_numero_siguiente(secuencia)
        maximo = self._ne_mayor_consecutivo_viajado(es_ajuste)
        if siguiente <= maximo:
            raise UserError(_(
                'La secuencia "%(secuencia)s" (código %(codigo)s) de la compañía "%(compania)s" va en %(siguiente)s, pero el consecutivo %(maximo)s ya viajó a la DIAN en %(ambiente)s '
                '(o es el último que se anotó en Ajustes > Nómina, «Último consecutivo que viajó»). La DIAN rechaza un número repetido con el veredicto viejo (regla 90). Cambie «Siguiente '
                'número» de esa secuencia a %(sugerido)s (Ajustes > Técnico > Secuencias); no se corrige sola. Consulte los números usados en Nómina > Consecutivos de nómina.',
                secuencia=secuencia.name, codigo=secuencia.code, compania=self.name, siguiente=siguiente, maximo=maximo,
                ambiente=_('producción') if self._ne_ambiente_consecutivos() == 'produccion' else _('habilitación'), sugerido=maximo + 1))
        asignado = self._ne_mayor_consecutivo_asignado(es_ajuste)
        if siguiente <= asignado and self._ne_consecutivo_asignado(secuencia.get_next_char(siguiente)):
            raise UserError(_(
                'La secuencia "%(secuencia)s" (código %(codigo)s) de la compañía "%(compania)s" daría el consecutivo %(numero)s, que ya está asignado a otro documento de la compañía. '
                'El siguiente disponible es %(disponible)s: cambie «Siguiente número» de esa secuencia a %(sugerido)s (Ajustes > Técnico > Secuencias); no se corrige sola.',
                secuencia=secuencia.name, codigo=secuencia.code, compania=self.name, numero=secuencia.get_next_char(siguiente), disponible=secuencia.get_next_char(asignado + 1),
                sugerido=asignado + 1))
        numero = secuencia.next_by_id()
        secuencia.invalidate_recordset(['number_next_actual'])      # el consumo (SQL) no invalida lo que leyó el control: la próxima lectura, aun en esta transacción, ve el siguiente
        return numero

    @api.model
    def _ne_numero_siguiente(self, secuencia):
        """Siguiente número de la secuencia, leído de la base y no de la caché de la transacción. ``ir.sequence._get_number_next_actual`` no declara dependencias: ``number_next_actual``
        queda en la caché y ``next_by_id`` (``_update_nogap``) solo invalida ``number_next``, así que con varios documentos en la MISMA transacción (generar el XML de varios recibos o
        documentos, o las pruebas) el segundo leía el mismo número que el primero y el control A lo daba por «ya asignado» (N2 «cv»: 16 errores y 14 fallos de ahí)."""
        secuencia.invalidate_recordset(['number_next', 'number_next_actual'])
        return secuencia.number_next_actual

    def _ne_numero_en_otro(self, numero, payslip=None, documento=None):
        """True si ``numero`` ya viajó a la DIAN, en el ambiente actual, en OTRO recibo, nota o documento mensual de la compañía. El propio no cuenta contra sí mismo; un envío fallido, tampoco."""
        self.ensure_one()
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT numero, origen FROM l10n_co_ne_consecutivo WHERE company_id = %(c)s AND ambiente = %(a)s AND numero = %(n)s AND estado <> %(f)s '
            'AND NOT (origen = %(r)s AND payslip_id = %(p)s) AND NOT (origen = %(d)s AND documento_id = %(doc)s) LIMIT 1',
            {'c': self.id, 'a': self._ne_ambiente_consecutivos(), 'n': numero, 'f': 'fallido', 'r': 'recibo', 'p': payslip.id if payslip else 0,
             'd': 'documento', 'doc': documento.id if documento else 0})
        return bool(self.env.cr.fetchone())

    def _ne_exigir_numero_sin_viajar(self, numero, es_ajuste, payslip=None, documento=None):
        """Control A antes de ENVIAR (.304): el número de este documento no puede haber viajado ya, en este ambiente, en OTRO recibo, nota o documento mensual de la compañía (la DIAN
        devuelve el veredicto viejo o lo rechaza). El mismo documento no cuenta contra sí mismo. Error claro que dice cuál es el siguiente disponible; no corrige nada."""
        self.ensure_one()
        if self._ne_numero_en_otro(numero, payslip=payslip, documento=documento):
            secuencia = self._ne_secuencia_consecutivo(es_ajuste)
            siguiente = self._ne_mayor_consecutivo_asignado(es_ajuste) + 1
            raise UserError(_(
                'El consecutivo %(numero)s ya viajó a la DIAN en %(ambiente)s en otro documento de la compañía "%(compania)s": no se envía otra vez con ese número (consulte Nómina > '
                'Consecutivos de nómina). El siguiente disponible es %(disponible)s: genere el XML otra vez después de ajustar «Siguiente número» de la secuencia "%(secuencia)s" a %(sugerido)s.',
                numero=numero, ambiente=_('producción') if self._ne_ambiente_consecutivos() == 'produccion' else _('habilitación'), compania=self.name,
                disponible=secuencia.get_next_char(siguiente), secuencia=secuencia.name, sugerido=siguiente))

    def _ne_consecutivo_asignado(self, numero):
        """¿Ya hay un recibo, nota o documento mensual de la compañía con ESTE número exacto?"""
        self.ensure_one()
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT 1 FROM hr_payslip WHERE company_id = %(c)s AND l10n_co_ne_consecutive = %(n)s UNION ALL SELECT 1 FROM l10n_co_ne_documento WHERE company_id = %(c)s AND consecutive = %(n)s LIMIT 1',
            {'c': self.id, 'n': numero})
        return bool(self.env.cr.fetchone())

    # ──────────────────────────────────────────────────────────────────
    # Campos UGPP – Clasificación del aportante
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_representante_legal_id = fields.Many2one(
        'res.partner', string='Representante legal',
        help='Contacto que firma los oficios de la compañía ante entidades (hoy, el oficio de respuesta a la UGPP). Su '
             'nombre y su identificación salen de Contactos: no se digitan aparte. Odoo no trae este dato en la '
             'compañía ni en la localización colombiana.')

    # Listas de la Guía UGPP V-20.1 (p. 15): el código de cada opción sale de ``_UGPP_NATURALEZA`` / ``_UGPP_TIPO_APORTANTE``
    # en models/l10n_co_nomina_ugpp.py (formulario 7001, columnas 16 y 20).
    l10n_co_ugpp_legal_nature = fields.Selection(
        selection=[
            ('publica', 'Pública'),
            ('privada', 'Privada'),
            ('mixta', 'Mixta'),
            ('organismo_multilateral', 'Organismos multilaterales'),
            ('publica_extranjera', 'Entidades de derecho público no sometidas a la legislación colombiana'),
        ],
        string='Naturaleza Jurídica',
        help='Naturaleza jurídica del aportante según la Guía UGPP V-20.1 (formulario nómina-aportante, campo 16). '
             'Obligatoria para el reporte UGPP.',
    )
    l10n_co_ugpp_contributor_type = fields.Selection(
        selection=[
            ('empleador', 'Empleador'),
            ('entidad_publica_especial', 'Entidades o universidades públicas de los regímenes especial y de excepción'),
            ('agremiacion', 'Agremiaciones, asociaciones o congregaciones religiosas'),
            ('cooperativa', 'Cooperativas y precooperativas de trabajo asociado'),
            ('mision_diplomatica', 'Misiones diplomáticas, consulares o de organismos multilaterales no sometidos a '
                                   'la legislación colombiana'),
            ('hogares_bienestar', 'Organizaciones administradoras del programa de hogares de bienestar'),
            ('pagador_concejales', 'Pagador de aportes de los concejales municipales o distritales o de los ediles '
                                   'de las juntas administradoras locales'),
            ('pagador_sindical', 'Pagador de aportes contrato sindical'),
            ('pagador_reincorporacion', 'Pagador programa de reincorporación'),
            ('pagador_magisterio', 'Pagador aportes parafiscales del Magisterio'),
            ('pagador_humanitaria', 'Pagador prestación humanitaria'),
        ],
        string='Tipo de Aportante',
        help='Tipo de aportante según la Guía UGPP V-20.1 (formulario nómina-aportante, campo 20). Obligatorio para '
             'el reporte UGPP.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Parámetros de Nómina Colombiana
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_exoneration_1607 = fields.Boolean(
        string='Exoneración Ley 1607/2012',
        default=False,
        help='Si la empresa es persona jurídica del régimen contributivo, '
             'queda exonerada de aportes a SENA e ICBF para empleados '
             'con salario inferior a 10 SMMLV (Art. 114-1 ET). También alimenta la '
             'columna "Autorretención especial" del formato de pagos UGPP (Guía V-20.1: '
             '"SI" si está exonerado del pago de aportes parafiscales según el art. 114-1 ET).',
    )

    l10n_co_ne_pension_patronal_sln = fields.Boolean(
        string='Cotizar pensión patronal en licencia no remunerada',
        default=True,
        help='En los días de suspensión o licencia no remunerada (SLN) el empleador paga '
             'salud sobre la base de continuidad; la pensión patronal sobre esos días es '
             'opcional en el sector privado (Concepto Min. Protección Social 134658, CST '
             'art. 53). Si se desmarca, nómina y PILA no cotizan pensión sobre los días SLN. '
             'El trabajador no paga su cuota sobre esos días en ningún caso.',
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
    )
    l10n_co_pila_arl_id = fields.Many2one(
        'res.partner', string='ARL',
        domain=[('l10n_co_entity_type', '=', 'arl')],
        help='Contacto de la ARL a la que está afiliada la empresa. La '
             'afiliación es de toda la compañía; el código PILA se toma del '
             'contacto.',
    )
    l10n_co_pila_arl_code = fields.Char(
        string='Código ARL', related='l10n_co_pila_arl_id.l10n_co_pila_entity_code',
        help='Código PILA derivado del contacto de la ARL (ej: 14-11).',
    )
    l10n_co_pila_arl_name = fields.Char(
        string='Nombre ARL', related='l10n_co_pila_arl_id.display_name',
        help='Nombre del contacto de la ARL.',
    )
    l10n_co_sena_partner_id = fields.Many2one(
        'res.partner', string='SENA',
        domain=[('l10n_co_entity_type', '=', 'sena')],
        help='Contacto al que se causa el aporte parafiscal al SENA.',
    )
    l10n_co_icbf_partner_id = fields.Many2one(
        'res.partner', string='ICBF',
        domain=[('l10n_co_entity_type', '=', 'icbf')],
        help='Contacto al que se causa el aporte parafiscal al ICBF.',
    )
    l10n_co_dian_partner_id = fields.Many2one(
        'res.partner', string='DIAN',
        domain=[('l10n_co_entity_type', '=', 'dian')],
        help='Contacto de la DIAN, tercero de la retención en la fuente.',
    )
    l10n_co_pila_forma_presentacion = fields.Selection(
        selection=[
            ('U', 'Único'),
            ('S', 'Sucursal'),
        ],
        string='Forma Presentación PILA',
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
    # H-161: valores GENERALES de la empresa, con excepción por empleado/contrato.
    # El valor efectivo se resuelve siempre con los métodos _ne_* de hr.employee y
    # hr.contract (empleado/contrato -> empresa); sin valor, error nombrado.
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pila_ccf_por_empleado = fields.Boolean(
        string='¿Maneja empleados en diferentes ciudades?',
        default=False,
        help='Si está activa, la Caja de Compensación se elige por empleado (y es obligatoria '
             'en cada uno). Si no, toda la empresa usa la Caja de Compensación general.',
    )
    l10n_co_pila_ccf_id = fields.Many2one(
        'res.partner', string='Caja de Compensación general',
        domain=[('l10n_co_entity_type', '=', 'ccf')],
        help='Contacto de la Caja de Compensación Familiar de toda la empresa.',
    )
    l10n_co_pila_clase_riesgo = fields.Selection(
        selection=NE_CLASES_RIESGO, string='Clase de Riesgo ARL general',
        help='Clase de riesgo ARL de la empresa. Un contrato puede tener otra clase propia '
             '(pestaña PILA del contrato).',
    )
    l10n_co_pila_centro_trabajo = fields.Char(
        string='Centro de Trabajo ARL general',
        help='Código del centro de trabajo ARL de la empresa. Un contrato puede tener otro '
             'propio (pestaña PILA del contrato).',
    )
    l10n_co_ne_payment_method = fields.Selection(
        selection=NE_MEDIOS_PAGO, string='Medio de Pago general',
        help='Medio de pago de la nómina de la empresa (atributo Metodo del nodo <Pago> del '
             'XML). Un empleado puede tener otro propio.',
    )

    l10n_co_ne_febrero_modo = fields.Selection(
        selection=[
            ('real', 'Días reales'),
            ('30', 'Mes de 30 días'),
        ],
        string='Febrero en prestaciones',
        help='Cómo se cuentan los días en prima, cesantías, intereses, indemnización y vacaciones '
             'causadas de la liquidación (el divisor sigue siendo 360). "Días reales": febrero '
             'cuenta 28 (29 si es bisiesto) y el día 31 no cuenta. "Mes de 30 días": cada mes, '
             'febrero incluido, cuenta 30. No afecta el sueldo mensual ni los días de PILA.',
    )

    l10n_co_ne_pago_dominical_mensual = fields.Selection(
        selection=[
            ('dia_mas_recargo', 'Valor de la hora + recargo del día de descanso'),
            ('solo_recargo', 'Solo el recargo del día de descanso'),
        ],
        string='Pago del día de descanso obligatorio (dominical) con salario mensual', tracking=False,
        help='Cómo se pagan las horas de la JORNADA ORDINARIA trabajadas en día de descanso obligatorio (dominical o festivo) a quien tiene salario mensual, cuyo sueldo ya cubre el día de descanso. '
             '«Valor de la hora + recargo del día de descanso»: la hora se paga con el factor total (1,80 / 1,90 / 2,00), es decir el valor de la hora trabajada más el recargo: la lectura del concepto MinTrabajo 24429 de 2026, adicional a los 30 días de salario '
             '(decisión D1 de David, 17-nov-2026). «Solo el recargo del día de descanso»: el factor menos 1 (0,80 / 0,90 / 1,00), es decir el recargo, porque el día de descanso ya está en el sueldo mensual: la lectura de la CSJ, SL3567-2019 («la remuneración '
             'por trabajar un domingo o festivo está inmersa en el salario ordinario»). En las dos opciones el trabajo en día de descanso obligatorio lleva recargo (CST art. 179 num. 1, Ley 2466 de 2025, art. 14): ninguna lo trata como un día ordinario sin recargo. '
             'Aplica a recargo diurno y nocturno dominical/festivo (HRDDF, HRNDF); las horas EXTRA dominicales (HEDDF, HENDF) no cambian porque el sueldo mensual no las cubre. '
             'Es una decisión de la compañía, sin valor por defecto: sin elegirla, calcular horas de recargo dominical da un error que dice dónde elegirla (Ley 2466 de 2025, art. 14).')

    l10n_co_ne_segmentar_mes = fields.Boolean(
        string='Separar el mes en documentos por cambio de tipo de trabajador', default=False, copy=False,
        help='Si el tipo de trabajador de un empleado cambia dentro del mes (por ejemplo un aprendiz que pasa de la etapa lectiva a la práctica), el mes se parte en un documento mensual por cada tramo: el segundo '
             'y los siguientes llevan «Novedad» con el CUNE del anterior (Resolución DIAN 000013 de 2021, art. 3 y su parágrafo; Anexo Técnico NIE199 y NIE204). APAGADO por defecto y solo lo cambia el administrador '
             'del sistema: NO VERIFICADO con la DIAN (doc 95 §4: si el cambio de tipo es una «novedad contractual», qué valores y fechas lleva el segundo documento, el orden de envío y si hay una regla de rechazo). '
             'Apagado, el mes con cambio de tipo se detiene con un error claro, como antes. No cambia nada si ningún empleado cambia de tipo.')

    l10n_co_ne_bloquear_extemporaneo = fields.Boolean(
        string='Bloquear envío fuera de plazo', default=False,
        help='Si está marcado, un documento mensual (o nota de ajuste) cuyo plazo de transmisión ya venció no se encola '
             'sin que un administrador de nómina confirme "envío extemporáneo" en Enviar y Procesar; queda constancia en '
             'el documento. Apagado por defecto: no cambia nada hasta activarlo. Es una política de la compañía, no una '
             'regla de la DIAN (el Anexo no valida el plazo).')

    l10n_co_ne_fuente_fecha_pago = fields.Selection(
        selection=[
            ('contabilidad', 'Pagos de Contabilidad'),
            ('recibo', 'Fecha de pago del recibo'),
        ],
        string='Fuente de la fecha de pago',
        help='De dónde sale la fecha de pago que decide el mes del documento de nómina electrónica y se reporta '
             'en FechasPagos. "Pagos de Contabilidad": las fechas de los pagos conciliados del asiento del recibo. '
             '"Fecha de pago del recibo": el campo Fecha de pago del recibo, que se llena con la acción Registrar '
             'pago. Un recibo con neto 0 no tiene pago en Contabilidad: su fecha se registra con "Registrar fecha de pago". '
             'Sin valor por defecto: si falta, se pide elegirlo.',
    )

    l10n_co_ne_redondeo_dias = fields.Selection(
        selection=[
            ('HALF-UP', 'HALF-UP (al entero más cercano; 0,5 sube)'),
            ('UP', 'UP (hacia arriba)'),
            ('DOWN', 'DOWN (hacia abajo)'),
        ],
        string='Redondeo de días del XML',
        help='Cómo se redondea un número de días fraccionario en los campos de días del XML de '
             'nómina electrónica, que la DIAN exige enteros (vacaciones pendientes, primas, '
             'incapacidades, licencias). Mismo vocabulario del método de redondeo nativo de Odoo.',
    )

    def write(self, vals):
        if ('l10n_co_ne_segmentar_mes' in vals and not (self.env.su or self.env.user.has_group('base.group_system'))
                and any(company.l10n_co_ne_segmentar_mes != bool(vals['l10n_co_ne_segmentar_mes']) for company in self)):      # guardar Ajustes con el mismo valor no es un cambio
            raise AccessError(_(
                'Solo el administrador del sistema cambia «Separar el mes en documentos por cambio de tipo de trabajador»: la DIAN todavía no ha verificado cómo recibe el segundo documento del mes '
                '(doc 95 §4). Pídale que lo active cuando esté verificado.'))
        if 'l10n_co_pila_ccf_por_empleado' in vals and not vals['l10n_co_pila_ccf_por_empleado']:
            for company in self.filtered('l10n_co_pila_ccf_por_empleado'):
                general = (
                    vals['l10n_co_pila_ccf_id'] if 'l10n_co_pila_ccf_id' in vals
                    else company.l10n_co_pila_ccf_id.id)
                distintos = self.env['hr.employee'].sudo().with_context(active_test=False).search_count([
                    ('company_id', '=', company.id),
                    ('l10n_co_pila_ccf_id', '!=', False),
                    ('l10n_co_pila_ccf_id', '!=', general or False),
                ])
                if distintos:
                    raise ValidationError(_(
                        'No se puede desactivar "¿Maneja empleados en diferentes ciudades?" en '
                        '%(company)s: %(n)s empleado(s) tienen una Caja de Compensación distinta '
                        'de la general. Deje a esos empleados con la caja general (o elija como '
                        'general la que corresponde) y vuelva a intentarlo.',
                        company=company.name, n=distintos))
        res = super().write(vals)
        if 'country_id' in vals:
            self._ne_asegurar_secuencias()
        return res

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

    # ──────────────────────────────────────────────────────────────────
    # Recargar paquete de nómina (.99, "Opción A" aprobada por David/Tech
    # Lead): recrea estructuras, reglas salariales y tipos de novedad que
    # falten, SIN tocar hr.rule.parameter.
    # ──────────────────────────────────────────────────────────────────
    _L10N_CO_NE_RELOAD_DATA_FILES = [
        'data/hr_payroll_structure_data.xml',
        'data/hr_payroll_structure_special_data.xml',
        'data/hr_salary_rule_auto_deductions.xml',
        'data/l10n_co_embargo_input_types_data.xml',
        'data/l10n_co_horas_extra_input_types_data.xml',
        'data/l10n_co_novedades_input_types_data.xml',
    ]

    def _l10n_co_ne_reload_payroll_package(self):
        """Vuelve a aplicar SOLO estos archivos de datos del módulo, en el
        mismo orden que el manifest, con el mismo mecanismo que usa un
        `-u` real (``odoo.tools.convert.convert_file``): cada archivo
        respeta su propio ``noupdate`` ya declarado -- los de
        estructuras/reglas llevan ``noupdate="0"`` y siempre se
        reaplican, los de tipos de novedad llevan ``noupdate="1"`` y solo
        se recrean si faltan (ver ``_tag_root`` en ``odoo/tools/
        convert.py``: el atributo del propio bloque ``<data>`` siempre
        gana sobre el ``noupdate`` que se pasa aquí).

        Deliberadamente NO incluye ``data/l10n_co_rule_parameters_data.xml``
        (parámetros legales versionados, nunca se pisan) ni
        ``data/hr_retefuente_data.xml`` (mismo motivo) -- quedan fuera de
        alcance por diseño, no por una comparación de valores.
        """
        self.ensure_one()
        module = 'l10n_co_nomina_electronica'
        idref = {}
        for relpath in self._L10N_CO_NE_RELOAD_DATA_FILES:
            convert.convert_file(self.env, module, relpath, idref, mode='update', noupdate=False)
