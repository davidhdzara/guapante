# -*- coding: utf-8 -*-
"""H-F3-04 (doc 117, .332): TipoTrabajador y SubTipoTrabajador salen del contrato del recibo (el mismo dato del cálculo y de la PILA), no de la ficha actual, y no se reescriben en un contrato
con recibos confirmados."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTipoTrabajadorDelContrato(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compania = cls.env['res.company'].create({
            'name': 'Compañía Tipo Trabajador', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_tipo_aportante': '1',
            'l10n_co_pila_forma_presentacion': 'U', 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Tipo Trabajador', 'country_id': cls.env.ref('base.co').id})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Tramos', 'company_id': cls.compania.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})

    def _contrato(self, desde=date(2025, 1, 1), **valores):
        return self.env['hr.contract'].create(dict({
            'name': 'Contrato %s' % desde, 'employee_id': self.empleado.id, 'company_id': self.compania.id, 'structure_type_id': self.tipo.id,
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': desde, 'state': 'open'}, **valores))

    def _recibo(self, contrato, desde=date(2026, 3, 1), hasta=date(2026, 3, 15), estado=None):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Tramo', 'employee_id': self.empleado.id, 'contract_id': contrato.id, 'company_id': self.compania.id,
            'struct_id': self.estructura.id, 'date_from': desde, 'date_to': hasta})
        if estado:
            recibo.state = estado
        return recibo

    def test_las_listas_de_la_ficha_son_las_de_las_tablas_del_anexo(self):
        """.335: tablas 5.5.3 y 5.5.4 del Anexo V1.0 (copiadas a mano en la prueba)."""
        campos = self.env['hr.employee']._fields
        tipos = dict(campos['l10n_co_ne_worker_type'].selection)
        self.assertEqual(sorted(tipos), ['01', '02', '04', '12', '18', '19', '21', '22', '23', '30', '31', '47', '51', '54', '56', '58'])
        self.assertEqual(tipos['23'], '23 - Estudiantes aportes solo riesgos laborales')
        self.assertEqual(tipos['30'], '30 - Dependiente entidades o universidades públicas con régimen especial en salud')
        self.assertEqual([codigo for codigo, _etiqueta in campos['l10n_co_ne_worker_subtype'].selection], ['00', '01', '02'])
        self.assertEqual(sorted(self.env['hr.payslip']._NE_SUBTIPOS_TRABAJADOR_DIAN), ['00', '01'])          # el 02 se conserva en la ficha; el XML no lo admite

    def test_el_xml_toma_el_contrato_aunque_la_ficha_diga_otra_cosa(self):
        recibo = self._recibo(self._contrato(l10n_co_pila_tipo_cotizante='51'))
        self.assertEqual(recibo._ne_clave_segmento(), ('51', '00'))
        self.empleado.l10n_co_ne_worker_type = '22'
        self.assertEqual(recibo._ne_clave_segmento(), ('51', '00'))

    def test_un_cambio_a_mitad_de_mes_con_contrato_nuevo_da_dos_tramos(self):
        anterior = self._contrato(date_end=date(2026, 3, 15), state='close')
        primero = self._recibo(anterior, estado='done')
        nuevo = self._contrato(date(2026, 3, 16), l10n_co_pila_subtipo_cotizante='01')
        segundo = self._recibo(nuevo, date(2026, 3, 16), date(2026, 3, 31), estado='done')
        self.empleado.l10n_co_ne_worker_subtype = '01'          # la ficha ya muestra el valor nuevo: el primer tramo no cambia
        self.assertEqual((primero._ne_clave_segmento(), segundo._ne_clave_segmento()), (('01', '00'), ('01', '01')))
        self.compania.l10n_co_ne_segmentar_mes = True
        tramos = self.env['l10n.co.ne.documento']._ne_segmentar(self.compania, primero | segundo)
        self.assertEqual([t.ids for t in tramos], [primero.ids, segundo.ids])

    def test_con_recibos_confirmados_no_se_reescribe_el_tipo_ni_el_subtipo(self):
        contrato = self._contrato()
        recibo = self._recibo(contrato)
        contrato.l10n_co_pila_subtipo_cotizante = '01'          # recibo en borrador: se permite
        contrato.l10n_co_pila_subtipo_cotizante = '00'
        recibo.state = 'done'
        for cambio in ({'l10n_co_pila_subtipo_cotizante': '01'}, {'l10n_co_pila_tipo_cotizante': '51'}):
            with self.assertRaises(UserError) as error:
                contrato.write(cambio)
            for texto in ('Empleado Tramos', contrato.name, 'Recibo Tramo', 'cree un contrato nuevo'):
                self.assertIn(texto, error.exception.args[0])
        contrato.write({'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'wage': 3100000.0})       # sin cambio de tipo: pasa
        self.assertEqual((contrato.l10n_co_pila_tipo_cotizante, contrato.l10n_co_pila_subtipo_cotizante), ('01', '00'))

    def test_completar_un_dato_vacio_si_se_permite(self):
        contrato = self._contrato(state='draft', l10n_co_pila_subtipo_cotizante=False)
        recibo = self._recibo(contrato, estado='done')
        with self.assertRaisesRegex(UserError, 'Subtipo Cotizante'):
            recibo._ne_subtipo_trabajador()
        contrato.l10n_co_pila_subtipo_cotizante = '00'
        self.assertEqual(recibo._ne_subtipo_trabajador(), '00')

    def test_un_codigo_fuera_de_las_tablas_de_la_dian_es_un_error(self):
        independiente = self._recibo(self._contrato(l10n_co_pila_tipo_cotizante='03'))
        with self.assertRaisesRegex(UserError, '03, que no está en las tablas'):
            independiente._ne_tipo_trabajador()
        independiente.contract_id.write({'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '02'})
        with self.assertRaisesRegex(UserError, '02, que no está en las tablas'):
            independiente._ne_subtipo_trabajador()

    def test_el_recibo_avisa_cuando_la_ficha_difiere_del_contrato(self):
        recibo = self._recibo(self._contrato())
        self.assertFalse(recibo.l10n_co_ne_aviso_tipo_trabajador)
        self.empleado.l10n_co_ne_worker_subtype = '01'
        for texto in ('Empleado Tramos', 'Subtipo Trabajador', 'usa el del contrato'):
            self.assertIn(texto, recibo.l10n_co_ne_aviso_tipo_trabajador)
