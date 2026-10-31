# -*- coding: utf-8 -*-
"""Caso actualización (módulo ya instalado, ej. staging): delega en la
misma función que usa post_init_hook (ver ../../hooks.py) para que una
instalación nueva (producción) y una actualización (staging) terminen
en el mismo estado — bloqueante encontrado por Tech Lead antes de la
salida a producción (2026-10-31): sin esto, el usuario compartido del
tablet (operacion@donguapante.com) se queda sin el grupo "Operario de
Picking" en una instalación nueva."""
from odoo import SUPERUSER_ID, api

from odoo.addons.ist_preparation_day_picking.hooks import grant_operator_group_once


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    grant_operator_group_once(env)
