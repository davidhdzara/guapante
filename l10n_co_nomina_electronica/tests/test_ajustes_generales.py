# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-161: valores generales de la empresa con excepción por empleado/contrato.

Nivel de verificación: lógica de los resolvers (empleado/contrato -> empresa), errores nombrados
y bloqueo al apagar "¿Maneja empleados en diferentes ciudades?". Valores esperados a mano."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAjustesGenerales(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'name': 'Compañía Ajustes Generales'})
        Partner = cls.env['res.partner']
        cls.comfama = Partner.create({'name': 'Comfama', 'l10n_co_entity_type': 'ccf'})
        cls.comfenalco = Partner.create({'name': 'Comfenalco', 'l10n_co_entity_type': 'ccf'})
        cls.empleado = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Ajustes', 'company_id': cls.company.id})
        cls.contrato = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Ajustes', 'employee_id': cls.empleado.id,
            'company_id': cls.company.id, 'wage': 2000000.0,
            'date_start': '2026-01-01', 'state': 'open'})

    # ── Caja de compensación ──────────────────────────────────────────
    def test_caja_general_sin_interruptor(self):
        self.company.l10n_co_pila_ccf_id = self.comfama
        self.empleado.l10n_co_pila_ccf_id = self.comfenalco  # se ignora
        self.assertEqual(self.empleado._ne_caja_compensacion(), self.comfama)

    def test_sin_caja_general_error_nombrado(self):
        with self.assertRaises(UserError) as exc:
            self.empleado._ne_caja_compensacion()
        self.assertIn(self.company.name, str(exc.exception))
        self.assertIn(self.empleado.name, str(exc.exception))

    def test_interruptor_encendido_usa_la_del_empleado(self):
        self.company.write({
            'l10n_co_pila_ccf_id': self.comfama, 'l10n_co_pila_ccf_por_empleado': True})
        self.empleado.l10n_co_pila_ccf_id = self.comfenalco
        self.assertEqual(self.empleado._ne_caja_compensacion(), self.comfenalco)

    def test_interruptor_encendido_sin_caja_del_empleado_no_cae_a_la_general(self):
        self.company.write({
            'l10n_co_pila_ccf_id': self.comfama, 'l10n_co_pila_ccf_por_empleado': True})
        with self.assertRaises(UserError) as exc:
            self.empleado._ne_caja_compensacion()
        self.assertIn(self.empleado.name, str(exc.exception))

    def test_apagar_con_cajas_distintas_se_bloquea_con_conteo(self):
        self.company.write({
            'l10n_co_pila_ccf_id': self.comfama, 'l10n_co_pila_ccf_por_empleado': True})
        self.empleado.l10n_co_pila_ccf_id = self.comfenalco
        with self.assertRaises(ValidationError) as exc:
            self.company.l10n_co_pila_ccf_por_empleado = False
        self.assertIn('1 empleado(s)', str(exc.exception))
        self.assertTrue(self.company.l10n_co_pila_ccf_por_empleado)

    def test_apagar_con_cajas_iguales_a_la_general_se_permite(self):
        self.company.write({
            'l10n_co_pila_ccf_id': self.comfama, 'l10n_co_pila_ccf_por_empleado': True})
        self.empleado.l10n_co_pila_ccf_id = self.comfama
        self.company.l10n_co_pila_ccf_por_empleado = False
        self.assertFalse(self.company.l10n_co_pila_ccf_por_empleado)

    # ── Medio de pago ─────────────────────────────────────────────────
    def test_medio_de_pago_empleado_gana_a_la_empresa(self):
        self.company.l10n_co_ne_payment_method = '10'
        self.assertEqual(self.empleado._ne_medio_pago(), '10')
        self.empleado.l10n_co_ne_payment_method = '1'
        self.assertEqual(self.empleado._ne_medio_pago(), '1')

    def test_medio_de_pago_sin_valor_error_nombrado(self):
        with self.assertRaises(UserError) as exc:
            self.empleado._ne_medio_pago()
        self.assertIn(self.empleado.name, str(exc.exception))

    # ── Clase de riesgo y centro de trabajo ───────────────────────────
    def test_clase_riesgo_general_y_excepcion_por_contrato(self):
        self.company.l10n_co_pila_clase_riesgo = '2'
        self.assertEqual(self.contrato._ne_clase_riesgo(), '2')
        self.contrato.l10n_co_pila_clase_riesgo = '4'
        self.assertEqual(self.contrato._ne_clase_riesgo(), '4')

    def test_clase_riesgo_sin_valor_error_nombrado(self):
        self.assertFalse(self.contrato.l10n_co_pila_clase_riesgo)  # sin default silencioso
        with self.assertRaises(UserError) as exc:
            self.contrato._ne_clase_riesgo()
        self.assertIn(self.empleado.name, str(exc.exception))

    def test_centro_trabajo_general_y_error(self):
        with self.assertRaises(UserError):
            self.contrato._ne_centro_trabajo()
        self.company.l10n_co_pila_centro_trabajo = 'CT-01'
        self.assertEqual(self.contrato._ne_centro_trabajo(), 'CT-01')
        self.contrato.l10n_co_pila_centro_trabajo = 'CT-02'
        self.assertEqual(self.contrato._ne_centro_trabajo(), 'CT-02')
