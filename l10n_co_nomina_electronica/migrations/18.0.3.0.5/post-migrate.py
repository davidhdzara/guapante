# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.5 -- provisiones de prestaciones sociales
(prima/cesantías/intereses/vacaciones) pasan de un modelo standalone
(l10n.co.hr.provision + .line + .wizard, wizard mensual manual) a 4 reglas
salariales invisibles dentro de hr_payroll_structure_co_nomina, calculadas
automáticamente en cada corrida de nómina (doc 18).

A diferencia de 18.0.3.0.1 (annual_params/time_params) y 18.0.3.0.3 (embargo
híbrido), donde las tablas viejas estaban vacías, acá SÍ había un registro
real: "Provisión 05/2026" (l10n_co_hr_provision id=5, estado 'confirmed',
18 líneas en l10n_co_hr_provision_line) -- verificado por SSH antes de
escribir este script. David confirmó (vía Tech Lead, 2026-09-10) que es
dato de prueba del ciclo de construcción de la función en mayo 2026, no
contabilidad real de Guapante -- autorizado a eliminarlo como parte de esta
migración, no a conservarlo ni migrarlo.

Mismo patrón que 18.0.3.0.1/18.0.3.0.3: eliminar el modelo Python no dispara
el DROP TABLE automático de ir.model.unlink() -> _drop_table() (para cuando
corre ir.model._process_end(), la clase ya no existe en el registro y
self.env.get(model.model) devuelve None -- el DROP se salta en silencio).
CASCADE por la relación l10n_co_hr_provision_line.provision_id -> ondelete
cascade a nivel ORM, pero a nivel SQL crudo hace falta CASCADE explícito
para no depender de esa FK estando ya fuera del registro de modelos.
"""

import logging

_logger = logging.getLogger(__name__)

_TABLES = ('l10n_co_hr_provision_line', 'l10n_co_hr_provision')


def migrate(cr, version):
    for table in _TABLES:
        cr.execute("SELECT to_regclass(%s)", (table,))
        exists = cr.fetchone()[0] is not None
        if not exists:
            _logger.info(
                'Post-migración 18.0.3.0.5: %s ya no existe, nada que hacer.',
                table,
            )
            continue

        cr.execute("SELECT count(*) FROM %s" % table)  # nombre de tabla fijo, no input de usuario
        row_count = cr.fetchone()[0]
        cr.execute("DROP TABLE IF EXISTS %s CASCADE" % table)
        _logger.info(
            'Post-migración 18.0.3.0.5: DROP TABLE %s (tenía %d fila(s) -- '
            'para l10n_co_hr_provision, incluía el registro real '
            '"Provisión 05/2026" (id=5), autorizado a eliminar por David '
            '2026-09-10, dato de prueba de mayo 2026, no contabilidad real). '
            'Reemplazado por reglas invisibles CO_PROV_PRIMA/CO_PROV_CESANTIAS/'
            'CO_PROV_INT_CES/CO_PROV_VACACIONES en hr_payroll_structure_co_nomina -- doc 18.',
            table, row_count,
        )
