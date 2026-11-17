# -*- coding: utf-8 -*-
"""Los parametros normativos de la liquidacion se resuelven a la fecha de RETIRO (date_to).

El asistente crea el recibo con date_from = contract.date_start, que puede ser de anos atras:
resolver SMMLV/auxilio/topes a esa fecha usaba los valores del ingreso (o ningun valor, si el
contrato es anterior al primer parametro cargado, 2024-01-01). Estas pruebas reproducen la
forma real del recibo del asistente (date_from = inicio de contrato). Los valores esperados
se calculan a mano con los parametros de data/l10n_co_rule_parameters_data.xml:
SMMLV 2024 = 1.300.000, 2025 = 1.423.500, 2026 = 1.750.905; auxilio 2024 = 162.000,
2025 = 200.000, 2026 = 249.095; 360 dias/anio; intereses de cesantias 12%.
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

RETIRO = date(2026, 8, 15)
SMMLV_2026 = 1750905.0
AUX_2026 = 249095.0
ANIO = 360.0


@tagged('post_install', '-at_install')
class TestLiquidacionFechaParametros(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Fecha Parámetros Liquidación'})
        co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Fecha Parámetros', 'country_id': co_country.id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _liquidacion(self, name, wage, date_start, cause=False, contract_type='2'):
        """Recibo de liquidacion como lo crea el asistente: date_from = inicio de contrato."""
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date_start, 'state': 'open',
            'l10n_co_ne_contract_type': contract_type})
        vals = {
            'name': 'Liquidación %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': RETIRO}
        if cause:
            vals['l10n_co_ne_liquidacion_cause'] = cause
        return self.env['hr.payslip'].create(vals)

    def _total(self, slip, code):
        line = slip.line_ids.filtered(lambda l: l.code == code)
        self.assertTrue(line, 'La regla %s no generó línea.' % code)
        return line.total

    def _verificar_prestaciones_con_auxilio_2026(self, slip):
        slip.compute_sheet()
        base = 3000000.0 + AUX_2026
        # Días reales sin el 31 (modo 'real'): 227 reales - 4 treintaiunos (31-ene, mar, may, jul)
        # = 223; prima 1-jul a 15-ago: 46 reales - el 31-jul = 45.
        dias_ces = 223  # 1-ene-2026 a 15-ago-2026
        dias_prima = 45  # 1-jul-2026 a 15-ago-2026
        cesantias = base * dias_ces / ANIO
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_CESANTIAS'), cesantias, delta=0.01)
        self.assertAlmostEqual(
            self._total(slip, 'CO_LIQ_INT_CES'), cesantias * 0.12 * dias_ces / ANIO, delta=0.01)
        self.assertAlmostEqual(
            self._total(slip, 'CO_LIQ_PRIMA'), base * dias_prima / ANIO, delta=0.01)

    def test_ingreso_2024_auxilio_y_tope_de_2026_en_prima_y_cesantias(self):
        """$3.000.000 es > 2 SMMLV de 2024 (sin auxilio) pero <= 2 SMMLV de 2026 (con auxilio):
        con la fecha de ingreso se omitia el auxilio de la base."""
        slip = self._liquidacion('Ingreso2024', 3000000.0, date(2024, 3, 1))
        self._verificar_prestaciones_con_auxilio_2026(slip)

    def test_ingreso_2025_usa_el_auxilio_de_2026_no_el_de_2025(self):
        """Con la fecha de ingreso el auxilio era 200.000 (2025) en vez de 249.095."""
        slip = self._liquidacion('Ingreso2025', 3000000.0, date(2025, 2, 1))
        self._verificar_prestaciones_con_auxilio_2026(slip)

    def test_ingreso_anterior_a_2024_no_falla_por_falta_de_parametro(self):
        """No existe parametro SMMLV/auxilio vigente en 2023: antes el recibo no se podia
        calcular; ahora se resuelve a la fecha de retiro."""
        slip = self._liquidacion('Ingreso2023', 3000000.0, date(2023, 5, 1))
        self._verificar_prestaciones_con_auxilio_2026(slip)

    def test_indemnizacion_tope_10_smmlv_se_evalua_con_el_smmlv_del_retiro(self):
        """$15.000.000: >= 10 SMMLV de 2024 (13.000.000) pero < 10 SMMLV de 2026
        (17.509.050) -> tramo de menos de 10 SMMLV: 30 dias el primer anio + 20 por cada anio
        adicional (con el SMMLV del ingreso daba 20 + 15)."""
        slip = self._liquidacion(
            'Indemnizacion2024', 15000000.0, date(2024, 3, 1), cause='sin_justa_causa')
        slip.compute_sheet()
        # Días 1-mar-2024 a 15-ago-2026: 898 reales - 17 treintaiunos = 881.
        anos = 881 / ANIO
        valor_dia = 15000000.0 / 30
        esperado = valor_dia * 30 + valor_dia * 20 * (anos - 1)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_INDEMNIZACION'), esperado, delta=0.01)

    def test_piso_del_ibc_usa_el_smmlv_del_retiro(self):
        """El IBC consolidado (PILA/UGPP) toma piso y techo de _ne_ibc_limites: 1 SMMLV de la
        fecha de retiro, no del ingreso (1.300.000 en 2024)."""
        slip = self._liquidacion('PisoIbc', 1000000.0, date(2024, 3, 1))
        self.assertAlmostEqual(slip._ne_ibc_limites(0.0, 0.0, 0.0, 0.0, 30), SMMLV_2026, delta=0.01)

    def test_ninguna_regla_de_liquidacion_resuelve_parametros_con_date_from(self):
        """Guarda estatica: las reglas de la estructura de liquidacion no deben leer date_from
        (cubre tambien el anio de la configuracion de UVT de CO_LIQ_RETE)."""
        for rule in self.liquidacion.rule_ids:
            for codigo in (rule.condition_python or '', rule.amount_python_compute or ''):
                self.assertNotIn(
                    'date_from', codigo,
                    'La regla %s de liquidación usa date_from.' % rule.code)

    def test_fecha_de_parametros_solo_cambia_en_liquidacion(self):
        """Nomina mensual: date_from como siempre (el cambio de jornada del 15-jul-2026 cae
        dentro de un mismo recibo mensual); liquidacion: fecha de retiro."""
        liquidacion = self._liquidacion('FechaLiq', 3000000.0, date(2024, 3, 1))
        self.assertEqual(liquidacion._ne_fecha_parametros(), RETIRO)
        mensual = self.env['hr.payslip'].create({
            'name': 'Nómina mensual', 'employee_id': liquidacion.employee_id.id,
            'contract_id': liquidacion.contract_id.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31)})
        self.assertEqual(mensual._ne_fecha_parametros(), date(2026, 7, 1))
