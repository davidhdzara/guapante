# -*- coding: utf-8 -*-
"""H-F1-05 (decision del TL con el Concepto DIAN 13840 de 2025): el XML de los 4 conceptos dominicales/festivos (HEDDF, HRDDF, HENDF, HRNDF) salia con Porcentaje 100,00 (line.rate). Ahora es
(factor vigente - 1) x 100, el mismo calculo de HED/HEN/HRN, con el factor de la fecha con que se paga (la de inicio del periodo del recibo). Cambia el XML, NO el pago ni el neto.

Valores a mano (parametros hr.rule.parameter, Ley 2466/2025): abril 2026 -> factores 2,05 / 1,80 / 2,55 / 2,15 -> 105 / 80 / 155 / 115; desde 2026-07-01 -> 2,15 / 1,90 / 2,65 / 2,25 ->
115 / 90 / 165 / 125. Un mes de documento con recibos antes y despues de la vigencia trae nodos SEPARADOS por porcentaje (la fusion concatena las listas)."""

from datetime import date

from odoo.addons.l10n_co_nomina_electronica.services import documento_merge as dm
from odoo.tests.common import TransactionCase, tagged

WAGE = 2310000.0
HORAS = 7.0
# xmlid del tipo de novedad, codigo de la regla, concepto del XML, factor antes y despues del 2026-07-01, porcentaje antes y despues
CONCEPTOS = (
    ('input_co_heddf', 'CO_HEDDF', 'HEDDF', 2.05, 2.15, '105.00', '115.00'),
    ('input_co_hrddf', 'CO_HRDDF', 'HRDDF', 1.80, 1.90, '80.00', '90.00'),
    ('input_co_hendf', 'CO_HENDF', 'HENDF', 2.55, 2.65, '155.00', '165.00'),
    ('input_co_hrndf', 'CO_HRNDF', 'HRNDF', 2.15, 2.25, '115.00', '125.00'),
)


@tagged('post_install', '-at_install')
class TestPorcentajeHorasDominicales(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Porcentaje Dominicales', 'l10n_co_ne_pago_dominical_mensual': 'dia_mas_recargo'})
        structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Porcentaje Dominicales', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.employee = cls.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Porcentaje Dominicales', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Porcentaje Dominicales',
            'employee_id': cls.employee.id, 'company_id': cls.company.id, 'structure_type_id': structure_type.id, 'wage': WAGE, 'date_start': date(2024, 3, 1), 'state': 'open'})

    def _quincena(self, desde, hasta):
        slip = self.env['hr.payslip'].create({
            'name': 'Quincena %s' % desde, 'employee_id': self.employee.id, 'contract_id': self.contract.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': desde, 'date_to': hasta})
        for xmlid, codigo, _concepto, _a, _d, _pa, _pd in CONCEPTOS:
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id, 'code': codigo, 'amount': HORAS, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id})
        slip.compute_sheet()
        return slip

    def _devengados(self, slip):
        devengados = {}
        slip._dev_horas_extra(slip._group_lines_by_concept(), devengados)
        return devengados

    def _porcentajes(self, slip):
        devengados = self._devengados(slip)
        return {concepto: devengados[concepto + 's'][0]['Porcentaje'] for _x, _c, concepto, *_resto in CONCEPTOS}

    def test_abril_2026_105_80_155_115(self):
        slip = self._quincena(date(2026, 4, 1), date(2026, 4, 15))
        self.assertEqual(self._porcentajes(slip), {'HEDDF': '105.00', 'HRDDF': '80.00', 'HENDF': '155.00', 'HRNDF': '115.00'})

    def test_desde_el_1_de_julio_de_2026_115_90_165_125(self):
        slip = self._quincena(date(2026, 7, 1), date(2026, 7, 15))
        self.assertEqual(self._porcentajes(slip), {'HEDDF': '115.00', 'HRDDF': '90.00', 'HENDF': '165.00', 'HRNDF': '125.00'})

    def test_la_quincena_16_a_30_de_junio_sigue_con_los_porcentajes_anteriores(self):
        """El corte es el 1-jul: la quincena que termina el 30-jun todavia es 105 / 80 / 155 / 115."""
        slip = self._quincena(date(2026, 6, 16), date(2026, 6, 30))
        self.assertEqual(self._porcentajes(slip), {'HEDDF': '105.00', 'HRDDF': '80.00', 'HENDF': '155.00', 'HRNDF': '115.00'})

    def test_porcentaje_y_pago_salen_del_mismo_factor(self):
        """Porcentaje y Pago no se contradicen: el factor implicito del pago (importe / valor de la hora) es 1 + Porcentaje / 100 a la fecha con que se paga."""
        for desde, hasta, columna in ((date(2026, 4, 1), date(2026, 4, 15), 3), (date(2026, 7, 1), date(2026, 7, 15), 4)):
            slip = self._quincena(desde, hasta)
            devengados = self._devengados(slip)
            valor_hora = WAGE / slip._rule_parameter('l10n_co_horas_mensuales', slip.date_from)
            for fila in CONCEPTOS:
                concepto, factor = fila[2], fila[columna]
                item = devengados[concepto + 's'][0]
                linea = slip.line_ids.filtered(lambda l, c=fila[1]: l.code == c)
                self.assertAlmostEqual(slip._rule_parameter('l10n_co_factor_%s' % concepto.lower(), slip.date_from), factor, places=4)
                self.assertAlmostEqual(1.0 + float(item['Porcentaje']) / 100.0, factor, places=4, msg=concepto)
                self.assertAlmostEqual(linea.amount, valor_hora * factor, delta=0.01, msg=concepto)
                self.assertEqual(item['Pago'], '%.2f' % linea.total)

    def test_un_solo_metodo_da_el_porcentaje_de_los_siete_conceptos_a_una_fecha(self):
        """``_ne_porcentaje_hora_en(concepto, fecha)`` es el unico calculo: los 7 conceptos, antes y desde la vigencia del 1-jul-2026, y el de una linea usa ``date_from`` del recibo."""
        slip = self._quincena(date(2026, 4, 1), date(2026, 4, 15))
        antes = {'HED': 25.0, 'HEN': 75.0, 'HRN': 35.0, 'HEDDF': 105.0, 'HRDDF': 80.0, 'HENDF': 155.0, 'HRNDF': 115.0}
        despues = {'HED': 25.0, 'HEN': 75.0, 'HRN': 35.0, 'HEDDF': 115.0, 'HRDDF': 90.0, 'HENDF': 165.0, 'HRNDF': 125.0}
        for concepto in antes:
            self.assertEqual(slip._ne_porcentaje_hora_en(concepto, date(2026, 6, 30)), antes[concepto], concepto)
            self.assertEqual(slip._ne_porcentaje_hora_en(concepto, date(2026, 7, 1)), despues[concepto], concepto)
        linea = slip.line_ids.filtered(lambda l: l.code == 'CO_HRDDF')
        self.assertEqual(slip._ne_porcentaje_hora('HRDDF', linea), slip._ne_porcentaje_hora_en('HRDDF', slip.date_from))

    def test_el_pago_no_cambia_solo_el_xml(self):
        """Los totales de las reglas son los de siempre (HRDDF a 1,80 x valor hora x 7 h en abril); el cambio es solo del Porcentaje del XML."""
        slip = self._quincena(date(2026, 4, 1), date(2026, 4, 15))
        valor_hora = WAGE / slip._rule_parameter('l10n_co_horas_mensuales', slip.date_from)
        total = slip.line_ids.filtered(lambda l: l.code == 'CO_HRDDF').total
        self.assertAlmostEqual(total, valor_hora * 1.80 * HORAS, delta=0.01)

    def test_los_otros_tres_conceptos_no_cambian(self):
        """HED, HEN y HRN conservan su porcentaje (25 / 75 / 35): el factor de HRN es solo el recargo."""
        slip = self.env['hr.payslip'].create({
            'name': 'Quincena otros', 'employee_id': self.employee.id, 'contract_id': self.contract.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': date(2026, 4, 1), 'date_to': date(2026, 4, 15)})
        for xmlid, codigo in (('input_co_hed', 'CO_HED'), ('input_co_hen', 'CO_HEN'), ('input_co_hrn', 'CO_HRN')):
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id, 'code': codigo, 'amount': HORAS, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id})
        slip.compute_sheet()
        devengados = self._devengados(slip)
        self.assertEqual(devengados['HEDs'][0]['Porcentaje'], '25.00')
        self.assertEqual(devengados['HENs'][0]['Porcentaje'], '75.00')
        self.assertEqual(devengados['HRNs'][0]['Porcentaje'], '35.00')

    def test_un_mes_de_documento_con_recibos_antes_y_despues_de_la_vigencia_trae_nodos_separados_por_porcentaje(self):
        """Documento de un mes con una quincena del 16 al 30 de junio (80 %) y otra del 1 al 15 de julio (90 %), p. ej. pagadas en el mismo mes: la fusion concatena las listas
        (cada elemento es un hecho distinto) y NO mezcla el porcentaje en un solo nodo ni lanza error (Concepto DIAN 13840 de 2025: varios porcentajes en un mes no impiden validar)."""
        junio = self._quincena(date(2026, 6, 16), date(2026, 6, 30))
        julio = self._quincena(date(2026, 7, 1), date(2026, 7, 15))
        recibos = []
        for slip in (junio, julio):
            recibos.append({
                'trabajador': {'NumeroDocumento': '1020304050', 'Sueldo': '2310000.00'}, 'pago': {'Forma': '1', 'Metodo': '10'}, 'empleador': {'NIT': '900123456'},
                'informacion_general': {'PeriodoNomina': '4', 'TipoXML': '102'}, 'numero_secuencia': {'Numero': 'NE1'},
                'devengados': dict({'Basico': {'DiasTrabajados': '15', 'SueldoTrabajado': '1155000.00'}}, **self._devengados(slip)),
                'deducciones': {'Salud': {'Porcentaje': '4.00', 'Deduccion': '46200.00'}, 'FondoPension': {'Porcentaje': '4.00', 'Deduccion': '46200.00'}},
                'devengados_total': 1155000.0, 'deducciones_total': 92400.0})
        documento = dm.fusionar_documento(
            recibos, fechas_pagos=['2026-06-30', '2026-07-15'], periodo={'FechaLiquidacionInicio': '2026-06-16', 'FechaLiquidacionFin': '2026-07-15'})
        for _xmlid, _codigo, concepto, _a, _d, antes, despues in CONCEPTOS:
            self.assertEqual([i['Porcentaje'] for i in documento['devengados'][concepto + 's']], [antes, despues], concepto)
            self.assertEqual([i['Cantidad'] for i in documento['devengados'][concepto + 's']], ['7.00', '7.00'], concepto)
