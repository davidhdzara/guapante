# -*- coding: utf-8 -*-
"""E-2 (doc 59 §19.1): aviso NO bloqueante cuando un recibo de la estructura general cubre exactamente 7 dias y el contrato no es
`weekly` (un semanal mal configurado se calcularia con dias comerciales: una semana que cruza un mes de 31 dias saldria de 6 dias).
Decision de David: el pago semanal cuenta 7 dias calendario (texto normativo NO VERIFICADO)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestAvisoPeriodicidad(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Aviso Periodicidad')
        cls.tipos = {
            clave: cls.env['hr.payroll.structure.type'].create({
                'name': 'Tipo aviso %s' % clave, 'country_id': cls.env.ref('base.co').id, 'default_schedule_pay': clave})
            for clave in ('weekly', 'monthly', 'semi-monthly')}
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, desde, hasta, periodicidad, struct=None):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Aviso %s' % self.n, 'company_id': self.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Aviso %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.tipos[periodicidad].id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Recibo Aviso %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': (struct or self.general).id, 'date_from': desde, 'date_to': hasta})

    def test_siete_dias_con_contrato_mensual_avisa_nombrando_al_empleado_y_como_corregir(self):
        recibo = self._recibo(date(2026, 3, 28), date(2026, 4, 3), 'monthly')
        aviso = recibo.l10n_co_ne_aviso_periodicidad
        self.assertTrue(aviso)
        for esperado in (recibo.employee_id.name, 'Semanal', 'Tipos de estructura', '31 días'):
            self.assertIn(esperado, aviso)

    def test_siete_dias_con_contrato_quincenal_tambien_avisa(self):
        self.assertTrue(self._recibo(date(2026, 3, 14), date(2026, 3, 20), 'semi-monthly').l10n_co_ne_aviso_periodicidad)

    def test_siete_dias_con_contrato_semanal_no_avisa(self):
        self.assertFalse(self._recibo(date(2026, 3, 28), date(2026, 4, 3), 'weekly').l10n_co_ne_aviso_periodicidad)

    def test_otras_duraciones_no_avisan(self):
        for desde, hasta in ((date(2026, 3, 1), date(2026, 3, 15)), (date(2026, 3, 1), date(2026, 3, 31)),
                             (date(2026, 3, 1), date(2026, 3, 6)), (date(2026, 3, 1), date(2026, 3, 8))):
            self.assertFalse(self._recibo(desde, hasta, 'monthly').l10n_co_ne_aviso_periodicidad, (desde, hasta))

    def test_otras_estructuras_y_companias_no_colombianas_no_avisan(self):
        liquidacion = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        self.assertFalse(self._recibo(date(2026, 3, 28), date(2026, 4, 3), 'monthly', struct=liquidacion)
                         .l10n_co_ne_aviso_periodicidad)

    def test_el_aviso_no_bloquea_calcular(self):
        recibo = self._recibo(date(2026, 3, 28), date(2026, 4, 3), 'monthly')
        recibo._ne_validar_duracion_periodo()          # la guarda E-4 no lo bloquea (7 dias <= 31)
        self.assertTrue(recibo.l10n_co_ne_aviso_periodicidad)
