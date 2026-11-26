# -*- coding: utf-8 -*-
"""Pieza .304 (doc 77, protección de consecutivos; diseño del TL aprobado el 22-nov). NO EJECUTADAS en Odoo al escribirlas; necesitan ``-u`` (campos ``numero`` y ``ambiente`` del
manifiesto, la vista SQL ``l10n.co.ne.consecutivo``, los dos controles manuales de la compañía y los permisos).

Qué se prueba:
- C: sin secuencia o sin prefijo es un error claro en las DOS rutas (recibo y documento mensual); ya no hay fallback silencioso.
- B: si la secuencia está por debajo del mayor número que YA VIAJÓ a la DIAN (aceptado, rechazado o pendiente; un envío fallido no cuenta), error que nombra la secuencia y el valor a
  poner; no se corrige sola. Por AMBIENTE (los números de habilitación no bloquean producción) y por PREFIJO (NE y NA aparte). El control manual de Ajustes («0 = sin control manual»).
- A: el número que daría la secuencia no puede estar ya asignado a otro documento; antes de enviar, no puede haber viajado ya en otro.
- F: un número rechazado no se reenvía.
- D: la lista «Consecutivos de nómina» (vista SQL) con el destino y el «reemplazado por» de cada número.
- El relleno de los manifiestos viejos (``numero`` y ``ambiente``) con contexto explícito, solo esos dos campos y una vez; la inmutabilidad sigue rechazando todo lo demás."""

import ast
import hashlib
import inspect
import textwrap
from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common_documento import DocumentoFixture


@tagged('post_install', '-at_install')
class TestConsecutivosProteccion(DocumentoFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture_documento('Compañía Consecutivos')
        cls.Consecutivo = cls.env['l10n.co.ne.consecutivo']
        cls.Manifiesto = cls.env['l10n.co.ne.exchange.document']
        cls.Intento = cls.env['l10n.co.ne.documento.intento']
        cls.secuencia_ne = cls.company.l10n_co_ne_sequence_id
        cls.secuencia_na = cls.env['ir.sequence'].search([('code', '=', 'l10n_co_nomina.ajuste'), ('company_id', '=', cls.company.id)], limit=1)

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self):
        """Un recibo de la compañía (los de un documento mensual de prueba)."""
        return self._documento(date(2024, 1, 1)).payslip_ids[:1]

    def _viaja(self, numero, ambiente='habilitacion', estado='accepted', recibo=None):
        """Un número que viajó en el ciclo por RECIBO: un manifiesto con su número y su ambiente, y el estado DIAN del recibo."""
        recibo = recibo or self._recibo()
        exchange = self.env['l10n.co.ne.exchange'].create({
            'company_id': self.company.id, 'operation': 'send_test_set', 'endpoint': 'https://example.test/%s' % ambiente})
        manifiesto = self.Manifiesto.create({
            'exchange_id': exchange.id, 'payslip_id': recibo.id, 'cune': 'CUNE-%s' % numero, 'file_name': 'ne_9001_%s.xml' % numero, 'numero': numero, 'ambiente': ambiente,
            'sha256': hashlib.sha256(numero.encode()).hexdigest()})
        recibo.write({'l10n_co_ne_consecutive': numero, 'l10n_co_ne_state': estado})
        return manifiesto

    def _intento(self, numero, estado='invoice_accepted', habilitacion=False, documento=None):
        """Un número que viajó en el ciclo del documento MENSUAL: un intento con su número, estado y ambiente."""
        documento = documento or self._documento(date(2024, 1, 1))
        return self.Intento.create({
            'documento_id': documento.id, 'state': estado, 'numero': numero, 'test_environment': habilitacion, 'certification_process': False})

    def _secuencia_en(self, secuencia, numero):
        secuencia.write({'number_next': numero})
        secuencia.invalidate_recordset(['number_next_actual', 'number_next'])

    def _produccion(self):
        patcher = patch.object(type(self.company), '_ne_en_produccion', lambda s: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ── C: sin fallback silencioso ───────────────────────────────────────────────────────────────────────────────────────────
    def test_01_sin_secuencia_o_sin_prefijo_es_un_error_claro_en_las_dos_rutas(self):
        recibo = self._recibo()
        documento = recibo.l10n_co_ne_documento_id
        self.company.l10n_co_ne_sequence_id = False
        with self.assertRaisesRegex(UserError, 'no tiene secuencia de nómina electrónica'):
            self.company._ne_tomar_consecutivo(False)
        with self.assertRaisesRegex(UserError, 'no tiene secuencia de nómina electrónica'):
            recibo._get_next_ne_consecutive()
        with self.assertRaisesRegex(UserError, 'no tiene secuencia de nómina electrónica'):
            documento._ne_siguiente_consecutivo()
        self.company.l10n_co_ne_sequence_id = self.secuencia_ne
        self.company.l10n_co_ne_payroll_prefix = ' '
        for ruta in (lambda: self.company._ne_tomar_consecutivo(False), recibo._get_next_ne_consecutive, documento._ne_siguiente_consecutivo, recibo._ne_expected_prefix):
            with self.assertRaisesRegex(UserError, 'no tiene prefijo'):
                ruta()

    def test_02_ya_no_existe_el_fallback_del_recibo(self):
        """El prefijo por defecto 'NE'/'NA' y el ``zfill(8)`` desaparecieron: la función del recibo no lee ni escribe más que la secuencia."""
        # Solo el CÓDIGO (sin la docstring, que cuenta lo que desapareció y nombra ``zfill``): N2 «cv», la docstring de la función lo traía.
        fuente = ''
        for funcion in (type(self.env['hr.payslip'])._get_next_ne_consecutive, type(self.env['hr.payslip'])._ne_expected_prefix):
            nodo = ast.parse(textwrap.dedent(inspect.getsource(funcion))).body[0]
            if nodo.body and isinstance(nodo.body[0], ast.Expr) and isinstance(nodo.body[0].value, ast.Constant) and isinstance(nodo.body[0].value.value, str):
                nodo.body = nodo.body[1:]
            fuente += ast.unparse(nodo)
        for resto in ('zfill', "or 'NE'", "or 'NA'", 'last_payslip', 'Fallback manual'):
            self.assertNotIn(resto, fuente)
        self.assertFalse(hasattr(self.env['l10n.co.ne.documento'], '_ne_siguiente_consecutivo_ajuste'), 'Una sola función: res.company._ne_tomar_consecutivo')

    def test_03_la_funcion_unica_toma_el_numero_de_la_secuencia_y_las_dos_rutas_la_usan(self):
        self._secuencia_en(self.secuencia_ne, 1)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000001')
        recibo = self._recibo()
        self.assertEqual(recibo._get_next_ne_consecutive(), 'NE0000000002')
        self.assertEqual(recibo.l10n_co_ne_documento_id._ne_siguiente_consecutivo(), 'NE0000000003')
        self._secuencia_en(self.secuencia_na, 1)
        self.assertEqual(self.company._ne_tomar_consecutivo(True), 'NA0000000001')

    # ── B: la secuencia por debajo de lo que ya viajó ─────────────────────────────────────────────────────────────────────────
    def test_04_la_secuencia_por_debajo_del_ultimo_numero_que_viajo_es_error_con_el_valor_a_poner_y_no_se_corrige_sola(self):
        self._viaja('NE0000000010')
        self._secuencia_en(self.secuencia_ne, 5)
        with self.assertRaisesRegex(UserError, 'va en 5') as contexto:
            self.company._ne_tomar_consecutivo(False)
        mensaje = str(contexto.exception)
        for texto in (self.secuencia_ne.name, self.secuencia_ne.code, '10', 'a 11', 'Consecutivos de nómina'):
            self.assertIn(texto, mensaje)
        self.assertEqual(self.secuencia_ne.number_next_actual, 5, 'No se corrige sola ni se consume')
        self._secuencia_en(self.secuencia_ne, 10)
        with self.assertRaisesRegex(UserError, 'va en 10'):
            self.company._ne_tomar_consecutivo(False)
        self._secuencia_en(self.secuencia_ne, 11)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000011')

    def test_05_un_numero_rechazado_tambien_cuenta_pero_un_envio_fallido_no(self):
        recibo = self._recibo()
        self._viaja('NE0000000020', estado='rejected', recibo=recibo)
        self._secuencia_en(self.secuencia_ne, 20)
        with self.assertRaisesRegex(UserError, 'va en 20'):
            self.company._ne_tomar_consecutivo(False)
        documento = self._documento(date(2024, 1, 1))
        self._intento('NE0000000040', estado='invoice_sending_failed', documento=documento)
        self._secuencia_en(self.secuencia_ne, 21)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000021', 'Un envío fallido no llegó a la DIAN: no cuenta')

    def test_06_el_control_es_por_ambiente_los_numeros_de_habilitacion_no_bloquean_produccion(self):
        self._viaja('NE0000000050', ambiente='habilitacion')
        self._secuencia_en(self.secuencia_ne, 1)
        self.assertEqual(self.company._ne_ambiente_consecutivos(), 'habilitacion', 'Premisa: la compañía de prueba está en habilitación')
        with self.assertRaisesRegex(UserError, 'va en 1'):
            self.company._ne_tomar_consecutivo(False)
        self._produccion()
        self.assertEqual(self.company._ne_ambiente_consecutivos(), 'produccion')
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000001', 'Habilitación hasta el 50: producción empieza en 1')

    def test_07_los_prefijos_son_aparte_una_nota_de_ajuste_no_bloquea_la_nomina(self):
        self._viaja('NA0000000030', recibo=self._recibo())
        self._secuencia_en(self.secuencia_ne, 1)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000001')
        self._secuencia_en(self.secuencia_na, 5)
        with self.assertRaisesRegex(UserError, 'va en 5'):
            self.company._ne_tomar_consecutivo(True)

    def test_08_el_documento_mensual_cuenta_por_sus_intentos_en_produccion(self):
        self._produccion()
        self._intento('NE0000000012', habilitacion=False)
        self._secuencia_en(self.secuencia_ne, 12)
        with self.assertRaisesRegex(UserError, 'va en 12'):
            self.company._ne_tomar_consecutivo(False)
        self._intento('NE0000000090', habilitacion=True)
        self._secuencia_en(self.secuencia_ne, 13)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000013', 'Un intento de habilitación no cuenta en producción')

    def test_09_el_control_manual_de_ajustes_y_su_ayuda_dice_que_cero_es_sin_control(self):
        self.assertIn('0 = sin control manual', self.env['res.company']._fields['l10n_co_ne_ultimo_nomina'].help)
        self.assertIn('0 = sin control manual', self.env['res.company']._fields['l10n_co_ne_ultimo_ajuste'].help)
        self._secuencia_en(self.secuencia_ne, 5)
        self.assertEqual(self.company.l10n_co_ne_ultimo_nomina, 0)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000005', '0: sin control manual')
        self.company.l10n_co_ne_ultimo_nomina = 30
        with self.assertRaisesRegex(UserError, 'va en 6') as contexto:
            self.company._ne_tomar_consecutivo(False)
        self.assertIn('a 31', str(contexto.exception))
        self._secuencia_en(self.secuencia_ne, 31)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000031')
        self.company.l10n_co_ne_ultimo_ajuste = 7
        self._secuencia_en(self.secuencia_na, 3)
        with self.assertRaisesRegex(UserError, 'va en 3'):
            self.company._ne_tomar_consecutivo(True)

    # ── A: número ya asignado y número ya enviado ────────────────────────────────────────────────────────────────────────────
    def test_10_un_numero_ya_asignado_a_otro_documento_es_error_claro_con_el_siguiente_disponible(self):
        recibo = self._recibo()
        recibo.l10n_co_ne_consecutive = 'NE0000000007'                    # asignado, todavía no viajó
        self._secuencia_en(self.secuencia_ne, 7)
        with self.assertRaisesRegex(UserError, 'ya está asignado') as contexto:
            self.company._ne_tomar_consecutivo(False)
        self.assertIn('NE0000000008', str(contexto.exception), 'El siguiente disponible')
        self._secuencia_en(self.secuencia_ne, 8)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000008')

    def test_11_los_pre_nom_temporales_no_cuentan(self):
        recibo = self._recibo()
        recibo.l10n_co_ne_consecutive = 'PRE-NOM0000000100'
        self._secuencia_en(self.secuencia_ne, 1)
        self.assertEqual(self.company._ne_mayor_consecutivo_asignado(False), 0)
        self.assertEqual(self.company._ne_tomar_consecutivo(False), 'NE0000000001')

    def test_12_antes_de_enviar_el_numero_no_pudo_haber_viajado_en_otro_documento_y_el_mismo_no_cuenta_contra_si(self):
        propio = self._recibo()
        self._viaja('NE0000000060', estado='sent', recibo=propio)
        propio._ne_exigir_numero_no_reusado()                              # su propio envío no es un «otro»
        # Un número no puede estar en dos recibos de la compañía a la vez (restricción única): el escenario real es que el recibo se REGENERÓ con otro número (el 60 queda en su
        # manifiesto) y otro recibo recibe el 60 de una secuencia reiniciada.
        propio.l10n_co_ne_consecutive = 'NE0000000062'
        self.env.flush_all()
        otro = self._recibo()
        otro.l10n_co_ne_consecutive = 'NE0000000060'
        with self.assertRaisesRegex(UserError, 'ya viajó a la DIAN'):
            otro._ne_exigir_numero_no_reusado()
        documento = self._documento(date(2024, 1, 1))
        with self.assertRaisesRegex(UserError, 'ya viajó a la DIAN'):
            self.company._ne_exigir_numero_sin_viajar('NE0000000060', False, documento=documento)
        self.company._ne_exigir_numero_sin_viajar('NE0000000061', False, documento=documento)

    # ── F: no se reutiliza el número rechazado ───────────────────────────────────────────────────────────────────────────────
    def test_13_un_numero_rechazado_no_se_reenvia_se_regenera_con_uno_nuevo(self):
        recibo = self._recibo()
        self._viaja('NE0000000070', estado='rejected', recibo=recibo)
        with self.assertRaisesRegex(UserError, 'no se reenvía') as contexto:
            recibo._ne_exigir_numero_no_reusado()
        self.assertIn('Regenerar XML', str(contexto.exception))
        recibo.l10n_co_ne_consecutive = 'NE0000000071'                     # regenerado: número nuevo
        recibo._ne_exigir_numero_no_reusado()

    # ── D: la lista de consecutivos ──────────────────────────────────────────────────────────────────────────────────────────
    def test_14_la_lista_trae_cada_numero_con_su_destino_y_el_reemplazo_del_rechazado(self):
        recibo = self._recibo()
        self._viaja('NE0000000080', estado='rejected', recibo=recibo)
        self._viaja('NE0000000081', estado='accepted', recibo=recibo)
        filas = self.Consecutivo.search([('company_id', '=', self.company.id), ('payslip_id', '=', recibo.id)], order='valor')
        self.assertEqual(filas.mapped('numero'), ['NE0000000080', 'NE0000000081'])
        self.assertEqual(filas.mapped('estado'), ['rechazado', 'aceptado'])
        self.assertEqual(filas[0].reemplazado_por, 'NE0000000081')
        self.assertFalse(filas[1].reemplazado_por)
        self.assertEqual(filas.mapped('valor'), [80, 81])
        self.assertEqual(set(filas.mapped('prefijo')), {'NE'})
        self.assertEqual(set(filas.mapped('origen')), {'recibo'})
        documento = self._documento(date(2024, 1, 1))
        rechazado = self._intento('NE0000000090', estado='invoice_rejected', documento=documento)
        aceptado = self._intento('NE0000000091', estado='invoice_accepted', documento=documento)
        filas = self.Consecutivo.search([('documento_id', '=', documento.id)], order='valor')
        self.assertEqual(filas.mapped('estado'), ['rechazado', 'aceptado'])
        self.assertEqual(filas[0].reemplazado_por, 'NE0000000091')
        self.assertEqual(set(filas.mapped('origen')), {'documento'})
        self.assertEqual(set(filas.mapped('ambiente')), {'produccion'})
        self.assertTrue(rechazado and aceptado)

    def test_15_la_lista_y_los_contadores_son_de_solo_lectura_y_de_la_compania(self):
        self._viaja('NE0000000100', estado='accepted')
        self._viaja('NE0000000101', estado='rejected')
        self.company.invalidate_recordset(['l10n_co_ne_consecutivos_usados', 'l10n_co_ne_consecutivos_rechazados'])
        self.assertEqual(self.company.l10n_co_ne_consecutivos_usados, 2)
        self.assertEqual(self.company.l10n_co_ne_consecutivos_rechazados, 1)
        fila = self.Consecutivo.search([('company_id', '=', self.company.id)], limit=1)
        propio = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'gerente_consecutivos', 'login': 'gerente_consecutivos', 'email': 'gerente_consecutivos@example.com', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr_payroll.group_hr_payroll_manager').id])]})
        self.assertTrue(self.Consecutivo.with_user(propio).search([('id', '=', fila.id)]), 'El gerente de nómina de la compañía los lee')
        with self.assertRaises(AccessError):                              # sin permiso de escritura (1,0,0,0)
            fila.with_user(propio).write({'numero': 'X'})
        otra = self.env['res.company'].create({
            'name': 'Otra compañía consecutivos', 'country_id': self.env.ref('base.co').id, 'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U'})
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'oficial_consecutivos', 'login': 'oficial_consecutivos', 'email': 'oficial_consecutivos@example.com', 'company_id': otra.id, 'company_ids': [(6, 0, otra.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr_payroll.group_hr_payroll_manager').id])]})
        self.assertFalse(self.Consecutivo.with_user(usuario).search([('company_id', '=', self.company.id)]), 'Una compañía no ve los consecutivos de otra')

    # ── el manifiesto: relleno de los viejos e inmutabilidad ─────────────────────────────────────────────────────────────────
    def _manifiesto_viejo(self, file_name, endpoint='https://example.test/habilitacion'):
        exchange = self.env['l10n.co.ne.exchange'].create({'company_id': self.company.id, 'operation': 'send_test_set', 'endpoint': endpoint})
        return self.Manifiesto.create({
            'exchange_id': exchange.id, 'payslip_id': self._recibo().id, 'cune': 'CUNE-%s' % file_name, 'file_name': file_name, 'sha256': hashlib.sha256(file_name.encode()).hexdigest()})

    def test_16_la_funcion_de_datos_rellena_numero_y_ambiente_de_los_manifiestos_viejos_una_sola_vez(self):
        hab = self._manifiesto_viejo('ne_9001234567_NE0000000042.xml')
        prod = self._manifiesto_viejo('ne_9001234567_NE0000000043.xml', endpoint=self.company._ne_dian_endpoint('1'))
        raro = self._manifiesto_viejo('sin_numero.xml')
        self.assertFalse(hab.numero or hab.ambiente)
        self.Manifiesto._ne_rellenar_numero_y_ambiente()
        self.assertEqual((hab.numero, hab.ambiente), ('NE0000000042', 'habilitacion'))
        self.assertEqual((prod.numero, prod.ambiente), ('NE0000000043', 'produccion'))
        self.assertFalse(raro.numero, 'Sin número en el nombre no se inventa')
        self.assertEqual(raro.ambiente, 'habilitacion')
        self.Manifiesto._ne_rellenar_numero_y_ambiente()                  # idempotente: no vuelve a escribir lo que ya tiene
        self.assertEqual(hab.numero, 'NE0000000042')

    def test_17_la_inmutabilidad_sigue_rechazando_todo_salvo_el_relleno_de_esos_dos_campos_una_vez(self):
        manifiesto = self._manifiesto_viejo('ne_9001234567_NE0000000044.xml')
        for valores in ({'cune': 'otro'}, {'numero': 'NE1'}, {'file_name': 'x.xml'}, {'sha256': 'x'}, {'numero': 'NE1', 'cune': 'otro'}):
            with self.assertRaises(AccessError):
                manifiesto.write(valores)                                  # sin el contexto explícito: nada
        relleno = manifiesto.with_context(ne_rellenar_numero_ambiente=True)
        for valores in ({'cune': 'otro'}, {'numero': 'NE1', 'cune': 'otro'}, {'signed_xml': False}, {}):
            with self.assertRaises(AccessError):
                relleno.write(valores)                                     # con el contexto, cualquier otro campo
        relleno.write({'numero': 'NE0000000044', 'ambiente': 'habilitacion'})
        self.assertEqual((manifiesto.numero, manifiesto.ambiente), ('NE0000000044', 'habilitacion'))
        for valores in ({'numero': 'NE0000000099'}, {'ambiente': 'produccion'}):
            with self.assertRaises(AccessError):
                relleno.write(valores)                                     # una sola vez: ya los tiene
        with self.assertRaises(AccessError):
            manifiesto.unlink()

    def test_18_un_manifiesto_nuevo_nace_con_su_numero_y_su_ambiente(self):
        recibo = self._recibo()
        recibo.l10n_co_ne_consecutive = 'NE0000000046'
        exchange = self.env['l10n.co.ne.exchange'].create_exchange(
            self.company, 'send_test_set', 'https://example.test/hab', {'ZipKey': 'z'}, recibo, manifest=[{'payslip': recibo, 'filename': 'ne_9001_NE0000000046.xml', 'xml': b'<x/>'}])
        manifiesto = exchange.document_ids
        self.assertEqual((manifiesto.numero, manifiesto.ambiente), ('NE0000000046', 'habilitacion'))

    # ── la vista y los datos ─────────────────────────────────────────────────────────────────────────────────────────────────
    def test_19_la_lista_es_de_solo_lectura_y_tiene_su_menu(self):
        arch = etree.fromstring(self.env.ref('l10n_co_nomina_electronica.view_l10n_co_ne_consecutivo_list').arch_db.encode('utf-8'))
        raiz = arch.xpath('/list')[0] if arch.tag == 'list' else arch
        for atributo in ('create', 'edit', 'delete'):
            self.assertEqual(raiz.get(atributo), '0', atributo)
        self.assertFalse(arch.xpath('//*[@style]'), 'Sin estilos propios')
        menu = self.env.ref('l10n_co_nomina_electronica.menu_l10n_co_ne_consecutivo')
        self.assertEqual(menu.name, 'Consecutivos de nómina')
        self.assertEqual(self.env.ref('l10n_co_nomina_electronica.action_l10n_co_ne_consecutivo').res_model, 'l10n.co.ne.consecutivo')
        self.assertFalse(self.env['ir.model.access'].search([
            ('model_id.model', '=', 'l10n.co.ne.consecutivo'), '|', '|', ('perm_write', '=', True), ('perm_create', '=', True), ('perm_unlink', '=', True)]))
