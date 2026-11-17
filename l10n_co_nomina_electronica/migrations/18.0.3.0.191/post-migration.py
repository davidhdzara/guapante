# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Etapa 1b (.191): lo ya transmitido por recibo pasa a documentos ``legacy`` 1:1 (doc 53 §8.2). No quita nada del
recibo. Idempotente (el recibo que ya apunta a un documento no se migra otra vez) y funciona con 0 filas."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['l10n.co.ne.documento']._ne_migrar_legacy()
