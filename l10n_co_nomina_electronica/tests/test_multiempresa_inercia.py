# -*- coding: utf-8 -*-
"""El modulo no estorba a una compania de otro pais (Mexico) que comparta la base.

Escenario: compania A colombiana y compania M mexicana. Lo propio de la nomina colombiana
(validaciones/IBC/libranzas al confirmar, prellenado de nombre y sincronizacion de identificacion,
piso integral) solo corre para la colombiana. La estructura mexicana se crea en la prueba: no hace
falta instalar l10n_mx_hr_payroll.
"""

from datetime import date
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiempresaInercia(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.co = Company.create({
            'country_id': cls.env.ref('base.co').id, 'name': 'Empresa Colombiana Inercia',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN'})
        cls.mx = Company.create({
            'country_id': cls.env.ref('base.mx').id, 'name': 'Empresa Mexicana Inercia'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Inercia', 'country_id': cls.env.ref('base.mx').id})
        cls.struct_mx = cls.env['hr.payroll.structure'].create({
            'name': 'Estructura MX Prueba', 'type_id': cls.tipo.id,
            'country_id': cls.env.ref('base.mx').id})

    def _empleado(self, company, name='Juan Carlos García López', **vals):
        return self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': company.id, **vals})

    def _recibo(self, company, struct=None):
        empleado = self._empleado(company, name='Recibo %s' % company.name)
        contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato', 'employee_id': empleado.id, 'company_id': company.id,
            'structure_type_id': self.tipo.id, 'wage': 1000000.0,
            'date_start': date(2026, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Recibo', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': company.id, 'struct_id': (struct or self.struct_mx).id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})

    def test_la_compania_sabe_si_es_colombiana(self):
        self.assertTrue(self.co._ne_es_colombia())
        self.assertFalse(self.mx._ne_es_colombia())

    def test_solo_colombia_filtra_los_recibos(self):
        a, m = self._recibo(self.co), self._recibo(self.mx)
        self.assertEqual((a | m)._ne_solo_colombia(), a)

    def test_confirmar_un_recibo_mexicano_no_dispara_logica_colombiana(self):
        """Las guardas llaman a cada metodo sobre el subconjunto colombiano: para el recibo mexicano
        es un conjunto VACIO (no hace nada); para el colombiano, el recibo. Se registra sobre que
        registros se llamo (un mock cuenta tambien la llamada sobre un conjunto vacio)."""
        a, m = self._recibo(self.co), self._recibo(self.mx)
        patron = 'odoo.addons.hr_payroll.models.hr_payslip.HrPayslip.action_payslip_done'
        llamadas = {'ibc': [], 'libranzas': [], 'solape': []}

        def registrar(clave):
            def _llamada(recibos, *args, **kwargs):
                llamadas[clave].append(recibos)
            return _llamada

        with mock.patch(patron, return_value=True), \
                mock.patch.object(type(a), '_ne_refrescar_ibc_mensual', autospec=True,
                                  side_effect=registrar('ibc')), \
                mock.patch.object(type(a), '_ne_aplicar_libranzas', autospec=True,
                                  side_effect=registrar('libranzas')), \
                mock.patch.object(type(a), '_ne_validar_sin_solape', autospec=True,
                                  side_effect=registrar('solape')):
            m.action_payslip_done()
            for clave, recibos in llamadas.items():
                self.assertTrue(all(not r for r in recibos), clave)  # solo conjuntos vacios
            self.assertEqual(m.number or '', '')  # sin numeracion PRE-NOM
            a.action_payslip_done()
            for clave, recibos in llamadas.items():
                self.assertEqual(recibos[-1], a, clave)

    def test_empleado_mexicano_no_recibe_prellenado_de_nombre(self):
        mx = self._empleado(self.mx)
        co = self._empleado(self.co)
        self.assertFalse(mx.l10n_co_primer_nombre)
        self.assertEqual(co.l10n_co_primer_nombre, 'Juan')

    def test_la_identificacion_de_un_empleado_mexicano_no_se_sincroniza_con_el_vat(self):
        mx = self._empleado(self.mx, identification_id='XAXX010101000')
        self.assertFalse(mx.work_contact_id.vat)
        co = self._empleado(self.co, name='Ana Pérez', identification_id='1020304050')
        self.assertEqual(co.work_contact_id.vat, '1020304050')

    def test_cambiar_el_vat_del_contacto_mexicano_no_pisa_la_identificacion(self):
        mx = self._empleado(self.mx, identification_id='XAXX010101000')
        mx.work_contact_id.vat = 'XEXX010101000'  # RFC generico valido (base_vat lo valida)
        self.assertEqual(mx.identification_id, 'XAXX010101000')

    def test_contrato_integral_mexicano_con_salario_bajo_guarda(self):
        mx = self._empleado(self.mx)
        contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Integral MX', 'employee_id': mx.id, 'company_id': self.mx.id,
            'structure_type_id': self.tipo.id, 'wage': 1000000.0,
            'date_start': date(2026, 1, 1), 'state': 'open',
            'l10n_co_ne_integral_salary': True})
        self.assertTrue(contrato)
