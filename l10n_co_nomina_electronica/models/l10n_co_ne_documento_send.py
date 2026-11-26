# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Lógica del asistente "Enviar y Procesar" sobre documentos mensuales (doc 53 §23.17, 8a / D-F).

Patrón de ``account.move.send`` COPIADO, no heredado (está atado a ``account.move``): un modelo abstracto con la lógica
(grupos, alertas ``{key, level, message}``, preparar, generar y encolar por lote) y el asistente ``hr.payslip.send`` como
capa de interfaz. Abrir el asistente solo CALCULA grupos y alertas: no crea ni escribe nada."""

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError


class L10nCoNeDocumentoSend(models.AbstractModel):
    _name = 'l10n.co.ne.documento.send'
    _description = 'Lógica del asistente de envío de documentos mensuales'

    @api.model
    def _ne_es_produccion(self, company):
        """Producción real: el documento mensual solo transmite aquí (D-b); en habilitación el ciclo es por recibo."""
        return company._ne_en_produccion()

    # ── grupos y alertas (sin ningún efecto) ──────────────────────────
    @api.model
    def _ne_grupos(self, recibos, documentos):
        """Grupos (compañía, empleado, mes de la primera fecha de pago) de los recibos, más los documentos dados. Un
        recibo sin fecha de pago o no confirmado va en un grupo sin mes (con su motivo). No toca la base de datos."""
        Documento = self.env['l10n.co.ne.documento']
        grupos = {}
        for slip in recibos:
            motivo = False
            periodo = False
            excluido = Documento._ne_motivo_no_entra(slip)
            if excluido:
                motivo = excluido
            elif slip.state not in ('done', 'paid'):
                motivo = _('El recibo "%s" no está confirmado (hecho o pagado).', slip.display_name)
            else:
                try:
                    periodo = slip._ne_fecha_pago().replace(day=1)
                except UserError as error:
                    motivo = str(error)
            clave = (slip.company_id.id, slip.employee_id.id, periodo)
            grupo = grupos.setdefault(clave, {
                'company': slip.company_id, 'employee': slip.employee_id, 'period': periodo,
                'recibos': self.env['hr.payslip'], 'documento': Documento, 'documentos': Documento, 'motivos': []})
            grupo['recibos'] |= slip
            if motivo:
                grupo['motivos'].append(motivo)
        for grupo in grupos.values():
            if grupo['period']:
                # H-F3-04: con el mes separado por tipo de trabajador hay un documento por segmento; ``documento`` es el del primer segmento (como siempre) y ``documentos`` son todos.
                grupo['documentos'] = Documento.search([
                    ('company_id', '=', grupo['company'].id), ('employee_id', '=', grupo['employee'].id),
                    ('period', '=', grupo['period']), ('is_adjustment', '=', False), ('legacy', '=', False),
                    ('eliminado', '=', False)], order='segmento, id')
                grupo['documento'] = grupo['documentos'][:1]
        resultado = list(grupos.values())
        ya = {d.id for g in resultado for d in g['documentos']}
        for doc in documentos:
            if doc.id in ya:
                continue
            resultado.append({'company': doc.company_id, 'employee': doc.employee_id, 'period': doc.period,
                              'recibos': doc.payslip_ids, 'documento': doc, 'documentos': doc, 'motivos': []})
        return resultado

    @api.model
    def _ne_alertas_grupo(self, grupo):
        """Alertas del grupo ``[{key, level (danger/warning/info), message, confirmable}]`` sin escribir nada. ``danger``
        bloquea el grupo (no aborta el lote); ``confirmable`` exige la casilla "Confirmo mes incompleto" (D14)."""
        alertas = []

        def alerta(key, level, message, confirmable=False, confirma=False):
            # ``confirma``: qué casilla del asistente la confirma ('mes_incompleto' o 'extemporaneo')
            alertas.append({'key': key, 'level': level, 'message': message, 'confirmable': confirmable,
                            'confirma': confirma})

        company, periodo = grupo['company'], grupo['period']
        for motivo in grupo['motivos']:
            alerta('sin_fecha', 'danger', motivo)
        if not self._ne_es_produccion(company):
            alerta('habilitacion', 'danger', _(
                'La compañía "%s" está en habilitación: el documento mensual solo se transmite en Producción (en '
                'habilitación el ciclo es por recibo).', company.name))
        for doc in grupo['documentos']:
            if doc.state in ('invoice_pending', 'invoice_accepted') and not doc.is_adjustment:
                nota = doc._ne_nota_abierta() if doc.state == 'invoice_accepted' else doc.browse()
                alerta('ya_enviado', 'info', _('El documento "%(doc)s" ya fue enviado a la DIAN (%(estado)s).',
                                               doc=doc.display_name,
                                               estado=dict(doc._fields['state'].selection).get(doc.state)))
                if doc.state == 'invoice_accepted':
                    nuevos = grupo['recibos'].filtered(lambda s: not s.l10n_co_ne_documento_id)
                    if company.l10n_co_ne_segmentar_mes:
                        nuevos = nuevos & doc._ne_recibos_del_segmento()      # H-F3-04: solo los de SU segmento
                    if nuevos and not nota:
                        alerta('recibo_tardio', 'warning', _(
                            'Hay recibos nuevos del mes y el documento ya fue aceptado: cree una nota de ajuste Reemplazar '
                            'para incluirlos.'))
            if doc.eliminado or doc.legacy:
                alerta('no_aplica', 'danger', _('El documento "%s" está eliminado o migrado: no se envía.', doc.display_name))
            if doc.segmento > 1 and not doc.is_adjustment and not doc.state:
                # H-F3-04 (Q7 del TL): el segundo documento espera, sin error, a que el anterior sea aceptado. ``warning``, no ``danger``: un problema del segmento 2 no debe bloquear el envío del 1.
                try:
                    espera = doc._ne_espera_anterior()
                except UserError as error:
                    alerta('segmento_no_sale', 'warning', str(error))
                else:
                    if espera:
                        alerta('segmento_espera', 'info', espera)
        if periodo and not any(a['level'] == 'danger' for a in alertas):
            fin = (periodo.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            del_mes = self.env['l10n.co.ne.documento']._ne_recibos_del_mes(company, grupo['employee'], periodo)
            hoy = fields.Date.context_today(self)
            liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion',
                                       raise_if_not_found=False)
            if hoy <= fin and not del_mes.filtered(lambda s: s.struct_id == liquidacion):
                alerta('mes_incompleto', 'warning', _(
                    'El mes %(mes)s no ha terminado y el empleado no tiene liquidación final pagada en él.',
                    mes=periodo.strftime('%Y-%m')), confirmable=True, confirma='mes_incompleto')
            faltan = self.env['l10n.co.ne.documento']._ne_recibos_que_faltan(
                company, grupo['employee'], periodo, del_mes)
            if faltan:
                alerta('faltan_recibos', 'warning', _(
                    'Hay recibos del mes sin pagar o sin fecha de pago: %s.', ', '.join(faltan.mapped('display_name'))),
                    confirmable=True, confirma='mes_incompleto')
            # Plazo vencido con el bloqueo de la compañía activo (D7): exige confirmar el envío extemporáneo.
            if company.l10n_co_ne_bloquear_extemporaneo:
                plazo = self._ne_plazo_del_grupo(grupo)
                if plazo and fields.Date.context_today(self) > plazo:
                    alerta('extemporaneo', 'warning', _(
                        'El plazo de transmisión venció el %s y la compañía exige confirmar el envío extemporáneo.',
                        plazo), confirmable=True, confirma='extemporaneo')
        return alertas

    @api.model
    def _ne_plazo_del_grupo(self, grupo):
        """Fecha límite del grupo: la del documento si existe; si no, la que tendría (registro virtual, sin crear
        nada). Un documento migrado no tiene plazo."""
        doc = grupo['documento']
        if doc:
            return doc.fecha_limite
        contrato = grupo['recibos'].sorted('date_to').contract_id[-1:]
        virtual = self.env['l10n.co.ne.documento'].new({
            'company_id': grupo['company'].id, 'employee_id': grupo['employee'].id,
            'contract_id': contrato.id, 'period': grupo['period']})
        return virtual.fecha_limite

    @api.model
    def _ne_resumen(self, grupos):
        """HTML del resumen de grupos y alertas (solo texto: sin íconos ni colores propios)."""
        etiquetas = {'danger': _('Bloqueo'), 'warning': _('Advertencia'), 'info': _('Aviso')}
        items = []
        for grupo in grupos:
            alertas = self._ne_alertas_grupo(grupo)
            titulo = '%s — %s' % (grupo['employee'].display_name,
                                  grupo['period'].strftime('%Y-%m') if grupo['period'] else _('sin mes'))
            detalle = Markup('').join(
                Markup('<li>%s: %s</li>') % (etiquetas.get(a['level'], a['level']), a['message']) for a in alertas)
            items.append(Markup('<li><b>%s</b><ul>%s</ul></li>') % (titulo, detalle))
        return Markup('<ul>%s</ul>') % Markup('').join(items) if items else False

    # ── ejecución ─────────────────────────────────────────────────────
    @api.model
    def _ne_exigir_cron_activo(self):
        cron = self.env.ref(self.env['l10n.co.ne.documento']._CRON_ENVIO_XMLID, raise_if_not_found=False)
        cron = cron.sudo() if cron else cron      # ir.cron solo lo lee el administrador del sistema
        if cron and not cron.active:
            mensaje = _('La acción planificada de envío de nómina electrónica está archivada: sin ella los envíos '
                        'quedarían en la cola sin salir.')
            if self.env.is_superuser() or self.env.user.has_group('base.group_system'):
                raise RedirectWarning(mensaje, {
                    'type': 'ir.actions.act_window', 'res_model': 'ir.cron', 'res_id': cron.id, 'view_mode': 'form',
                    'views': [(False, 'form')]}, _('Abrir la acción planificada'))
            raise UserError(mensaje + ' ' + _('Pida a un administrador que la active.'))

    @api.model
    def _ne_procesar(self, recibos, documentos, enviar, confirma, confirma_ext=False):
        """Prepara (y, si ``enviar``, genera el XML y encola) cada grupo. Un grupo bloqueado no aborta a los demás: se
        lista. Devuelve ``{'preparados', 'encolados', 'bloqueados': [texto]}``."""
        Documento = self.env['l10n.co.ne.documento']
        preparados, encolados, bloqueados = [], [], []
        grupos = self._ne_grupos(recibos, documentos)
        bloqueo = {}
        for grupo in grupos:
            alertas = self._ne_alertas_grupo(grupo)
            nombre = '%s %s' % (grupo['employee'].display_name,
                                grupo['period'].strftime('%Y-%m') if grupo['period'] else '')
            peligros = [a['message'] for a in alertas if a['level'] == 'danger']
            if peligros:
                bloqueados.append('%s: %s' % (nombre.strip(), ' '.join(peligros)))
                bloqueo[id(grupo)] = True
            elif enviar and not confirma and any(a['confirma'] == 'mes_incompleto' for a in alertas):
                bloqueados.append(_('%s: requiere confirmar el mes incompleto.', nombre.strip()))
                bloqueo[id(grupo)] = 'preparar'
            elif enviar and not confirma_ext and any(a['confirma'] == 'extemporaneo' for a in alertas):
                bloqueados.append(_('%s: requiere confirmar el envío extemporáneo (plazo vencido).', nombre.strip()))
                bloqueo[id(grupo)] = 'preparar'
        # Preparar: crea o actualiza el documento (no envía). Los bloqueados por fecha o no confirmados no se preparan.
        docs = Documento.browse()
        for grupo in grupos:
            if bloqueo.get(id(grupo)) is True:
                continue
            if grupo['recibos'] and grupo['period']:
                docs |= Documento._ne_preparar(grupo['recibos'])['documentos'].filtered(
                    lambda d, g=grupo: d.period == g['period'] and d.employee_id == g['employee'])
            elif grupo['documentos']:
                for existente in grupo['documentos']:
                    existente._ne_validar()
                    docs |= existente
        preparados = docs.ids
        if enviar:
            confirmados = {id(g) for g in grupos if bloqueo.get(id(g)) != 'preparar'}
            permitidos = Documento.browse()
            for grupo in grupos:
                if id(grupo) in confirmados and bloqueo.get(id(grupo)) is not True:
                    permitidos |= docs.filtered(lambda d, g=grupo: d.period == g['period']
                                                and d.employee_id == g['employee'])
            for doc in permitidos.sorted(lambda d: (d.period, d.employee_id.id, d.segmento, d.id)):       # H-F3-04: en orden de segmento (el segundo lleva el CUNE del primero)
                try:
                    with self.env.cr.savepoint():
                        if doc.state in (False, 'invoice_sending_failed') and not doc.is_being_sent:
                            if not doc.state:
                                # Sin envío previo: se (re)genera el XML vigente (reutiliza el consecutivo no usado, no
                                # gasta otro); un envío fallido se reintenta con el MISMO XML y no se regenera.
                                doc.action_generar_xml()
                            doc._ne_encolar(confirmo_extemporaneo=confirma_ext)
                            encolados.append(doc.id)
                            if confirma and any(a.get('confirmable') and a.get('key') != 'extemporaneo'
                                                for a in doc.alertas or []):
                                doc.message_post(
                                    body=_('Mes incompleto confirmado por %(usuario)s el %(fecha)s.',
                                           usuario=self.env.user.name, fecha=fields.Date.context_today(self)),
                                    message_type='comment', subtype_xmlid='mail.mt_note')
                except UserError as error:
                    bloqueados.append('%s: %s' % (doc.display_name, error))
        return {'preparados': preparados, 'encolados': encolados, 'bloqueados': bloqueados}
