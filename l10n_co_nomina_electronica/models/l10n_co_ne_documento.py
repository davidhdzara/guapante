# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Documento mensual de nómina electrónica por empleado (doc 53 §3, §16.2, §18.6, §20).

Etapa 1b: SOLO el modelo, la relación con el recibo, las reglas multiempresa y la migración de lo ya
transmitido (``legacy``, 1:1). Todavía no genera XML ni envía (etapas 3 y 4): no hereda el mixin del ciclo
DIAN; sus campos de estado son ``etapa`` + ``state`` calculado del último intento (patrón de ``account.move`` +
``l10n_co_dian.document``)."""

import base64
import hashlib
import logging
from datetime import datetime as _dt, time, timedelta

import pytz

from markupsafe import Markup

from odoo import _, api, fields, models, modules
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services import (
    cune as cune_service, dian_message, dian_respuesta, dian_utils, documento_merge, ne_xml_utils, nomina_xml_builder,
    nota_ajuste, representacion_grafica, soap_client, xml_signer)
from ..services.soap_client import _parse_response

_logger = logging.getLogger(__name__)

# Mapa del estado del recibo (ciclo DIAN de hoy) al documento legacy: (etapa, estado del intento o None).
# 'generated' (XML con número, sin enviar) queda como etapa 'ready' con su CUNE/número/XML; 'uncertain'
# conserva un intento pendiente y la marca ``incierto``; 'eliminated' conserva un intento aceptado y ``eliminado``.
_MAPA_ESTADO_LEGACY = {
    'draft': ('draft', None),
    'generated': ('ready', None),
    'sent': ('draft', 'invoice_pending'),
    'uncertain': ('draft', 'invoice_pending'),
    'accepted': ('draft', 'invoice_accepted'),
    'rejected': ('draft', 'invoice_rejected'),
    'eliminated': ('draft', 'invoice_accepted'),
}
_OPERACIONES_ENVIO = ('send_sync', 'send_test_set')

# Veredicto neutral del servicio (dian_respuesta) -> estado del intento del documento (doc 53 §23.13). Un fallo de
# transporte NUNCA es rechazo.
_ESTADO_INTENTO_POR_VEREDICTO = {
    dian_respuesta.ACEPTADO: 'invoice_accepted',
    dian_respuesta.RECHAZADO: 'invoice_rejected',
    dian_respuesta.PENDIENTE: 'invoice_pending',
    dian_respuesta.ERROR_TRANSPORTE: 'invoice_sending_failed',
}


class L10nCoNeDocumento(models.Model):
    _name = 'l10n.co.ne.documento'
    _description = 'Documento mensual de nómina electrónica'
    _inherit = ['mail.thread']
    _order = 'period desc, employee_id, id desc'
    _check_company_auto = True

    name = fields.Char(string='Documento', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, index=True,
                                  check_company=True, ondelete='restrict')
    contract_id = fields.Many2one('hr.contract', string='Contrato', check_company=True, ondelete='restrict',
                                  help='Contrato vigente en el mes (ingreso/retiro, tipo de contrato).')
    period = fields.Date(string='Mes', required=True, index=True,
                         help='Primer día del mes del documento (mes de la primera fecha de pago de sus recibos).')
    payslip_ids = fields.One2many('hr.payslip', 'l10n_co_ne_documento_id', string='Recibos incluidos', check_company=True)       # H-F2-03 (C5)
    recibo_xml_ids = fields.Many2many('hr.payslip', string='Recibos del XML', compute='_compute_recibo_xml_ids',
                                      help='Recibos con los que se arma el XML: los propios y, en una nota de ajuste, '
                                           'los de la cadena de documentos (doc 53 §23.16, D-1).')

    etapa = fields.Selection([('draft', 'Borrador'), ('ready', 'Listo')], string='Etapa', default='draft',
                             required=True, copy=False,
                             help='Preparación previa al envío: Borrador (composición editable) y Listo (validado).')
    incierto = fields.Boolean(string='Envío incierto', copy=False,
                              help='No hubo acuse ni veredicto pasado el tiempo configurado; requiere conciliación y '
                                   'sale del cron de reconsulta.')
    eliminado = fields.Boolean(string='Eliminado por nota de ajuste', copy=False)
    eliminado_por_id = fields.Many2one('l10n.co.ne.documento', string='Eliminado por', copy=False,
                                       ondelete='set null', check_company=True)
    # Estado DIAN: SOLO los 4 valores nativos de l10n_co_dian (account.move.l10n_co_dian_state), calculado del último
    # intento y VACÍO mientras no hay un envío del XML vigente. Borrador/Listo viven en ``etapa``; Incierto y
    # Eliminado en sus banderas (doc 53 §26b).
    state = fields.Selection([
        ('invoice_sending_failed', 'Envío fallido'),
        ('invoice_pending', 'Pendiente'),
        ('invoice_rejected', 'Rechazado'),
        ('invoice_accepted', 'Aceptado'),
    ], string='Estado DIAN', compute='_compute_state', store=True, copy=False, index=True)
    intento_ids = fields.One2many('l10n.co.ne.documento.intento', 'documento_id', string='Intentos')
    message = fields.Html(string='Motivo', compute='_compute_message', sanitize=False)

    cune = fields.Char(string='CUNE', copy=False, index=True, readonly=True)
    consecutive = fields.Char(string='Consecutivo NE', copy=False, readonly=True)
    xml_attachment_id = fields.Many2one('ir.attachment', string='XML firmado', copy=False, readonly=True,
                                        ondelete='set null')
    zip_key = fields.Char(string='ZipKey DIAN', copy=False, readonly=True)
    hab_set_id = fields.Char(string='Set de habilitación DIAN', copy=False, index=True)
    exchange_ids = fields.Many2many('l10n.co.ne.exchange', 'l10n_co_ne_exchange_documento_rel',
                                    'documento_id', 'exchange_id', string='Historial de intercambios DIAN',
                                    readonly=True, copy=False, check_company=True)

    is_adjustment = fields.Boolean(string='Es nota de ajuste', copy=False)
    adjustment_type = fields.Selection([('1', 'Reemplazar'), ('2', 'Eliminar')], string='Tipo de nota de ajuste',
                                       copy=False)
    adjustment_ref_cune = fields.Char(string='CUNE del documento original', copy=False)
    parent_id = fields.Many2one('l10n.co.ne.documento', string='Documento original', copy=False,
                                ondelete='restrict', check_company=True)
    error_conocido_el = fields.Date(string='Error conocido el', copy=False,
                                    help='Fecha en que se conoció el error (nota de ajuste): fija el plazo de 10 días hábiles.')
    legacy = fields.Boolean(string='Migrado (legacy)', copy=False, readonly=True,
                            help='Documento migrado 1:1 desde un recibo ya transmitido: conserva su CUNE y número; '
                                 'queda fuera de la unicidad por mes y del plazo.')
    fecha_limite = fields.Date(
        string='Fecha límite', compute='_compute_fecha_limite', store=True, readonly=True,
        help='10.º día hábil del mes siguiente al del documento (Res. DIAN 000013/2021 art. 8); en una nota de ajuste, '
             'del mes siguiente al conocimiento del error. Día hábil = día con jornada en el calendario del contrato '
             '(o de la compañía) y no festivo (D10). Solo alerta, no bloquea (sin sanción automática). No aplica a '
             'documentos migrados.')

    # Reconsulta automática (doc 53 §23.17, 7c / D-B): una consulta por documento por intervalo y espera creciente tras
    # fallos de transporte seguidos. Solo técnicos (sin vista).
    proxima_consulta = fields.Datetime(string='Próxima consulta DIAN', copy=False, readonly=True)
    fallos_consulta = fields.Integer(string='Fallos de consulta seguidos', copy=False, readonly=True)

    # Cola de envío y alertas (patrón de account.move.send; los llena el asistente y el cron, etapas 2 y 4).
    sending_data = fields.Json(string='Datos de envío en cola', copy=False, readonly=True)
    entregar_representacion = fields.Boolean(
        string='Entregar representación al empleado', copy=False, readonly=True,
        help='Intención registrada desde Enviar y Procesar (casilla "Correo: representación gráfica y XML"): cuando la '
             'DIAN acepte el documento se envía al empleado un ZIP con la representación gráfica (PDF) y el XML '
             'validado. Es una comodidad de este módulo, no un contenedor definido por la DIAN. No es parte de la cola '
             'de envío a la DIAN: un documento puede tener la intención sin estar en la cola.')
    is_being_sent = fields.Boolean(string='En cola', compute='_compute_is_being_sent')
    alertas = fields.Json(string='Alertas', copy=False,
                          help='Lista de {"key", "level" (danger/warning), "message"} calculada al validar el documento.')
    alertas_texto = fields.Html(string='Alertas', compute='_compute_alertas_texto', sanitize=False)

    _sql_constraints = [
        ('cune_unique', 'UNIQUE(cune)', 'El CUNE debe ser único: ya existe un documento con este CUNE.'),
        ('consecutive_company_unique', 'UNIQUE(consecutive, company_id)',
         'El consecutivo de nómina electrónica debe ser único por empresa.'),
    ]

    def init(self):
        """Un original activo por (compañía, empleado, mes): índice parcial (el ORM no lo expresa)."""
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS l10n_co_ne_documento_mes_unico
            ON l10n_co_ne_documento (company_id, employee_id, period)
            WHERE is_adjustment IS NOT TRUE AND legacy IS NOT TRUE AND eliminado IS NOT TRUE
        """)

    # ──────────────────────────────────────────────────────────────────
    # Calculados
    # ──────────────────────────────────────────────────────────────────
    @api.depends('employee_id.name', 'period', 'is_adjustment')
    def _compute_name(self):
        for doc in self:
            mes = doc.period.strftime('%Y-%m') if doc.period else ''
            base = '%s %s' % (doc.employee_id.name or '', mes)
            doc.name = ('%s %s' % (_('Ajuste'), base) if doc.is_adjustment else base).strip()

    @api.depends('payslip_ids', 'payslip_ids.state', 'is_adjustment', 'parent_id')
    def _compute_recibo_xml_ids(self):
        for doc in self:
            doc.recibo_xml_ids = doc._ne_recibos_para_xml()

    def _ultimo_intento(self):
        """Último intento (como el nativo: ``.sorted()[:1]``); el orden es por fecha y luego id."""
        self.ensure_one()
        return self.intento_ids.sorted(lambda i: (i.datetime or _dt.min, i.id), reverse=True)[:1]

    @api.depends('intento_ids.state', 'intento_ids.datetime', 'intento_ids.identifier', 'cune')
    def _compute_state(self):
        for doc in self:
            ultimo = doc._ultimo_intento()
            if not ultimo or (ultimo.state == 'invoice_rejected' and ultimo.identifier != doc.cune):
                # Sin envío, o el rechazo fue de un XML ANTERIOR: el documento se regeneró con consecutivo y CUNE
                # nuevos (doc 53 §23.15, D-a) y el XML vigente todavía no se envió: sin estado DIAN. El intento
                # rechazado queda en el historial como evidencia.
                doc.state = False
            else:
                doc.state = ultimo.state

    @api.depends('intento_ids.message', 'intento_ids.datetime')
    def _compute_message(self):
        for doc in self:
            doc.message = doc._ultimo_intento().message or False

    @api.depends('sending_data')
    def _compute_is_being_sent(self):
        for doc in self:
            doc.is_being_sent = bool(doc.sending_data)

    @api.depends('alertas')
    def _compute_alertas_texto(self):
        etiquetas = {'danger': _('Bloqueo'), 'warning': _('Advertencia')}
        for doc in self:
            items = doc.alertas or []
            doc.alertas_texto = Markup('<ul>%s</ul>') % Markup('').join(
                Markup('<li>%s: %s</li>') % (etiquetas.get(a.get('level'), a.get('level') or ''),
                                              a.get('message') or '') for a in items) if items else False

    # ──────────────────────────────────────────────────────────────────
    # Plazo de transmisión (doc 53 §4.4, D10)
    # ──────────────────────────────────────────────────────────────────
    DIAS_HABILES_PLAZO = 10   # Res. DIAN 000013/2021 art. 8: 10 primeros días hábiles del mes siguiente

    def _ne_calendario(self):
        """Calendario laboral del documento: el del contrato; si no, el de la compañía."""
        self.ensure_one()
        return self.contract_id.resource_calendar_id or self.company_id.resource_calendar_id

    def _ne_dias_habiles(self, desde, hasta):
        """Fechas hábiles de [desde, hasta]: con jornada en el calendario y sin festivo (festivos globales de la
        compañía del documento). El sábado cuenta si la jornada lo incluye (D10)."""
        self.ensure_one()
        calendario = self._ne_calendario()
        if not calendario:
            return set()
        zona = pytz.timezone(calendario.tz or self.env.user.tz or 'UTC')
        inicio = zona.localize(_dt.combine(desde, time.min))
        fin = zona.localize(_dt.combine(hasta, time.max))
        # Sin ``resources``, el nativo NO filtra los festivos por compañía (su filtro solo corre cuando
        # hay un recurso): los festivos globales de otra compañía restarían días hábiles de ESTE plazo.
        # Se limita explícitamente a los de la compañía del documento (o sin compañía).
        dominio_festivos = [('time_type', '=', 'leave'), ('company_id', 'in', [self.company_id.id, False])]
        intervalos = calendario.with_company(self.company_id)._work_intervals_batch(
            inicio, fin, domain=dominio_festivos, compute_leaves=True)[False]
        return {a.astimezone(zona).date() for a, _b, _rec in intervalos}

    def _ne_calcular_fecha_limite(self):
        """10.º día hábil del mes siguiente, o False si no se puede calcular (sin calendario o sin 10 días hábiles
        en ~45 días: falta cargar jornada o hay festivos de más).

        Original: el mes siguiente al del documento. NOTA de ajuste (doc 53 §28.4, doctrina que entregó David: oficios
        DIAN 914809/2021 y 901476/2022; NO verificada contra el texto primario): el mes siguiente al CONOCIMIENTO del
        error (``error_conocido_el``); sin esa fecha no hay plazo."""
        self.ensure_one()
        base = self.error_conocido_el if self.is_adjustment else self.period
        if not base:
            return False
        primero = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
        dias = int(self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_co_ne_dias_plazo_transmision', primero))   # Res. DIAN 000013/2021 art. 8 (versionado)
        habiles = sorted(self._ne_dias_habiles(primero, primero + timedelta(days=44)))
        return habiles[dias - 1] if len(habiles) >= dias else False

    @api.depends('period', 'contract_id.resource_calendar_id', 'company_id.resource_calendar_id',
                 'legacy', 'is_adjustment', 'error_conocido_el')
    def _compute_fecha_limite(self):
        for doc in self:
            doc.fecha_limite = (doc._ne_calcular_fecha_limite()
                                if doc.period and not doc.legacy and (not doc.is_adjustment or doc.error_conocido_el)
                                else False)

    # ──────────────────────────────────────────────────────────────────
    # Preparar: agrupar recibos, crear/reutilizar el documento y validarlo (doc 53 §17.2, §20.2, §22.2)
    # ──────────────────────────────────────────────────────────────────
    @api.model
    def _ne_recibos_del_mes(self, company, employee, period):
        """Recibos pagados (hechos o pagados, no notas de crédito) del empleado cuya PRIMERA fecha de pago cae en el
        mes ``period``. Con fuente 'recibo' filtra en SQL por fecha; con 'contabilidad' calcula por recibo. NO entran
        las notas de ajuste por recibo, los recibos de un documento migrado (legacy) ni los de habilitación."""
        fin = (period.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        dominio = [('company_id', '=', company.id), ('employee_id', '=', employee.id),
                   ('state', 'in', ('done', 'paid')), ('credit_note', '=', False),
                   ('l10n_co_ne_is_adjustment', '=', False)]
        if company.l10n_co_ne_fuente_fecha_pago == 'recibo':
            recibos = self.env['hr.payslip'].search(dominio + [('paid_date', '>=', period), ('paid_date', '<=', fin)])
        else:
            candidatos = self.env['hr.payslip'].search(dominio)
            recibos = candidatos.filtered(lambda s: s._ne_fechas_pagos_contables()
                                          and period <= s._ne_fechas_pagos_contables()[0] <= fin)
        return recibos.filtered(lambda s: not self._ne_motivo_no_entra(s))

    @api.model
    def _ne_motivo_no_entra(self, slip):
        """Motivo (texto) por el que un recibo NO puede entrar a un documento mensual, o False si puede."""
        if slip.l10n_co_ne_is_adjustment:
            return _('El recibo "%s" es una nota de ajuste por recibo: no entra a un documento mensual.',
                     slip.display_name)
        if slip.l10n_co_ne_documento_id.legacy:
            return _('El recibo "%(recibo)s" ya fue transmitido por recibo y está en el documento migrado "%(doc)s": '
                     'no se reporta otra vez.', recibo=slip.display_name, doc=slip.l10n_co_ne_documento_id.display_name)
        if slip._ne_historia_solo_habilitacion():
            return _('El recibo "%s" solo tiene historia de habilitación (pruebas): no entra a un documento real.',
                     slip.display_name)
        return False

    @api.model
    def _ne_recibos_que_faltan(self, company, employee, period, entran):
        """Recibos del mes (no cancelados, no notas de crédito) que NO entraron al documento: **sin pagar o sin fecha de
        pago**. Un recibo con fecha de pago en OTRO mes no falta: pertenece al documento de ese mes (con pagos los 5 y 20,
        mensual pagado el mes siguiente o semanal que cruza el mes, el periodo y el pago caen en meses distintos y eso es
        lo normal, doc 58 §12 H-F3-1). Excluye notas de ajuste por recibo, legacy y habilitación (no faltan: no
        aplican)."""
        fin = (period.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        faltan = self.env['hr.payslip'].search([
            ('company_id', '=', company.id), ('employee_id', '=', employee.id),
            ('credit_note', '=', False), ('state', '!=', 'cancel'), ('l10n_co_ne_is_adjustment', '=', False),
            ('date_to', '>=', period), ('date_to', '<=', fin), ('id', 'not in', entran.ids)])
        return faltan.filtered(lambda s: not self._ne_motivo_no_entra(s) and not self._ne_tiene_fecha_pago(s))

    @api.model
    def _ne_tiene_fecha_pago(self, slip):
        """True si el recibo está hecho o pagado y su fecha de pago se puede resolver (``_ne_fechas_pago``); sin fecha, o
        sin la fuente de la fecha configurada, es False (se trata como "sin fecha de pago")."""
        if slip.state not in ('done', 'paid'):
            return False
        try:
            return bool(slip._ne_fechas_pago())
        except UserError:
            return False

    @api.model
    def _ne_preparar(self, recibos):
        """Agrupa ``recibos`` por (compañía, empleado, mes de la primera fecha de pago), crea o reutiliza el documento
        de cada grupo, enlaza TODOS los recibos pagados del mes (no solo los seleccionados) y lo valida.

        No gasta consecutivo ni envía. Devuelve ``{'documentos': recordset, 'sin_fecha': [(recibo, motivo)]}``: los
        recibos sin fecha de pago (o no hechos) no pertenecen a ningún mes y se informan aparte."""
        resultado = {'documentos': self.browse(), 'sin_fecha': []}
        previos = recibos.l10n_co_ne_documento_id   # antes de relinkear: de dónde vienen los recibos
        grupos = {}
        for slip in recibos:
            if not slip.company_id._ne_es_colombia():
                resultado['sin_fecha'].append((slip, _('La compañía no es colombiana.')))
                continue
            motivo = self._ne_motivo_no_entra(slip)
            if motivo:
                resultado['sin_fecha'].append((slip, motivo))
                continue
            if slip.state not in ('done', 'paid'):
                resultado['sin_fecha'].append((slip, _('El recibo no está en estado "Hecho" ni "Pagado".')))
                continue
            try:
                primera = slip._ne_fecha_pago()
            except UserError as error:
                resultado['sin_fecha'].append((slip, str(error)))
                continue
            clave = (slip.company_id, slip.employee_id, primera.replace(day=1))
            grupos.setdefault(clave, self.env['hr.payslip'])
            grupos[clave] |= slip
        for (company, employee, period) in grupos:
            doc = self._ne_documento_del_grupo(company, employee, period)
            # Solo se recompone un documento SIN estado DIAN: uno con envío fallido (``invoice_sending_failed``) pudo haber
            # llegado a la DIAN, así que se reenvía el MISMO XML y su composición no cambia (solo se valida y alerta);
            # mismo criterio que un envío incierto (doc 53 §28.7, D6).
            if not doc.state and not doc.is_being_sent:
                doc._ne_componer(self._ne_recibos_del_mes(company, employee, period))
            else:
                # Documento ya transmitido (D-5): los recibos nuevos del mes se adoptan en la nota abierta, nunca en el
                # documento aceptado; sin nota abierta queda la alerta persistente ``recibo_tardio``.
                nota = doc._ne_nota_abierta()
                if nota:
                    mes = self._ne_recibos_del_mes(company, employee, period)
                    nota._ne_componer_adoptados(doc._ne_adoptables(mes, nota))
                    nota._ne_validar()
                    resultado['documentos'] |= nota
            doc._ne_validar()
            resultado['documentos'] |= doc
        # Un recibo que cambió de mes (nueva fecha de pago) sale del documento donde estaba: ese documento se
        # recompone y revalida; si queda vacío y sin historia, se elimina.
        for previo in previos - resultado['documentos']:
            if previo.is_adjustment and not previo.legacy:
                # D-M: un recibo adoptado cuya fecha de pago pasó a otro mes sale de la nota abierta; una nota ya
                # enviada no se toca (``_ne_validar`` deja la alerta persistente ``recibo_otro_mes``).
                if not previo.state and not previo.is_being_sent:
                    previo._ne_componer_adoptados(
                        previo.payslip_ids & self._ne_recibos_del_mes(previo.company_id, previo.employee_id, previo.period))
                previo._ne_validar()
                continue
            if previo.legacy or previo.state:
                continue
            previo._ne_componer(self._ne_recibos_del_mes(previo.company_id, previo.employee_id, previo.period))
            if previo.payslip_ids:
                previo._ne_validar()
            else:
                previo.unlink()
        return resultado

    @api.model
    def _ne_documento_del_grupo(self, company, employee, period):
        doc = self.search([
            ('company_id', '=', company.id), ('employee_id', '=', employee.id), ('period', '=', period),
            ('is_adjustment', '=', False), ('legacy', '=', False), ('eliminado', '=', False)], limit=1)
        return doc or self.create({'company_id': company.id, 'employee_id': employee.id, 'period': period})

    def _ne_componer(self, recibos):
        """Deja exactamente ``recibos`` en el documento (los que ya no corresponden se sueltan) y fija el contrato.
        Solo se compone un documento sin transmitir (draft/ready/envío fallido): lo llama ``_ne_preparar``."""
        self.ensure_one()
        sueltos = self.payslip_ids - recibos
        if sueltos:
            sueltos.write({'l10n_co_ne_documento_id': False})
        nuevos = recibos - self.payslip_ids
        if nuevos:
            nuevos.write({'l10n_co_ne_documento_id': self.id})
        contratos = recibos.sorted('date_to').contract_id
        self.contract_id = contratos[-1:] or False
        if self.etapa == 'ready':
            self.etapa = 'draft'   # cambió la composición: se revalida
        if (sueltos or nuevos) and not self.state and self.xml_attachment_id:
            # El XML generado ya no corresponde a los recibos: se descarta para que NADA inconsistente se encole ni se
            # transmita (hay que volver a generarlo). El consecutivo no usado se conserva y se reutiliza (doc 53 §28.7).
            self.write({'xml_attachment_id': False, 'cune': False})

    # ──────────────────────────────────────────────────────────────────
    # Cadena de notas de ajuste (doc 53 §23.16, precisión (e)): original → notas, por ``parent_id`` (sin parent_path)
    # ──────────────────────────────────────────────────────────────────
    def _ne_cadena(self):
        """Documento original y todas las notas que cuelgan de él (directa o indirectamente), con guarda de ciclos."""
        self.ensure_one()
        raiz = self
        vistos = {self.id}
        while raiz.parent_id and raiz.parent_id.id not in vistos:
            raiz = raiz.parent_id
            vistos.add(raiz.id)
        cadena = raiz
        frontera = raiz
        while frontera:
            hijos = self.search([('parent_id', 'in', frontera.ids)]) - cadena
            cadena |= hijos
            frontera = hijos
        return cadena

    def _ne_ultimo_aceptado(self):
        """Último documento ACEPTADO de la cadena (D9): el de intento aceptado más reciente que no esté eliminado ni
        sea una nota Eliminar. Si no hay notas aceptadas, es el original."""
        self.ensure_one()

        def fecha(doc):
            aceptados = doc.intento_ids.filtered(lambda i: i.state == 'invoice_accepted')
            return (max((i.datetime or _dt.min) for i in aceptados) if aceptados else _dt.min, doc.id)

        candidatos = self._ne_cadena().filtered(
            lambda d: d.state == 'invoice_accepted' and not d.eliminado
            and not (d.is_adjustment and d.adjustment_type == '2'))
        return candidatos.sorted(fecha)[-1:]

    def _ne_nota_en_curso(self):
        """Notas de la cadena que todavía no terminaron: cualquiera cuyo estado DIAN no sea 'aceptado' (borrador,
        listo, envío fallido, pendiente, incierta o rechazada sin regenerar)."""
        self.ensure_one()
        return self._ne_cadena().filtered(lambda d: d.is_adjustment and d.state != 'invoice_accepted')

    def _ne_nota_abierta(self):
        """Nota de la cadena que aún se puede componer: sin enviar (o con envío fallido) y fuera de la cola."""
        self.ensure_one()
        return self._ne_nota_en_curso().filtered(
            lambda d: d.state in (False, 'invoice_sending_failed') and not d.is_being_sent and not d.incierto)[:1]

    def _ne_componer_adoptados(self, recibos):
        """Deja exactamente ``recibos`` como los recibos propios (adoptados) de la nota. NO toca el contrato (lo hereda de
        la cadena): una nota sin recibos propios no lo pierde (precisión (a))."""
        self.ensure_one()
        sueltos = self.payslip_ids - recibos
        if sueltos:
            sueltos.write({'l10n_co_ne_documento_id': False})
        nuevos = recibos - self.payslip_ids
        if nuevos:
            nuevos.write({'l10n_co_ne_documento_id': self.id})
        if (sueltos or nuevos) and self.etapa == 'ready':
            self.etapa = 'draft'   # cambió la composición: se revalida

    def action_crear_ajuste(self, tipo, error_conocido_el=None):
        """Crea la nota de ajuste en borrador sobre este documento aceptado (doc 53 §23.16). ``tipo``: '1' Reemplazar o
        '2' Eliminar. No llama a la DIAN, no genera XML ni gasta consecutivo."""
        self.ensure_one()
        if self.legacy:
            raise UserError(_('El documento "%s" se migró del ciclo por recibo: se ajusta por recibo, no por documento.',
                              self.display_name))
        if tipo not in ('1', '2'):
            raise UserError(_('Tipo de nota de ajuste inválido: debe ser "1" (Reemplazar) o "2" (Eliminar).'))
        hoy = fields.Date.context_today(self)
        fecha = fields.Date.to_date(error_conocido_el) if error_conocido_el else hoy
        if fecha > hoy:
            raise UserError(_('La fecha en que se conoció el error no puede ser futura (%s).', fecha))
        if self.is_adjustment:
            raise UserError(_('"%s" es una nota de ajuste: la nota se crea desde el documento original.',
                              self.display_name))
        if self.eliminado:
            raise UserError(_('El documento "%s" ya fue eliminado por una nota de ajuste.', self.display_name))
        if self.state == 'invoice_rejected':
            raise UserError(_('El documento "%s" fue rechazado: se corrige y se regenera, no lleva nota de ajuste.',
                              self.display_name))
        if self.state != 'invoice_accepted':
            raise UserError(_('Solo se crean notas de ajuste para documentos aceptados por la DIAN; "%s" no lo está.',
                              self.display_name))
        # Eliminar la última nota aceptada SÍ se permite (David, 2026-11-14): la nota Eliminar toma como padre el
        # último aceptado de la cadena (``_ne_ultimo_aceptado``); al aceptarse, ese queda eliminado y vuelve a ser
        # vigente el anterior (nota previa u original).
        en_curso = self._ne_nota_en_curso()
        if en_curso:
            raise UserError(_('Ya hay una nota de ajuste en curso para este documento: "%s". Termínela antes de crear '
                              'otra.', en_curso[:1].display_name))
        padre = self._ne_ultimo_aceptado()
        nota = self.create({
            'company_id': self.company_id.id, 'employee_id': self.employee_id.id, 'period': self.period,
            'contract_id': self.contract_id.id, 'is_adjustment': True, 'adjustment_type': tipo,
            'parent_id': padre.id, 'adjustment_ref_cune': padre.cune, 'error_conocido_el': fecha, 'etapa': 'draft'})
        if tipo == '1':
            nota._ne_componer_adoptados(self._ne_adoptables(
                self._ne_recibos_del_mes(self.company_id, self.employee_id, self.period)))
        return nota

    def _ne_adoptables(self, recibos, nota=None):
        """De ``recibos`` (los pagados del mes), los que una nota de esta cadena puede adoptar: los que no están en
        ningún documento, los que ya son de ``nota`` y (D-S, doc 53 §28.3) los de las notas ELIMINADAS de la cadena:
        al eliminar una nota sus recibos quedan sin reportar y la siguiente Reemplazar debe llevarlos."""
        self.ensure_one()
        eliminadas = self._ne_cadena().filtered(lambda d: d.is_adjustment and d.eliminado)
        return recibos.filtered(lambda s: not s.l10n_co_ne_documento_id or s.l10n_co_ne_documento_id in eliminadas
                                or (nota and s.l10n_co_ne_documento_id == nota))

    def _ne_abrir_nota(self, tipo):
        nota = self.action_crear_ajuste(tipo)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': nota.id, 'view_mode': 'form',
                'target': 'current'}

    def action_crear_nota_reemplazar(self):
        return self._ne_abrir_nota('1')

    def action_crear_nota_eliminar(self):
        return self._ne_abrir_nota('2')

    @api.constrains('error_conocido_el')
    def _check_error_conocido_el(self):
        hoy = fields.Date.context_today(self)
        for doc in self:
            if doc.error_conocido_el and doc.error_conocido_el > hoy:
                raise ValidationError(_('La fecha en que se conoció el error no puede ser futura (%s).',
                                        doc.error_conocido_el))

    def _ne_validar(self):
        """Calcula las alertas (persistidas en ``alertas``) y pasa a 'ready' si no hay bloqueos. Alertas de esta
        etapa; las del XML (conciliación de totales, Salud/FondoPension) llegan con la etapa 3."""
        self.ensure_one()
        alertas = []

        def alerta(key, level, message, **extra):
            alertas.append(dict({'key': key, 'level': level, 'message': message}, **extra))

        if self.state == 'invoice_pending':
            alerta('en_proceso', 'danger', _('El documento espera el veredicto de la DIAN: consulte su estado primero.'))
        elif self.state == 'invoice_accepted' and not self.eliminado:
            alerta('aceptado', 'danger', _(
                'El documento ya fue aceptado por la DIAN: un cambio se corrige con una nota de ajuste.'))
        recibos_xml = self._ne_recibos_para_xml()
        if not recibos_xml:
            alerta('sin_recibos', 'danger', _('El documento no tiene recibos pagados en el mes.'))
        # Datos incompletos: los mismos prerrequisitos del ciclo por recibo, sin sus chequeos de estado.
        try:
            self.company_id._l10n_co_ne_validar_config()
        except UserError as error:
            alerta('compania', 'danger', str(error))
        for slip in recibos_xml:
            try:
                self._ne_validar_datos_recibo(slip)
            except UserError as error:
                alerta('datos_%s' % slip.id, 'danger', str(error))
        # Recibos propios cuya fecha de pago ya no cae en el mes del documento (cambio posterior a la transmisión).
        if not self.legacy:
            for slip in self.payslip_ids:
                try:
                    otro_mes = slip._ne_fecha_pago().replace(day=1) != self.period
                except UserError:
                    otro_mes = True
                if otro_mes:
                    alerta('recibo_otro_mes_%s' % slip.id, 'warning', _(
                        'La fecha de pago del recibo %(recibo)s ya no cae en el mes del documento.',
                        recibo=slip.display_name))
        # Recibo pagado en el mes que no está en ningún documento y el original ya se transmitió (D-5): pide una nota.
        if self.state and not self.is_adjustment and not self.legacy and not self.eliminado:
            tardios = self._ne_recibos_del_mes(self.company_id, self.employee_id, self.period).filtered(
                lambda s: not s.l10n_co_ne_documento_id)
            if tardios:
                alerta('recibo_tardio', 'warning', _(
                    'Hay recibos pagados del mes que no están en ningún documento: %(recibos)s. Cree una nota de '
                    'ajuste Reemplazar para incluirlos.', recibos=', '.join(tardios.mapped('display_name'))))
        # Envío fallido: no se recompone (su XML pudo llegar a la DIAN); si el mes cambió, se avisa en vez de cambiarlo.
        if self.state == 'invoice_sending_failed' and not self.is_adjustment and not self.legacy:
            mes = self._ne_recibos_del_mes(self.company_id, self.employee_id, self.period)
            if mes != self.payslip_ids:
                alerta('fallo_envio_composicion', 'warning', _(
                    'El documento tuvo un fallo de envío y su XML pudo haber llegado a la DIAN: no se recompone. Los '
                    'recibos del mes ya no coinciden con los del documento (%(recibos)s). Reintente el envío tal como '
                    'está y corrija el resto con una nota de ajuste.',
                    recibos=', '.join(((mes - self.payslip_ids) | (self.payslip_ids - mes)).mapped('display_name'))))
        # Recibos del mes que NO entraron (sin fecha de pago, en borrador...): ¿falta una quincena?
        fin = (self.period.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        faltan = self._ne_recibos_que_faltan(self.company_id, self.employee_id, self.period, recibos_xml)
        if faltan:
            alerta('faltan_recibos', 'warning', _(
                'Hay recibos del mes que no están en el documento (sin pagar, pagados en otro mes o sin fecha de pago): %(recibos)s.',
                recibos=', '.join(faltan.mapped('display_name'))), confirmable=True)
        # Mes en curso sin liquidación final pagada (D14: confirmación explícita del usuario, no bloqueo).
        hoy = fields.Date.context_today(self)
        liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion',
                                   raise_if_not_found=False)
        if hoy <= fin and not recibos_xml.filtered(lambda s: s.struct_id == liquidacion):
            alerta('mes_en_curso', 'warning', _(
                'El mes del documento no ha terminado y el empleado no tiene liquidación final pagada en él.'),
                confirmable=True)
        # Plazo de transmisión (D10): solo alerta, no bloquea.
        if self.fecha_limite and hoy > self.fecha_limite and self.state in (
                False, 'invoice_sending_failed'):
            alerta('plazo_vencido', 'warning', _(
                'El plazo de transmisión venció el %(fecha)s (10 días hábiles del mes siguiente%(base)s). Se puede '
                'transmitir igual: es una advertencia, no un bloqueo.', fecha=self.fecha_limite,
                base=_(' al conocimiento del error') if self.is_adjustment else ''))
        elif not self.fecha_limite and not self.legacy:
            alerta('plazo_sin_calcular', 'warning', _(
                'No se pudo calcular el plazo de transmisión: revise el calendario laboral y los festivos%(nota)s.',
                nota=_(' y la fecha en que se conoció el error') if self.is_adjustment else ''))
        alertas += self._ne_validar_xml()
        self.alertas = alertas
        bloqueos = [a for a in alertas if a['level'] == 'danger']
        if not self.state:
            self.etapa = 'draft' if bloqueos else 'ready'

    def _ne_validar_datos_recibo(self, slip):
        """Datos mínimos del empleado/contrato para generar el documento (sin los chequeos de estado del recibo)."""
        self.ensure_one()
        if not slip.employee_id.identification_id:
            raise UserError(_('El empleado %s no tiene número de identificación configurado.',
                              slip.employee_id.name))
        if not slip.contract_id:
            raise UserError(_('El recibo %s no tiene contrato asociado.', slip.number or slip.name))
        slip._ne_validar_cuenta_transferencia()
        slip.employee_id._l10n_co_nombre_dian()

    # ──────────────────────────────────────────────────────────────────
    # XML mensual: fusión de los recibos (doc 53 §5.3, §19; etapa 3)
    # ──────────────────────────────────────────────────────────────────
    def _ne_recibos_para_xml(self):
        """Recibos con los que se arma el XML (doc 53 §23.16, D-1 opción A).

        Un original: sus ``payslip_ids``. Una nota de ajuste NO reenlaza recibos: se derivan de la cadena (el
        documento padre y los de arriba, subiendo por ``parent_id``) más los propios, y solo cuentan los PAGADOS (un
        recibo cancelado del original sale solo). El M2O recibo → documento queda en el original."""
        self.ensure_one()
        if not self.is_adjustment:
            return self.payslip_ids
        recibos = self.payslip_ids
        vistos = {self.id}
        padre = self.parent_id
        while padre and padre.id not in vistos:
            vistos.add(padre.id)
            recibos |= padre.payslip_ids
            padre = padre.parent_id
        return recibos.filtered(lambda slip: slip.state in ('done', 'paid'))

    def _ne_predecesor(self):
        """Bloque ``predecesor`` de una nota de ajuste: número, CUNE y fecha de emisión del documento padre (NIAE190 y
        NIAE192). Sin padre aceptado, sin su XML o sin su ``FechaGen`` es un error claro, nunca un valor vacío."""
        self.ensure_one()
        padre = self.parent_id
        if not padre:
            raise UserError(_('La nota de ajuste "%s" no tiene documento original (padre).', self.display_name))
        if padre.state != 'invoice_accepted' or padre.eliminado:
            # Un documento eliminado conserva su último intento aceptado: no es un padre válido (doc 53 §26b).
            raise UserError(_('La nota de ajuste "%(nota)s" solo se arma contra un documento aceptado por la DIAN '
                              'y no eliminado (el original está: %(estado)s).', nota=self.display_name,
                              estado=_('Eliminado por nota de ajuste') if padre.eliminado else
                              (dict(padre._fields['state'].selection).get(padre.state) or _('Sin enviar'))))
        if not (padre.consecutive and padre.cune):
            raise UserError(_('El documento original "%s" no tiene consecutivo o CUNE.', padre.display_name))
        if self.adjustment_ref_cune != padre.cune:
            raise UserError(_('El CUNE de referencia de la nota "%s" no es el del documento original.',
                              self.display_name))
        if not padre.xml_attachment_id:
            raise UserError(_('Falta el XML del documento original "%s": no se puede leer su fecha de emisión.',
                              padre.display_name))
        try:
            fecha = nota_ajuste.fecha_gen_de_xml(base64.b64decode(padre.xml_attachment_id.datas))
        except Exception:   # XML ilegible: error claro, no un valor vacío
            fecha = ''
        if not fecha:
            raise UserError(_('No se pudo leer la fecha de emisión (FechaGen) del XML del documento original "%s".',
                              padre.display_name))
        return nota_ajuste.predecesor(padre.consecutive, padre.cune, fecha)

    def _ne_periodo(self, contrato):
        """Bloque ``Periodo`` del documento mensual (D3): liquidación desde max(1.º del mes, ingreso) hasta el retiro
        si el contrato terminó ese mes, o el fin de mes si sigue vigente. TiempoLaborado 360/30 con el día de
        ingreso incluido (D19, Anexo §8.3.1)."""
        self.ensure_one()
        primero = self.period
        ultimo = (primero.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        inicio = max(primero, contrato.date_start) if contrato.date_start else primero
        fin = min(ultimo, contrato.date_end) if contrato.date_end else ultimo
        ahora = _dt.now(pytz.timezone('America/Bogota'))
        return {
            'FechaIngreso': str(contrato.date_start) if contrato.date_start else '',
            'FechaRetiro': str(contrato.date_end) if contrato.date_end else '',
            'FechaLiquidacionInicio': str(inicio),
            'FechaLiquidacionFin': str(fin),
            'TiempoLaborado': str(dian_utils.compute_worked_time_360(contrato.date_start, fin, inclusive=True)),
            'FechaGen': ahora.strftime('%Y-%m-%d'),
        }

    def _collect_documento_data(self, consecutivo=None):
        """Diccionario del documento mensual para ``nomina_xml_builder``: los datos de cada recibo (código existente,
        sin reescribir constructores) fusionados por ``documento_merge``. ``consecutivo`` provisional (con prefijo)
        solo para armar la numeración cuando el documento aún no tiene el suyo; no gasta ninguno."""
        self.ensure_one()
        predecesor = self._ne_predecesor() if self.is_adjustment else None   # sin padre aceptado: error claro
        recibos = self._ne_recibos_para_xml().sorted('date_to')
        if not recibos:
            raise UserError(_('El documento "%s" no tiene recibos.', self.display_name))
        contrato = self.contract_id or recibos[-1].contract_id
        fechas = sorted({str(f) for slip in recibos for f in slip._ne_fechas_pago()})
        datos_recibos = [slip._collect_payslip_data() for slip in recibos]
        try:
            datos = documento_merge.fusionar_documento(
                datos_recibos, fechas, self._ne_periodo(contrato), periodo_nomina='5')
        except documento_merge.ErrorFusion as error:
            raise UserError(_('No se pueden fusionar los recibos del mes: %s', str(error)))
        # §5.4: el CUNE depende de ValDev/ValDed/ValTol; un error de suma es un rechazo de la DIAN.
        descuadres = documento_merge.conciliar_fusion(datos_recibos, datos)
        if descuadres:
            raise UserError(_('La fusión de los recibos no cuadra: %s', ' '.join(descuadres)))
        company = self.company_id
        numero = self.consecutive or consecutivo or ''
        prefijo = self._ne_prefijo()
        modo = company.l10n_co_ne_operation_mode_ids
        datos['numero_secuencia'] = dict(
            datos.get('numero_secuencia', {}), Prefijo=prefijo, Numero=numero,
            Consecutivo=numero[len(prefijo):] if prefijo and numero.startswith(prefijo) else numero)
        datos['proveedor_xml'] = dict(
            datos.get('proveedor_xml', {}),
            SoftwareSC=dian_utils.compute_software_security_code(modo.software_id, modo._ne_pin_del_software(), numero)
            if numero else '')
        if self.is_adjustment:
            # Nota de ajuste (Anexo §5.5.8): TipoXML 103, ``novedad`` con el CUNE de referencia y la sección
            # <Reemplazar> o <Eliminar> armada por el servicio (sin duplicar el código del recibo).
            datos['informacion_general'] = dict(datos.get('informacion_general', {}), TipoXML='103')
            datos['novedad'] = {'CUNENov': self.adjustment_ref_cune, 'value': True}
            if self.adjustment_type == '2':
                datos['tipo_nota'] = '2'
                datos['eliminar'] = nota_ajuste.eliminar_desde(datos, predecesor)
            else:
                datos['tipo_nota'] = '1'
                datos['reemplazar'] = nota_ajuste.reemplazar_desde(datos, predecesor)
        return datos

    def _ne_construir_xml(self, datos):
        """XML del documento: nota de ajuste o nómina individual (ambos sin CUNE ni firma)."""
        self.ensure_one()
        if self.is_adjustment:
            return nomina_xml_builder.build_nota_ajuste_v2(datos)
        return nomina_xml_builder.build_nomina_individual_v2(datos)

    def _ne_xml_sin_firmar(self, consecutivo=None):
        """XML mensual sin CUNE ni firma (para validar o previsualizar; no gasta consecutivo)."""
        self.ensure_one()
        return self._ne_construir_xml(self._collect_documento_data(consecutivo))

    def _ne_validar_xml(self):
        """Alertas que dependen del XML (se llaman desde ``_ne_validar``): la fusión debe ser posible y, D4, un
        documento sin Salud ni FondoPension solo avisa (p. ej. un mes con un solo pago de prima, que no lleva salud ni
        pensión; sin bloqueo)."""
        self.ensure_one()
        alertas = []
        if not self._ne_recibos_para_xml():
            return alertas
        try:
            datos = self._collect_documento_data(consecutivo='PRE')
        except UserError as error:
            return [{'key': 'xml', 'level': 'danger', 'message': str(error)}]
        nit = self.env.ref('l10n_co.rut', raise_if_not_found=False)
        if nit and self.employee_id.work_contact_id.l10n_latam_identification_type_id == nit:
            # Anexo, tabla 5.2.1: el codigo 31 (NIT) pasa el esquema, pero un trabajador (persona natural) se identifica
            # con Cedula, PPT, Cedula de extranjeria o Pasaporte: regla de negocio de InSoTech (David, 2026-11-14).
            alertas.append({'key': 'tipo_documento_trabajador', 'level': 'danger', 'message': _(
                'El empleado %(empleado)s está identificado con NIT. Un trabajador (persona natural) se identifica con '
                'Cédula de ciudadanía, Cédula de extranjería, PPT o Pasaporte: corrija el Tipo de documento en '
                'Contactos (contacto de trabajo del empleado) antes de enviar. El código 31 (NIT) pasa el esquema del '
                'Anexo (tabla 5.2.1) pero no corresponde a un trabajador.', empleado=self.employee_id.name)})
        if self.is_adjustment and self.adjustment_type == '2':
            return alertas   # <Eliminar> no lleva totales ni deducciones: no hay nada que conciliar
        dif_dev, dif_ded = documento_merge.diferencias_nodos(datos)
        if dif_dev or dif_ded:
            alertas.append({'key': 'totales_nodos', 'level': 'warning', 'message': _(
                'Los totales no son la suma de los nodos del XML (devengados %(dev)s, deducciones %(ded)s de '
                'diferencia): revise los conceptos antes de enviar.', dev=dif_dev, ded=dif_ded)})
        deducciones = datos.get('deducciones', {})
        if 'Salud' not in deducciones or 'FondoPension' not in deducciones:
            alertas.append({'key': 'sin_seguridad_social', 'level': 'warning', 'message': _(
                'El documento queda sin Salud o sin FondoPension (por ejemplo, un mes solo con prima): revíselo '
                'antes de enviarlo.')})
        diferencias = self._ne_conciliar_comprobantes()
        if diferencias:
            alertas.append({'key': 'conciliacion_comprobantes', 'level': 'warning', 'message': _(
                'Los comprobantes de pago no cuadran con los totales del documento en: %s. Suele deberse a líneas del '
                'recibo sin nodo en el XML de la DIAN; revíselas. El XML no se modifica.',
                '; '.join(self._ne_texto_diferencia(d) for d in diferencias))})
        return alertas

    # Representación gráfica oficial (Frente 5, C6a): solo para un documento ACEPTADO por la DIAN.
    def _ne_datos_representacion(self):
        """Datos de la representación gráfica (Res. 13/2021 art. 24: contenido mínimo de los arts. 5 y 17 y QR) leídos del
        XML validado del documento. Solo existe para un documento aceptado por la DIAN, con CUNE y consecutivo reales:
        nunca para borradores, pendientes, rechazados, eliminados ni migrados. No recalcula nada."""
        self.ensure_one()
        estado = dict(self._fields['state'].selection).get(self.state) or _('sin enviar')
        if self.legacy or self.eliminado:
            raise UserError(_('El documento "%s" está migrado o eliminado: no tiene representación gráfica.',
                              self.display_name))
        if self.state != 'invoice_accepted':
            raise UserError(_(
                'El documento "%(doc)s" no está aceptado por la DIAN (estado: %(estado)s): la representación gráfica '
                'solo se genera para documentos aceptados.', doc=self.display_name, estado=estado))
        if not (self.cune and self.consecutive and self.xml_attachment_id):
            raise UserError(_('El documento "%s" no tiene CUNE, consecutivo o XML validado.', self.display_name))
        try:
            return representacion_grafica.datos_representacion(self.xml_attachment_id.raw)
        except representacion_grafica.ErrorRepresentacion as error:
            raise UserError(_('No se puede generar la representación gráfica de "%(doc)s": %(error)s',
                              doc=self.display_name, error=str(error)))

    # Conciliación comprobante de pago ↔ documento mensual (Frente 5, C4): el comprobante (desglose del recibo, lo que
    # se le muestra al empleado) debe cuadrar con los valores del recibo que viajan al XML (devengados, deducciones y
    # su diferencia). Solo ALERTA: no bloquea y no toca el XML.
    _NE_UMBRAL_CONCILIACION = 1.0       # un peso: el XML lleva 2 decimales y las líneas pueden traer fracciones

    def _ne_conciliar_comprobantes(self):
        """Recibos del documento cuyo desglose del comprobante no cuadra con los totales que van al XML:
        ``[{'recibo', 'dev', 'ded', 'neto', 'motivo'}]`` con la diferencia (comprobante - XML) de devengado,
        deducciones y neto. Vacío si todo cuadra. Un recibo sin línea de neto se informa con su motivo (no falla).
        Solo lee: no escribe ni cambia el XML."""
        self.ensure_one()
        diferencias = []
        for recibo in self._ne_recibos_para_xml().sorted('date_to'):
            datos = recibo._collect_payslip_data()
            dev_xml = float(datos.get('devengados_total') or 0.0)
            ded_xml = float(datos.get('deducciones_total') or 0.0)
            try:
                desglose = recibo._ne_desglose()
            except UserError as error:
                diferencias.append({'recibo': recibo, 'dev': 0.0, 'ded': 0.0, 'neto': 0.0, 'motivo': str(error)})
                continue
            dev = desglose['devengado'] - dev_xml
            ded = desglose['deducciones'] - ded_xml
            neto = desglose['neto'] - (dev_xml - ded_xml)
            if max(abs(dev), abs(ded), abs(neto)) >= self._NE_UMBRAL_CONCILIACION:
                diferencias.append({'recibo': recibo, 'dev': dev, 'ded': ded, 'neto': neto, 'motivo': False})
        return diferencias

    @api.model
    def _ne_texto_diferencia(self, diferencia):
        """Texto de una diferencia de conciliación (nombra el recibo y los importes)."""
        recibo = diferencia['recibo']
        if diferencia['motivo']:
            return '%s (%s)' % (recibo.display_name, diferencia['motivo'])
        moneda = recibo.company_id.currency_id
        return _('%(recibo)s (devengado %(dev)s, deducciones %(ded)s, neto %(neto)s)', recibo=recibo.display_name,
                 dev=moneda.format(diferencia['dev']), ded=moneda.format(diferencia['ded']),
                 neto=moneda.format(diferencia['neto']))

    # ──────────────────────────────────────────────────────────────────
    # Generar y firmar (etapa 3b): consecutivo, CUNE, firma y adjunto
    # ──────────────────────────────────────────────────────────────────
    def _ne_prefijo_nomina(self):
        """Prefijo de nómina electrónica de la compañía. Sin prefijo configurado es un error claro (``res.company._ne_prefijo_consecutivo``, .304: una sola fuente)."""
        self.ensure_one()
        return self.company_id._ne_prefijo_consecutivo(False)

    def _ne_prefijo_ajuste(self):
        """Prefijo de las notas de ajuste de la compañía. Sin prefijo es un error claro."""
        self.ensure_one()
        return self.company_id._ne_prefijo_consecutivo(True)

    def _ne_prefijo(self):
        """Prefijo del consecutivo de ESTE documento: el de ajuste para una nota, el de nómina para un original."""
        self.ensure_one()
        return self.company_id._ne_prefijo_consecutivo(self.is_adjustment)

    def _ne_siguiente_consecutivo(self):
        """Siguiente consecutivo oficial de la compañía (la misma secuencia no_gap del ciclo por recibo): UNA sola función, ``res.company._ne_tomar_consecutivo`` (.304), con los controles de
        número ya enviado, secuencia atrasada y número ya asignado; sin secuencia o sin prefijo es un error claro, no hay fallback."""
        self.ensure_one()
        return self.company_id._ne_tomar_consecutivo(self.is_adjustment)

    def action_generar_xml(self):
        """Genera el XML mensual firmado: revalida, toma consecutivo (después de una corrida en seco), arma el
        XML fusionado, calcula el CUNE (depende de los totales fusionados), lo inserta, firma con XAdES-BES y
        guarda el adjunto. El documento queda 'ready' con su consecutivo, CUNE y XML (sin estado 'generado',
        doc 53 §18.6); un fallo después de tomar el número lo devuelve con el rollback (secuencia no_gap)."""
        self.ensure_one()
        # Se genera si nunca se envió, o si TODOS los envíos anteriores fueron rechazados (D-a: se corrige y se
        # regenera en el MISMO documento, con consecutivo y CUNE nuevos). Aceptado, pendiente, incierto, eliminado
        # o con un fallo de envío (se reintenta con el mismo XML) no se regeneran.
        solo_rechazos = all(i.state == 'invoice_rejected' for i in self.intento_ids)
        if self.incierto or self.eliminado or not (self.state in (False, 'invoice_rejected') and solo_rechazos):
            raise UserError(_(
                'El XML solo se genera para un documento en estado "Borrador", "Listo" o "Rechazado" que no se '
                'haya enviado con éxito (hoy: %s).',
                dict(self._fields['state'].selection).get(self.state) or dict(self._fields['etapa'].selection).get(self.etapa)))
        self._ne_validar()
        bloqueos = [a['message'] for a in (self.alertas or []) if a['level'] == 'danger']
        if bloqueos:
            raise UserError(_('El documento tiene bloqueos: %s', ' '.join(bloqueos)))
        company = self.company_id
        prefijo = self._ne_prefijo()
        # Un consecutivo que ya viajó a la DIAN en un intento rechazado NO se reutiliza jamás: la DIAN devuelve el
        # veredicto viejo si se repite (doc 53 §23.15; memoria del equipo sobre consecutivos rechazados).
        consecutivo_usado = bool(self.consecutive) and self.consecutive in self.intento_ids.mapped('numero')
        if consecutivo_usado or not self.consecutive or not self.consecutive.startswith(prefijo):
            self._ne_xml_sin_firmar('%s1' % prefijo)   # corrida en seco: los errores de datos salen ANTES del número
            self.consecutive = self._ne_siguiente_consecutivo()
        datos = self._collect_documento_data()
        xml_bytes = self._ne_construir_xml(datos)
        cune = self._ne_calcular_cune(datos)
        xml_bytes = ne_xml_utils.insertar_cune_y_qr(xml_bytes, cune, company._ne_dian_qr_host())
        llave, cert_pem, cert_der, cert_obj, cadena = xml_signer.load_from_certificate(company._get_ne_certificate())
        firmado = xml_signer.sign_xml(
            xml_bytes=xml_bytes, private_key=llave, cert_pem=cert_pem, cert_der=cert_der, cert_obj=cert_obj,
            cert_chain=cadena)
        nit = (company.vat or 'SIN_NIT').replace('-', '').strip()
        self.cune = cune
        self.xml_attachment_id = self.env['ir.attachment'].create({
            'name': 'ne_%s_%s.xml' % (nit, self.consecutive), 'type': 'binary', 'datas': base64.b64encode(firmado),
            'res_model': self._name, 'res_id': self.id, 'mimetype': 'application/xml'})
        _logger.info('XML mensual generado para %s (CUNE: %s)', self.display_name, cune)
        return True

    def _ne_calcular_cune(self, datos):
        """CUNE del documento mensual (Anexo §8.1.1.4): ValDev/ValDed/ValTol son los totales FUSIONADOS."""
        self.ensure_one()
        company = self.company_id
        info = datos['informacion_general']
        totales = datos['totales']
        # Nota Eliminar: el Anexo §8.1.1.4 fija ValDev=ValDed=ValTol=0.00 y DocEmp=0 (no lee los totales).
        es_eliminar = bool(self.is_adjustment and self.adjustment_type == '2')
        valores = nota_ajuste.cune_valores(
            es_eliminar, {} if es_eliminar else totales, self.employee_id.identification_id or '')
        cune, _raw = cune_service.compute_cune(
            num_ne=self.consecutive, fec_ne=info['FechaGen'], hor_ne=info['HoraGen'],
            val_dev=valores['val_dev'], val_ded=valores['val_ded'],
            val_tol=valores['val_tol'], nit_ne=dian_utils.clean_nit(company.vat),
            doc_trab=valores['doc_trab'], cl_ne='103' if self.is_adjustment else '102',
            software_pin=company.l10n_co_ne_operation_mode_ids._ne_pin_del_software() or '',
            tipo_amb=company.l10n_co_ne_environment or '2')
        return cune

    # ──────────────────────────────────────────────────────────────────
    # Enviar a la DIAN (doc 53 §23.12 3.1, §23.15)
    # ──────────────────────────────────────────────────────────────────
    def _ne_fuera_de_plazo(self):
        """True si el plazo de transmisión (``fecha_limite``; para una nota, el de D4) ya venció. Un documento migrado
        (legacy) no tiene plazo."""
        self.ensure_one()
        return bool(self.fecha_limite and not self.legacy and fields.Date.context_today(self) > self.fecha_limite)

    def _ne_exigir_plazo(self, confirmado=False):
        """Bloqueo por plazo vencido (doc 53 §28.8, D7): política PROPIA de la compañía (apagada por defecto), no un
        rechazo de la DIAN (el Anexo no valida el plazo). Con el bloqueo activo y el plazo vencido, el documento solo
        se encola/envía si un administrador de nómina confirmó el envío extemporáneo."""
        self.ensure_one()
        if self.company_id.l10n_co_ne_bloquear_extemporaneo and self._ne_fuera_de_plazo() and not confirmado:
            raise UserError(_(
                'El plazo de transmisión del documento "%(doc)s" venció el %(fecha)s y la compañía exige confirmar el '
                'envío extemporáneo: marque "Confirmo envío extemporáneo" en Enviar y Procesar (solo el administrador de '
                'nómina puede confirmarlo).', doc=self.display_name, fecha=self.fecha_limite))

    def _ne_precondiciones_envio(self, confirmado=None):
        """UserError local, ANTES de tocar la DIAN: sin intento, sin consecutivo gastado. ``confirmado`` (envío
        extemporáneo): al encolar lo trae quien confirma; el cron lo lee de la cola (``sending_data``), así no puede
        saltarse el bloqueo."""
        self.ensure_one()
        nombre_estado = dict(self._fields['state'].selection).get(self.state)
        if self.legacy:
            raise UserError(_(
                'El documento "%s" es un documento migrado del ciclo por recibo: se reporta por recibo.',
                self.display_name))
        if self.eliminado:
            raise UserError(_('El documento "%s" ya fue eliminado por una nota de ajuste.', self.display_name))
        if self.is_adjustment:
            # La nota solo se envía contra el ÚLTIMO documento aceptado de su cadena, vigente y no eliminado (§23.16).
            padre = self.parent_id
            if not padre or padre.state != 'invoice_accepted' or padre.eliminado \
                    or padre != padre._ne_ultimo_aceptado():
                raise UserError(_(
                    'La nota de ajuste "%s" ya no cuelga del último documento aceptado de su cadena (o este fue '
                    'eliminado): no se envía. Cree una nota nueva.', self.display_name))
        if self.incierto:
            raise UserError(_('El documento "%s" tiene un envío incierto: consulte su estado primero.',
                              self.display_name))
        if self.state in ('invoice_pending', 'invoice_accepted'):
            raise UserError(_('El documento "%(doc)s" ya fue enviado a la DIAN (estado: %(estado)s).',
                              doc=self.display_name, estado=nombre_estado))
        if self.state == 'invoice_rejected':
            raise UserError(_(
                'La DIAN rechazó el XML vigente del documento "%s". Corrija los datos y genere el XML otra vez '
                '(toma un consecutivo nuevo): el mismo XML no se reenvía.', self.display_name))
        if self.etapa != 'ready' or not (self.cune and self.consecutive and self.xml_attachment_id):
            raise UserError(_('Genere el XML del documento "%s" antes de enviarlo.', self.display_name))
        # .304 (doc 77, A): el número de este documento no pudo haber viajado ya en otro (p. ej. tras restaurar o mover la secuencia).
        self.company_id._ne_exigir_numero_sin_viajar(self.consecutive, self.is_adjustment, documento=self)
        if confirmado is None:
            confirmado = bool((self.sending_data or {}).get('extemporaneo_confirmado'))
        self._ne_exigir_plazo(confirmado)
        self._ne_bloquear_en_habilitacion()
        self.company_id._l10n_co_ne_validar_config()

    def _ne_bloquear_en_habilitacion(self):
        """El documento mensual solo habla con la DIAN en Producción hasta la etapa 5 (D-b): una compañía en ambiente
        de pruebas o con el proceso de certificación activo se atiende por recibo."""
        self.ensure_one()
        company = self.company_id
        if company.l10n_co_ne_environment == '2' or company.l10n_co_ne_certification_process:
            raise UserError(_(
                'La compañía "%s" está en habilitación (ambiente de pruebas o proceso de certificación): en '
                'habilitación el ciclo es por recibo hasta que el documento mensual pase a habilitación. El '
                'documento mensual solo se transmite y se consulta en Producción.', company.name))

    def _ne_enviar_uno(self):
        """Envía UN documento a la DIAN y registra el resultado en un intento nuevo.

        No lanza por lo que responda o por lo que falle en la DIAN (queda en el intento: un fallo de conexión
        es "Envío fallido", reintentable con el MISMO consecutivo, CUNE y XML, nunca rechazo). Lanza UserError solo
        por precondiciones locales, antes de llamar. El ``state`` del documento se recalcula solo.

        Returns:
            ``l10n.co.ne.documento.intento`` creado.
        """
        self.ensure_one()
        self._ne_precondiciones_envio()
        company = self.company_id
        xml = base64.b64decode(self.xml_attachment_id.datas)
        nit = (company.vat or 'SIN_NIT').replace('-', '').strip()
        filename = 'ne_%s_%s.xml' % (nit, self.consecutive)
        exchange = self.env['l10n.co.ne.exchange']
        respuesta = {}
        if company.l10n_co_ne_demo_mode:
            # Modo Demo: validación local, sin transmitir (mismo criterio que el ciclo por recibo).
            estado, zip_key = 'invoice_accepted', ''
            message_json = {
                'is_valid': True, 'status_code': '00', 'detail': '', 'errors': [], 'transport': False, 'fault': [],
                'status': _('Validado localmente en Modo Demo (sin transmisión real a la DIAN).')}
        else:
            llave, cert_pem, _der, _cert_obj, _cadena = xml_signer.load_from_certificate(company._get_ne_certificate())
            endpoint = company._ne_dian_endpoint()
            respuesta = soap_client.send_nomina_sync(
                xml_bytes=xml, filename=filename, private_key=llave, cert_pem=cert_pem, endpoint=endpoint,
                timeout=company._ne_config_int_param(
                    'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT))
            resultado = dian_respuesta.interpretar_respuesta(respuesta, contexto=dian_respuesta.CONTEXTO_ENVIO)
            estado = _ESTADO_INTENTO_POR_VEREDICTO[resultado.veredicto]
            zip_key = resultado.zip_key
            message_json = dian_message.build_message_json(respuesta)
            exchange = self.env['l10n.co.ne.exchange'].create_exchange(
                company, 'send_sync', endpoint, respuesta, self.payslip_ids, documento=self)
        intento = self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': self.id, 'datetime': fields.Datetime.now(), 'state': estado,
            'identifier': self.cune, 'zip_key': zip_key or False, 'numero': self.consecutive,
            'file_name': filename, 'sha256': hashlib.sha256(xml).hexdigest(),
            'attachment_id': self.xml_attachment_id.id, 'message_json': message_json,
            'test_environment': company.l10n_co_ne_environment == '2',
            'certification_process': bool(company.l10n_co_ne_certification_process),
            'exchange_id': exchange.id or False})
        intento._ne_guardar_application_response(respuesta)           # E-1: constancia de la DIAN legible (.xml)
        vals = {'sending_data': False}
        if zip_key:
            vals['zip_key'] = zip_key
        self.write(vals)
        self._ne_tras_veredicto()
        self.message_post(
            body=_('Envío a la DIAN: %s.', dict(intento._fields['state'].selection).get(estado)),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return intento

    # Entrega de la representación gráfica y el XML al empleado (Frente 5, C6c). Solo tras la aceptación de la DIAN (patrón
    # de facturación: el correo sale después de la DIAN y solo si fue aceptado). Un fallo de correo NO cambia el estado DIAN.
    NE_MARCA_REPRESENTACION = 'Representación gráfica y XML enviados por correo'
    NE_PLANTILLA_REPRESENTACION_XMLID = 'l10n_co_nomina_electronica.mail_template_representacion_grafica'
    NE_REPORTE_REPRESENTACION_XMLID = 'l10n_co_nomina_electronica.action_report_representacion_grafica'

    def _ne_tras_veredicto(self):
        """Lo que sigue a un veredicto de la DIAN (envío síncrono, reconsulta o consulta por CUNE): aplicar la eliminación
        de una nota y, si se pidió, entregar la representación al empleado."""
        self._ne_aplicar_eliminacion()
        self._ne_entregar_representacion_si_acepta()

    def _ne_entregar_representacion_si_acepta(self):
        """Para cada documento con la intención registrada y ya ACEPTADO por la DIAN, envía la representación. Nunca
        lanza: un fallo (sin correo, sin plantilla, error de render o de cola) queda como nota en el chatter y no cambia
        el estado DIAN; la intención se consume en ambos casos (se reintenta marcando de nuevo la casilla)."""
        for doc in self.filtered(lambda d: d.entregar_representacion and d.state == 'invoice_accepted'):
            try:
                with self.env.cr.savepoint():
                    doc._ne_enviar_representacion()
            except Exception as error:   # no se traga: queda en el chatter y en el log
                _logger.error('Fallo al enviar la representación del documento %s: %s', doc.display_name, error)
                doc.message_post(
                    body=_('Fallo al enviar la representación gráfica y el XML por correo: %s', error),
                    message_type='comment', subtype_xmlid='mail.mt_note')
            doc.entregar_representacion = False

    def _ne_zip_representacion(self):
        """Adjunto ZIP del documento: la representación gráfica (PDF) y el XML validado, con
        ``ir.attachment._build_zip_from_attachments`` (helper nativo). Se REUTILIZA el existente (mismo nombre). No es un
        contenedor definido por la DIAN: es una comodidad de este módulo."""
        self.ensure_one()
        self._ne_datos_representacion()          # solo para un documento aceptado, con XML y QR
        nombre = 'Nomina_electronica_%s.zip' % self.consecutive
        existente = self.env['ir.attachment'].search([
            ('res_model', '=', self._name), ('res_id', '=', self.id), ('name', '=', nombre)], limit=1)
        if existente:
            return existente
        reporte = self.env.ref(self.NE_REPORTE_REPRESENTACION_XMLID, raise_if_not_found=False)
        if not reporte:
            raise UserError(_('No se encontró el reporte de la representación gráfica (%s).',
                              self.NE_REPORTE_REPRESENTACION_XMLID))
        pdf, _tipo = self.env['ir.actions.report'].sudo()._render_qweb_pdf(reporte.id, self.ids)
        Adjunto = self.env['ir.attachment']
        piezas = Adjunto.create([
            {'name': 'Representacion_grafica_%s.pdf' % self.consecutive, 'raw': pdf, 'mimetype': 'application/pdf'},
            {'name': '%s.xml' % self.consecutive, 'raw': self.xml_attachment_id.raw, 'mimetype': 'application/xml'}])
        try:
            contenido = piezas._build_zip_from_attachments()
        finally:
            piezas.unlink()
        return Adjunto.create({
            'name': nombre, 'raw': contenido, 'mimetype': 'application/zip', 'res_model': self._name,
            'res_id': self.id})

    def _ne_enviar_representacion(self, template=None):
        """Envía al correo del contacto de trabajo del empleado el ZIP (PDF de la representación + XML validado), por la
        cola nativa de correo. Solo para un documento aceptado. Deja nota en el chatter."""
        self.ensure_one()
        correo = self.employee_id.work_contact_id.email
        if not correo:
            raise UserError(_('El empleado %s no tiene correo en su contacto de trabajo.', self.employee_id.name))
        template = template or self.env.ref(self.NE_PLANTILLA_REPRESENTACION_XMLID, raise_if_not_found=False)
        if not template:
            raise UserError(_('No se encontró la plantilla de correo "%s".', self.NE_PLANTILLA_REPRESENTACION_XMLID))
        adjunto = self._ne_zip_representacion()
        valores = {'email_to': correo, 'attachment_ids': [(6, 0, adjunto.ids)]}
        # Remitente: el usuario que envía (patron de la plantilla nativa de la colilla). Si lo envia el sistema (el cron
        # que recibe la aceptacion) no hay usuario humano: se deja el remitente por defecto del servidor de correo.
        if not self.env.user._is_superuser() and self.env.user.email:
            valores['email_from'] = self.env.user.email_formatted
        mail_id = template.send_mail(self.id, force_send=False, email_values=valores)
        if not self.env['mail.mail'].sudo().browse(mail_id).exists():
            raise UserError(_('La plantilla "%s" no generó el correo.', template.display_name))
        self.message_post(
            body=_('%(marca)s a %(correo)s.', marca=self.NE_MARCA_REPRESENTACION, correo=correo),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return True

    def _ne_solicitar_entrega_representacion(self):
        """Desde Enviar y Procesar: si el documento ya está aceptado, envía la representación al momento; si no, registra
        la intención y la envía el cron/consulta que reciba la aceptación. Devuelve un texto de aviso o False."""
        self.ensure_one()
        if self.legacy or self.eliminado:
            raise UserError(_('El documento "%s" está migrado o eliminado: no tiene representación gráfica.',
                              self.display_name))
        ya_enviada = any(self.NE_MARCA_REPRESENTACION in str(m.body or '') for m in self.message_ids)
        aviso = _('%s: ya se había enviado la representación gráfica y el XML por correo antes.',
                  self.display_name) if ya_enviada else False
        self.entregar_representacion = True
        if self.state == 'invoice_accepted':
            self._ne_entregar_representacion_si_acepta()
        return aviso

    def _ne_aplicar_eliminacion(self):
        """Una nota Eliminar ACEPTADA marca a su padre como eliminado (``eliminado_por_id`` = la nota). Rechazada o
        pendiente no cambia nada; una Reemplazar aceptada deja al padre como histórico (§23.16, 6c)."""
        for nota in self:
            if nota.is_adjustment and nota.adjustment_type == '2' and nota.state == 'invoice_accepted' \
                    and nota.parent_id and not nota.parent_id.eliminado:
                nota.parent_id.write({'eliminado': True, 'eliminado_por_id': nota.id})
                nota.parent_id.message_post(
                    body=_('Eliminado por la nota de ajuste "%s".', nota.display_name),
                    message_type='comment', subtype_xmlid='mail.mt_note')

    # ──────────────────────────────────────────────────────────────────
    # Cola de envío y cron (doc 53 §23.17, 7b). Patrón de ``account.move.send``: ``sending_data`` + ``_trigger`` + cron.
    # ──────────────────────────────────────────────────────────────────
    _CRON_ENVIO_XMLID = 'l10n_co_nomina_electronica.ir_cron_ne_documento_send'

    def _ne_commit(self):
        """Único punto de ``commit`` de la cola (como ``_can_commit`` del nativo): un commit dentro de una prueba
        rompería su transacción, así que no se hace cuando hay una prueba en curso; las pruebas lo parchean."""
        if not modules.module.current_test:
            self.env.cr.commit()

    def _ne_cron_envio(self):
        # sudo: ``ir.cron`` solo lo lee el administrador del sistema y quien encola es el administrador de NÓMINA
        # (mismo criterio del nativo ``account.move.send``: consultar/disparar la acción planificada con sudo).
        cron = self.env.ref(self._CRON_ENVIO_XMLID, raise_if_not_found=False)
        if not cron:
            raise UserError(_('Falta la acción planificada del envío de documentos de nómina electrónica '
                              '(%s).', self._CRON_ENVIO_XMLID))
        return cron.sudo()

    def _ne_encolar(self, confirmo_extemporaneo=False):
        """Pone los documentos en la cola de envío. NO envía: lo hace el cron.

        Corre las MISMAS precondiciones de ``_ne_enviar_uno`` (el error sale ahora, no horas después) y exige que no
        estén ya en la cola. Es atómico: si uno falla, ninguno se encola. ``sending_data`` lleva autor, hora y el
        estado de reintentos; se dispara el cron una sola vez.

        ``confirmo_extemporaneo`` (D7): con el bloqueo por plazo activo, un documento fuera de plazo solo se encola si
        lo confirma un administrador de nómina; queda constancia (usuario, fecha y plazo vencido) en el chatter y en
        la cola, y el cron la respeta."""
        if confirmo_extemporaneo and not (self.env.is_superuser()
                                          or self.env.user.has_group('hr_payroll.group_hr_payroll_manager')):
            raise AccessError(_('Solo el administrador de nómina puede confirmar un envío extemporáneo.'))
        cron = self._ne_cron_envio()
        if not cron.active:
            raise UserError(_('La acción planificada de envío de nómina electrónica está archivada: actívela en '
                              'Ajustes > Técnico > Acciones planificadas para poder encolar envíos.'))
        for doc in self:
            if doc.is_being_sent:
                raise UserError(_('El documento "%s" ya está en la cola de envío.', doc.display_name))
            doc._ne_precondiciones_envio(confirmado=confirmo_extemporaneo)
        ahora = fields.Datetime.to_string(fields.Datetime.now())
        for doc in self:
            datos = {
                'author_user_id': self.env.user.id, 'author_partner_id': self.env.user.partner_id.id,
                'queued_at': ahora, 'intentos': 0, 'proximo': ahora}
            if confirmo_extemporaneo and doc.company_id.l10n_co_ne_bloquear_extemporaneo and doc._ne_fuera_de_plazo():
                datos['extemporaneo_confirmado'] = {
                    'user_id': self.env.user.id, 'fecha': str(fields.Date.context_today(self)),
                    'plazo': str(doc.fecha_limite)}
                doc.message_post(
                    body=_('Envío extemporáneo confirmado por %(usuario)s el %(fecha)s: el plazo de transmisión venció '
                           'el %(plazo)s.', usuario=self.env.user.name, fecha=fields.Date.context_today(self),
                           plazo=doc.fecha_limite),
                    message_type='comment', subtype_xmlid='mail.mt_note')
            doc.sending_data = datos
        if self:
            cron._trigger()
        return self

    @api.model
    def _ne_espera_reintento(self, intentos, company):
        """Minutos de espera tras ``intentos`` fallos de transporte seguidos: base × 2^(n-1) con tope (5, 10, 20, 40, 60)."""
        base = company._ne_config_int_param('l10n_co_nomina_electronica.send_retry_minutes', 5)
        tope = company._ne_config_int_param('l10n_co_nomina_electronica.send_retry_max_minutes', 60)
        return min(base * 2 ** (intentos - 1), tope)

    def _ne_avisar_autor(self, partner_id, titulo, mensaje, advertencia=False):
        """Notificación nativa del bus (``simple_notification``, sin JavaScript propio) al autor del envío."""
        if partner_id:
            self.env['bus.bus']._sendone(
                self.env['res.partner'].browse(partner_id), 'simple_notification',
                {'title': titulo, 'message': mensaje, 'warning': advertencia})

    @api.model
    def _ne_barrido_en_curso(self, ahora):
        """Un envío ``en_curso`` más viejo que ``send_stale_minutes`` sin intento posterior es un proceso que murió
        durante el envío: el documento pasa a ``incierto`` (pudo llegar a la DIAN) y se avisa al autor. Con un intento
        posterior solo se limpia la cola. Un ``en_curso`` reciente no se toca (otro proceso puede estar enviando)."""
        company = self.env.company
        minutos = company._ne_config_int_param('l10n_co_nomina_electronica.send_stale_minutes', 15)
        limite = ahora - timedelta(minutes=minutos)
        for doc in self.sudo().search([('sending_data', '!=', False)]):
            datos = doc.sending_data or {}
            if not datos.get('en_curso'):
                continue
            desde = fields.Datetime.to_datetime(datos['en_curso'])
            if desde > limite:
                continue
            if doc.intento_ids.filtered(lambda i: i.create_date and i.create_date >= desde):
                doc.sending_data = False
                continue
            doc.write({'incierto': True, 'sending_data': False})
            doc.message_post(
                body=_('El proceso se interrumpió durante el envío a la DIAN: el documento queda como envío incierto. '
                       'Consulte su estado.'), message_type='comment', subtype_xmlid='mail.mt_note')
            doc._ne_avisar_autor(datos.get('author_partner_id'), _('Envío interrumpido'), _(
                'El envío de "%s" se interrumpió: consulte su estado en la DIAN.', doc.display_name), True)
            self._ne_commit()

    @api.model
    def _cron_enviar_cola(self):
        """Cron de envío: procesa la cola de documentos, uno por uno y aislados.

        1. Barrido de envíos interrumpidos. 2. Por compañía colombiana y fuera de habilitación, hasta
        ``send_batch_size`` documentos con ``proximo`` vencido (orden: mes e id), con candado de fila. 3. Por
        documento: COMMIT PREVIO de ``en_curso`` ANTES de llamar a la DIAN y otro al terminar (un ZipKey ya recibido
        no se pierde). Aceptado, rechazado o pendiente no se reintentan; un fallo de transporte sí, con espera
        creciente; un ``UserError`` local no; una excepción inesperada deja el documento ``incierto`` (nunca un fallo
        reintentable: pudo haber llegado a la DIAN)."""
        ahora = fields.Datetime.now()
        self._ne_barrido_en_curso(ahora)
        resultados = {}   # author_partner_id -> {'aceptado': n, ...}
        quedan = False
        companias = self.env['res.company'].sudo().search([
            ('partner_id.country_id.code', '=', 'CO'), ('l10n_co_ne_environment', '=', '1'),
            ('l10n_co_ne_certification_process', '=', False)])
        for company in companias:
            vencidos = self.sudo().search([
                ('company_id', '=', company.id), ('sending_data', '!=', False),
                ('legacy', '=', False), ('eliminado', '=', False)], order='period, id').filtered(
                lambda d: not (d.sending_data or {}).get('en_curso') and not (d.sending_data or {}).get('error')
                and fields.Datetime.to_datetime((d.sending_data or {}).get('proximo') or ahora) <= ahora)
            lote = company._ne_config_int_param('l10n_co_nomina_electronica.send_batch_size', 10)
            if len(vencidos) > lote:
                quedan = True
            vencidos = vencidos[:lote]
            if vencidos:
                self.env.cr.execute(
                    'SELECT id FROM l10n_co_ne_documento WHERE id IN %s FOR UPDATE SKIP LOCKED', (tuple(vencidos.ids),))
                vencidos = vencidos.browse([row[0] for row in self.env.cr.fetchall()])
            for doc in vencidos:
                datos = dict(doc.sending_data)
                resumen = resultados.setdefault(datos.get('author_partner_id') or 0, {})

                def contar(clave, _r=resumen):
                    _r[clave] = _r.get(clave, 0) + 1
                datos['en_curso'] = fields.Datetime.to_string(fields.Datetime.now())
                doc.sending_data = datos
                self._ne_commit()                      # commit previo: ANTES de llamar a la DIAN
                try:
                    with self.env.cr.savepoint():
                        intento = doc._ne_enviar_uno()
                except UserError as error:
                    doc.sending_data = {'error': str(error), 'author_partner_id': datos.get('author_partner_id')}
                    doc.message_post(body=_('No se envió el documento desde la cola: %s', error),
                                     message_type='comment', subtype_xmlid='mail.mt_note')
                    contar('fallido')
                except Exception as error:   # noqa: BLE001 -- pudo llegar a la DIAN: incierto, no reintento
                    _logger.exception('Cola de envío: error inesperado enviando el documento %s', doc.id)
                    doc.write({'incierto': True, 'sending_data': False})
                    doc.message_post(body=_('Error inesperado durante el envío (%s): el documento queda como envío '
                                            'incierto. Consulte su estado.', error),
                                     message_type='comment', subtype_xmlid='mail.mt_note')
                    contar('incierto')
                else:
                    if intento.state == 'invoice_sending_failed':
                        intentos = int(datos.get('intentos') or 0) + 1
                        maximo = company._ne_config_int_param('l10n_co_nomina_electronica.send_max_retries', 5)
                        if intentos <= maximo:
                            espera = self._ne_espera_reintento(intentos, company)
                            doc.sending_data = {
                                'author_user_id': datos.get('author_user_id'),
                                'author_partner_id': datos.get('author_partner_id'),
                                'queued_at': datos.get('queued_at'), 'intentos': intentos,
                                'extemporaneo_confirmado': datos.get('extemporaneo_confirmado'),
                                'proximo': fields.Datetime.to_string(fields.Datetime.now() + timedelta(minutes=espera))}
                            contar('reintento')
                        else:
                            doc.sending_data = False
                            doc.message_post(body=_('Se agotaron los reintentos de envío: el documento queda como '
                                                    'envío fallido.'), message_type='comment',
                                             subtype_xmlid='mail.mt_note')
                            contar('fallido')
                    else:
                        contar({'invoice_accepted': 'aceptado', 'invoice_rejected': 'rechazado'}.get(
                            intento.state, 'pendiente'))
                self._ne_commit()
        # Avisos al autor y limpieza de los errores locales ya notificados.
        for doc in self.sudo().search([('sending_data', '!=', False)]):
            if (doc.sending_data or {}).get('error'):
                doc.sending_data = False
        for partner_id, resumen in resultados.items():
            if partner_id and resumen:
                texto = _('Envío a la DIAN: %s.', ', '.join('%s %s' % (n, k) for k, n in sorted(resumen.items())))
                self._ne_avisar_autor(partner_id, _('Nómina electrónica'), texto,
                                      bool(resumen.get('fallido') or resumen.get('incierto')))
        if quedan:
            self._ne_cron_envio()._trigger()

    # ──────────────────────────────────────────────────────────────────
    # Reconsultar el estado en la DIAN (doc 53 §23.12 3.2, §23.3)
    # ──────────────────────────────────────────────────────────────────
    def _ne_precondiciones_consulta(self):
        """UserError local, ANTES de tocar la DIAN. Devuelve el intento que se consulta (el último)."""
        self.ensure_one()
        if self.legacy:
            raise UserError(_('El documento "%s" es un documento migrado del ciclo por recibo: se consulta por '
                              'recibo.', self.display_name))
        if self.eliminado:
            raise UserError(_('El documento "%s" ya fue eliminado por una nota de ajuste.', self.display_name))
        intento = self._ultimo_intento()
        if not intento:
            raise UserError(_('El documento "%s" no se ha enviado a la DIAN: no hay nada que consultar.',
                              self.display_name))
        if intento.state in ('invoice_accepted', 'invoice_rejected'):
            raise UserError(_('El último envío del documento "%(doc)s" ya tiene veredicto de la DIAN (%(estado)s).',
                              doc=self.display_name,
                              estado=dict(intento._fields['state'].selection).get(intento.state)))
        if not intento.zip_key:
            raise UserError(_('El último envío del documento "%s" no tiene ZipKey: no se puede consultar su estado.',
                              self.display_name))
        self._ne_bloquear_en_habilitacion()
        self.company_id._l10n_co_ne_validar_config()
        return intento

    def _ne_respuesta_es_de_este_documento(self, respuesta, intento):
        """Un ZIP = un documento. Si la respuesta trae un identificador (CUNE; si no, número), debe ser el de este
        envío; sin identificadores se identifica por el ZipKey consultado."""
        cunes = dian_respuesta.candidatos_cune(respuesta)
        if cunes:
            return intento.identifier in cunes
        numeros = dian_respuesta.candidatos_numero(respuesta)
        if numeros:
            return intento.numero in numeros
        return True

    def _ne_nota_una_vez(self, texto, clave):
        """Aviso en el chatter sin repetirlo en cada consulta (el cron reconsulta cada pocos minutos). ``clave`` es
        una frase fija del aviso, sin comillas ni símbolos HTML (el cuerpo se guarda escapado)."""
        self.ensure_one()
        if not self.message_ids.filtered(lambda m: m.body and clave in str(m.body)):
            self.message_post(body=texto, message_type='comment', subtype_xmlid='mail.mt_note')

    def _ne_reconsultar(self):
        """Consulta a la DIAN el estado del último envío (``GetStatusZip`` por su ZipKey) y lo aplica.

        - ``aceptado`` / ``rechazado``: actualiza el MISMO intento (no crea otro) y limpia ``incierto``.
        - ``pendiente``: el intento sigue pendiente; pasadas ``recheck_max_hours`` desde el envío, el documento queda
          ``incierto`` (sale de la reconsulta automática y se concilia a mano).
        - ``nivel_set``: la DIAN respondió sobre el SET de pruebas, no sobre este documento: no resuelve nada.
        - ``error_transporte``: no cambia el estado.
        - Respuesta de otro documento (CUNE distinto) o con varios resultados: no cambia el estado y avisa.
        Siempre guarda la evidencia de la consulta (inmutable). Lanza UserError solo por precondiciones locales.

        Returns:
            ``dian_respuesta.ResultadoDian`` de la consulta.
        """
        self.ensure_one()
        intento = self._ne_precondiciones_consulta()
        company = self.company_id
        llave, cert_pem, _der, _cert_obj, _cadena = xml_signer.load_from_certificate(company._get_ne_certificate())
        endpoint = company._ne_dian_endpoint()
        respuesta = soap_client.get_status_zip(
            track_id=intento.zip_key, private_key=llave, cert_pem=cert_pem, endpoint=endpoint,
            timeout=company._ne_config_int_param(
                'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT))
        resultado = dian_respuesta.interpretar_respuesta(respuesta, contexto=dian_respuesta.CONTEXTO_CONSULTA)
        self.env['l10n.co.ne.exchange'].create_exchange(
            company, 'get_status_zip', endpoint, respuesta, self.payslip_ids, queried_zip_key=intento.zip_key,
            parent_exchange=intento.exchange_id, documento=self)
        veredicto = resultado.veredicto
        if veredicto == dian_respuesta.ERROR_TRANSPORTE:
            return resultado
        if veredicto == dian_respuesta.NIVEL_SET:
            self._ne_nota_una_vez(_(
                'La DIAN respondió sobre el SET de pruebas, no sobre este documento: %s. No se cambia el estado.',
                resultado.mensaje), 'respondió sobre el SET de pruebas')
            return resultado
        if len(respuesta.get('DianResponses') or []) > 1:
            self._ne_nota_una_vez(_(
                'La DIAN devolvió varios resultados para un envío de un solo documento: no se cambia el estado. '
                'Revise la evidencia de la consulta.'), 'varios resultados para un envío')
            return resultado
        if veredicto in (dian_respuesta.ACEPTADO, dian_respuesta.RECHAZADO) \
                and not self._ne_respuesta_es_de_este_documento(respuesta, intento):
            self._ne_nota_una_vez(_(
                'La respuesta de la DIAN corresponde a otro documento (no coincide el CUNE del envío): no se cambia '
                'el estado. Revise la evidencia de la consulta.'), 'corresponde a otro documento')
            return resultado
        message_json = dian_message.build_message_json(respuesta)
        if veredicto in (dian_respuesta.ACEPTADO, dian_respuesta.RECHAZADO):
            intento.write({'state': _ESTADO_INTENTO_POR_VEREDICTO[veredicto], 'message_json': message_json})
            intento._ne_guardar_application_response(respuesta)       # E-1
            self._ne_tras_veredicto()
            if self.incierto:
                self.incierto = False                    # el veredicto concilió el envío incierto
            self.message_post(
                body=_('Consulta a la DIAN: %s.', dict(intento._fields['state'].selection).get(intento.state)),
                message_type='comment', subtype_xmlid='mail.mt_note')
            return resultado
        # pendiente
        vals = {}
        if intento.state != 'invoice_pending':
            vals['state'] = 'invoice_pending'
        if intento.message_json != message_json:
            vals['message_json'] = message_json
        if vals:
            intento.write(vals)
        horas = company._ne_config_int_param('l10n_co_nomina_electronica.recheck_max_hours', 72)
        if not self.incierto and intento.datetime and fields.Datetime.now() - intento.datetime > timedelta(hours=horas):
            self.incierto = True
            self.message_post(
                body=_('La DIAN no dio veredicto en %s horas: el envío queda incierto y sale de la reconsulta '
                       'automática. Consulte su estado a mano.', horas),
                message_type='comment', subtype_xmlid='mail.mt_note')
        return resultado

    def _ne_reconsultar_por_cune(self):
        """Consulta a la DIAN el estado del documento por su CUNE (``GetStatus``, Anexo §9.8) y lo aplica (doc 53
        §23.17, 7a / D-A). Sirve cuando se perdió el ZipKey (el proceso murió tras el envío y antes del commit).

        El formato real de la respuesta es NO VERIFICADO hasta el piloto de producción: lo que no se pueda interpretar
        con ``interpretar_respuesta``, una respuesta de otro documento (``XmlDocumentKey`` distinto del CUNE) o con
        varios resultados NO cambia el estado y el documento SIGUE incierto: nunca se asume un veredicto.

        - ``aceptado`` / ``rechazado``: actualiza el último intento pendiente o fallido de este CUNE; sin intento, crea
          uno (identifier = CUNE, con la evidencia enlazada). Limpia ``incierto`` y aplica la eliminación.
        - ``pendiente`` y ``error_transporte``: no cambian nada.
        Siempre guarda la evidencia. Lanza UserError solo por precondiciones locales.
        """
        self.ensure_one()
        if self.legacy:
            raise UserError(_('El documento "%s" es un documento migrado del ciclo por recibo: se consulta por '
                              'recibo.', self.display_name))
        if self.eliminado:
            raise UserError(_('El documento "%s" ya fue eliminado por una nota de ajuste.', self.display_name))
        if not self.cune:
            raise UserError(_('El documento "%s" no tiene CUNE: no se puede consultar por CUNE.', self.display_name))
        ultimo = self._ultimo_intento()
        if ultimo and ultimo.state in ('invoice_accepted', 'invoice_rejected') and ultimo.identifier == self.cune:
            raise UserError(_('El último envío del documento "%(doc)s" ya tiene veredicto de la DIAN (%(estado)s).',
                              doc=self.display_name,
                              estado=dict(ultimo._fields['state'].selection).get(ultimo.state)))
        self._ne_bloquear_en_habilitacion()
        self.company_id._l10n_co_ne_validar_config()
        company = self.company_id
        llave, cert_pem, _der, _cert_obj, _cadena = xml_signer.load_from_certificate(company._get_ne_certificate())
        endpoint = company._ne_dian_endpoint()
        respuesta = soap_client.get_status(
            track_id=self.cune, private_key=llave, cert_pem=cert_pem, endpoint=endpoint,
            timeout=company._ne_config_int_param(
                'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT))
        resultado = dian_respuesta.interpretar_respuesta(respuesta, contexto=dian_respuesta.CONTEXTO_CONSULTA)
        exchange = self.env['l10n.co.ne.exchange'].create_exchange(
            company, 'get_status', endpoint, respuesta, self.payslip_ids, documento=self)
        veredicto = resultado.veredicto
        if veredicto in (dian_respuesta.ERROR_TRANSPORTE, dian_respuesta.PENDIENTE):
            return resultado
        if veredicto == dian_respuesta.NIVEL_SET:
            self._ne_nota_una_vez(_(
                'La DIAN respondió sobre el SET de pruebas, no sobre este documento: %s. No se cambia el estado.',
                resultado.mensaje), 'respondió sobre el SET de pruebas')
            return resultado
        if len(respuesta.get('DianResponses') or []) > 1:
            self._ne_nota_una_vez(_(
                'La DIAN devolvió varios resultados para la consulta por CUNE: no se cambia el estado. Revise la '
                'evidencia de la consulta.'), 'varios resultados para la consulta')
            return resultado
        cunes = dian_respuesta.candidatos_cune(respuesta)
        if not cunes or self.cune not in cunes:
            self._ne_nota_una_vez(_(
                'La respuesta de la DIAN no identifica este documento (no coincide el CUNE): no se cambia el estado '
                'y el documento sigue como estaba. Revise la evidencia de la consulta.'), 'no identifica este documento')
            return resultado
        estado = _ESTADO_INTENTO_POR_VEREDICTO[veredicto]
        message_json = dian_message.build_message_json(respuesta)
        if ultimo and ultimo.identifier == self.cune and ultimo.state in ('invoice_pending', 'invoice_sending_failed'):
            vals = {'state': estado, 'message_json': message_json}
            if respuesta.get('ZipKey') and not ultimo.zip_key:
                vals['zip_key'] = respuesta['ZipKey']
            ultimo.write(vals)
            ultimo._ne_guardar_application_response(respuesta)        # E-1
        else:
            nuevo = self.env['l10n.co.ne.documento.intento'].create({
                'documento_id': self.id, 'datetime': fields.Datetime.now(), 'state': estado,
                'identifier': self.cune, 'numero': self.consecutive, 'zip_key': respuesta.get('ZipKey') or False,
                'message_json': message_json, 'exchange_id': exchange.id or False,
                'test_environment': company.l10n_co_ne_environment == '2',
                'certification_process': bool(company.l10n_co_ne_certification_process)})
            nuevo._ne_guardar_application_response(respuesta)         # E-1
        self._ne_tras_veredicto()
        if self.incierto:
            self.incierto = False
        self.message_post(
            body=_('Consulta a la DIAN por CUNE: %s.', dict(self.env['l10n.co.ne.documento.intento']._fields[
                'state'].selection).get(estado)),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return resultado

    # ──────────────────────────────────────────────────────────────────
    # Cron de reconsulta del documento (doc 53 §23.17, 7c). El cron del RECIBO no se toca.
    # ──────────────────────────────────────────────────────────────────
    _CRON_RECONSULTA_XMLID = 'l10n_co_nomina_electronica.ir_cron_ne_documento_recheck'

    @api.model
    def _ne_intervalo_reconsulta(self):
        """Minutos entre consultas = el intervalo editable de la acción planificada (30 por defecto)."""
        cron = self.env.ref(self._CRON_RECONSULTA_XMLID, raise_if_not_found=False)
        if not cron:
            return 30
        factor = {'minutes': 1, 'hours': 60, 'days': 1440, 'weeks': 10080, 'months': 43200}.get(cron.interval_type, 1)
        return max(cron.interval_number * factor, 1)

    @api.model
    def _cron_reconsultar_pendientes(self):
        """Reconsulta (``GetStatusZip``) los documentos cuyo último intento sigue pendiente o con envío fallido pero con
        ZipKey. Una consulta por documento por intervalo (``proxima_consulta``); tras ``n`` fallos de transporte seguidos
        la espera es ``min(intervalo × 2^n, send_retry_max_minutes)`` (30 → 60 y se queda en 60); un veredicto o una
        respuesta pendiente reinician el contador. Lotes de ``recheck_batch_limit`` en orden de envío ascendente (el que
        más espera, primero), commit por documento y aislamiento (un error no frena a los demás). Pasadas
        ``recheck_max_hours`` ``_ne_reconsultar`` lo deja ``incierto`` y sale de este cron."""
        ahora = fields.Datetime.now()
        intervalo = self._ne_intervalo_reconsulta()
        companias = self.env['res.company'].sudo().search([
            ('partner_id.country_id.code', '=', 'CO'), ('l10n_co_ne_environment', '=', '1'),
            ('l10n_co_ne_certification_process', '=', False)])
        for company in companias:
            candidatos = self.sudo().search([
                ('company_id', '=', company.id), ('incierto', '=', False), ('legacy', '=', False),
                ('eliminado', '=', False), ('state', 'in', ('invoice_pending', 'invoice_sending_failed'))])
            elegibles = candidatos.filtered(
                lambda d: d._ultimo_intento().zip_key and (not d.proxima_consulta or d.proxima_consulta <= ahora))
            lote = company._ne_config_int_param('l10n_co_nomina_electronica.recheck_batch_limit', 200)
            elegibles = elegibles.sorted(lambda d: (d._ultimo_intento().datetime or _dt.min, d.id))[:lote]
            tope = company._ne_config_int_param('l10n_co_nomina_electronica.send_retry_max_minutes', 60)
            for doc in elegibles:
                try:
                    with self.env.cr.savepoint():
                        resultado = doc._ne_reconsultar()
                except UserError as error:
                    doc.message_post(body=_('Reconsulta automática omitida: %s', error),
                                     message_type='comment', subtype_xmlid='mail.mt_note')
                    doc.proxima_consulta = ahora + timedelta(minutes=intervalo)
                except Exception:   # noqa: BLE001 -- un documento con error nunca frena a los demás
                    _logger.exception('Reconsulta automática: error consultando el documento %s', doc.id)
                    doc.proxima_consulta = ahora + timedelta(minutes=intervalo)
                else:
                    if resultado.veredicto == dian_respuesta.ERROR_TRANSPORTE:
                        fallos = doc.fallos_consulta + 1
                        doc.write({'fallos_consulta': fallos, 'proxima_consulta': ahora + timedelta(
                            minutes=min(intervalo * 2 ** fallos, tope))})
                    elif resultado.veredicto in (dian_respuesta.ACEPTADO, dian_respuesta.RECHAZADO):
                        doc.write({'fallos_consulta': 0, 'proxima_consulta': False})
                    else:   # pendiente o respuesta sobre el set: se vuelve a consultar en un intervalo
                        doc.write({'fallos_consulta': 0, 'proxima_consulta': ahora + timedelta(minutes=intervalo)})
                self._ne_commit()

    # ──────────────────────────────────────────────────────────────────
    # Restricciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('company_id')
    def _check_company_colombia(self):
        """Inerte en compañías no colombianas (doc 51): no se crean documentos para ellas."""
        for doc in self:
            if not doc.company_id._ne_es_colombia():
                raise ValidationError(_(
                    'La compañía "%(compania)s" no es colombiana: el documento mensual de nómina electrónica '
                    'solo existe para compañías de Colombia.', compania=doc.company_id.name))

    @api.constrains('period')
    def _check_period(self):
        for doc in self:
            if doc.period and doc.period.day != 1:
                raise ValidationError(_(
                    'El mes del documento debe ser el primer día del mes; se recibió %(fecha)s.', fecha=doc.period))

    @api.constrains('company_id', 'employee_id', 'period', 'is_adjustment', 'legacy', 'eliminado')
    def _check_original_unico(self):
        for doc in self.filtered(lambda d: not d.is_adjustment and not d.legacy and not d.eliminado):
            otro = self.search([
                ('id', '!=', doc.id), ('company_id', '=', doc.company_id.id), ('employee_id', '=', doc.employee_id.id),
                ('period', '=', doc.period), ('is_adjustment', '=', False), ('legacy', '=', False),
                ('eliminado', '=', False)], limit=1)
            if otro:
                raise ValidationError(_(
                    'Ya existe un documento mensual activo de %(empleado)s para %(mes)s (%(otro)s). Solo puede haber '
                    'uno por empleado y mes; para corregirlo cree una nota de ajuste.',
                    empleado=doc.employee_id.display_name, mes=doc.period.strftime('%Y-%m'), otro=otro.display_name))

    @api.constrains('is_adjustment', 'adjustment_ref_cune')
    def _check_adjustment_ref_cune(self):
        for doc in self:
            if doc.is_adjustment and not doc.adjustment_ref_cune:
                raise ValidationError(_(
                    'Para una nota de ajuste debe indicar el CUNE del documento original (%(doc)s).', doc=doc.display_name))

    @api.constrains('payslip_ids', 'company_id', 'employee_id')
    def _check_recibos(self):
        """Coherencia de sus recibos (la misma regla se valida del lado del recibo al enlazarlo)."""
        self.payslip_ids._check_documento_coherente()

    @api.model_create_multi
    def create(self, vals_list):
        """Un original activo por (compañía, empleado, mes): se comprueba ANTES del INSERT para dar el mensaje claro
        (el índice parcial ``l10n_co_ne_documento_mes_unico`` queda como respaldo ante concurrencia)."""
        vistos = set()
        for vals in vals_list:
            if vals.get('is_adjustment') or vals.get('legacy') or vals.get('eliminado') or not vals.get('period'):
                continue
            company = vals.get('company_id') or self.env.company.id
            clave = (company, vals.get('employee_id'), fields.Date.to_date(vals['period']))
            otro = self.search([
                ('company_id', '=', company), ('employee_id', '=', clave[1]), ('period', '=', clave[2]),
                ('is_adjustment', '=', False), ('legacy', '=', False), ('eliminado', '=', False)], limit=1)
            if otro or clave in vistos:
                raise ValidationError(_(
                    'Ya existe un documento mensual activo para ese empleado y mes (%(otro)s). Solo puede haber uno por '
                    'empleado y mes; para corregirlo cree una nota de ajuste.', otro=otro.display_name or clave[2]))
            vistos.add(clave)
        return super().create(vals_list)

    def unlink(self):
        for doc in self:
            if doc.legacy or doc.cune or doc.consecutive or doc.intento_ids:
                raise UserError(_(
                    'El documento "%(doc)s" ya tiene historia ante la DIAN (CUNE, consecutivo o intentos) y no se '
                    'puede borrar. Si hay un error, cree una nota de ajuste.', doc=doc.display_name))
        # Una nota en borrador suelta primero los recibos que adoptó (el M2O del recibo es ``restrict``).
        self.filtered('is_adjustment').payslip_ids.write({'l10n_co_ne_documento_id': False})
        return super().unlink()

    # ──────────────────────────────────────────────────────────────────
    # Migración: lo ya transmitido por recibo pasa a documentos legacy 1:1
    # ──────────────────────────────────────────────────────────────────
    @api.model
    def _ne_migrar_legacy(self, recibos=None):
        """Crea un documento ``legacy`` por cada recibo colombiano con historia DIAN (estado distinto de borrador, o
        CUNE, consecutivo o intercambios). NO quita nada del recibo. Idempotente: el recibo que ya apunta a un documento
        no se vuelve a migrar. Funciona con 0 filas. ``recibos`` limita la migración a esos recibos (las pruebas la
        usan para no depender de los datos de la base); sin él migra todos los pendientes. Devuelve los documentos
        creados."""
        Payslip = self.env['hr.payslip'].sudo().with_context(active_test=False)
        dominio = [
            ('l10n_co_ne_documento_id', '=', False),
            '|', '|', '|', ('l10n_co_ne_state', '!=', 'draft'), ('l10n_co_ne_cune', '!=', False),
            ('l10n_co_ne_consecutive', '!=', False), ('l10n_co_ne_exchange_ids', '!=', False)]
        if recibos is not None:
            dominio.append(('id', 'in', recibos.ids))
        recibos = Payslip.search(dominio, order='id')
        recibos = recibos.filtered(lambda s: s.company_id._ne_es_colombia())
        # Lo transmitido SOLO en habilitación (set de pruebas) no es un reporte real: no se migra (doc 53 §28.6). Un
        # recibo con consecutivo gastado pero sin intercambios sí se migra (ocupa ese número).
        recibos = recibos.filtered(lambda s: not s._ne_historia_solo_habilitacion())
        Documento = self.sudo().with_context(mail_notrack=True, mail_create_nolog=True)
        creados = Documento
        por_cune = {}
        for slip in recibos:
            doc = Documento.create(self._ne_valores_legacy(slip))
            creados |= doc
            if doc.cune:
                por_cune[doc.cune] = doc
            self._ne_crear_intento_legacy(doc, slip)
            slip._write({'l10n_co_ne_documento_id': doc.id})
        # _write no toca la caché: sin invalidar, el recibo seguiría mostrando el valor anterior en esta transacción.
        recibos.invalidate_recordset(['l10n_co_ne_documento_id'])
        recibos.modified(['l10n_co_ne_documento_id'])
        # Las notas de ajuste migradas apuntan a su original por CUNE (el original puede ser de un lote anterior).
        for doc in creados.filtered(lambda d: d.is_adjustment and d.adjustment_ref_cune):
            original = por_cune.get(doc.adjustment_ref_cune) or Documento.search(
                [('cune', '=', doc.adjustment_ref_cune), ('id', '!=', doc.id)], limit=1)
            if original:
                doc.parent_id = original
                if doc.adjustment_type == '2' and doc.state == 'invoice_accepted' and not doc.eliminado:
                    original.eliminado_por_id = doc
        _logger.info('Documentos legacy creados desde recibos ya transmitidos: %s', len(creados))
        return creados

    @api.model
    def _ne_recalcular_estado(self):
        """Recalcula ``state`` (y su related almacenado en el recibo) desde el último intento (doc 53 §26b). Lo usa la
        post-migración de .210: el campo almacenado tenía valores propios (borrador, listo, incierto, eliminado) que
        la pre-migración dejó vacíos. Idempotente."""
        docs = self.search([])
        self.env.add_to_compute(self._fields['state'], docs)
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE hr_payslip p SET l10n_co_ne_documento_state = d.state
              FROM l10n_co_ne_documento d
             WHERE p.l10n_co_ne_documento_id = d.id
               AND p.l10n_co_ne_documento_state IS DISTINCT FROM d.state
        """)
        self.env['hr.payslip'].invalidate_model(['l10n_co_ne_documento_state'])
        return docs

    @api.model
    def _ne_valores_legacy(self, slip):
        etapa, _estado_intento = _MAPA_ESTADO_LEGACY[slip.l10n_co_ne_state or 'draft']
        return {
            'company_id': slip.company_id.id,
            'employee_id': slip.employee_id.id,
            'contract_id': slip.contract_id.id or False,
            'period': slip.date_to.replace(day=1),
            'legacy': True,
            'etapa': etapa,
            'incierto': slip.l10n_co_ne_state == 'uncertain',
            'eliminado': slip.l10n_co_ne_state == 'eliminated',
            'cune': slip.l10n_co_ne_cune or False,
            'consecutive': slip.l10n_co_ne_consecutive or False,
            'xml_attachment_id': slip.l10n_co_ne_xml_attachment_id.id or False,
            'zip_key': slip.l10n_co_ne_zip_key or False,
            'hab_set_id': slip.l10n_co_ne_hab_set_id or False,
            'is_adjustment': slip.l10n_co_ne_is_adjustment,
            'adjustment_type': slip.l10n_co_ne_adjustment_type if slip.l10n_co_ne_is_adjustment else False,
            'adjustment_ref_cune': slip.l10n_co_ne_adjustment_ref_cune or False,
            'exchange_ids': [(6, 0, slip.l10n_co_ne_exchange_ids.ids)],
        }

    @api.model
    def _ne_crear_intento_legacy(self, doc, slip):
        """Un intento por documento legacy transmitido, con el motivo reparseado de la respuesta guardada."""
        _etapa, estado = _MAPA_ESTADO_LEGACY[slip.l10n_co_ne_state or 'draft']
        if not estado:
            return self.env['l10n.co.ne.documento.intento']
        envios = slip.l10n_co_ne_exchange_ids.filtered(lambda e: e.operation in _OPERACIONES_ENVIO).sorted('id')
        intercambio = envios[-1:]
        manifiesto = self.env['l10n.co.ne.exchange.document'].sudo().search(
            [('payslip_id', '=', slip.id)], order='id desc', limit=1)
        message_json = False
        if slip.l10n_co_ne_dian_response:
            try:
                message_json = dian_message.build_message_json(_parse_response(slip.l10n_co_ne_dian_response))
            except Exception:  # la respuesta guardada es texto libre: nunca bloquea la migración
                message_json = {'transport': 'PARSE_ERROR', 'errors': [], 'fault': [], 'is_valid': False,
                                'status_code': 'PARSE_ERROR', 'status': '', 'detail': ''}
        habilitacion = bool(slip.l10n_co_ne_hab_set_id)
        return self.env['l10n.co.ne.documento.intento'].sudo().create({
            'documento_id': doc.id,
            'datetime': intercambio.create_date or slip.write_date,
            'state': estado,
            'identifier': slip.l10n_co_ne_cune or False,
            'zip_key': slip.l10n_co_ne_zip_key or False,
            'numero': slip.l10n_co_ne_consecutive or False,
            'file_name': manifiesto.file_name or False,
            'sha256': manifiesto.sha256 or False,
            'attachment_id': slip.l10n_co_ne_xml_attachment_id.id or False,
            'message_json': message_json,
            'exchange_id': intercambio.id or False,
            'test_environment': habilitacion or slip.company_id.l10n_co_ne_environment == '2',
            'certification_process': habilitacion,
        })
