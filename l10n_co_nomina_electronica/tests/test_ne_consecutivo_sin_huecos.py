# -*- coding: utf-8 -*-
"""H-023: el consecutivo DIAN no se gasta si la generación falla.

1. Corrida en seco: un error de datos/XML sale ANTES de tomar un número.
2. Secuencias ``no_gap``: un fallo posterior (firma) devuelve el número con el rollback;
   con una secuencia ``standard`` el número se pierde (control negativo, demuestra que la
   elección de ``no_gap`` es la que cierra el hueco).
3. La migración conserva el siguiente número real al cambiar de implementación.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.models import hr_payslip as hr_payslip_mod


@tagged('post_install', '-at_install')
class TestNeConsecutivoSinHuecos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba Sin Huecos'})
        co = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Estructura Sin Huecos', 'country_id': co.id})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Sin Huecos', 'type_id': cls.structure_type.id})

    def _secuencia(self, implementation, code='l10n_co_nomina.electronica'):
        return self.env['ir.sequence'].create({
            'name': 'Prueba %s' % implementation, 'code': code, 'prefix': 'NE',
            'padding': 10, 'implementation': implementation, 'company_id': False})

    def _payslip(self, name):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'C %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 1800000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})

    def _parchear_hasta_firma(self, slip_cls, firma_falla=True):
        """Parches para llegar hasta la firma sin datos reales."""
        datos = {'informacion_general': {'FechaGen': '2026-10-01', 'HoraGen': '00:00:00-05:00'},
                 'totales': {}}
        return [
            patch.object(slip_cls, '_validate_ne_prerequisites', return_value=None),
            patch.object(slip_cls, '_collect_payslip_data', return_value=datos),
            patch.object(slip_cls, '_ne_cune_valores', return_value={
                'val_dev': '0.00', 'val_ded': '0.00', 'val_tol': '0.00', 'doc_trab': '1'}),
            patch.object(slip_cls, '_ne_insert_cune_and_qr', return_value=b'<x/>'),
            patch.object(hr_payslip_mod.nomina_xml_builder, 'build_nomina_individual_v2',
                         return_value=b'<x/>'),
            patch.object(hr_payslip_mod.cune_service, 'compute_cune',
                         return_value=('cune', 'raw')),
            patch.object(self.registry['res.company'], '_get_ne_certificate',
                         return_value=False),
            patch.object(hr_payslip_mod.xml_signer, 'load_from_certificate',
                         side_effect=UserError('falla de firma simulada')),
        ]

    def _generar_y_fallar(self, slip):
        parches = self._parchear_hasta_firma(type(slip))
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        with self.assertRaisesRegex(UserError, 'falla de firma simulada'):
            with self.env.cr.savepoint():
                slip.action_generate_ne_xml()

    def test_error_de_datos_no_toca_la_secuencia(self):
        seq = self._secuencia('no_gap')
        self.company.l10n_co_ne_sequence_id = seq
        slip = self._payslip('Datos')
        antes = seq.number_next_actual
        with patch.object(type(slip), '_validate_ne_prerequisites', return_value=None), \
                patch.object(type(slip), '_collect_payslip_data',
                             side_effect=UserError('dato faltante simulado')):
            with self.assertRaisesRegex(UserError, 'dato faltante simulado'):
                slip.action_generate_ne_xml()
        seq.invalidate_recordset()
        self.assertEqual(seq.number_next_actual, antes)
        self.assertFalse(slip.l10n_co_ne_consecutive)

    def test_corrida_en_seco_no_persiste_el_consecutivo_provisional(self):
        slip = self._payslip('Seco')
        datos = {'informacion_general': {}, 'totales': {}}
        with patch.object(type(slip), '_collect_payslip_data', return_value=datos), \
                patch.object(hr_payslip_mod.nomina_xml_builder,
                             'build_nomina_individual_v2', return_value=b'<x/>'):
            slip._ne_corrida_en_seco()
        self.assertFalse(slip.l10n_co_ne_consecutive)

    def test_no_gap_fallo_de_firma_no_deja_hueco(self):
        seq = self._secuencia('no_gap')
        self.company.l10n_co_ne_sequence_id = seq
        slip = self._payslip('NoGap')
        antes = seq.number_next_actual
        self._generar_y_fallar(slip)
        seq.invalidate_recordset()
        self.assertEqual(seq.number_next_actual, antes)
        self.assertEqual(seq.next_by_id(), 'NE%010d' % antes)

    def test_standard_fallo_de_firma_deja_hueco_control_negativo(self):
        seq = self._secuencia('standard')
        self.company.l10n_co_ne_sequence_id = seq
        slip = self._payslip('Standard')
        antes = seq.number_next_actual
        self._generar_y_fallar(slip)
        self.assertGreater(seq.number_next_actual, antes)

    def test_migracion_conserva_el_siguiente_numero(self):
        seq = self._secuencia('standard', code='l10n_co_nomina.ajuste')
        for _i in range(3):
            seq.next_by_id()
        esperado = seq.number_next_actual
        self.assertEqual(esperado, 4)
        self.env['ir.sequence']._l10n_co_ne_asegurar_sin_huecos()
        seq.invalidate_recordset()
        self.assertEqual(seq.implementation, 'no_gap')
        self.assertEqual(seq.number_next_actual, esperado)
        self.assertEqual(seq.next_by_id(), 'NE%010d' % esperado)

    def test_migracion_es_idempotente(self):
        seq = self._secuencia('no_gap', code='l10n_co_nomina.ajuste')
        seq.next_by_id()
        antes = seq.number_next_actual
        self.env['ir.sequence']._l10n_co_ne_asegurar_sin_huecos()
        seq.invalidate_recordset()
        self.assertEqual(seq.number_next_actual, antes)
