# -*- coding: utf-8 -*-
"""C-24 (doc 106 §12-§13): no se confirma un recibo cuyas líneas no corresponden a sus datos («hoja al día»).

Defecto: una novedad agregada por importación, con el recálculo apagado, por una fila escrita por fuera del recibo, con un error de cálculo, o un día trabajado / salario / ausencia cambiado
después de calcular, dejaba la hoja vieja y la confirmación no lo comprobaba (asiento, pago, XML y PILA salían sin la novedad). Ahora ``compute_sheet`` guarda la huella de los datos propios del
recibo (``l10n_co_ne_huella_calculo``) y ``action_payslip_done`` la compara.

Las pruebas de confirmación parchan las OTRAS validaciones (afiliación, cuenta, pacto, solape, periodo), el nativo y el asiento: solo la comprobación de la hoja al día puede fallar, y «se
confirma» significa que se llegó al nativo. ``TestHuellaCalculoPura`` es Python puro. NO EJECUTADAS en Odoo al escribirlas (la función pura y los métodos del recibo se verificaron fuera de Odoo)."""

from datetime import date
from unittest.mock import patch

from odoo.addons.l10n_co_nomina_electronica.services import huella_calculo
from odoo.exceptions import UserError
from odoo.tests.common import BaseCase, TransactionCase, tagged

NATIVO = 'odoo.addons.hr_payroll.models.hr_payslip.HrPayslip.action_payslip_done'
_DESACTUALIZADA = 'la hoja de cálculo no está al día'

_BASE = dict(cabecera=(1, 2, 3, date(2026, 9, 1), date(2026, 9, 15)), salario=3000000.0, entradas=[(10, 200000.0), (11, 5.0)], dias=[(20, 11.0, 88.0), (21, 2.0, 16.0)],
             ajustes=[(30, 1.0, 100.0, 1500000.0)], ausencias=[(40, date(2026, 9, 7), date(2026, 9, 10), 50)])


def _huella(**cambios):
    return huella_calculo.huella(**dict(_BASE, **cambios))


@tagged('post_install', '-at_install')
class TestHuellaCalculoPura(BaseCase):
    """La función pura ``services.huella_calculo.huella``."""

    def test_los_mismos_datos_dan_la_misma_huella_con_la_version(self):
        self.assertEqual(_huella(), _huella())
        self.assertTrue(_huella().startswith(huella_calculo.VERSION + ':'))
        self.assertEqual(len(_huella().split(':')[1]), 64)

    def test_el_orden_de_las_lineas_no_cambia_la_huella(self):
        self.assertEqual(_huella(entradas=[(11, 5.0), (10, 200000.0)], dias=[(21, 2.0, 16.0), (20, 11.0, 88.0)]), _huella())

    def test_el_ruido_de_los_flotantes_y_el_menos_cero_no_cambian_la_huella(self):
        self.assertEqual(_huella(entradas=[(10, 200000.0000000001), (11, 5.0)], salario=3000000.0000000004), _huella())
        self.assertEqual(_huella(salario=-0.0), _huella(salario=0.0))
        self.assertEqual(_huella(entradas=[(10, 0.1 + 0.2)]), _huella(entradas=[(10, 0.3)]))
        self.assertEqual(_huella(salario=3000000), _huella(salario=3000000.0))

    def test_cada_dato_cambia_la_huella(self):
        casos = {
            'empleado': dict(cabecera=(9, 2, 3, date(2026, 9, 1), date(2026, 9, 15))),
            'contrato': dict(cabecera=(1, 9, 3, date(2026, 9, 1), date(2026, 9, 15))),
            'estructura': dict(cabecera=(1, 2, 9, date(2026, 9, 1), date(2026, 9, 15))),
            'desde': dict(cabecera=(1, 2, 3, date(2026, 9, 2), date(2026, 9, 15))),
            'hasta': dict(cabecera=(1, 2, 3, date(2026, 9, 1), date(2026, 9, 14))),
            'salario': dict(salario=3000001.0),
            'importe de una novedad': dict(entradas=[(10, 200001.0), (11, 5.0)]),
            'tipo de una novedad': dict(entradas=[(12, 200000.0), (11, 5.0)]),
            'novedad borrada': dict(entradas=[(11, 5.0)]),
            'novedad repetida': dict(entradas=[(10, 200000.0), (10, 200000.0), (11, 5.0)]),
            'días trabajados': dict(dias=[(20, 12.0, 88.0), (21, 2.0, 16.0)]),
            'horas trabajadas': dict(dias=[(20, 11.0, 80.0), (21, 2.0, 16.0)]),
            'ajuste': dict(ajustes=[(30, 1.0, 100.0, 1500001.0)]),
            'ajuste quitado': dict(ajustes=[]),
            'ausencia nueva': dict(ausencias=[(40, date(2026, 9, 7), date(2026, 9, 10), 50), (41, date(2026, 9, 14), date(2026, 9, 15), 50)]),
            'fechas de la ausencia': dict(ausencias=[(40, date(2026, 9, 7), date(2026, 9, 11), 50)]),
            'tipo de la ausencia': dict(ausencias=[(40, date(2026, 9, 7), date(2026, 9, 10), 51)]),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.assertNotEqual(_huella(**cambio), _huella())


@tagged('post_install', '-at_install')
class TestHojaAlDia(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Hoja al Día'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Hoja al Dia', 'country_id': cls.env.ref('base.co').id})
        cls.est_general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.tipo_bonificacion = cls.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.tipo_incapacidad = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _recibo(self, calculado=True, novedades=(200000.0,)):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Hoja %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Hoja %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        contrato.generate_work_entries(date(2026, 9, 1), date(2026, 9, 30))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Hoja %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.est_general.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15),
            'input_line_ids': [(0, 0, self._vals_novedad(None, monto)) for monto in novedades]})
        if calculado:
            recibo.compute_sheet()
        return recibo

    def _vals_novedad(self, recibo, monto):
        vals = {'input_type_id': self.tipo_bonificacion.id, 'code': 'CO_BONIF_NOSAL', 'amount': monto}
        if recibo:
            vals['payslip_id'] = recibo.id
        return vals

    def _novedad(self, recibo, monto, **contexto):
        return self.env['hr.payslip.input'].with_context(**contexto).create(self._vals_novedad(recibo, monto))

    def _parches(self, recibos):
        tipo = type(recibos)
        return [patch.object(tipo, nombre) for nombre in (
            '_ne_validar_duracion_periodo', '_ne_validar_sin_solape', '_ne_validar_cuenta_neto', '_ne_validar_pacto_no_salarial', '_ne_validar_afiliaciones',
            '_ne_aplicar_libranzas', '_ne_refrescar_ibc_mensual', '_action_create_account_move')]

    def _confirmar(self, recibos):
        """Confirma con todo lo demás parchado; devuelve el parche del nativo (llamado = pasó la comprobación)."""
        parches = self._parches(recibos)
        for parche in parches:
            parche.start()
        try:
            with patch(NATIVO, return_value=True) as nativo:
                recibos.action_payslip_done()
        finally:
            for parche in parches:
                parche.stop()
        return nativo

    def _se_confirma(self, recibos):
        self.assertTrue(self._confirmar(recibos).called, 'Debía pasar la comprobación y llegar al nativo.')

    def _no_se_confirma(self, recibos):
        estados = recibos.mapped('state')
        # sin avisos de traduccion («no translation language detected»): el mensaje del bloqueo busca el idioma en el marco que llama a `_()`
        with self.assertNoLogs('odoo.tools.translate', 'WARNING'), self.assertRaisesRegex(UserError, _DESACTUALIZADA) as error:
            self._confirmar(recibos)
        self.assertEqual(recibos.mapped('state'), estados)
        return str(error.exception)

    def _hoja_vieja(self, recibo):
        """Agrega una novedad como la dejaría una importación: sin recalcular."""
        self._novedad(recibo, 30000.0, import_file=True)

    def _usuario_de_nomina(self):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'c24_nomina', 'login': 'c24_nomina', 'email': 'c24_nomina@example.com', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref(g).id for g in ('base.group_user', 'hr_payroll.group_hr_payroll_manager')])]})

    # ── calculado y al dia: se confirma ──────────────────────────────
    def test_un_recibo_calculado_tiene_huella_estable_y_se_confirma(self):
        recibo = self._recibo()
        guardada = recibo.l10n_co_ne_huella_calculo
        self.assertTrue(guardada)
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(recibo._ne_huella_calculo(), guardada, 'El mismo recibo leído de la base da la misma huella')
        recibo.compute_sheet()
        self.assertEqual(recibo.l10n_co_ne_huella_calculo, guardada, 'Recalcular sin cambios no cambia la huella')
        self._se_confirma(recibo)

    def test_los_caminos_que_si_recalculan_no_dan_falso_positivo(self):
        recibo = self._recibo()
        self._novedad(recibo, 50000.0)                                                      # ORM directo: recalcula solo
        self._se_confirma(recibo)
        recibo.write({'input_line_ids': [(0, 0, self._vals_novedad(None, 25000.0))]})       # formulario (web_save)
        self._se_confirma(recibo)
        fila = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.salary_rule_id.code == 'CO_BASICO')
        self.assertTrue(fila, 'Premisa: la pestaña Conceptos de pago trae la fila del sueldo')
        recibo.write({'l10n_co_concepto_ids': [(1, fila.id, {'amount': fila.amount + 1000.0})]})       # ajuste desde la pestaña
        self.assertTrue(recibo.l10n_co_ajuste_ids, 'Premisa: quedó un ajuste de la empresa')
        self._se_confirma(recibo)

    def test_cambiar_el_nombre_o_el_orden_de_una_novedad_no_bloquea(self):
        recibo = self._recibo()
        recibo.input_line_ids.write({'name': 'Otro nombre', 'sequence': 99})
        self._se_confirma(recibo)

    # ── hoja desactualizada: no se confirma ──────────────────────────
    def test_nunca_calculado_no_se_confirma(self):
        recibo = self._recibo(calculado=False)
        self.assertFalse(recibo.l10n_co_ne_huella_calculo)
        self._no_se_confirma(recibo)

    def test_calculado_antes_de_la_version_pide_calcular_y_despues_se_confirma(self):
        recibo = self._recibo()
        self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip SET l10n_co_ne_huella_calculo = NULL WHERE id = %s', [recibo.id])
        recibo.invalidate_recordset(['l10n_co_ne_huella_calculo'])
        self._no_se_confirma(recibo)
        recibo.compute_sheet()
        self._se_confirma(recibo)

    def test_el_mensaje_nombra_el_recibo_el_empleado_y_que_hacer(self):
        recibo = self._recibo()
        self._hoja_vieja(recibo)
        mensaje = self._no_se_confirma(recibo)
        for esperado in (recibo.number or recibo.name, recibo.employee_id.name, 'Calcular hoja', 'salario del contrato', 'ausencias'):
            self.assertIn(esperado, mensaje)

    def test_una_novedad_importada_no_se_paga_en_silencio(self):
        recibo = self._recibo()
        self._hoja_vieja(recibo)
        self._no_se_confirma(recibo)
        recibo.compute_sheet()
        self._se_confirma(recibo)

    def test_una_carga_masiva_sin_recalculo_no_se_confirma(self):
        recibo = self._recibo()
        self._novedad(recibo, 30000.0, ne_sin_recalculo_hoja=True)
        self._no_se_confirma(recibo)

    def test_borrar_una_novedad_sin_recalcular_no_se_confirma(self):
        recibo = self._recibo()
        recibo.input_line_ids.with_context(ne_sin_recalculo_hoja=True).unlink()
        self._no_se_confirma(recibo)

    def test_borrar_la_fila_de_conceptos_por_fuera_del_recibo_no_se_confirma(self):
        recibo = self._recibo()
        fila = recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'novedad' and f.input_id)
        self.assertTrue(fila, 'Premisa: la novedad tiene su fila')
        fila.unlink()
        self.assertFalse(recibo.input_line_ids)
        self._no_se_confirma(recibo)

    def test_un_error_de_calculo_al_recalcular_no_deja_confirmar(self):
        recibo = self._recibo()
        with patch.object(type(recibo), 'compute_sheet', side_effect=UserError('Falla de cálculo de prueba')):
            self._novedad(recibo, 30000.0)                  # la novedad se guarda; el recálculo falla y deja una nota
        self.assertEqual(len(recibo.input_line_ids), 2)
        self._no_se_confirma(recibo)

    def test_un_ajuste_escrito_por_fuera_del_recibo_no_se_confirma(self):
        recibo = self._recibo()
        regla = self.est_general.rule_ids.filtered(lambda r: r.code == 'CO_BASICO')
        linea = recibo.line_ids.filtered(lambda l: l.code == 'CO_BASICO')
        self.env['l10n.co.payslip.ajuste'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'quantity': linea.quantity, 'rate': linea.rate, 'amount': linea.amount + 1000.0})
        self._no_se_confirma(recibo)

    def test_editar_los_dias_trabajados_no_se_confirma(self):
        recibo = self._recibo()
        linea = recibo.worked_days_line_ids[:1]
        self.assertTrue(linea, 'Premisa: el recibo trae días trabajados')
        linea.number_of_days = linea.number_of_days + 1
        self._no_se_confirma(recibo)

    def test_cambiar_las_fechas_del_recibo_no_se_confirma(self):
        recibo = self._recibo()
        recibo.write({'date_to': date(2026, 9, 14)})
        self._no_se_confirma(recibo)

    def test_cambiar_el_salario_del_contrato_no_se_confirma(self):
        recibo = self._recibo()
        recibo.contract_id.write({'wage': 3100000.0})
        self._no_se_confirma(recibo)
        recibo.compute_sheet()
        self._se_confirma(recibo)

    def test_una_ausencia_aprobada_en_el_periodo_despues_de_calcular_no_se_confirma(self):
        """El recálculo que Odoo pueda hacer al aprobar se apaga aquí: se prueba que la huella ve la ausencia."""
        recibo = self._recibo()
        tipo = type(recibo)
        with patch.object(tipo, 'compute_sheet'), patch.object(tipo, 'action_refresh_from_work_entries'):
            fuera = self.env['hr.leave'].create({
                'employee_id': recibo.employee_id.id, 'holiday_status_id': self.tipo_incapacidad.id,
                'request_date_from': date(2026, 11, 2), 'request_date_to': date(2026, 11, 3)})
            fuera.action_validate()
        self.assertEqual(recibo._ne_huella_calculo(), recibo.l10n_co_ne_huella_calculo, 'Una ausencia fuera del periodo no entra')
        with patch.object(tipo, 'compute_sheet'), patch.object(tipo, 'action_refresh_from_work_entries'):
            dentro = self.env['hr.leave'].create({
                'employee_id': recibo.employee_id.id, 'holiday_status_id': self.tipo_incapacidad.id,
                'request_date_from': date(2026, 9, 7), 'request_date_to': date(2026, 9, 10)})
            dentro.action_validate()
        self.assertEqual(dentro.state, 'validate')
        self._no_se_confirma(recibo)

    def test_un_duplicado_no_hereda_la_huella_y_pide_calcular(self):
        recibo = self._recibo()
        copia = recibo.copy()
        self.assertTrue(copia.line_ids, 'Premisa: el duplicado trae las líneas del origen')
        self.assertFalse(copia.l10n_co_ne_huella_calculo)
        self._no_se_confirma(copia)
        copia.compute_sheet()
        self._se_confirma(copia)

    def test_un_lote_con_varios_desactualizados_da_un_solo_error_que_los_nombra(self):
        uno, dos = self._recibo(), self._recibo()
        self._hoja_vieja(uno)
        self._hoja_vieja(dos)
        mensaje = self._no_se_confirma(uno | dos)
        for recibo in (uno, dos):
            self.assertIn(recibo.employee_id.name, mensaje)
        self.assertIn('2 recibo(s)', mensaje)
        self.assertFalse((uno | dos).mapped('move_id'))

    # ── lo que no se mira ────────────────────────────────────────────
    def test_un_reembolso_no_se_mira(self):
        recibo = self._recibo()
        reembolso = recibo.copy({'name': 'Reembolso', 'credit_note': True, 'edited': True, 'state': 'verify'})
        self.assertFalse(reembolso.l10n_co_ne_huella_calculo)
        reembolso._ne_validar_hoja_al_dia()                 # no lanza

    def test_un_recibo_hecho_no_se_mira_ni_su_huella_se_refresca(self):
        recibo = self._recibo()
        guardada = recibo.l10n_co_ne_huella_calculo
        recibo.write({'state': 'done'})
        self._novedad(recibo, 30000.0, ne_sin_recalculo_hoja=True)
        recibo._ne_validar_hoja_al_dia()                    # no lanza
        recibo.compute_sheet()                              # el nativo no recalcula un recibo hecho
        self.assertEqual(recibo.l10n_co_ne_huella_calculo, guardada)

    def test_cancelar_y_volver_a_borrador_sin_cambios_deja_confirmar(self):
        recibo = self._recibo()
        recibo.action_payslip_cancel()
        recibo.action_payslip_draft()
        self._se_confirma(recibo)

    # ── D3: la huella no se escribe por fuera ────────────────────────
    def test_la_huella_solo_la_escribe_el_calculo(self):
        recibo = self._recibo()
        guardada = recibo.l10n_co_ne_huella_calculo
        usuario = self._usuario_de_nomina()
        como_usuario = recibo.with_user(usuario)
        mensaje = 'solo «Calcular hoja»'
        with self.assertRaisesRegex(UserError, mensaje):
            como_usuario.write({'l10n_co_ne_huella_calculo': 'falsa'})
        with self.assertRaisesRegex(UserError, mensaje):
            como_usuario.with_context(ne_huella_del_calculo=True, ne_sin_recalculo_hoja=True).write({'l10n_co_ne_huella_calculo': 'falsa'})      # ningún contexto abre la puerta
        vals = {'name': 'Recibo con huella', 'employee_id': recibo.employee_id.id, 'contract_id': recibo.contract_id.id, 'company_id': self.company.id,
                'struct_id': self.est_general.id, 'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 15)}
        with self.assertRaisesRegex(UserError, mensaje):
            self.env['hr.payslip'].with_user(usuario).create(dict(vals, l10n_co_ne_huella_calculo='falsa'))
        with self.assertRaisesRegex(UserError, mensaje):
            self.env['hr.payslip'].with_user(usuario).with_context(default_l10n_co_ne_huella_calculo='falsa').create(dict(vals))
        try:                                                # importación (load), la otra puerta pública del ORM
            self.env['hr.payslip'].with_user(usuario).load(['.id', 'l10n_co_ne_huella_calculo'], [[str(recibo.id), 'falsa']])
        except UserError:
            pass
        recibo.invalidate_recordset(['l10n_co_ne_huella_calculo'])
        self.assertEqual(recibo.l10n_co_ne_huella_calculo, guardada)
        como_usuario.compute_sheet()                        # el cálculo del mismo usuario sí la escribe
        self.assertEqual(recibo.l10n_co_ne_huella_calculo, recibo._ne_huella_calculo())
