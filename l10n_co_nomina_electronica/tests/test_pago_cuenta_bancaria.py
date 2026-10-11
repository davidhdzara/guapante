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

from odoo.exceptions import ValidationError, UserError
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_co_nomina_electronica.services import nomina_xml_builder as builder
from lxml import etree


class TestPagoCuentaBancaria(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
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
        employee = self.env['hr.employee'].create({
            'name': name,
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': payment_method,
        })
        contract = self.env['hr.contract'].create({
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
        """Medio Transferencia sin bank_account_id: UserError explícito, nunca
        un Banco/NumeroCuenta vacíos enviados a la DIAN.

        .91 (hallazgo propio): esta combinación ya no se puede alcanzar por un
        write()/create() normal -- el constraint del empleado (_check_bank_
        account_for_transfer, el MISMO caso que prueba test_constraint_bank_
        account_id_para_transferencia) la bloquea primero con ValidationError.
        El UserError de _ne_pago() es una segunda defensa, pensada para un
        estado que pudo quedar inconsistente antes de que ese constraint
        existiera (ej. datos migrados) -- para poder probarlo hay que forzar
        ese estado por SQL directo, igual que test_dian_status_recheck.py
        hace con write_date, nunca alcanzable desde el ORM."""
        payslip = self._make_payslip('SinCuentaTransferencia', payment_method='10')
        self.env.cr.execute(
            "UPDATE hr_employee SET l10n_co_ne_payment_method = '1' WHERE id = %s",
            (payslip.employee_id.id,),
        )
        payslip.employee_id.invalidate_recordset(['l10n_co_ne_payment_method'])
        with self.assertRaises(UserError) as exc:
            payslip._ne_pago()
        self.assertIn('SinCuentaTransferencia', str(exc.exception))

    def test_constraint_bank_account_id_para_transferencia(self):
        """El constraint del empleado (ajustado en UX-02) mira bank_account_id,
        no el campo propio retirado."""
        payslip = self._make_payslip('ConstraintCuenta', payment_method='10')
        employee = payslip.employee_id
        with self.assertRaises(ValidationError):
            employee.l10n_co_ne_payment_method = '1'
