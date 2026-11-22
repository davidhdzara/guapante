# -*- coding: utf-8 -*-
"""Etapa 2b (doc 53 §17.2, §20.2, §22.2): agrupar recibos por empleado y mes de pago, crear/reutilizar el documento,
alertas persistidas y plazo de transmision (10 dias habiles, D10). Valores a mano."""

from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDocumentoPreparar(TransactionCase):

    @classmethod
    def _calendario(cls, nombre, dias):
        asistencias = []
        for dia in dias:
            asistencias += [
                (0, 0, {'name': 'M%s' % dia, 'dayofweek': str(dia), 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'T%s' % dia, 'dayofweek': str(dia), 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'})]
        return cls.env['resource.calendar'].create({
            'name': nombre, 'company_id': cls.company.id, 'tz': 'America/Bogota', 'attendance_ids': asistencias})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía Preparar', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        cls.lun_vie = cls._calendario('Lun-Vie Preparar', range(5))
        cls.lun_sab = cls._calendario('Lun-Sab Preparar', range(6))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Estructura Preparar', 'country_id': cls.env.ref('base.co').id})
        cls.struct = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.emp_a, cls.contract_a = cls._empleado('Empleado A')
        cls.emp_b, cls.contract_b = cls._empleado('Empleado B')

    @classmethod
    def _empleado(cls, nombre):
        empleado = cls.env['hr.employee'].create({
            'name': nombre, 'company_id': cls.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = cls.env['hr.contract'].create({
            'name': 'Contrato %s' % nombre, 'employee_id': empleado.id, 'company_id': cls.company.id,
            'structure_type_id': cls.structure_type.id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'resource_calendar_id': cls.lun_vie.id, 'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        return empleado, contrato

    def setUp(self):
        super().setUp()
        # Los prerrequisitos de certificado/software/cuenta se prueban aparte; aqui se aislan.
        patcher = patch.object(type(self.company), '_l10n_co_ne_validar_config', lambda s, *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(type(self.env['l10n.co.ne.documento']), '_ne_validar_datos_recibo', lambda s, slip: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(type(self.env['l10n.co.ne.documento']), '_ne_validar_xml', lambda s: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _recibo(self, empleado, contrato, desde, hasta, pagado=None, estado='paid'):
        slip = self.env['hr.payslip'].create({
            'name': 'Recibo %s %s' % (empleado.name, hasta), 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': self.struct.id, 'date_from': desde, 'date_to': hasta})
        slip.write({'state': estado, 'paid_date': pagado})
        return slip

    def _marzo(self):
        a1 = self._recibo(self.emp_a, self.contract_a, date(2026, 3, 1), date(2026, 3, 15), date(2026, 3, 15))
        a2 = self._recibo(self.emp_a, self.contract_a, date(2026, 3, 16), date(2026, 3, 31), date(2026, 3, 31))
        b1 = self._recibo(self.emp_b, self.contract_b, date(2026, 3, 1), date(2026, 3, 15), date(2026, 3, 16))
        return a1, a2, b1

    def _preparar(self, recibos):
        return self.env['l10n.co.ne.documento']._ne_preparar(recibos)

    def _claves(self, doc):
        return {a['key'] for a in doc.alertas or []}

    # ── Agrupar y reutilizar ─────────────────────────────────────────
    def test_agrupa_por_empleado_y_mes(self):
        a1, a2, b1 = self._marzo()
        res = self._preparar(a1 | a2 | b1)
        self.assertEqual(len(res['documentos']), 2)
        doc_a = a1.l10n_co_ne_documento_id
        self.assertEqual(a2.l10n_co_ne_documento_id, doc_a)
        self.assertEqual(doc_a.payslip_ids, a1 | a2)
        self.assertEqual(doc_a.period, date(2026, 3, 1))
        self.assertEqual(doc_a.contract_id, self.contract_a)
        self.assertEqual(b1.l10n_co_ne_documento_id.payslip_ids, b1)
        self.assertNotEqual(doc_a, b1.l10n_co_ne_documento_id)

    def test_seleccionar_una_quincena_trae_la_otra_si_esta_pagada(self):
        a1, a2, _b1 = self._marzo()
        self._preparar(a1)
        self.assertEqual(a1.l10n_co_ne_documento_id.payslip_ids, a1 | a2)

    def test_repetir_reutiliza_el_documento(self):
        a1, a2, b1 = self._marzo()
        self._preparar(a1 | a2 | b1)
        antes = self.env['l10n.co.ne.documento'].search([('company_id', '=', self.company.id)])
        self._preparar(a1 | a2 | b1)
        despues = self.env['l10n.co.ne.documento'].search([('company_id', '=', self.company.id)])
        self.assertEqual(antes, despues)
        self.assertEqual(len(despues), 2)

    def test_recibo_sin_fecha_o_no_hecho_no_pertenece_a_ningun_mes(self):
        sin_fecha = self._recibo(self.emp_a, self.contract_a, date(2026, 3, 1), date(2026, 3, 15), None, 'done')
        borrador = self._recibo(self.emp_b, self.contract_b, date(2026, 3, 1), date(2026, 3, 15), None, 'draft')
        res = self._preparar(sin_fecha | borrador)
        self.assertFalse(res['documentos'])
        self.assertEqual({s.id for s, _m in res['sin_fecha']}, {sin_fecha.id, borrador.id})
        self.assertFalse(self.env['l10n.co.ne.documento'].search([('company_id', '=', self.company.id)]))

    def test_recibo_que_cambia_de_mes_sale_del_documento_anterior(self):
        a1, a2, _b1 = self._marzo()
        self._preparar(a1)
        doc_marzo = a1.l10n_co_ne_documento_id
        a2.paid_date = date(2026, 4, 2)
        self._preparar(a2)
        self.assertEqual(a2.l10n_co_ne_documento_id.period, date(2026, 4, 1))
        self.assertEqual(doc_marzo.payslip_ids, a1)
        # si el unico recibo se mueve de mes, el documento vacio sin historia desaparece
        a1.paid_date = date(2026, 5, 4)
        self._preparar(a1)
        self.assertFalse(doc_marzo.exists())

    # ── Alertas ──────────────────────────────────────────────────────
    def test_documento_listo_sin_bloqueos(self):
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1 | a2)['documentos']
        self.assertEqual(doc.etapa, 'ready')
        self.assertFalse(doc.state)
        self.assertFalse([a for a in doc.alertas if a['level'] == 'danger'])

    def test_alerta_faltan_recibos_del_mes_es_confirmable(self):
        a1, a2, _b1 = self._marzo()
        a2.write({'state': 'draft', 'paid_date': False})
        doc = self._preparar(a1)['documentos']
        self.assertIn('faltan_recibos', self._claves(doc))
        alerta = next(a for a in doc.alertas if a['key'] == 'faltan_recibos')
        self.assertEqual(alerta['level'], 'warning')
        self.assertTrue(alerta['confirmable'])
        self.assertEqual(doc.etapa, 'ready')   # una advertencia no bloquea

    def test_un_recibo_pagado_en_otro_mes_no_dispara_faltan_recibos(self):
        # H-F3-1 (doc 58 §12): periodo de marzo pagado en abril (pagos los 5 y 20, mensual pagado el mes siguiente...):
        # pertenece al documento de abril y no "falta" en el de marzo.
        a1, a2, _b1 = self._marzo()
        a2.paid_date = date(2026, 4, 5)
        doc = self._preparar(a1)['documentos']
        self.assertNotIn('faltan_recibos', self._claves(doc))
        self.assertNotIn(a2, doc.payslip_ids)

    def test_un_recibo_sin_fecha_de_pago_sigue_disparando_faltan_recibos(self):
        a1, a2, _b1 = self._marzo()
        a2.write({'state': 'done', 'paid_date': False})
        doc = self._preparar(a1)['documentos']
        self.assertIn('faltan_recibos', self._claves(doc))

    def test_alerta_mes_en_curso_y_liquidacion(self):
        hoy = fields.Date.context_today(self.env.user)
        inicio = hoy.replace(day=1)
        slip = self._recibo(self.emp_a, self.contract_a, inicio, hoy, hoy)
        doc = self._preparar(slip)['documentos']
        self.assertIn('mes_en_curso', self._claves(doc))
        self.assertTrue(next(a for a in doc.alertas if a['key'] == 'mes_en_curso')['confirmable'])
        slip.struct_id = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        self._preparar(slip)
        self.assertNotIn('mes_en_curso', self._claves(doc))

    def test_alerta_datos_incompletos_bloquea(self):
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1 | a2)['documentos']
        self.assertEqual(doc.etapa, 'ready')
        def falla(documento, slip):
            raise UserError('El empleado X no tiene número de identificación configurado.')
        with patch.object(type(doc), '_ne_validar_datos_recibo', falla):
            doc._ne_validar()
        self.assertEqual({a['key'] for a in doc.alertas if a['level'] == 'danger'},
                         {'datos_%s' % a1.id, 'datos_%s' % a2.id})
        self.assertEqual(doc.etapa, 'draft')

    def test_documento_aceptado_no_se_recompone_y_alerta(self):
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1)['documentos']
        self.env['l10n.co.ne.documento.intento'].create({
            'documento_id': doc.id, 'state': 'invoice_accepted', 'datetime': datetime(2026, 4, 5, 10, 0)})
        nuevo = self._recibo(self.emp_a, self.contract_a, date(2026, 3, 20), date(2026, 3, 25), date(2026, 3, 26))
        self._preparar(nuevo)
        self.assertEqual(doc.payslip_ids, a1 | a2)          # intacto
        self.assertFalse(nuevo.l10n_co_ne_documento_id)      # el recibo nuevo no entra a un documento aceptado
        self.assertIn('aceptado', self._claves(doc))

    # ── Plazo (D10) ──────────────────────────────────────────────────
    def test_fecha_limite_lunes_a_viernes(self):
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1 | a2)['documentos']
        # abril 2026, lun-vie sin festivos: 1,2,3,6,7,8,9,10,13,14 -> el 10.º es el 14
        self.assertEqual(doc.fecha_limite, date(2026, 4, 14))
        self.assertIn('plazo_vencido', self._claves(doc))   # hoy es posterior (alerta, no bloqueo)
        self.assertEqual(doc.etapa, 'ready')

    def test_fecha_limite_cuenta_el_sabado_si_la_jornada_lo_incluye(self):
        a1, a2, _b1 = self._marzo()
        self.contract_a.resource_calendar_id = self.lun_sab
        doc = self._preparar(a1 | a2)['documentos']
        # lun-sab: 1,2,3,4(sab),6,7,8,9,10,11(sab) -> el 10.º es el 11
        self.assertEqual(doc.fecha_limite, date(2026, 4, 11))

    def test_fecha_limite_descuenta_festivos(self):
        a1, a2, _b1 = self._marzo()
        self.env['resource.calendar.leaves'].create({
            'name': 'Festivo de prueba', 'company_id': self.company.id, 'calendar_id': self.lun_vie.id,
            'resource_id': False, 'date_from': datetime(2026, 4, 2, 5, 0), 'date_to': datetime(2026, 4, 3, 4, 59, 59)})
        doc = self._preparar(a1 | a2)['documentos']
        # sin el 2 de abril: 1,3,6,7,8,9,10,13,14,15 -> el 10.º es el 15
        self.assertEqual(doc.fecha_limite, date(2026, 4, 15))

    def test_festivo_de_otra_compania_no_cambia_el_plazo(self):
        """El nativo no filtra los festivos globales por compañía cuando no hay recurso: la de otra compañía
        (p. ej. Jueves y Viernes Santo cargados en la compañía real de staging) no puede restar días hábiles de
        ESTE plazo. Con lun-vie y sin festivos propios, el 10.º día hábil de abril 2026 sigue siendo el 14."""
        a1, a2, _b1 = self._marzo()
        otra = self.env['res.company'].create({'name': 'Otra compañía con festivos', 'country_id': self.env.ref('base.co').id})
        # El nativo impide dos festivos globales que se crucen DENTRO de la misma compañía y una compañía colombiana
        # nueva ya trae los suyos (Jueves y Viernes Santo, 2-3 de abril): se quitan (con sudo) y el festivo de la
        # prueba cae en otro día hábil (miércoles 8 de abril), sin depender de cuáles traiga la compañía nueva.
        self.env['resource.calendar.leaves'].sudo().search(
            [('company_id', '=', otra.id), ('resource_id', '=', False)]).unlink()
        self.env['resource.calendar.leaves'].create({
            'name': 'Festivo global de otra compañía', 'company_id': otra.id, 'calendar_id': False,
            'resource_id': False, 'date_from': datetime(2026, 4, 8, 5, 0), 'date_to': datetime(2026, 4, 9, 4, 59, 59)})
        doc = self._preparar(a1 | a2)['documentos']
        self.assertEqual(doc.fecha_limite, date(2026, 4, 14))

    def test_legacy_no_tiene_plazo(self):
        legacy = self.env['l10n.co.ne.documento'].create({
            'company_id': self.company.id, 'employee_id': self.emp_a.id, 'period': date(2026, 3, 1), 'legacy': True})
        self.assertFalse(legacy.fecha_limite)

    # ── Plazo de las notas de ajuste (doc 53 §28.4): mes siguiente al CONOCIMIENTO del error ──
    def _nota(self, error_conocido_el, **vals):
        datos = {'company_id': self.company.id, 'employee_id': self.emp_a.id, 'contract_id': self.contract_a.id,
                 'period': date(2026, 3, 1), 'is_adjustment': True, 'adjustment_type': '1',
                 'adjustment_ref_cune': 'x' * 96, 'error_conocido_el': error_conocido_el}
        datos.update(vals)
        return self.env['l10n.co.ne.documento'].create(datos)

    def test_la_nota_tiene_plazo_desde_el_mes_siguiente_al_error(self):
        # error conocido en marzo -> abril 2026 (lun-vie sin festivos): el 10.º día hábil es el 14, como el original
        self.assertEqual(self._nota(date(2026, 3, 20)).fecha_limite, date(2026, 4, 14))

    def test_el_plazo_de_la_nota_no_sigue_al_mes_del_documento_original(self):
        # mismo documento de marzo, pero el error se conoció en febrero -> marzo 2026: 2,3,4,5,6,9,10,11,12,13 -> 13
        self.assertEqual(self._nota(date(2026, 2, 10)).fecha_limite, date(2026, 3, 13))

    def test_el_plazo_de_la_nota_se_recalcula_si_cambia_la_fecha_del_error(self):
        nota = self._nota(date(2026, 3, 20))
        nota.error_conocido_el = date(2026, 2, 10)
        self.assertEqual(nota.fecha_limite, date(2026, 3, 13))

    def test_una_nota_sin_fecha_de_error_no_tiene_plazo_y_avisa(self):
        nota = self._nota(False)
        self.assertFalse(nota.fecha_limite)
        nota._ne_validar()
        claves = [a['key'] for a in nota.alertas]
        self.assertIn('plazo_sin_calcular', claves)
        self.assertIn('fecha en que se conoció el error',
                      [a['message'] for a in nota.alertas if a['key'] == 'plazo_sin_calcular'][0])

    def test_plazo_vencido_de_una_nota_es_advertencia_no_bloqueo(self):
        nota = self._nota(date(2026, 3, 20))            # vencía el 14-abr-2026: hoy es posterior
        nota._ne_validar()
        vencido = [a for a in nota.alertas if a['key'] == 'plazo_vencido']
        self.assertEqual(len(vencido), 1)
        self.assertEqual(vencido[0]['level'], 'warning')                # sin sanción automática: no bloquea
        self.assertIn('conocimiento del error', vencido[0]['message'])

    def test_parametro_del_plazo_esta_versionado(self):
        valor = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_co_ne_dias_plazo_transmision', date(2026, 4, 1))
        self.assertEqual(int(valor), 10)

    def _plazo_virtual(self, doc, periodo):
        """Fecha limite que tendria un documento del ``periodo`` (registro virtual: no toca los guardados, cuyo campo calculado no depende del parametro)."""
        return doc.new({'company_id': doc.company_id.id, 'contract_id': doc.contract_id.id, 'period': periodo})._ne_calcular_fecha_limite()

    def test_cambiar_la_vigencia_del_parametro_cambia_el_plazo_sin_tocar_codigo(self):
        """H-F3-05 (Res. DIAN 000013/2021 art. 8): los dias del plazo salen del parametro versionado, no de una constante. Valor de fabrica 10: el 10.º dia habil de abril de 2026 (lun-vie) es el 14.
        Un valor nuevo de 8 con vigencia desde el 1-abr-2026 (la vigencia se evalua en el primer dia del mes siguiente al periodo) da el 8.º dia habil, el 10; un periodo anterior a la vigencia (febrero:
        primero = 1-mar-2026) conserva los 10 dias (13-mar-2026)."""
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1 | a2)['documentos']
        self.assertEqual(self._plazo_virtual(doc, date(2026, 3, 1)), date(2026, 4, 14))
        parametro = self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_ne_dias_plazo_transmision')])
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'date_from': date(2026, 4, 1), 'parameter_value': '8'})
        self.assertEqual(self._plazo_virtual(doc, date(2026, 3, 1)), date(2026, 4, 10))          # abril 2026: 1,2,3,6,7,8,9,10 -> el 8.º es el 10
        self.assertEqual(self._plazo_virtual(doc, date(2026, 2, 1)), date(2026, 3, 13))          # antes de la vigencia: siguen siendo 10 dias habiles
        self.assertFalse(hasattr(type(doc), 'DIAS_HABILES_PLAZO'), 'La constante ya no existe: el plazo es solo el parametro')

    def test_sin_el_parametro_del_plazo_un_error_que_lo_nombra(self):
        a1, a2, _b1 = self._marzo()
        doc = self._preparar(a1 | a2)['documentos']
        self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_ne_dias_plazo_transmision')]).unlink()
        with self.assertRaisesRegex(UserError, 'l10n_co_ne_dias_plazo_transmision'):
            self._plazo_virtual(doc, date(2026, 3, 1))
