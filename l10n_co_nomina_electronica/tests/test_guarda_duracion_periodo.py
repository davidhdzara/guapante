# -*- coding: utf-8 -*-
"""E-4 (doc 59 §21): un recibo de la estructura general que cubre mas dias que el maximo de la periodicidad de su contrato no se
calcula ni se confirma (UserError claro con la causa probable: dia y mes invertidos). Hallazgo del lote 2 de QA: recibos con
`date_from = 2026-01-04` y `date_to = 2026-04-15` (102 dias) que desde M1-1 se pagarian completos en silencio. Tope por
periodicidad, no igualdad; liquidacion, prima y bonificacion excluidas; compania no colombiana inerte."""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestGuardaDuracionPeriodo(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Guarda Duración')
        cls.tipos = {
            clave: cls.env['hr.payroll.structure.type'].create({
                'name': 'Tipo duración %s' % clave, 'country_id': cls.env.ref('base.co').id, 'default_schedule_pay': clave})
            for clave in ('weekly', 'bi-weekly', 'semi-monthly', 'monthly')}
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, desde, hasta, periodicidad='monthly', struct=None, ingreso=date(2024, 1, 1), company=None):
        type(self).n += 1
        company = company or self.company
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Guarda %s' % self.n, 'company_id': company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Guarda %s' % self.n, 'employee_id': empleado.id, 'company_id': company.id,
            'structure_type_id': self.tipos[periodicidad].id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': ingreso, 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Recibo Guarda %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': company.id, 'struct_id': (struct or self.general).id, 'date_from': desde, 'date_to': hasta})

    def _pasa(self, recibo):
        recibo._ne_validar_duracion_periodo()       # no lanza

    def _falla(self, recibo):
        with self.assertRaises(UserError) as error:
            recibo._ne_validar_duracion_periodo()
        return str(error.exception)

    # ── el caso del lote 2 de QA ─────────────────────────────────────
    def test_mensual_con_periodo_de_102_dias_falla_nombrando_recibo_empleado_y_fechas(self):
        recibo = self._recibo(date(2026, 1, 4), date(2026, 4, 15))
        mensaje = self._falla(recibo)
        for esperado in (recibo.name, recibo.employee_id.name, '102', '31'):
            self.assertIn(esperado, mensaje)

    def test_el_mensaje_es_claro_en_espanol_con_la_causa_probable(self):
        mensaje = self._falla(self._recibo(date(2026, 1, 4), date(2026, 4, 15)))
        self.assertIn('invertidos', mensaje)                      # causa probable: dia y mes invertidos
        self.assertIn('periodicidad', mensaje)                    # como corregir
        for jerga in ('IA', 'inteligencia artificial', 'Claude', 'modelo de lenguaje', 'traceback', 'ORM'):
            self.assertNotIn(jerga, mensaje)

    def test_compute_sheet_y_confirmar_aplican_la_guarda(self):
        recibo = self._recibo(date(2026, 1, 4), date(2026, 4, 15))
        with self.assertRaises(UserError):
            recibo.compute_sheet()
        with self.assertRaises(UserError):
            recibo.action_payslip_done()

    # ── lo que SI pasa ───────────────────────────────────────────────
    def test_mensual_y_quincenal_dentro_del_maximo_pasan(self):
        for desde, hasta in ((date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 3, 1), date(2026, 3, 15)),
                             (date(2026, 3, 16), date(2026, 3, 31)), (date(2026, 2, 1), date(2026, 2, 28))):
            self._pasa(self._recibo(desde, hasta))

    def test_5_y_20_el_periodo_que_cruza_mes_pasa_y_uno_largo_falla(self):
        self._pasa(self._recibo(date(2026, 3, 21), date(2026, 4, 5), periodicidad='semi-monthly'))     # 16 dias
        self._pasa(self._recibo(date(2026, 2, 21), date(2026, 3, 5), periodicidad='semi-monthly'))
        self._falla(self._recibo(date(2026, 3, 21), date(2026, 4, 10), periodicidad='semi-monthly'))   # 21 dias

    def test_semanal_que_cruza_mes_de_31_dias_pasa_y_8_dias_falla(self):
        self._pasa(self._recibo(date(2026, 3, 28), date(2026, 4, 3), periodicidad='weekly'))           # 7 dias
        self._falla(self._recibo(date(2026, 3, 28), date(2026, 4, 4), periodicidad='weekly'))          # 8 dias

    def test_bi_weekly_se_trata_como_quincena(self):
        self._pasa(self._recibo(date(2026, 3, 16), date(2026, 3, 31), periodicidad='bi-weekly'))       # 16 dias
        self._falla(self._recibo(date(2026, 3, 1), date(2026, 3, 20), periodicidad='bi-weekly'))       # 20 dias

    def test_un_periodo_mas_corto_que_la_periodicidad_pasa(self):
        """Ingreso o retiro a mitad de periodo: el maximo es un tope, no una igualdad."""
        self._pasa(self._recibo(date(2026, 3, 10), date(2026, 3, 20), periodicidad='semi-monthly'))
        self._pasa(self._recibo(date(2026, 3, 30), date(2026, 3, 31), periodicidad='weekly'))

    def test_limite_conocido_mes_completo_en_un_contrato_quincenal_pasa_en_un_tipo_monthly(self):
        """Limitacion documentada (doc 59 §21): un tipo `monthly` con pagos quincenales (default nativo, H-QA-016) acepta un
        periodo digitado de mes completo (1 a 30): el tope es el de la periodicidad del contrato, no el del calendario real
        de pagos de la compania."""
        self._pasa(self._recibo(date(2026, 4, 1), date(2026, 4, 30), periodicidad='monthly'))

    # ── exclusiones ──────────────────────────────────────────────────
    def test_liquidacion_prima_y_bonificacion_no_se_validan(self):
        for xmlid in ('hr_payroll_structure_co_liquidacion', 'hr_payroll_structure_co_prima',
                      'hr_payroll_structure_co_bonificacion'):
            estructura = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
            self._pasa(self._recibo(date(2024, 1, 1), date(2026, 4, 15), struct=estructura))

    def test_compania_no_colombiana_es_inerte(self):
        recibo = self._recibo(date(2026, 1, 4), date(2026, 4, 15))
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            self._pasa(recibo)

    # ── recibos ya confirmados ───────────────────────────────────────
    def test_un_recibo_confirmado_antiguo_no_se_revalida_al_consultarlo(self):
        recibo = self._recibo(date(2026, 1, 4), date(2026, 4, 15))
        recibo.state = 'done'
        recibo.read(['name', 'state'])            # consultar no valida nada
        self.assertEqual(recibo.state, 'done')
