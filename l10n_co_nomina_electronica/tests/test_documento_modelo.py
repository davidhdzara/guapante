# -*- coding: utf-8 -*-
"""Etapa 1b (doc 53 §3, §16.2, §18.6): modelo l10n.co.ne.documento + intento, enlace del recibo, reglas multiempresa y
migracion legacy 1:1. Valores a mano."""

import importlib.util
import os
from datetime import date, datetime
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

CUNE_A = 'a' * 96
CUNE_B = 'b' * 96
RESPUESTA_RECHAZO = (
    '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><GetStatusZipResponse '
    'xmlns="http://wcf.dian.colombia"><GetStatusZipResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse">'
    '<b:DianResponse><b:ErrorMessage><c:string xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays">'
    'Regla: NIAE191a, Rechazo: Documento a Reemplazar no se encuentra recibido en la Base de Datos.</c:string></b:ErrorMessage>'
    '<b:IsValid>false</b:IsValid><b:StatusCode>99</b:StatusCode>'
    '<b:StatusDescription>Validación contiene errores en campos mandatorios.</b:StatusDescription>'
    '<b:StatusMessage>Documento con errores en campos mandatorios.</b:StatusMessage></b:DianResponse>'
    '</GetStatusZipResult></GetStatusZipResponse></s:Body></s:Envelope>')


@tagged('post_install', '-at_install')
class TestDocumentoModelo(TransactionCase):

    @classmethod
    def _crear_compania(cls, nombre):
        return cls.env['res.company'].create({
            'name': nombre, 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_tipo_aportante': '1',
            'l10n_co_pila_forma_presentacion': 'U', 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'})

    @classmethod
    def _crear_empleado(cls, nombre, company):
        return cls.env['hr.employee'].create({
            'name': nombre, 'company_id': company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls._crear_compania('Compañía Documento A')
        cls.company_b = cls._crear_compania('Compañía Documento B')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Estructura Documento', 'country_id': cls.env.ref('base.co').id})
        cls.employee = cls._crear_empleado('Empleado Documento', cls.company)
        cls.employee2 = cls._crear_empleado('Otro Empleado Documento', cls.company)
        cls.employee_b = cls._crear_empleado('Empleado Documento B', cls.company_b)
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Contrato Documento', 'employee_id': cls.employee.id, 'company_id': cls.company.id,
            'structure_type_id': cls.structure_type.id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        cls.contract2 = cls.env['hr.contract'].create({
            'name': 'Contrato Documento 2', 'employee_id': cls.employee2.id, 'company_id': cls.company.id,
            'structure_type_id': cls.structure_type.id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        cls.struct = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, mes, employee=None, **vals):
        employee = employee or self.employee
        contract = {self.employee: self.contract, self.employee2: self.contract2}.get(employee)
        datos = {
            'name': 'Recibo %s' % mes, 'employee_id': employee.id, 'company_id': employee.company_id.id,
            'struct_id': self.struct.id, 'date_from': date(2026, mes, 1), 'date_to': date(2026, mes, 28)}
        if contract:
            datos['contract_id'] = contract.id
        datos.update(vals)
        return self.env['hr.payslip'].create(datos)

    def _documento(self, mes=3, employee=None, **vals):
        datos = {'company_id': self.company.id, 'employee_id': (employee or self.employee).id,
                 'period': date(2026, mes, 1)}
        datos.update(vals)
        return self.env['l10n.co.ne.documento'].create(datos)

    def _intento(self, doc, estado, dt, **vals):
        datos = {'documento_id': doc.id, 'state': estado, 'datetime': dt}
        datos.update(vals)
        return self.env['l10n.co.ne.documento.intento'].create(datos)

    # ── Estado ───────────────────────────────────────────────────────
    def test_estado_sin_intentos_esta_vacio_y_la_etapa_dice_la_preparacion(self):
        doc = self._documento()
        self.assertFalse(doc.state)
        self.assertEqual(doc.etapa, 'draft')
        doc.etapa = 'ready'
        self.assertFalse(doc.state)                       # Borrador/Listo viven en la etapa, no en el estado DIAN

    def test_estado_es_el_del_ultimo_intento(self):
        doc = self._documento()
        self._intento(doc, 'invoice_pending', datetime(2026, 4, 1, 10, 0))
        self.assertEqual(doc.state, 'invoice_pending')
        self._intento(doc, 'invoice_accepted', datetime(2026, 4, 1, 11, 0))
        self.assertEqual(doc.state, 'invoice_accepted')
        # un intento anterior (por fecha) no cambia el estado
        self._intento(doc, 'invoice_rejected', datetime(2026, 4, 1, 9, 0))
        self.assertEqual(doc.state, 'invoice_accepted')

    def test_incierto_y_eliminado_son_banderas_y_no_cambian_el_estado_dian(self):
        doc = self._documento()
        self._intento(doc, 'invoice_pending', datetime(2026, 4, 1, 10, 0))
        doc.incierto = True
        self.assertEqual(doc.state, 'invoice_pending')    # lo que la DIAN sabe de verdad
        self._intento(doc, 'invoice_accepted', datetime(2026, 4, 1, 11, 0))
        doc.eliminado = True
        self.assertEqual(doc.state, 'invoice_accepted')

    def test_los_estados_son_solo_los_cuatro_nativos(self):
        self.assertEqual(
            {valor for valor, _etiqueta in self.env['l10n.co.ne.documento']._fields['state'].selection},
            {'invoice_sending_failed', 'invoice_pending', 'invoice_rejected', 'invoice_accepted'})

    # ── Migración de estados (.210, doc 53 §26b) ─────────────────────
    def _migracion_pre(self):
        ruta = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.3.0.210', 'pre-migration.py')
        spec = importlib.util.spec_from_file_location('pre_migracion_210', ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def _guardar_estado_viejo(self, doc, valor):
        self.env.flush_all()
        self.env.cr.execute('UPDATE l10n_co_ne_documento SET state = %s WHERE id = %s', (valor, doc.id))
        doc.invalidate_recordset(['state'])

    def test_migracion_de_estados_deja_solo_los_nativos_y_recalcula(self):
        incierto = self._documento(3, incierto=True)
        self._intento(incierto, 'invoice_pending', datetime(2026, 4, 1, 10, 0))
        eliminado = self._documento(4, eliminado=True)
        self._intento(eliminado, 'invoice_accepted', datetime(2026, 4, 1, 10, 0))
        listo = self._documento(5, etapa='ready')
        borrador = self._documento(6)
        aceptado = self._documento(7)
        self._intento(aceptado, 'invoice_accepted', datetime(2026, 4, 1, 10, 0))
        slip = self._recibo(3)
        slip.l10n_co_ne_documento_id = incierto
        for doc, viejo in ((incierto, 'uncertain'), (eliminado, 'eliminated'), (listo, 'ready'),
                           (borrador, 'draft'), (aceptado, 'invoice_accepted')):
            self._guardar_estado_viejo(doc, viejo)
        self.env.cr.execute('UPDATE hr_payslip SET l10n_co_ne_documento_state = %s WHERE id = %s',
                            ('uncertain', slip.id))
        self._migracion_pre().migrate(self.env.cr, '18.0.3.0.209')
        self.env.cr.execute('SELECT id, state FROM l10n_co_ne_documento WHERE id IN %s',
                            ((incierto.id, eliminado.id, listo.id, borrador.id, aceptado.id),))
        guardado = dict(self.env.cr.fetchall())
        self.assertIsNone(guardado[incierto.id])                       # los 4 valores retirados quedan vacíos
        self.assertIsNone(guardado[eliminado.id])
        self.assertIsNone(guardado[listo.id])
        self.assertIsNone(guardado[borrador.id])
        self.assertEqual(guardado[aceptado.id], 'invoice_accepted')    # un valor nativo no se toca
        self.env['l10n.co.ne.documento']._ne_recalcular_estado()
        self.env.invalidate_all()
        self.assertEqual((incierto.state, incierto.incierto), ('invoice_pending', True))
        self.assertEqual((eliminado.state, eliminado.eliminado), ('invoice_accepted', True))
        self.assertEqual((listo.state, listo.etapa), (False, 'ready'))
        self.assertFalse(borrador.state)
        self.assertEqual(aceptado.state, 'invoice_accepted')
        self.assertEqual(slip.l10n_co_ne_documento_state, 'invoice_pending')   # el related del recibo se recalcula

    def test_migracion_de_estados_es_idempotente_y_funciona_sin_filas(self):
        self._migracion_pre().migrate(self.env.cr, '18.0.3.0.209')
        self.env['l10n.co.ne.documento']._ne_recalcular_estado()
        doc = self._documento(3)
        self._intento(doc, 'invoice_pending', datetime(2026, 4, 1, 10, 0))
        self.env['l10n.co.ne.documento']._ne_recalcular_estado()
        self.env['l10n.co.ne.documento']._ne_recalcular_estado()
        self.assertEqual(doc.state, 'invoice_pending')

    def test_nombre_y_cola(self):
        doc = self._documento()
        self.assertEqual(doc.name, 'Empleado Documento 2026-03')
        self.assertFalse(doc.is_being_sent)
        doc.sending_data = {'intentos': 0}
        self.assertTrue(doc.is_being_sent)
        doc.alertas = [{'key': 'a', 'level': 'danger', 'message': 'Falta <b>x</b>'}]
        self.assertIn('Bloqueo: Falta &lt;b&gt;x&lt;/b&gt;', str(doc.alertas_texto))

    # ── Restricciones ────────────────────────────────────────────────
    def test_mes_debe_ser_primer_dia(self):
        with self.assertRaises(ValidationError):
            self._documento(period=date(2026, 3, 15))

    def test_un_original_por_empleado_y_mes(self):
        self._documento(3)
        with self.assertRaises(ValidationError):
            self._documento(3)
        self._documento(4)                       # otro mes: ok
        self._documento(3, employee=self.employee2)  # otro empleado: ok

    def test_ajuste_legacy_y_eliminado_no_cuentan_para_la_unicidad(self):
        original = self._documento(3)
        self._documento(3, is_adjustment=True, adjustment_type='1', adjustment_ref_cune=CUNE_A)
        self._documento(3, legacy=True)
        original.eliminado = True
        original.flush_recordset()   # el UPDATE pendiente debe llegar a la base antes del INSERT del nuevo
        self._documento(3)  # el eliminado ya no cuenta

    def test_ajuste_exige_cune_de_referencia(self):
        with self.assertRaises(ValidationError):
            self._documento(3, is_adjustment=True, adjustment_type='1')

    def test_compania_no_colombiana_no_tiene_documentos(self):
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            with self.assertRaises(ValidationError):
                self._documento(3)

    def test_recibo_de_otro_empleado_no_entra(self):
        doc = self._documento(3)
        otro = self._recibo(3, employee=self.employee2)
        with self.assertRaises(ValidationError):
            otro.l10n_co_ne_documento_id = doc

    def test_recibo_enlazado_refleja_el_estado(self):
        doc = self._documento(3)
        slip = self._recibo(3)
        slip.l10n_co_ne_documento_id = doc
        self.assertEqual(doc.payslip_ids, slip)
        self.assertFalse(slip.l10n_co_ne_documento_state)
        self._intento(doc, 'invoice_accepted', datetime(2026, 4, 1, 10, 0))
        self.assertEqual(slip.l10n_co_ne_documento_state, 'invoice_accepted')

    def test_borrar_solo_sin_historia(self):
        self._documento(3).unlink()
        con_intento = self._documento(4)
        self._intento(con_intento, 'invoice_pending', datetime(2026, 5, 1))
        with self.assertRaises(UserError):
            con_intento.unlink()
        with self.assertRaises(UserError):
            self._documento(5, legacy=True).unlink()

    def test_intento_motivo_desde_message_json(self):
        doc = self._documento(3)
        intento = self._intento(doc, 'invoice_rejected', datetime(2026, 4, 1), message_json={
            'status': 'Rechazado', 'detail': '', 'errors': ['Regla: NIAE191a, Rechazo: x'], 'status_code': '99',
            'is_valid': False, 'transport': False, 'fault': []})
        self.assertIn('Regla: NIAE191a', intento.message)
        self.assertIn('Regla: NIAE191a', doc.message)
        self.assertFalse(self._intento(doc, 'invoice_pending', datetime(2026, 3, 1)).show_button_get_status)
        self.assertTrue(self._intento(doc, 'invoice_pending', datetime(2026, 3, 2), zip_key='Z1').show_button_get_status)

    # ── Multiempresa ─────────────────────────────────────────────────
    def test_regla_multiempresa(self):
        doc_a = self._documento(3)
        doc_b = self.env['l10n.co.ne.documento'].create({
            'company_id': self.company_b.id, 'employee_id': self.employee_b.id, 'period': date(2026, 3, 1)})
        grupo = self.env.ref('hr_payroll.group_hr_payroll_manager')
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario Solo A', 'login': 'solo_a_documento', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [grupo.id, self.env.ref('base.group_user').id])]})
        visibles = self.env['l10n.co.ne.documento'].with_user(usuario).search(
            [('id', 'in', (doc_a | doc_b).ids)])
        self.assertEqual(visibles, doc_a)

    # ── Migración legacy ─────────────────────────────────────────────
    def _legacy(self, mes, estado, **vals):
        datos = {'l10n_co_ne_state': estado}
        datos.update(vals)
        return self._recibo(mes, **datos)

    def test_migracion_sin_filas(self):
        # no depende de la base: la base real ya tiene documentos legacy creados por la migracion .191
        self.assertFalse(self.env['l10n.co.ne.documento']._ne_migrar_legacy(self.env['hr.payslip']))
        borrador = self._recibo(4)   # sin historia: nada que migrar
        self.assertFalse(self.env['l10n.co.ne.documento']._ne_migrar_legacy(borrador))

    def test_migracion_aceptado_uno_a_uno_e_idempotente(self):
        # (doc 53 §28.6) un recibo con hab_set_id es historia de HABILITACIÓN y ya no se migra; este es un envío real
        slip = self._legacy(3, 'accepted', l10n_co_ne_cune=CUNE_A, l10n_co_ne_consecutive='NE1',
                            l10n_co_ne_zip_key='Z1')
        borrador = self._recibo(4)   # sin historia: no se migra
        creados = self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip | borrador)
        doc = slip.l10n_co_ne_documento_id
        self.assertEqual(creados, doc)
        self.assertFalse(borrador.l10n_co_ne_documento_id)
        self.assertTrue(doc.legacy)
        self.assertEqual((doc.cune, doc.consecutive, doc.zip_key, doc.hab_set_id), (CUNE_A, 'NE1', 'Z1', False))
        self.assertEqual(doc.period, date(2026, 3, 1))
        self.assertEqual(doc.state, 'invoice_accepted')
        self.assertEqual(doc.intento_ids.state, 'invoice_accepted')
        self.assertEqual(doc.intento_ids.identifier, CUNE_A)
        self.assertEqual(doc.intento_ids.numero, 'NE1')
        self.assertFalse(doc.intento_ids.certification_process)
        # no se quita nada del recibo
        self.assertEqual((slip.l10n_co_ne_state, slip.l10n_co_ne_cune, slip.l10n_co_ne_consecutive),
                         ('accepted', CUNE_A, 'NE1'))
        self.assertEqual(slip.l10n_co_ne_documento_state, 'invoice_accepted')
        # idempotente
        self.assertFalse(self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip | borrador))
        self.assertEqual(self.env['l10n.co.ne.documento'].search_count([('legacy', '=', True), ('cune', '=', CUNE_A)]), 1)

    def test_migracion_mapa_de_estados(self):
        # mes: (estado del recibo, estado DIAN del documento, etapa, incierto, eliminado)
        esperado = {2: ('generated', False, 'ready', False, False),
                    3: ('sent', 'invoice_pending', 'draft', False, False),
                    4: ('uncertain', 'invoice_pending', 'draft', True, False),
                    5: ('rejected', 'invoice_rejected', 'draft', False, False),
                    6: ('eliminated', 'invoice_accepted', 'draft', False, True)}
        recibos = {mes: self._legacy(mes, datos[0], l10n_co_ne_consecutive='NE%s' % mes)
                   for mes, datos in esperado.items()}
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(self.env['hr.payslip'].concat(*recibos.values()))
        for mes, (_estado, estado_doc, etapa, incierto, eliminado) in esperado.items():
            doc = recibos[mes].l10n_co_ne_documento_id
            self.assertEqual(
                (doc.state, doc.etapa, doc.incierto, doc.eliminado), (estado_doc, etapa, incierto, eliminado),
                'mes %s' % mes)
        self.assertFalse(recibos[2].l10n_co_ne_documento_id.intento_ids)   # generado: sin intento
        self.assertEqual(len(recibos[3].l10n_co_ne_documento_id.intento_ids), 1)

    def test_migracion_motivo_reparseado_de_la_respuesta_guardada(self):
        slip = self._legacy(3, 'rejected', l10n_co_ne_cune=CUNE_A, l10n_co_ne_dian_response=RESPUESTA_RECHAZO)
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip)
        intento = slip.l10n_co_ne_documento_id.intento_ids
        self.assertIn('Regla: NIAE191a', intento.message)
        self.assertEqual(intento.message_json['status_code'], '99')

    def test_migracion_respuesta_ilegible_no_bloquea(self):
        slip = self._legacy(3, 'sent', l10n_co_ne_cune=CUNE_A, l10n_co_ne_dian_response='esto no es xml')
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip)
        self.assertEqual(slip.l10n_co_ne_documento_id.intento_ids.message_json['status_code'], 'PARSE_ERROR')

    def test_migracion_nota_de_ajuste_apunta_a_su_original(self):
        original = self._legacy(3, 'accepted', l10n_co_ne_cune=CUNE_A, l10n_co_ne_consecutive='NE1')
        ajuste = self._legacy(4, 'accepted', l10n_co_ne_cune=CUNE_B, l10n_co_ne_consecutive='NA1',
                              l10n_co_ne_is_adjustment=True, l10n_co_ne_adjustment_type='2',
                              l10n_co_ne_adjustment_ref_cune=CUNE_A)
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(original | ajuste)
        doc_aj = ajuste.l10n_co_ne_documento_id
        self.assertEqual(doc_aj.parent_id, original.l10n_co_ne_documento_id)
        self.assertEqual(doc_aj.adjustment_type, '2')
        self.assertEqual(original.l10n_co_ne_documento_id.eliminado_por_id, doc_aj)

    def test_migracion_compania_no_colombiana_no_se_toca(self):
        slip = self._legacy(3, 'accepted', l10n_co_ne_cune=CUNE_A)
        with patch.object(type(self.company), '_ne_es_colombia', lambda s: False):
            self.assertFalse(self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip))
        self.assertFalse(slip.l10n_co_ne_documento_id)

    # ── Vistas ───────────────────────────────────────────────────────
    def test_vistas_del_documento_cargan(self):
        for tipo in ('form', 'list', 'search'):
            vista = self.env['l10n.co.ne.documento'].get_view(view_type=tipo)
            self.assertTrue(vista['arch'], tipo)
        recibo = self.env['hr.payslip'].get_view(view_type='form')
        self.assertIn('l10n_co_ne_documento_state', recibo['arch'])

    def test_recibo_tiene_una_sola_pestana_dian_con_el_grupo_del_documento(self):
        """Doc 53 §26: una sola pestaña DIAN en el recibo ("Nómina Electrónica"), sin la pestaña "DIAN" aparte; el
        documento mensual es un grupo de esa pestaña y el ciclo por recibo se oculta cuando el recibo tiene documento."""
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        self.assertEqual(len(arch.xpath("//page[@name='nomina_electronica']")), 1)
        self.assertFalse(arch.xpath("//page[@name='edi_documents']"))
        self.assertFalse(arch.xpath("//field[@name='l10n_co_ne_intento_ids']"))
        grupo = arch.xpath("//page[@name='nomina_electronica']//group[@string='Documento DIAN mensual']")
        self.assertEqual(len(grupo), 1)
        self.assertEqual(grupo[0].xpath(".//field[@name='l10n_co_ne_documento_state']")[0].get('widget'),
                         'account_document_state')
        for titulo in ('Estado DIAN', 'Solicitud DIAN', 'Respuesta DIAN'):
            oculto = arch.xpath("//page[@name='nomina_electronica']//group[@string='%s']" % titulo)[0].get('invisible')
            self.assertIn('l10n_co_ne_documento_id', oculto, titulo)

    def test_botones_del_ciclo_por_recibo_solo_se_ocultan_si_el_recibo_tiene_documento(self):
        """Un recibo SIN documento (ciclo viejo) sigue viendo sus botones; con documento no legacy (ciclo del recibo
        sin tocar, 'draft') se ocultan; un recibo con documento legacy (ya transmitido por recibo) los conserva."""
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        # (texto del botón, estado del recibo en el que se ve en el ciclo por recibo)
        botones = (('Generar XML', 'draft'), ('Regenerar XML', 'generated'),
                   ('Enviar a DIAN', 'generated'), ('Consultar Estado', 'sent'), ('Nota de Ajuste', 'accepted'),
                   ('Eliminar Documento', 'accepted'))
        for texto, estado in botones:
            nodo = arch.xpath("//header/button[@string='%s']" % texto)
            self.assertEqual(len(nodo), 1, texto)
            condicion = nodo[0].get('invisible')

            def oculto(documento, estado_recibo, _condicion=condicion):
                return bool(safe_eval(_condicion, {
                    'country_code': 'CO', 'state': 'done', 'l10n_co_ne_is_adjustment': False,
                    'l10n_co_ne_documento_id': documento, 'l10n_co_ne_state': estado_recibo,
                    'l10n_co_ne_en_produccion': False}))
            self.assertFalse(oculto(False, estado), '%s: recibo sin documento debe verlo' % texto)
            if estado == 'draft':
                self.assertTrue(oculto(1, 'draft'), '%s: recibo con documento no debe verlo' % texto)
            else:
                self.assertFalse(oculto(1, estado), '%s: ciclo viejo ya transmitido lo conserva' % texto)

    def test_enviar_y_procesar_abre_el_asistente_tambien_para_recibos_con_documento(self):
        """D-P (doc 53 §23.17): el botón del recibo pasa a abrir el asistente de documentos también si el recibo va
        en un documento (el bloqueo B ya impide el ciclo por recibo); sin documento conserva sus condiciones."""
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        nodo = arch.xpath("//header/button[@string='Enviar y Procesar']")
        self.assertEqual(len(nodo), 1)
        condicion = nodo[0].get('invisible')

        def oculto(documento, estado_recibo, estado_ne='draft'):
            return bool(safe_eval(condicion, {
                'country_code': 'CO', 'state': estado_recibo, 'l10n_co_ne_documento_id': documento,
                'l10n_co_ne_state': estado_ne, 'l10n_co_ne_en_produccion': False}))
        self.assertFalse(oculto(1, 'done'))                 # con documento: visible
        self.assertFalse(oculto(1, 'paid'))
        self.assertTrue(oculto(1, 'draft'))                 # un recibo sin confirmar nunca
        self.assertFalse(oculto(False, 'done', 'generated'))   # sin documento: igual que antes
        self.assertTrue(oculto(False, 'done', 'accepted'))
        self.assertTrue(oculto(False, 'paid', 'draft'))

    # ── Bloqueo del ciclo por recibo cuando el recibo va en un documento mensual (doc 53 §23.6) ──
    def test_el_ciclo_por_recibo_se_bloquea_si_el_recibo_va_en_un_documento_no_legacy(self):
        doc = self._documento(3)
        slip = self._recibo(3)
        slip.l10n_co_ne_documento_id = doc
        for metodo in ('action_generate_ne_xml', 'action_send_ne_dian', 'action_regenerate_ne_xml',
                       'action_check_dian_status', 'action_send_test_set', 'action_create_adjustment',
                       'action_create_elimination'):
            with self.subTest(metodo=metodo):
                with self.assertRaises(UserError) as exc:
                    getattr(slip, metodo)()
                self.assertIn(doc.display_name, str(exc.exception))      # nombra el documento, no un código
                self.assertIn('documento mensual', str(exc.exception))
        self.assertEqual(slip.l10n_co_ne_state, 'draft')                  # el bloqueo no deja el recibo a medias

    def test_un_recibo_sin_documento_no_se_bloquea(self):
        slip = self._recibo(3)
        self.assertFalse(slip.l10n_co_ne_documento_id)
        self.assertIsNone(slip._ne_bloquear_si_va_en_documento())
        # y su ciclo sigue siendo el de hoy: sin XML generado no hay nada que consultar (error propio, no el bloqueo)
        with self.assertRaises(UserError) as exc:
            slip.action_check_dian_status()
        self.assertNotIn('documento mensual', str(exc.exception))

    def test_un_recibo_con_documento_legacy_conserva_su_ciclo(self):
        slip = self._legacy(3, 'accepted', l10n_co_ne_cune=CUNE_A, l10n_co_ne_consecutive='NE1')
        self.env['l10n.co.ne.documento']._ne_migrar_legacy(slip)
        self.assertTrue(slip.l10n_co_ne_documento_id.legacy)
        self.assertIsNone(slip._ne_bloquear_si_va_en_documento())
        accion = slip.action_create_adjustment()                          # aceptado por recibo: abre el formulario
        self.assertEqual(accion['res_model'], 'hr.payslip')

    def test_menu_del_documento_cuelga_de_los_recibos(self):
        menu = self.env.ref('l10n_co_nomina_electronica.menu_l10n_co_ne_documento')
        self.assertEqual(menu.parent_id, self.env.ref('hr_payroll.menu_hr_payroll_payslips'))
        self.assertTrue(self.env.ref('l10n_co_nomina_electronica.menu_l10n_co_ne_documento'))
