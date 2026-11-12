# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Libranzas y embargos con tercero real.

1) hr.contract.l10n_co_ne_libranza (monto unico) -> una asignacion salarial
   tipo Libranza por contrato abierto con monto > 0. SIN entidad: no se
   inventa; la nomina de ese empleado fallara con un error claro hasta que se
   complete "Juzgado / Entidad".
2) hr.salary.attachment.l10n_co_embargo_juzgado (texto) -> l10n_co_partner_id
   por coincidencia exacta de nombre (sin distinguir mayusculas) con UN solo
   contacto; sin coincidencia el texto queda como legado.
En las bases conocidas (staging y produccion de Guapante) no hay filas.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _columna(cr, tabla, columna):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s", (tabla, columna))
    return bool(cr.fetchone())


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if _columna(cr, 'hr_contract', 'l10n_co_ne_libranza'):
        tipo = env.ref(
            'l10n_co_nomina_electronica.input_l10n_co_libranza',
            raise_if_not_found=False)
        cr.execute(
            "SELECT id, employee_id, company_id, date_start, l10n_co_ne_libranza "
            "FROM hr_contract WHERE state = 'open' "
            "AND COALESCE(l10n_co_ne_libranza, 0) > 0")
        for cid, emp, company, fecha, monto in cr.fetchall():
            if not tipo:
                break
            env['hr.salary.attachment'].create({
                'description': 'Libranza (migrada del contrato %s)' % cid,
                'employee_ids': [(6, 0, [emp])],
                'company_id': company,
                'other_input_type_id': tipo.id,
                'monthly_amount': monto,
                'date_start': fecha,
                'no_end_date': True,
            })
            _logger.warning(
                'Libranza del contrato %s migrada sin entidad: complete '
                '"Juzgado / Entidad" en Asignaciones Salariales.', cid)
    if _columna(cr, 'hr_salary_attachment', 'l10n_co_embargo_juzgado'):
        cr.execute(
            """
            UPDATE hr_salary_attachment a SET l10n_co_partner_id = p.id,
                   l10n_co_embargo_juzgado = NULL
              FROM (SELECT LOWER(TRIM(name)) AS n, MIN(id) AS id
                      FROM res_partner WHERE active GROUP BY LOWER(TRIM(name))
                    HAVING COUNT(*) = 1) p
             WHERE a.l10n_co_partner_id IS NULL
               AND LOWER(TRIM(a.l10n_co_embargo_juzgado)) = p.n
            """)
        _logger.info('Embargos enlazados a contacto: %s', cr.rowcount)
