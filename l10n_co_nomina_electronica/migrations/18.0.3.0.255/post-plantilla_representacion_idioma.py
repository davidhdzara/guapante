# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 6, P6-4 (doc 59 §9 decisión 4): la plantilla de la representación gráfica se entrega en el idioma del empleado
(patrón de la plantilla nativa de la colilla). La plantilla se instaló en .253 como noupdate: una actualización no la
reescribe, así que esta migración fija el idioma SOLO si está vacío (un ajuste hecho a mano no se pisa). Idempotente."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    plantilla = env.ref('l10n_co_nomina_electronica.mail_template_representacion_grafica', raise_if_not_found=False)
    if plantilla and not plantilla.lang:
        plantilla.lang = '{{ object.employee_id.lang }}'
