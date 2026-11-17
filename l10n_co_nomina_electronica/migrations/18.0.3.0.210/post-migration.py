# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Estados del documento mensual (doc 53 §26b, .210): recalcula ``state`` desde el último intento. ``etapa``,
``incierto`` y ``eliminado`` ya estaban guardados y no se tocan. Funciona con 0 filas."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['l10n.co.ne.documento']._ne_recalcular_estado()
