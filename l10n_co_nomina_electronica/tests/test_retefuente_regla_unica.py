# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-02 (condicion del TL de una sola fuente): las entradas de la depuracion de la retencion (ingreso bruto, IBC de pension y salud, integral) y la llamada a ``compute_retefuente`` estaban copiadas en
CO_RETEFUENTE y en CO_EXENTO_PENSION_AFC (y con la regla del exceso serian tres copias). Ahora las arma UN metodo, ``HrPayslip._ne_resultado_retefuente(categories)``, y las 3 reglas lo llaman.

Esta prueba demuestra que la extraccion no cambia nada, en los 4 casos del doc 90 §5 (recibos mensuales de septiembre de 2026, UVT 52.374): la linea CO_RETEFUENTE de cada recibo es EXACTAMENTE lo que daba la copia
de antes (``compute_retefuente`` con ingreso = IBC = sueldo, un periodo limpio) y coincide con el valor a mano; CO_EXENTO_PENSION_AFC no cambia y CO_RETEFUENTE_EXCESO_LIMITE vale lo que el limite recorto."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

# (nombre, sueldo, pension voluntaria, AFC, dependientes) -> (retencion, exento vol+AFC, exceso del limite)  [valores a mano del doc 90 §5]
CASOS = (
    ('Caso 1', 8000000.0, 0.0, 0.0, False, 103449.0, 0.0, 0.0),
    ('Caso 2', 12000000.0, 2000000.0, 1600000.0, True, 313209.0, 3600000.0, 1944000.0),
    ('Caso 3', 30000000.0, 3000000.0, 2000000.0, False, 4569793.0, 5000000.0, 2599525.0),
    ('Caso 4', 30000000.0, 0.0, 0.0, False, 5361950.0, 0.0, 0.0),
)


@tagged('post_install', '-at_install')
class TestRetefuenteReglaUnica(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Retención Única'})
        cls.config = cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Retención', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        # Una deduccion fija calculada exige el contacto de su entidad en el contrato (.118/.285: «Entidad AFC», «Fondo Pensión Voluntaria»); sin el, ``compute_sheet`` da un UserError (N2 «db» del 23-nov).
        cls.entidad = cls.env['res.partner'].create({'name': 'Entidad AFC y Pensión Voluntaria de Prueba', 'l10n_co_entity_type': 'other'})

    def _recibo(self, nombre, sueldo, vol, afc, dependientes):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10',
            'l10n_co_ne_dependientes': dependientes})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato %s' % nombre,
            'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': sueldo, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_pension_voluntaria': vol, 'l10n_co_ne_afc': afc,
            'l10n_co_ne_afc_partner_id': self.entidad.id, 'l10n_co_ne_pension_voluntaria_partner_id': self.entidad.id})
        contrato.generate_work_entries(date(2026, 9, 1), date(2026, 9, 30))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % nombre, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        recibo.compute_sheet()
        return empleado, contrato, recibo

    def _total(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def test_la_extraccion_no_cambia_la_retencion_en_los_4_casos(self):
        for nombre, sueldo, vol, afc, dependientes, retencion, exento, exceso in CASOS:
            empleado, contrato, recibo = self._recibo(nombre, sueldo, vol, afc, dependientes)
            # lo que daba la copia de antes dentro de la regla: ingreso = IBC de pension = IBC de salud = sueldo en un periodo limpio
            antes = self.config.compute_retefuente(empleado, sueldo, sueldo, sueldo, self.company, contract=contrato, payslip=recibo)
            self.assertAlmostEqual(-self._total(recibo, 'CO_RETEFUENTE'), antes['retencion_pesos'], delta=0.01, msg=nombre)
            self.assertAlmostEqual(antes['retencion_pesos'], retencion, delta=1.0, msg=nombre)                      # y es el valor a mano
            self.assertAlmostEqual(self._total(recibo, 'CO_EXENTO_PENSION_AFC'), exento, delta=0.01, msg=nombre)    # el acumulador no cambia
            self.assertAlmostEqual(self._total(recibo, 'CO_RETEFUENTE_EXCESO_LIMITE'), exceso, delta=1.0, msg=nombre)

    def test_las_tres_reglas_usan_el_metodo_y_ninguna_arma_sus_propias_entradas(self):
        for codigo in ('CO_RETEFUENTE', 'CO_EXENTO_PENSION_AFC', 'CO_RETEFUENTE_EXCESO_LIMITE'):
            regla = self.env['hr.salary.rule'].search([('code', '=', codigo), ('struct_id', '=', self.nomina.id)], limit=1)
            self.assertTrue(regla, codigo)
            self.assertIn('_ne_resultado_retefuente', regla.amount_python_compute, codigo)
            self.assertNotIn('_rete_cfg.compute_retefuente', regla.amount_python_compute, codigo)      # la llamada copiada ya no esta en la regla
            self.assertNotIn("categories.get('DEV_SAL'", regla.amount_python_compute, codigo)
