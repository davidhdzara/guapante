# -*- coding: utf-8 -*-
"""Q-15 (.332): un recibo de una compañía colombiana solo admite un contrato de su empleado y de su compañía, también por RPC, importación o código."""

from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContratoDelRecibo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
                   'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'}
        cls.compania = cls.env['res.company'].create(dict(valores, name='Compañía Contrato del Recibo'))
        cls.otra = cls.env['res.company'].create(dict(valores, name='Compañía Ajena del Recibo'))
        cls.tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Tipo Contrato del Recibo', 'country_id': cls.env.ref('base.co').id})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _empleado(self, nombre, compania, tipo=None):
        empleado = self.env['hr.employee'].create({
            'name': nombre, 'company_id': compania.id, 'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato %s' % nombre, 'employee_id': empleado.id, 'company_id': compania.id, 'structure_type_id': (tipo or self.tipo).id,
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        return empleado, contrato

    def _recibo(self, empleado, contrato, estructura=None):
        return self.env['hr.payslip'].create({
            'name': 'Recibo de %s' % empleado.name, 'employee_id': empleado.id, 'contract_id': contrato.id, 'struct_id': (estructura or self.estructura).id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 15)})

    def test_el_contrato_propio_se_acepta(self):
        empleado, contrato = self._empleado('Propia', self.compania)
        recibo = self._recibo(empleado, contrato)
        self.assertEqual((recibo.contract_id, recibo.company_id), (contrato, self.compania))

    def test_el_contrato_de_otro_empleado_se_rechaza_al_crear_y_al_cambiar(self):
        empleado, contrato = self._empleado('Titular', self.compania)
        _ajeno, contrato_ajeno = self._empleado('Vecino', self.compania)
        with self.assertRaises(ValidationError) as error:
            self._recibo(empleado, contrato_ajeno)
        for texto in ('Recibo de Titular', 'Titular', 'Contrato Vecino'):
            self.assertIn(texto, error.exception.args[0])
        recibo = self._recibo(empleado, contrato)
        with self.assertRaisesRegex(ValidationError, 'otro empleado o de otra'):
            recibo.contract_id = contrato_ajeno

    def test_el_contrato_de_otra_compania_se_rechaza(self):
        empleado, contrato = self._empleado('Trasladada', self.compania)
        # Escrito por debajo del ORM: el caso (datos importados) no depende de lo que el nativo deje escribir en el contrato.
        self.env.cr.execute('UPDATE hr_contract SET company_id = %s WHERE id = %s', (self.otra.id, contrato.id))
        contrato.invalidate_recordset(['company_id'])
        with self.assertRaisesRegex(ValidationError, 'otro empleado o de otra'):
            self._recibo(empleado, contrato)

    def test_fuera_de_colombia_no_se_exige(self):
        mexico = self.env['res.company'].create({'name': 'Compañía Mexicana del Recibo', 'country_id': self.env.ref('base.mx').id})
        tipo = self.env['hr.payroll.structure.type'].create({'name': 'Tipo MX del Recibo', 'country_id': self.env.ref('base.mx').id})
        estructura = self.env['hr.payroll.structure'].create({'name': 'Estructura MX del Recibo', 'type_id': tipo.id})
        empleado, _contrato = self._empleado('Titular MX', mexico, tipo)
        _ajeno, contrato_ajeno = self._empleado('Vecino MX', mexico, tipo)
        recibo = self._recibo(empleado, contrato_ajeno, estructura)
        self.assertEqual(recibo.contract_id, contrato_ajeno)
