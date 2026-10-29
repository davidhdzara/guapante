# -*- coding: utf-8 -*-
"""Caso actualización (módulo ya instalado, ej. staging): delega en la
misma función que usa post_init_hook (ver ../../hooks.py) para que una
instalación nueva (producción) y una actualización (staging) terminen
en el mismo estado, sin duplicar ni reinstalar nada (QA, 2026-10-29)."""
from odoo import SUPERUSER_ID, api

from odoo.addons.ist_preparation_day_picking.hooks import grant_admin_group_once


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    grant_admin_group_once(env)
