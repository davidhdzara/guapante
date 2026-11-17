# -*- coding: utf-8 -*-
"""Fusion sobre recibos CALCULADOS POR EL MOTOR REAL (spike etapa 3, doc 53 §19): dos quincenas de febrero (28
dias) y de marzo (31 dias) de 2026. Se compara cada total fusionado con la suma de las lineas de las colillas
y se REGISTRA en el log los dias que entrega el motor por quincena (para ver febrero y el mes de 31 dias).
No escribe nada fuera de la transaccion de la prueba."""

import logging
from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import documento_merge as dm

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDocumentoFusionReal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Fusion Real', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'l10n_co_pila_tipo_aportante': '1',
            'l10n_co_pila_forma_presentacion': 'U'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Fusion Real', 'country_id': cls.env.ref('base.co').id})
        cls.est = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibos(self, mes, ultimo_dia):
        empleado = self.env['hr.employee'].create({
            'name': 'Fusion %s' % mes, 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10', 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00'})
        contrato = self.env['hr.contract'].create({
            'name': 'C', 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1),
            'state': 'open', 'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        recibos = self.env['hr.payslip']
        for ini, fin in ((1, 15), (16, ultimo_dia)):
            recibo = self.env['hr.payslip'].create({
                'name': 'Q %s-%s' % (mes, ini), 'employee_id': empleado.id, 'contract_id': contrato.id,
                'company_id': self.company.id, 'struct_id': self.est.id,
                'date_from': date(2026, mes, ini), 'date_to': date(2026, mes, fin)})
            recibo.compute_sheet()
            recibos |= recibo
        return recibos

    def _suma(self, recibos, codigo):
        return sum((abs(Decimal(str(l.total))) for r in recibos
                    for l in r.line_ids if l.code == codigo), Decimal('0'))

    def _dato(self, recibo):
        """Lo mismo que _collect_payslip_data() aporta a la fusion: Devengados, Deducciones y totales."""
        devengados, deducciones = recibo._map_salary_rules_to_xml()
        dev = sum(l.total for l in recibo.line_ids
                  if l.salary_rule_id.l10n_co_ne_dian_concept and not l.salary_rule_id.l10n_co_ne_is_deduction)
        ded = sum(abs(l.total) for l in recibo.line_ids
                  if l.salary_rule_id.l10n_co_ne_dian_concept and l.salary_rule_id.l10n_co_ne_is_deduction)
        return {'devengados': devengados, 'deducciones': deducciones,
                'devengados_total': dev, 'deducciones_total': ded}

    def _verificar_mes(self, mes, ultimo_dia):
        recibos = self._recibos(mes, ultimo_dia)
        dias = [recibo._ne_dias_pagables() for recibo in recibos]
        _logger.warning('FUSION REAL mes=%s dias pagables por quincena=%s suma=%s', mes, dias, sum(dias))
        doc = dm.fusionar_documento(
            [self._dato(r) for r in recibos],
            fechas_pagos=['2026-%02d-15' % mes, '2026-%02d-%02d' % (mes, ultimo_dia)],
            periodo={'FechaLiquidacionInicio': '2026-%02d-01' % mes,
                     'FechaLiquidacionFin': '2026-%02d-%02d' % (mes, ultimo_dia)})
        basico = doc['devengados']['Basico']
        self.assertEqual(Decimal(basico['SueldoTrabajado']), self._suma(recibos, 'CO_BASICO'))
        self.assertEqual(int(basico['DiasTrabajados']), sum(int(r._ne_dias_xml(r._ne_dias_pagables())) for r in recibos))
        self.assertEqual(Decimal(doc['deducciones']['Salud']['Deduccion']), self._suma(recibos, 'CO_SALUD_EMP'))
        self.assertEqual(Decimal(doc['deducciones']['FondoPension']['Deduccion']),
                         self._suma(recibos, 'CO_PENSION_EMP'))
        transporte = doc['devengados'].get('Transporte')
        if transporte:
            self.assertEqual(Decimal(transporte[0]['AuxilioTransporte']), self._suma(recibos, 'CO_AUX_TRANS'))
        self.assertEqual(Decimal(doc['totales']['DevengadosTotal']).quantize(Decimal('0.01')),
                         sum((Decimal(str(self._dato(r)['devengados_total'])) for r in recibos),
                             Decimal('0')).quantize(Decimal('0.01')))
        self.assertEqual(doc['fechas_pagos'], ['2026-%02d-15' % mes, '2026-%02d-%02d' % (mes, ultimo_dia)])
        return doc

    def test_febrero_de_28_dias(self):
        self._verificar_mes(2, 28)

    def test_marzo_de_31_dias(self):
        self._verificar_mes(3, 31)
