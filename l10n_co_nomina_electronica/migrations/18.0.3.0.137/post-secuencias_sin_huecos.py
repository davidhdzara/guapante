# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """H-023: secuencias NE/NA a ``no_gap`` conservando el siguiente número."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.sequence']._l10n_co_ne_asegurar_sin_huecos()
