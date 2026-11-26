# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-006: consulta del estado DIAN a partir de un CUNE.

Resuelve el CUNE a la nómina que lo generó usando el historial de envíos
(``l10n.co.ne.exchange.document``, que guarda ``cune`` y ``payslip_id`` por cada documento de
cualquier envío) y reutiliza ``hr.payslip.action_check_dian_status()`` -- toda la lógica de
emparejamiento y estado ya verificada. No transmite nada nuevo a la DIAN: la consulta sigue
siendo por ZipKey (GetStatusZip) para un recibo. Un CUNE de un DOCUMENTO MENSUAL se consulta con GetStatus por CUNE
(Anexo §9.8; ``l10n.co.ne.documento._ne_reconsultar_por_cune``, formato real NO VERIFICADO hasta el piloto). Un CUNE
que no pasó por un envío de este sistema no se puede consultar aquí.
"""

from odoo import fields, models, _
from odoo.exceptions import UserError


class L10nCoNeStatusCuneWizard(models.TransientModel):
    _name = 'l10n.co.ne.status.cune.wizard'
    _description = 'Consultar estado DIAN por CUNE'

    cune = fields.Char(string='CUNE', required=True)

    def _resolve_payslip(self):
        self.ensure_one()
        cune = (self.cune or '').strip()
        # Sin filtrar por la compania activa: la regla multiempresa del intercambio deja ver solo
        # los de las companias autorizadas; la compania del documento decide el resto.
        documento = self.env['l10n.co.ne.exchange.document'].search([
            ('cune', '=', cune),
        ], order='id desc', limit=1)
        if not documento:
            raise UserError(_(
                'CUNE no encontrado en el historial de envíos de sus compañías. Solo se pueden '
                'consultar documentos que este sistema ya envió a la DIAN.'))
        documento.company_id._ne_exigir_colombia()
        payslip = documento.payslip_id
        if not payslip.l10n_co_ne_zip_key:
            # El envío guardó el ZipKey en el intercambio, no necesariamente en la nómina.
            payslip.l10n_co_ne_zip_key = documento.exchange_id.zip_key
        if not payslip.l10n_co_ne_zip_key:
            raise UserError(_(
                'El envío de ese CUNE no tiene ZipKey registrado; no hay con qué consultar a la DIAN.'))
        return payslip

    def action_check_status(self):
        self.ensure_one()
        cune = (self.cune or '').strip()
        # Un CUNE de un documento mensual se consulta con ``GetStatus`` por CUNE (doc 53 §23.17, 7a); el resto sigue
        # el camino del recibo (GetStatusZip por ZipKey).
        documento = self.env['l10n.co.ne.documento'].search([('cune', '=', cune)], limit=1)
        if documento:
            documento.company_id._ne_exigir_colombia()
            documento._ne_reconsultar_por_cune()
            return {'type': 'ir.actions.act_window', 'res_model': documento._name, 'res_id': documento.id,
                    'view_mode': 'form', 'target': 'current'}
        payslip = self._resolve_payslip()
        return payslip.action_check_dian_status()
