# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Documento firmado de un registro del empleado (pacto de desalarización, día de descanso pactado): vincula al registro los adjuntos que el widget ``many2many_binary`` sube ANTES de guardar la fila.

La lógica estaba en ``l10n.co.employee.pacto`` (.302, revisión v19 del consultor, 22-nov); H-F1-07 la comparte con el registro del día de descanso en vez de copiarla."""

from odoo import api, models


class L10nCoAdjuntoVinculado(models.AbstractModel):
    _name = 'l10n.co.adjunto.vinculado'
    _description = 'Vincula al registro los adjuntos subidos antes de guardar'

    @api.model_create_multi
    def create(self, vals_list):
        registros = super().create(vals_list)
        registros._vincular_adjuntos()
        return registros

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._vincular_adjuntos()
        return res

    def _vincular_adjuntos(self):
        """El widget ``many2many_binary`` sube el archivo ANTES de guardar la fila, con el ``res_model`` del registro y ``res_id = 0`` (``web/controllers/binary.py``, ``upload_attachment``). Un
        ``ir.attachment`` sin ``res_id`` solo lo puede leer quien lo creó o el administrador (``ir.attachment.check``: ``if not res_id and create_uid != uid``): un segundo usuario de nómina no vería el
        documento firmado, que es la prueba. Al guardar, los adjuntos sin enlace se vinculan al registro: desde ahí el acceso sigue el del registro (lectura del usuario de nómina, regla de compañía). Los que
        ya cuelgan de otro registro no se mueven. La cobertura no depende de esto (se lee con ``sudo``): solo la visibilidad del documento."""
        for registro in self:
            sin_enlace = registro.attachment_ids.filtered(lambda adjunto: not adjunto.res_id)
            if sin_enlace:
                sin_enlace.sudo().write({'res_model': registro._name, 'res_id': registro.id})
