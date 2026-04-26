from . import models
from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    """
    Se ejecuta automáticamente al instalar el módulo por primera vez.
    Genera la jerarquía DANE y pre-carga los conceptos de retención.
    """
    # 1. Generar maestro DANE
    env['insotech.retention.category'].auto_generate_colombian_dane_categories()
    
    # 2. Inyectar conceptos por defecto
    env['insotech.retention.concept'].init_default_concepts()
