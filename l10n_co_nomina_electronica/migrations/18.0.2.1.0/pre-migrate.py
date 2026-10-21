# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Pre-migración 18.0.2.1.0 — vincula filas existentes de
l10n.co.payroll.annual.params con los external IDs nuevos de
data/l10n_co_payroll_annual_params_data.xml (annual_params_2024/2025/2026).

Por que hace falta: ese data file es nuevo (nunca existio antes), pero el
modelo l10n.co.payroll.annual.params no es nuevo -- instalaciones ya en
producción (ej. Guapante) pueden tener filas manuales para esos mismos
year+company_id, sin ir_model_data asociado. Sin este pre-migrate, al
cargar el data file Odoo no encuentra el external ID, intenta crear un
registro nuevo, y choca con el _sql_constraints unique_year_company
(IntegrityError, falla el -u completo del modulo).

Corre ANTES de que se carguen los data files (a diferencia de
post-migrate.py, que corre despues). Vincula por year+company_id; si la
fila no existe todavia (instalacion nueva), no hace nada y el data file
se comporta normal -- crea los 3 registros.

LIMITACION CONOCIDA (multi-compañia): el external ID se arma solo con el
year ('annual_params_2024', etc.), no con company_id. Si una misma
instalacion tuviera mas de una compañia con fila propia para el mismo
year, el `ON CONFLICT (module, name) DO NOTHING` solo vincula la primera
fila que procese la consulta -- las demas companias con ese year quedan
sin vincular (no se rompen, pero un futuro -u podria intentar crear un
duplicado para ellas). No aplica hoy: todas las instalaciones actuales
de este modulo son un cliente = una compañia. Fix futuro si hiciera
falta: agregar company_id al nombre del external ID e iterar por
year+company_id en vez de solo year.
"""

import logging

_logger = logging.getLogger(__name__)

_YEARS_SEEDED_BY_DATA_FILE = (2024, 2025, 2026)


def migrate(cr, version):
    cr.execute("""
        SELECT id, year FROM l10n_co_payroll_annual_params
        WHERE year IN %s
    """, (_YEARS_SEEDED_BY_DATA_FILE,))
    rows = cr.fetchall()
    for res_id, year in rows:
        cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
            VALUES (%s, 'l10n_co_nomina_electronica',
                    'l10n.co.payroll.annual.params', %s, True)
            ON CONFLICT (module, name) DO NOTHING
        """, ('annual_params_%d' % year, res_id))
    _logger.info(
        'Pre-migración 18.0.2.1.0: %d fila(s) existente(s) de '
        'l10n.co.payroll.annual.params vinculada(s) a external ID '
        'annual_params_<year> antes de cargar el data file nuevo.',
        len(rows),
    )
