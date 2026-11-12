# -*- coding: utf-8 -*-
"""UX-02 (2026-10-11, decisión de David + Tech Lead), parte (b): el nodo <Pago>
ya no lee Banco/TipoCuenta/NumeroCuenta de 3 campos propios
(l10n_co_ne_bank_name/bank_account_type/bank_account, retirados) -- Banco y
NumeroCuenta salen de la Cuenta Bancaria nativa del empleado
(employee.bank_account_id, res.partner.bank). TipoCuenta se omite a propósito:
no existe campo nativo real para Ahorro/Corriente (acc_type nativo es formato
IBAN/banco, no eso; l10n_co_account_type viene de un módulo propio de InSoTech
fuera de este repo, David decidió no depender de él). El XSD V1.0.6 marca
Banco/TipoCuenta/NumeroCuenta como opcionales (solo Forma/Metodo son
obligatorios) -- Tech Lead confirmó contra el Anexo Técnico (NIE067) que la
regla de TipoCuenta es de notificación ("N"), no de rechazo ("R"): omitirlo no
rechaza el documento.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import nomina_xml_builder as builder
from lxml import etree


@tagged('post_install', '-at_install')
class TestPagoCuentaBancaria(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Pago Cuenta Bancaria',
        })
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Pago',
            'country_id': cls.env.ref('base.co').id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Pago',
            'type_id': cls.structure_type.id,
        })

    def _make_payslip(self, name, payment_method='10'):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name,
            'l10n_co_primer_nombre': 'Prueba',
            'l10n_co_primer_apellido': 'Fixture',
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': payment_method,
        })
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
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
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })

    def _set_bank_account(self, employee, bank_name, acc_number):
        bank = self.env['res.bank'].create({'name': bank_name})
        return self.env['res.partner.bank'].create({
            'acc_number': acc_number,
            'partner_id': employee.work_contact_id.id,
            'bank_id': bank.id,
        })

    def test_pago_con_cuenta_bancaria_lee_banco_y_numero(self):
        """Banco y NumeroCuenta salen de bank_account_id, no de campos propios.

        .91 (hallazgo propio al corregir test_leave_integration.py por el
        mismo patrón, Tech Lead): no se puede crear el empleado con
        payment_method='1' de una sola vez -- _check_bank_account_for_
        transfer() exige la cuenta YA puesta en esa misma escritura, y
        bank_account_id no existe todavía en el create() (requiere
        work_contact_id, que hr nativo crea DESPUÉS). Por eso se crea en
        Efectivo y se cambia a Transferencia junto con bank_account_id en un
        solo write()."""
        payslip = self._make_payslip('ConCuenta', payment_method='10')
        cuenta = self._set_bank_account(payslip.employee_id, 'Bancolombia', '00000000001')
        payslip.employee_id.write({
            'l10n_co_ne_payment_method': '1',
            'bank_account_id': cuenta.id,
        })

        pago = payslip._ne_pago()
        self.assertEqual(pago['Metodo'], '1')
        self.assertEqual(pago['Banco'], 'Bancolombia')
        self.assertEqual(pago['NumeroCuenta'], '00000000001')
        self.assertNotIn('TipoCuenta', pago)

    def test_pago_tipocuenta_no_sale_en_el_xml(self):
        """A nivel del XML serializado (no solo del dict): TipoCuenta no debe
        aparecer como atributo del nodo Pago, porque _ne_pago() nunca lo
        incluye (XSD V1.0.6: opcional, sin fuente nativa real)."""
        payslip = self._make_payslip('XmlSinTipoCuenta', payment_method='10')
        cuenta = self._set_bank_account(payslip.employee_id, 'Davivienda', '99887766')
        payslip.employee_id.write({
            'l10n_co_ne_payment_method': '1',
            'bank_account_id': cuenta.id,
        })

        pago = payslip._ne_pago()
        parent = etree.Element('Test')
        builder._add_pago(parent, pago)
        pago_el = parent.find('Pago')
        self.assertIsNotNone(pago_el)
        self.assertEqual(pago_el.get('Banco'), 'Davivienda')
        self.assertEqual(pago_el.get('NumeroCuenta'), '99887766')
        self.assertIsNone(pago_el.get('TipoCuenta'))

    def test_pago_sin_cuenta_y_efectivo_no_falla(self):
        """Sin bank_account_id pero con medio Efectivo: no debe fallar, Banco/
        NumeroCuenta simplemente vacíos."""
        payslip = self._make_payslip('SinCuentaEfectivo', payment_method='10')
        pago = payslip._ne_pago()
        self.assertEqual(pago['Metodo'], '10')
        self.assertEqual(pago['Banco'], '')
        self.assertEqual(pago['NumeroCuenta'], '')

    def test_pago_sin_cuenta_y_transferencia_levanta_usererror(self):
        """Medio Transferencia sin bank_account_id: UserError explícito al armar <Pago>,
        nunca un Banco/NumeroCuenta vacíos enviados a la DIAN.

        H-021 (2026-11-09): el empleado SÍ puede quedar así (ya no hay constraint en
        hr.employee), por eso se puede dejar por el ORM normal -- sin el UPDATE por SQL
        que hacía falta mientras el constraint bloqueaba este estado."""
        payslip = self._make_payslip('SinCuentaTransferencia', payment_method='10')
        payslip.employee_id.l10n_co_ne_payment_method = '1'
        with self.assertRaises(UserError) as exc:
            payslip._ne_pago()
        self.assertIn('SinCuentaTransferencia', str(exc.exception))

    def test_empleado_nuevo_transferencia_sin_cuenta_se_guarda(self):
        """H-021: crear un empleado con los valores por defecto (Transferencia, sin cuenta
        bancaria) NO debe fallar -- antes lo impedía el constraint de hr.employee."""
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Nuevo Sin Cuenta', 'company_id': self.company.id,
        })
        # .161: sin valor por defecto silencioso; el medio efectivo sale de la empresa.
        self.assertFalse(employee.l10n_co_ne_payment_method)
        self.assertFalse(employee.bank_account_id)
        # y cambiarlo después a Transferencia explícita tampoco falla
        employee.l10n_co_ne_payment_method = '10'
        employee.l10n_co_ne_payment_method = '1'

    def test_validar_cuenta_transferencia_exige_solo_con_transferencia(self):
        """La exigencia vive en hr.payslip._ne_validar_cuenta_transferencia(): con
        Transferencia y sin cuenta falla; con Efectivo, o con cuenta, no."""
        payslip = self._make_payslip('ValidaCuenta', payment_method='10')
        payslip._ne_validar_cuenta_transferencia()  # efectivo: no falla
        payslip.employee_id.l10n_co_ne_payment_method = '1'
        with self.assertRaises(UserError):
            payslip._ne_validar_cuenta_transferencia()
        cuenta = self._set_bank_account(payslip.employee_id, 'Banco Valida', '5544')
        payslip.employee_id.bank_account_id = cuenta.id
        payslip._ne_validar_cuenta_transferencia()  # con cuenta: no falla
