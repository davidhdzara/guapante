# -*- coding: utf-8 -*-
"""M1-1 (doc 61): periodos de pago que cruzan de mes calendario.

Antes el motor recortaba CUALQUIER periodo que cruza de mes al mes de ``date_to`` (se escribio para la liquidacion):
con pagos los 5 y 20 el recibo 21-mar -> 5-abr pagaba solo 5 dias. Ahora el recorte es solo de la liquidacion y los
dias se cuentan por segmentos de mes (mes comercial de 30 dias). El pago SEMANAL cuenta dias calendario (David,
2026-11-14: 7 dias, valor del dia = salario / 30). Fuentes: Anexo DIAN V1.0 NIE069 (dias laborados) y convencion de
mes comercial de 30 dias del marco PILA; texto de CST art. 134 NO VERIFICADO (doc 61 §2)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestPeriodosCruzanMes(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Periodos Cruzan Mes')
        cls.tipo_semanal = cls.env['hr.payroll.structure.type'].create({
            'name': 'Semanal M1', 'country_id': cls.env.ref('base.co').id, 'default_schedule_pay': 'weekly'})

    def _recibo(self, desde, hasta, ingreso=date(2024, 1, 1), semanal=False, struct=None):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado M1 %s' % self.n, 'company_id': self.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato M1 %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': (self.tipo_semanal if semanal else self.structure_type).id,
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': ingreso, 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Recibo M1 %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': (struct or self.struct).id,
            'date_from': desde, 'date_to': hasta})

    # ── pagos los 5 y 20 ─────────────────────────────────────────────
    def test_5_y_20_el_periodo_que_cruza_el_mes_paga_sus_15_dias(self):
        recibo = self._recibo(date(2026, 3, 21), date(2026, 4, 5))
        self.assertEqual(recibo._ne_tramo_pagable_periodo(), (date(2026, 3, 21), date(2026, 4, 5)))
        self.assertEqual(recibo._ne_dias_pagables(), 15)       # antes: 5 (solo 1 a 5 de abril)

    def test_5_y_20_los_dos_periodos_de_un_mes_suman_30(self):
        cruza = self._recibo(date(2026, 2, 21), date(2026, 3, 5))     # cruza febrero (28 dias reales) a marzo
        dentro = self._recibo(date(2026, 3, 6), date(2026, 3, 20))
        resto = self._recibo(date(2026, 3, 21), date(2026, 4, 5))
        self.assertEqual((cruza._ne_dias_pagables(), dentro._ne_dias_pagables(), resto._ne_dias_pagables()), (15, 15, 15))

    def test_5_y_20_con_ingreso_a_mitad_del_periodo_cuenta_solo_los_dias_del_contrato(self):
        recibo = self._recibo(date(2026, 3, 21), date(2026, 4, 5), ingreso=date(2026, 3, 28))
        self.assertEqual(recibo._ne_dias_pagables(), 8)        # 28-31 de marzo (comerciales 28 a 30 = 3) + 5

    # ── semanal: dias calendario, valor del dia = salario / 30 ───────
    def test_semanal_que_cruza_un_mes_de_31_dias_paga_7_dias(self):
        recibo = self._recibo(date(2026, 3, 28), date(2026, 4, 3), semanal=True)
        self.assertEqual(recibo._ne_dias_pagables(), 7)         # 28,29,30,31 de marzo + 1,2,3 de abril

    def test_semanal_dentro_del_mes_paga_7_dias(self):
        self.assertEqual(self._recibo(date(2026, 3, 14), date(2026, 3, 20), semanal=True)._ne_dias_pagables(), 7)
        self.assertEqual(self._recibo(date(2026, 2, 21), date(2026, 2, 27), semanal=True)._ne_dias_pagables(), 7)

    # ── mensual y quincenal: sin cambio ──────────────────────────────
    def test_mensual_y_quincenal_no_cambian(self):
        self.assertEqual(self._recibo(date(2026, 3, 1), date(2026, 3, 31))._ne_dias_pagables(), 30)
        self.assertEqual(self._recibo(date(2026, 2, 1), date(2026, 2, 28))._ne_dias_pagables(), 30)
        self.assertEqual(self._recibo(date(2026, 3, 1), date(2026, 3, 15))._ne_dias_pagables(), 15)
        self.assertEqual(self._recibo(date(2026, 3, 16), date(2026, 3, 31))._ne_dias_pagables(), 15)
        self.assertEqual(self._recibo(date(2026, 2, 16), date(2026, 2, 28))._ne_dias_pagables(), 15)

    # ── liquidacion: conserva el recorte al ultimo mes (H-009) ───────
    def test_liquidacion_conserva_el_recorte_al_mes_de_date_to(self):
        liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        recibo = self._recibo(date(2024, 3, 1), date(2026, 4, 15), ingreso=date(2024, 3, 1), struct=liquidacion)
        self.assertEqual(recibo._ne_tramo_pagable_periodo(), (date(2026, 4, 1), date(2026, 4, 15)))
        self.assertEqual(recibo._ne_dias_pagables(), 15)

    def test_liquidacion_de_un_semanal_cuenta_dias_comerciales_no_calendario(self):
        """Un mes completo de liquidacion de un empleado semanal sigue siendo 30 (mes comercial), no 31."""
        liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        recibo = self._recibo(date(2024, 1, 1), date(2026, 3, 31), ingreso=date(2024, 1, 1), semanal=True,
                              struct=liquidacion)
        self.assertEqual(recibo._ne_dias_pagables(), 30)
