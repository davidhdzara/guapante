from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    """
    Al instalar el modulo, genera automaticamente el snapshot del dia
    para que el usuario vea datos inmediatamente.
    """
    env['guapante.kardex.daily'].take_daily_snapshot()
