# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-167: la configuracion de retencion del anio existe (2026) y, si falta, es un error claro.

Antes, sin l10n.co.retefuente.uvt del anio las reglas de retencion se omitian en silencio y la
nomina salia sin retencion. Valores a mano (UVT 2026 = 52.374; Art. 383 ET; renta exenta 25 %):
prima 10.000.000 -> base 7.500.000 = 143,2008 UVT, tramo 19 % -> 9,1582 UVT x 52.374 = 479.649."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRetefuenteConfigAnio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'name': 'Compañía de Prueba Config Retención'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Retención', 'country_id': cls.env.ref('base.co').id})
        cls.est_prima = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')

    def _prima(self, wage, date_from, date_to, struct=None):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Prima Config %s' % date_from, 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Config', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Prima Config', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': (struct or self.est_prima).id,
            'date_from': date_from, 'date_to': date_to})

    def test_la_configuracion_2026_se_carga_con_los_datos(self):
        config = self.env.ref('l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2026')
        self.assertEqual(config.year, '2026')
        self.assertEqual(config.procedure, '1')
        self.assertEqual(config.uvt_value, 52374.0)

    def test_prima_sobre_el_umbral_en_2026_retiene_sin_configuracion_propia(self):
        """La compañía de prueba no tiene configuración propia: se usa la de los datos (2026)."""
        self.assertFalse(self.env['l10n.co.retefuente.uvt'].search(
            [('year', '=', '2026'), ('company_id', '=', self.company.id)]))
        slip = self._prima(20000000.0, date(2026, 7, 1), date(2026, 12, 31))
        slip.compute_sheet()
        rete = slip.line_ids.filtered(lambda l: l.code == 'CO_PRIMA_RETE')
        self.assertTrue(rete, 'La prima de 10.000.000 debe tener retención en 2026.')
        self.assertAlmostEqual(rete.total, -479649.0, delta=0.01)

    def test_sin_configuracion_del_anio_el_helper_falla_nombrando_anio_y_empresa(self):
        slip = self._prima(20000000.0, date(2027, 7, 1), date(2027, 12, 31))
        with self.assertRaises(UserError) as exc:
            slip._ne_retefuente_config()
        self.assertIn('2027', str(exc.exception))
        self.assertIn(self.company.name, str(exc.exception))

    def test_la_configuracion_propia_de_la_empresa_tiene_prioridad(self):
        propia = self.env['l10n.co.retefuente.uvt'].create({
            'year': '2026', 'company_id': self.company.id, 'procedure': '1'})
        slip = self._prima(3000000.0, date(2026, 7, 1), date(2026, 12, 31))
        self.assertEqual(slip._ne_retefuente_config(), propia)

    def test_en_liquidacion_el_anio_es_el_del_retiro(self):
        """date_from de la liquidacion es el inicio del contrato (2024): el anio de la
        configuracion sale de la fecha de retiro (2026)."""
        liq = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        slip = self._prima(3000000.0, date(2024, 3, 1), date(2026, 8, 15), struct=liq)
        self.assertEqual(
            slip._ne_retefuente_config(),
            self.env.ref('l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2026'))
