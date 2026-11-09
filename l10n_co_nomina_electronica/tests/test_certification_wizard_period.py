# -*- coding: utf-8 -*-
""".98 (2026-10-11, hallazgo de Tech Lead en staging):
l10n.co.ne.certification.wizard._auto_select_period() elegía el periodo
del último hr.payslip 'done' de Nómina General por order='date_to desc'
sin filtrar fechas. En staging había payslips de prueba con date_to hasta
2027-01-31 (datos de habilitación anteriores), y el asistente terminaba
eligiendo un periodo futuro que todavía no empieza.

Arreglo: el candidato debe tener además date_from <= hoy ("ya iniciado").
Entre los que cumplen esa condición, sigue ganando el de mayor date_to.
Sin candidato ninguno, el fallback al mes calendario actual sigue igual
(no se tocó esa rama).
"""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestCertificationWizardPeriod(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py)
        # -- sin esto, el fallback de esta prueba podría chocar con payslips
        # 'done' reales de la compañía por defecto en la copia de la BD de
        # staging/Guapante sobre la que corre la build.
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Periodo Habilitación',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Periodo Habilitación',
            'country_id': co_country.id,
        })
        # El método filtra por ESTA estructura real específicamente (es la
        # que usa el pipeline real de habilitación) -- no una estructura
        # dedicada de prueba como en otros archivos de tests.
        cls.struct = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.wizard = cls.env['l10n.co.ne.certification.wizard'].create({
            'company_id': cls.company.id,
        })

    def _make_done_payslip(self, name, date_from, date_to):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '20' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.struct.id,
            'date_from': date_from,
            'date_to': date_to,
            'state': 'done',
        })

    def test_periodo_futuro_se_ignora_gana_el_ya_iniciado(self):
        """Caso real de staging: payslip 'done' en periodo futuro (aún no
        empieza) convive con uno en periodo ya iniciado -- debe ganar el
        ya iniciado, nunca el futuro, aunque el futuro tenga date_to
        mayor (lo que antes lo hacía ganar por order='date_to desc')."""
        hoy = fields.Date.context_today(self.wizard)
        self._make_done_payslip(
            'PeriodoFuturo',
            hoy + relativedelta(months=2, day=1),
            hoy + relativedelta(months=3, day=1, days=-1),
        )
        ya_iniciado = self._make_done_payslip(
            'PeriodoYaIniciado',
            hoy + relativedelta(months=-1, day=1),
            hoy + relativedelta(day=1, days=-1),
        )
        date_from, date_to = self.wizard._auto_select_period()
        self.assertEqual(date_from, ya_iniciado.date_from)
        self.assertEqual(date_to, ya_iniciado.date_to)

    def test_sin_payslips_cae_al_mes_actual(self):
        """Sin ningún payslip 'done' (compañía nueva, aislada de las
        demás pruebas) -- fallback sin cambios: mes calendario actual
        completo."""
        hoy = fields.Date.context_today(self.wizard)
        primer_dia = hoy.replace(day=1)
        ultimo_dia = primer_dia + relativedelta(months=1, days=-1)
        date_from, date_to = self.wizard._auto_select_period()
        self.assertEqual(date_from, primer_dia)
        self.assertEqual(date_to, ultimo_dia)
