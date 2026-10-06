# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Habilitación DIAN automática de Nómina Electrónica: un botón, el resto es interno.

Lo que el usuario ve: presiona "Iniciar Proceso de Habilitación", ve una barra de avance y
recibe avisos al aceptar/rechazar cada documento y al terminar.

Lo que pasa por dentro (cada paso es idempotente y retomable; un ``ir.cron`` que se
re-programa a sí mismo avanza una etapa por tick, patrón nativo ``ir.cron._trigger``):

1. Nómina Individual: prepara los documentos de la meta y los envía de a UNO por ZIP
   (la DIAN solo procesa un XML por ZIP), guardando el ZipKey de cada uno.
2. Consulta cada ZipKey hasta que la DIAN resuelve.
3. Con las individuales aceptadas, prepara las Notas de Ajuste sobre ellas y repite 1 y 2.
4. Si algún documento es rechazado el proceso se DETIENE y muestra la regla: no reintenta
   solo, porque la DIAN cierra el set de pruebas tras varios rechazos. Al presionar de nuevo
   el botón, los rechazados se regeneran (consecutivo y CUNE nuevos) y se continúa.

Los documentos se identifican por ``l10n_co_ne_hab_set_id`` (TestSetId con el que se
prepararon): un set nuevo ignora los de sets anteriores.
"""

import base64
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import habilitacion_test_data, soap_client

_logger = logging.getLogger(__name__)

_CRON_XMLID = 'l10n_co_nomina_electronica.ir_cron_ne_habilitacion'
# AUD-DIAN-34 (2026-10-05): valores por defecto -- el valor real usado puede venir de
# ir.config_parameter (ResCompany._ne_config_int_param(), ver models/res_company.py);
# estas 2 constantes quedan solo como el default de ese parámetro, no se usan directo.
_TICK_SECONDS = 20
_TIMEOUT_MINUTES = 45


class L10nCoNeHabilitacion(models.AbstractModel):
    _name = 'l10n.co.ne.habilitacion'
    _description = 'Habilitación DIAN automática (Nómina Electrónica)'

    # ──────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────

    @api.model
    def start(self, company):
        """Inicia (o retoma) la habilitación de ``company``. Devuelve una notificación."""
        company.ensure_one()
        if company.l10n_co_ne_hab_state == 'running':
            return self._toast(
                _('Habilitación en proceso'),
                _('Ya hay una habilitación en curso. Vea el avance en esta pantalla.'), 'info')
        try:
            self._validate_config(company)
        except UserError as exc:
            return self._toast(_('Falta configuración'), exc.args[0], 'warning', sticky=True)
        replaced = self._replace_failed(company)
        company.sudo().write({
            'l10n_co_ne_hab_state': 'running',
            'l10n_co_ne_hab_message': False,
            'l10n_co_ne_hab_user_id': self.env.user.id,
            'l10n_co_ne_hab_started': fields.Datetime.now(),
        })
        self._schedule(0)
        message = _('Preparando, enviando y consultando los documentos en la DIAN. '
                    'Le avisaremos cada vez que la DIAN responda.')
        if replaced:
            message = _('Se regeneraron %d documento(s) rechazado(s) con consecutivo nuevo. ',
                        replaced) + message
        return self._toast(_('Habilitación iniciada'), message, 'success')

    @api.model
    def progress(self, company):
        """Conteos del set vigente: {'ind': (aceptadas, rechazadas, meta), 'aj': (...), 'percent'}."""
        slips = self._set_slips(company)
        ind = slips.filtered(lambda s: not s.l10n_co_ne_is_adjustment)
        aj = slips - ind
        t_i = company.l10n_co_ne_num_nomina_certificar or 0
        t_a = company.l10n_co_ne_num_ajuste_certificar or 0

        def count(records, state):
            return len(records.filtered(lambda s: s.l10n_co_ne_state == state))

        total = t_i + t_a
        accepted = min(count(ind, 'accepted'), t_i) + min(count(aj, 'accepted'), t_a)
        return {
            'ind': (count(ind, 'accepted'), count(ind, 'rejected'), t_i),
            'aj': (count(aj, 'accepted'), count(aj, 'rejected'), t_a),
            'percent': (100.0 * accepted / total) if total else 0.0,
        }

    # ──────────────────────────────────────────────────────────────────
    # Cron: una etapa por tick, se re-programa mientras haya trabajo
    # ──────────────────────────────────────────────────────────────────

    @api.model
    def _cron_step(self):
        companies = self.env['res.company'].sudo().search([('l10n_co_ne_hab_state', '=', 'running')])
        for company in companies:
            try:
                finished = self.with_company(company)._step(company)
            except Exception as exc:  # noqa: BLE001 -- el proceso nunca debe quedar "en proceso" para siempre
                self.env.cr.rollback()
                self.env.invalidate_all()
                _logger.exception('Habilitación DIAN automática: error inesperado')
                company = company.exists()
                finished = self._finish(
                    company, 'error',
                    _('Error inesperado: %s. Presione "Iniciar Proceso de Habilitación" para continuar.',
                      str(exc)[:300]))
            self._commit()
            if not finished:
                tick_seconds = company._ne_config_int_param(
                    'l10n_co_nomina_electronica.habilitacion_tick_seconds', _TICK_SECONDS)
                self._schedule(tick_seconds)

    def _step(self, company):
        """Ejecuta UNA etapa. Devuelve True cuando el proceso terminó (completo o detenido)."""
        mode = company.l10n_co_ne_operation_mode_ids
        started = company.l10n_co_ne_hab_started
        timeout_minutes = company._ne_config_int_param(
            'l10n_co_nomina_electronica.habilitacion_timeout_minutes', _TIMEOUT_MINUTES)
        if started and started < fields.Datetime.now() - timedelta(minutes=timeout_minutes):
            return self._finish(company, 'error', _(
                'La DIAN no resolvió los documentos en %d minutos. '
                'Presione "Iniciar Proceso de Habilitación" para continuar.', timeout_minutes))

        slips = self._set_slips(company)
        ind = slips.filtered(lambda s: not s.l10n_co_ne_is_adjustment)
        aj = slips - ind
        target_ind = company.l10n_co_ne_num_nomina_certificar or 0
        target_aj = company.l10n_co_ne_num_ajuste_certificar or 0

        # 1) Un rechazo o un envío incierto detiene el proceso (no se quema cupo reintentando).
        failed = slips.filtered(lambda s: s.l10n_co_ne_state in ('rejected', 'uncertain'))
        if failed:
            return self._finish(company, 'error', self._failure_message(failed))

        # 2) Consultar a la DIAN lo ya enviado (un ZipKey por documento).
        sent = slips.filtered(lambda s: s.l10n_co_ne_state == 'sent')
        if sent:
            for slip in sent:
                before = slip.l10n_co_ne_state
                slip.action_check_dian_status()
                self._commit()
                if slip.l10n_co_ne_state != before:
                    self._notify_result(company, slip)
            return False

        # 3) Enviar los XML listos, de a uno por ZIP.
        generated = slips.filtered(lambda s: s.l10n_co_ne_state == 'generated')
        if generated:
            software_id = (mode.software_id or '').encode()
            for slip in generated:
                xml = base64.b64decode(slip.l10n_co_ne_xml_attachment_id.datas)
                if software_id and software_id not in xml:
                    slip.action_regenerate_ne_xml()  # el SoftwareID cambió después de generarlo
                slip.action_send_test_set()
                self._commit()
            return False

        # 4) Preparar las nóminas individuales (todo o nada).
        if not ind:
            error = self._prepare(company, individual=True)
            return self._finish(company, 'error', error) if error else False

        accepted_ind = len(ind.filtered(lambda s: s.l10n_co_ne_state == 'accepted'))
        if accepted_ind < target_ind:
            return self._finish(company, 'error', _(
                'Hay %(have)d de %(want)d nóminas individuales aceptadas y ninguna pendiente. '
                'Revise la meta de nómina individual en Ajustes.', have=accepted_ind, want=target_ind))

        # 5) Con las individuales aceptadas, preparar las Notas de Ajuste sobre ellas.
        if not aj:
            error = self._prepare(company, individual=False)
            return self._finish(company, 'error', error) if error else False

        accepted_aj = len(aj.filtered(lambda s: s.l10n_co_ne_state == 'accepted'))
        if accepted_aj >= target_aj:
            return self._finish(company, 'done', _(
                'Habilitación completa: %(i)d nóminas individuales y %(a)d notas de ajuste '
                'aceptadas por la DIAN.', i=accepted_ind, a=accepted_aj))
        return self._finish(company, 'error', _(
            'Hay %(have)d de %(want)d notas de ajuste aceptadas y ninguna pendiente. '
            'Revise la meta de nota de ajuste en Ajustes.', have=accepted_aj, want=target_aj))

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    @api.model
    def _set_slips(self, company):
        set_id = company.l10n_co_ne_operation_mode_ids.test_set_id
        if not set_id:
            return self.env['hr.payslip']
        return self.env['hr.payslip'].sudo().search([
            ('company_id', '=', company.id),
            ('l10n_co_ne_hab_set_id', '=', set_id),
        ], order='id')

    @api.model
    def _validate_config(self, company):
        if company.l10n_co_ne_environment != '2':
            raise UserError(_('La habilitación solo se ejecuta en Ambiente de Pruebas.'))
        if not company.l10n_co_ne_certification_process:
            raise UserError(_('Active "Proceso de Certificación" en Ajustes > Nómina.'))
        self.env['hr.payslip']._validate_company_ne_config(company)
        if not company.l10n_co_ne_operation_mode_ids.test_set_id:
            raise UserError(_('Configure el ID de Pruebas (TestSetId) en el Modo de Operación.'))
        available = len(habilitacion_test_data.TEST_EMPLOYEES)
        for target in (company.l10n_co_ne_num_nomina_certificar, company.l10n_co_ne_num_ajuste_certificar):
            if not target or target > available:
                raise UserError(_(
                    'Las metas de nómina y de nota de ajuste deben estar entre 1 y %d.', available))

    @api.model
    def _replace_failed(self, company):
        """Regenera (consecutivo y CUNE nuevos) lo rechazado o incierto, para retomar tras una detención."""
        failed = self._set_slips(company).filtered(
            lambda s: s.l10n_co_ne_state in ('rejected', 'uncertain'))
        failed.action_regenerate_ne_xml()
        return len(failed)

    def _prepare(self, company, individual):
        """Crea los documentos de la fase con el asistente existente. Devuelve un error o None.

        Todo o nada: si falla cualquier documento se deshace lo creado, para no dejar el set a medias.
        """
        wizard = self.env['l10n.co.ne.certification.wizard'].create({'company_id': company.id})
        try:
            with self.env.cr.savepoint():
                if individual:
                    wizard.action_prepare_individual()
                else:
                    wizard.payslip_individual_ids = [(6, 0, self._set_slips(company).filtered(
                        lambda s: not s.l10n_co_ne_is_adjustment
                        and s.l10n_co_ne_state == 'accepted').ids)]
                    wizard.action_prepare_ajuste()
        except UserError as exc:
            return exc.args[0]
        return None

    @api.model
    def _failure_message(self, failed):
        lines = []
        for slip in failed:
            label = slip.l10n_co_ne_consecutive or slip.name
            if slip.l10n_co_ne_state == 'uncertain':
                lines.append(_('%s: envío incierto (la DIAN no confirmó la recepción).', label))
            else:
                lines.append(_('%(doc)s rechazado: %(why)s',
                               doc=label, why=self._rejection_reasons(slip) or _('sin detalle')))
        return _('Proceso detenido. %s\nCorrija la causa y presione de nuevo '
                 '"Iniciar Proceso de Habilitación": se regenerarán con consecutivo nuevo.',
                 '\n'.join(lines))

    @api.model
    def _rejection_reasons(self, slip):
        exchange = self.env['l10n.co.ne.exchange'].sudo().search([
            ('operation', '=', 'get_status_zip'),
            ('queried_zip_key', '=', slip.l10n_co_ne_zip_key),
        ], order='id desc', limit=1)
        if not exchange or not exchange.response_payload:
            return ''
        try:
            parsed = soap_client._parse_response(base64.b64decode(exchange.response_payload))
        except Exception:  # noqa: BLE001 -- el motivo es informativo; nunca debe romper el proceso
            return ''
        return '; '.join(
            message
            for response in parsed.get('DianResponses', [])
            for message in response.get('ErrorMessages', [])
        )

    def _commit(self):
        """Confirma lo hecho hasta aquí (un ZipKey ya enviado no puede perderse por un fallo posterior).

        Aislado en un método para que las pruebas lo reemplacen: Odoo prohíbe cr.commit() en un test.
        """
        self.env.cr.commit()

    @api.model
    def _schedule(self, delay_seconds):
        cron = self.env.ref(_CRON_XMLID, raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger(at=fields.Datetime.now() + timedelta(seconds=delay_seconds))

    @api.model
    def _finish(self, company, state, message):
        company.sudo().write({'l10n_co_ne_hab_state': state, 'l10n_co_ne_hab_message': message})
        self._notify(company, _('Habilitación DIAN') if state == 'done' else _('Habilitación detenida'),
                     message, 'success' if state == 'done' else 'danger', sticky=True)
        return True

    @api.model
    def _notify_result(self, company, slip):
        progress = self.progress(company)
        kind = _('Nota de ajuste') if slip.l10n_co_ne_is_adjustment else _('Nómina')
        key = 'aj' if slip.l10n_co_ne_is_adjustment else 'ind'
        accepted, _rejected, target = progress[key]
        if slip.l10n_co_ne_state == 'accepted':
            self._notify(company, _('Aceptada por la DIAN'),
                         _('%(kind)s %(n)s — %(acc)d de %(tgt)d', kind=kind,
                           n=slip.l10n_co_ne_consecutive, acc=accepted, tgt=target), 'success')
        elif slip.l10n_co_ne_state == 'rejected':
            self._notify(company, _('Rechazada por la DIAN'),
                         '%s %s' % (kind, slip.l10n_co_ne_consecutive), 'danger')

    @api.model
    def _notify(self, company, title, message, kind='info', sticky=False):
        """Aviso en vivo al usuario que inició el proceso (notificación nativa del bus)."""
        user = company.l10n_co_ne_hab_user_id
        if user:
            self.env['bus.bus'].sudo()._sendone(
                user.partner_id, 'simple_notification',
                {'title': title, 'message': message, 'type': kind, 'sticky': sticky})

    @api.model
    def _toast(self, title, message, kind='info', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind, 'sticky': sticky},
        }
