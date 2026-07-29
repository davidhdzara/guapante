# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import report


def post_init_hook(env):
    """Clasifica los impuestos de retención colombianos ya existentes
    al instalar el módulo. Ver ESPEC §4 Fase 1 para el orden de reglas.
    """
    taxes = env['account.tax'].with_context(active_test=False).search([])
    taxes._l10n_co_compute_retention_type()
