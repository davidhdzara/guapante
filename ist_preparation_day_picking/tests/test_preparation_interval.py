# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationInterval(TestPreparationDayProductClaim):
    """Commit 1 de Fase 2 (modelo + índices + FKs) — solo lo que se puede
    probar a nivel de esquema: el constraint de Python
    (employee_id obligatorio para 'working') y el índice único parcial
    que impide dos intervalos 'working' abiertos del mismo operario
    (backstop de base de datos, condición (a) de Tech Lead,
    2026-11-04). La apertura/cierre reales desde action_open_lines_
    kanban/action_stop/etc. llegan en el próximo commit — acá no hay
    nada de eso todavía."""

    def setUp(self):
        super().setUp()
        self.Interval = self.env['guapante.preparation.interval']
        self.session = self._load_session_with_product()
        self.claim = self.session.product_claim_ids

    def _interval_vals(self, employee=None, kind='working', **extra):
        now = fields.Datetime.now()
        vals = {
            'wizard_id': self.session.id,
            'claim_id': self.claim.id,
            'kind': kind,
            'start_dt': now,
            'last_touched_dt': now,
        }
        if employee is not None:
            vals['employee_id'] = employee.id
        vals.update(extra)
        return vals

    def test_working_interval_requires_employee(self):
        with self.assertRaises(ValidationError):
            self.Interval.create(self._interval_vals(employee=None, kind='working'))

    def test_stopped_interval_without_employee_allowed(self):
        """'Detenido' es un estado del producto, no el reloj de un
        operario (cualquiera puede detener el claim de cualquiera) —
        no exige employee_id."""
        interval = self.Interval.create(
            self._interval_vals(employee=None, kind='stopped')
        )
        self.assertTrue(interval)
        self.assertFalse(interval.employee_id)

    def test_stopped_interval_with_employee_informational_allowed(self):
        """employee_id en un 'stopped' es solo informativo (quién lo
        detuvo) — permitido, pero NO debe chocar con el índice único
        de 'working' (son tipos distintos)."""
        interval = self.Interval.create(
            self._interval_vals(employee=self.operator_a, kind='stopped')
        )
        self.assertEqual(interval.employee_id, self.operator_a)

    def test_unique_open_working_per_employee_db_constraint(self):
        """Backstop de base de datos (condición (a), Tech Lead
        2026-11-04): el candado real en caliente es un
        pg_advisory_xact_lock (próximo commit) — este índice único
        parcial es la red de respaldo que nunca debería saltar en
        operación normal, pero tiene que existir y funcionar."""
        self.Interval.create(self._interval_vals(employee=self.operator_a))
        with self.assertRaises(IntegrityError):
            with mute_logger('odoo.sql_db'):
                with self.env.cr.savepoint():
                    self.Interval.create(
                        self._interval_vals(employee=self.operator_a)
                    )

    def test_unique_constraint_does_not_block_different_employees(self):
        self.Interval.create(self._interval_vals(employee=self.operator_a))
        second = self.Interval.create(self._interval_vals(employee=self.operator_b))
        self.assertTrue(second)

    def test_unique_constraint_does_not_block_closed_intervals(self):
        """Dos 'working' del mismo operario no chocan si el primero ya
        está cerrado (end_dt puesto) — el índice es WHERE end_dt IS
        NULL, a propósito."""
        now = fields.Datetime.now()
        self.Interval.create(self._interval_vals(
            employee=self.operator_a, end_dt=now, duration_s=0,
            close_reason='left',
        ))
        second = self.Interval.create(self._interval_vals(employee=self.operator_a))
        self.assertTrue(second)

    def test_unique_constraint_scoped_to_working_kind(self):
        """Un 'working' abierto y un 'stopped' abierto del MISMO
        operario no se pisan entre sí — el índice único es
        kind='working' únicamente (ver docstring de la clase: 'stopped'
        no es el reloj personal de nadie)."""
        self.Interval.create(self._interval_vals(employee=self.operator_a, kind='working'))
        second = self.Interval.create(
            self._interval_vals(employee=self.operator_a, kind='stopped')
        )
        self.assertTrue(second)

    def test_employee_restrict_blocks_unlink_with_interval(self):
        """ondelete='restrict' en employee_id — desde el commit 7/7
        (guarda amigable en hr_employee.py) el unlink falla con
        UserError, nunca borra en silencio. Ver
        test_preparation_interval_unlink_guard.py para la cobertura
        dedicada de ese guard (mensaje, empleado sin intervalos sí se
        puede borrar)."""
        self.Interval.create(self._interval_vals(employee=self.operator_a))
        with self.assertRaises(UserError):
            self.operator_a.unlink()
