# -*- coding: utf-8 -*-
"""Frente 5, C2 (doc 58 §12): el comprobante de pago se agrupa SOLO por (empleado, primera fecha de pago): sin suponer
quincenas, 15/30 ni que la prima viaje con otro recibo. Calendarios: mensual, quincenal, 5/20, semanal."""
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComprobantesAgrupador(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Agrupador Pago', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Agrupador Pago', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.nomina = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.ana, cls.contrato_ana = cls._empleado('Ana Pago')
        cls.luis, cls.contrato_luis = cls._empleado('Luis Pago')

    @classmethod
    def _empleado(cls, nombre):
        emp = cls.env['hr.employee'].create({
            'name': nombre, 'company_id': cls.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = cls.env['hr.contract'].create({
            'name': 'Contrato %s' % nombre, 'employee_id': emp.id, 'company_id': cls.company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        return emp, contrato

    def _recibo(self, empleado, contrato, estructura, desde, hasta, pagado, nombre, estado='done'):
        recibo = self.env['hr.payslip'].create({
            'name': nombre, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': estructura.id, 'date_from': desde, 'date_to': hasta})
        recibo.write({'state': estado, 'paid_date': pagado})
        return recibo

    def _ana(self, estructura, desde, hasta, pagado, nombre, **kw):
        return self._recibo(self.ana, self.contrato_ana, estructura, desde, hasta, pagado, nombre, **kw)

    def _agrupar(self, recibos):
        return self.env['hr.payslip']._ne_comprobantes(recibos)

    def test_quincena_y_prima_pagadas_el_mismo_dia_van_en_un_comprobante(self):
        q = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Q1')
        p = self._ana(self.prima, date(2026, 1, 1), date(2026, 6, 15), date(2026, 6, 15), 'Prima')
        grupos = self._agrupar(q | p)['grupos']
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['recibos'], q | p)
        self.assertEqual(grupos[0]['fecha_pago'], date(2026, 6, 15))
        self.assertEqual(grupos[0]['empleado'], self.ana)

    def test_la_prima_en_otro_dia_es_otro_comprobante(self):
        q = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Q1')
        p = self._ana(self.prima, date(2026, 1, 1), date(2026, 6, 15), date(2026, 6, 20), 'Prima tarde')
        grupos = self._agrupar(q | p)['grupos']
        self.assertEqual([g['recibos'] for g in grupos], [q, p])

    def test_seleccionar_un_solo_recibo_trae_el_grupo_completo(self):
        q = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Q1')
        p = self._ana(self.prima, date(2026, 1, 1), date(2026, 6, 15), date(2026, 6, 15), 'Prima')
        otro_dia = self._ana(self.nomina, date(2026, 6, 16), date(2026, 6, 30), date(2026, 6, 30), 'Q2')
        grupos = self._agrupar(p)['grupos']
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['recibos'], q | p)
        self.assertNotIn(otro_dia, grupos[0]['recibos'])

    def test_liquidacion_pagada_despues_es_aparte_y_el_mismo_dia_va_junta(self):
        q = self._ana(self.nomina, date(2026, 6, 16), date(2026, 6, 30), date(2026, 6, 30), 'Q2')
        liq_tarde = self._ana(self.liquidacion, date(2024, 1, 1), date(2026, 6, 30), date(2026, 7, 15), 'Liq tarde')
        self.assertEqual(len(self._agrupar(q | liq_tarde)['grupos']), 2)
        liq_tarde.paid_date = date(2026, 6, 30)
        grupos = self._agrupar(q | liq_tarde)['grupos']
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['recibos'], q | liq_tarde)

    def test_semana_que_cruza_el_mes_va_por_la_fecha_de_pago(self):
        semana = self._ana(self.nomina, date(2026, 3, 28), date(2026, 4, 3), date(2026, 4, 3), 'Semana')
        grupo = self._agrupar(semana)['grupos'][0]
        self.assertEqual(grupo['fecha_pago'], date(2026, 4, 3))

    def test_pagos_los_5_y_20_son_dos_comprobantes(self):
        a = self._ana(self.nomina, date(2026, 3, 21), date(2026, 4, 5), date(2026, 4, 5), 'P5')
        b = self._ana(self.nomina, date(2026, 4, 6), date(2026, 4, 20), date(2026, 4, 20), 'P20')
        grupos = self._agrupar(a | b)['grupos']
        self.assertEqual([g['fecha_pago'] for g in grupos], [date(2026, 4, 5), date(2026, 4, 20)])

    def test_dos_empleados_el_mismo_dia_son_dos_comprobantes(self):
        a = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Q1 Ana')
        l = self._recibo(self.luis, self.contrato_luis, self.nomina, date(2026, 6, 1), date(2026, 6, 15),
                         date(2026, 6, 15), 'Q1 Luis')
        grupos = self._agrupar(a | l)['grupos']
        self.assertEqual(len(grupos), 2)
        self.assertEqual({g['empleado'] for g in grupos}, {self.ana, self.luis})

    def test_sin_fecha_de_pago_o_sin_confirmar_no_tiene_comprobante_agrupado(self):
        sin_fecha = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), False, 'Sin fecha')
        borrador = self._ana(self.nomina, date(2026, 6, 16), date(2026, 6, 30), date(2026, 6, 30), 'Borrador',
                             estado='draft')
        resultado = self._agrupar(sin_fecha | borrador)
        self.assertFalse(resultado['grupos'])
        recibos = {r for r, _m in resultado['sin_fecha']}
        self.assertEqual(recibos, {sin_fecha, borrador})
        motivo = dict(resultado['sin_fecha'])[sin_fecha]
        self.assertIn('Sin fecha', motivo)
        self.assertIn('fecha de pago', motivo)

    def test_las_notas_no_son_pagos_y_no_entran_al_grupo(self):
        q = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Q1')
        credito = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Nota credito')
        credito.credit_note = True
        ajuste = self._ana(self.nomina, date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 15), 'Nota ajuste')
        ajuste.write({'l10n_co_ne_is_adjustment': True, 'l10n_co_ne_adjustment_ref_cune': 'a' * 96})
        self.assertEqual(self._agrupar(q)['grupos'][0]['recibos'], q)
