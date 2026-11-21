# -*- coding: utf-8 -*-
"""E11 pieza 2b (.288, doc 71c §2, §3 y §13): ajuste de la empresa a un concepto del recibo, aplicado DENTRO del cálculo.

Orden pedido por TL: la prueba de base va primero (sin ajustes el cálculo es idéntico, en las 4 estructuras); después el valor exacto del
ajuste, la cascada contra un cálculo manual equivalente (el «oráculo» fija la fórmula de la regla al mismo valor y calcula SIN ajuste: así la
comparación no depende del gancho que se prueba), la supervivencia al recálculo, los avisos del chatter, los bloqueos, los permisos y el
aislamiento por compañía. NO EJECUTADAS en Odoo al escribirlas (el N1 necesita ``-u``: tabla, permisos y reglas de registro nuevos)."""

from datetime import date
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.addons.hr_payroll.models.hr_salary_rule import HrSalaryRule as ReglaNativa
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

_G_MANAGER = 'hr_payroll.group_hr_payroll_manager'
_G_USER = 'hr_payroll.group_hr_payroll_user'


@tagged('post_install', '-at_install')
class TestAjusteConceptoRecibo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Ajustes A'))
        cls.company_b = cls.env['res.company'].create(dict(valores, name='Compañía Ajustes B'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Ajustes', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.bonificacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')
        cls.tipo_bonif_nosal = ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.Ajuste = cls.env['l10n.co.payslip.ajuste']
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, estructura=None, desde=date(2026, 9, 1), hasta=date(2026, 9, 15), wage=3000000.0, inicio=date(2024, 3, 1), compania=None):
        """Recibo calculado (en espera) de un empleado nuevo."""
        type(self).n += 1
        compania = compania or self.company
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Ajuste %s' % self.n,
            'company_id': compania.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Ajuste %s' % self.n, 'employee_id': empleado.id, 'company_id': compania.id,
            'structure_type_id': self.structure_type.id, 'wage': wage, 'date_start': inicio, 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Ajuste %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': compania.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})
        if estructura == self.bonificacion:
            self.env['hr.payslip.input'].create({
                'payslip_id': recibo.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_bon_valor').id,
                'code': 'CO_BON_VALOR', 'amount': 500000.0})
        recibo.compute_sheet()
        return recibo

    def _regla(self, codigo, estructura=None):
        regla = self.env['hr.salary.rule'].search([('code', '=', codigo), ('struct_id', '=', (estructura or self.general).id)], limit=1)
        self.assertTrue(regla, codigo)
        return regla

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _total(self, recibo, codigo):
        return sum(self._linea(recibo, codigo).mapped('total'))

    def _lineas(self, recibo):
        """Todas las líneas del recibo como datos comparables: (código, importe, cantidad, porcentaje, total)."""
        return sorted((l.code, l.amount, l.quantity, l.rate, l.total) for l in recibo.line_ids)

    def _ajustar(self, recibo, codigo, **valores):
        regla = self._regla(codigo, recibo.struct_id)
        linea = self._linea(recibo, codigo)
        base = {'quantity': linea.quantity, 'rate': linea.rate, 'amount': linea.amount}
        return self.Ajuste.create(dict(base, slip_id=recibo.id, salary_rule_id=regla.id, **valores))

    def _notas(self, recibo):
        return ' '.join(str(cuerpo) for cuerpo in recibo.message_ids.mapped('body'))

    def _usuario(self, login, grupos, companias):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': companias[0].id,
            'company_ids': [(6, 0, companias.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    # ── 1. BASE: sin ajustes el cálculo es idéntico, en las 4 estructuras ─────────────────────────────────────────────────────────
    def test_01_sin_ajustes_el_calculo_es_identico_al_nativo_en_las_cuatro_estructuras(self):
        casos = (
            (self.general, {}),
            (self.prima, {'desde': date(2026, 7, 1), 'hasta': date(2026, 12, 31)}),
            (self.liquidacion, {'desde': date(2024, 3, 1), 'hasta': date(2026, 8, 15)}),
            (self.bonificacion, {}),
        )
        Regla = type(self.env['hr.salary.rule'])
        for estructura, extra in casos:
            recibo = self._recibo(estructura=estructura, **extra)
            self.assertTrue(recibo.line_ids, estructura.name)
            con_gancho = self._lineas(recibo)
            with patch.object(Regla, '_compute_rule', ReglaNativa._compute_rule):    # sin nuestro override
                recibo.compute_sheet()
            self.assertEqual(con_gancho, self._lineas(recibo), 'La estructura %s cambió con el gancho' % estructura.name)

    # ── 2. valor exacto del ajuste ─────────────────────────────────────────────────────────────────────────────────────────────
    def test_02_ajustar_la_salud_a_cero_deja_la_linea_en_cero_y_el_neto_sube_exactamente(self):
        recibo = self._recibo()
        sugerido = self._total(recibo, 'CO_SALUD_EMP')
        self.assertLess(sugerido, 0.0, 'Premisa: la deducción de salud es negativa')
        neto0, retencion0 = recibo._ne_pdf_neto(), self._total(recibo, 'CO_RETEFUENTE')
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        self.assertAlmostEqual(ajuste.sugerido_total, sugerido, delta=0.01, msg='Al crear, lo sugerido es la línea que ya traía el recibo')
        recibo.compute_sheet()
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0)
        neto1, retencion1 = recibo._ne_pdf_neto(), self._total(recibo, 'CO_RETEFUENTE')
        # neto = suma de las líneas: la salud deja de restar |sugerido| y la retención se mueve por la cascada.
        self.assertAlmostEqual(neto1 - neto0, (0.0 - sugerido) + (retencion1 - retencion0), delta=0.01)
        self.assertEqual((ajuste.estado, ajuste.user_id, ajuste.con_sugerido), ('aplicado', self.env.user, True))
        self.assertAlmostEqual(ajuste.sugerido_total, sugerido, delta=0.01)

    # ── 3. (TL b) cascada igual que un cálculo manual equivalente ──────────────────────────────────────────────────────────────
    def test_03_la_cascada_del_ajuste_es_igual_a_la_de_un_calculo_manual_equivalente(self):
        """El ajuste baja la deducción de salud a la mitad. El oráculo es OTRO recibo idéntico, sin ajuste, con la fórmula de la regla fijada al
        mismo valor: todas las líneas (neto, IBC, bases y retención) deben coincidir EXACTAMENTE."""
        recibo = self._recibo()
        linea = self._linea(recibo, 'CO_SALUD_EMP')
        sugerido_total = linea.total
        # ``compute_sheet`` borra las líneas del recibo y crea otras (nativo ``hr_payslip.py:600``): se leen ANTES de calcular, porque ``linea``
        # ya no existe después (N2 «co» de .289: MissingError en la línea 59140).
        cantidad, porcentaje = linea.quantity, linea.rate
        neto0, retencion0 = recibo._ne_pdf_neto(), self._total(recibo, 'CO_RETEFUENTE')
        nuevo_importe = round(linea.amount / 2.0, 2)          # a la precisión con que se guarda el importe del ajuste
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=nuevo_importe)
        recibo.compute_sheet()
        total_ajustado = nuevo_importe * cantidad * porcentaje / 100.0
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), total_ajustado, delta=0.01)
        neto1, retencion1 = recibo._ne_pdf_neto(), self._total(recibo, 'CO_RETEFUENTE')
        self.assertAlmostEqual(neto1 - neto0, (total_ajustado - sugerido_total) + (retencion1 - retencion0), delta=0.01)
        oraculo = self._recibo()
        regla = self._regla('CO_SALUD_EMP')
        regla.amount_python_compute = 'result = %r\nresult_qty = %r\nresult_rate = %r' % (nuevo_importe, cantidad, porcentaje)
        oraculo.compute_sheet()
        self.assertFalse(oraculo.l10n_co_ajuste_ids, 'El oráculo no lleva ajuste')
        self.assertEqual(self._lineas(recibo), self._lineas(oraculo))
        self.assertEqual(recibo._ne_pdf_neto(), oraculo._ne_pdf_neto())
        for codigo in ('CO_IBC_SP', 'CO_IBC_SALARIAL', 'CO_RETEFUENTE_BASE_GROSS', 'CO_RETEFUENTE_BASE_IBC', 'CO_RETEFUENTE'):
            self.assertEqual(self._total(recibo, codigo), self._total(oraculo, codigo), codigo)
        self.assertEqual(ajuste.estado, 'aplicado')

    # ── 4. sobrevive al recálculo ──────────────────────────────────────────────────────────────────────────────────────────────
    def test_04_el_ajuste_sobrevive_a_calcular_la_hoja_al_refrescar_y_a_una_novedad_del_formulario(self):
        recibo = self._recibo()
        self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        recibo.compute_sheet()
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0)
        recibo.compute_sheet()
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0, 'Calcular hoja')
        recibo.action_refresh_from_work_entries()
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0, 'Refrescar desde las entradas de trabajo')
        # .286: el formulario recalcula la hoja. La estructura general oculta la página nativa de novedades (``views/hr_payslip_conceptos_views.xml:13-15``,
        # ``odoo/tests/form.py:855``): la novedad se agrega como fila de «Conceptos de pago» (``l10n_co_concepto_ids``), lo que ve el usuario.
        with Form(recibo) as formulario:
            with formulario.l10n_co_concepto_ids.new() as fila:
                fila.input_type_id = self.tipo_bonif_nosal
                fila.amount = 100000.0
        self.assertEqual(self._total(recibo, 'CO_BONIF_NOSAL'), 100000.0)
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0, 'Novedad guardada desde el formulario')

    # ── 5. volver al sugerido ──────────────────────────────────────────────────────────────────────────────────────────────────
    def test_05_volver_al_valor_sugerido_borra_el_ajuste_y_deja_nota(self):
        recibo = self._recibo()
        sugerido = self._total(recibo, 'CO_SALUD_EMP')
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        recibo.compute_sheet()
        ajuste.write({'amount': ajuste.sugerido_amount, 'quantity': ajuste.sugerido_quantity, 'rate': ajuste.sugerido_rate})
        recibo.compute_sheet()
        self.assertFalse(ajuste.exists(), 'El ajuste igual al sugerido se borra solo')
        self.assertAlmostEqual(self._total(recibo, 'CO_SALUD_EMP'), sugerido, delta=0.01)
        self.assertIn('quedó igual al valor sugerido', self._notas(recibo))

    # ── 6. la condición de la regla deja de cumplirse ──────────────────────────────────────────────────────────────────────────
    def test_06_si_la_regla_deja_de_generar_linea_el_ajuste_queda_sin_linea_y_avisa(self):
        recibo = self._recibo()
        self.assertTrue(self._linea(recibo, 'CO_AUX_TRANS'), 'Premisa: con 3.000.000 hay auxilio de transporte')
        ajuste = self._ajustar(recibo, 'CO_AUX_TRANS', amount=5000.0, quantity=15.0)
        recibo.compute_sheet()
        self.assertEqual(self._total(recibo, 'CO_AUX_TRANS'), 75000.0)
        recibo.contract_id.wage = 9000000.0                                  # por encima de 2 SMMLV: la regla ya no paga auxilio
        recibo.compute_sheet()
        self.assertFalse(self._linea(recibo, 'CO_AUX_TRANS'))
        self.assertEqual(ajuste.estado, 'sin_linea')
        self.assertIn('no se aplicó en este cálculo', self._notas(recibo))

    # ── 7. cambia lo sugerido (Q2 de TL) ───────────────────────────────────────────────────────────────────────────────────────
    def test_07_si_cambia_el_sugerido_se_conserva_lo_ajustado_y_hay_nota(self):
        recibo = self._recibo()
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        recibo.compute_sheet()
        sugerido_antes = ajuste.sugerido_total
        recibo.contract_id.wage = 3500000.0
        recibo.compute_sheet()
        self.assertNotAlmostEqual(ajuste.sugerido_total, sugerido_antes, places=2, msg='Premisa: el sugerido cambió con el sueldo')
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0, 'Se conserva el valor ajustado')
        self.assertIn('cambió de', self._notas(recibo))
        recibo.compute_sheet()                                               # sin cambio de sugerido: no repite la nota
        self.assertEqual(self._notas(recibo).count('cambió de'), 1)

    # ── 8. bloqueos (Q6 de TL) ─────────────────────────────────────────────────────────────────────────────────────────────────
    def test_08_un_recibo_hecho_o_con_documento_enviado_incierto_o_aceptado_no_admite_ajustes(self):
        recibo = self._recibo()
        regla = self._regla('CO_SALUD_EMP')
        valores = {'slip_id': recibo.id, 'salary_rule_id': regla.id, 'amount': 0.0}
        for estado in ('sent', 'uncertain', 'accepted'):
            with patch.object(type(recibo), '_ne_estado_documento_ajuste', return_value=estado):
                with self.assertRaises(UserError, msg=estado):
                    self.Ajuste.create(valores)
        for estado in (False, 'draft', 'rejected', 'eliminated'):
            with patch.object(type(recibo), '_ne_estado_documento_ajuste', return_value=estado):
                self.Ajuste.create(valores).unlink()                          # estos estados no bloquean por sí mismos
        ajuste = self.Ajuste.create(valores)
        recibo.write({'state': 'done'})
        with self.assertRaises(UserError):
            ajuste.write({'amount': 1.0})
        with self.assertRaises(UserError):
            ajuste.unlink()
        with self.assertRaises(UserError):
            self.Ajuste.create(dict(valores, salary_rule_id=self._regla('CO_PENSION_EMP').id))
        self.assertTrue(ajuste.exists(), 'Un recibo hecho conserva sus ajustes como rastro')

    # ── 9. permisos ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_09_el_gerente_ajusta_el_usuario_de_nomina_solo_lee_y_otros_no_ven_nada(self):
        recibo = self._recibo()
        gerente = self._usuario('gerente_ajustes', (_G_MANAGER, 'base.group_user'), self.company)
        oficial = self._usuario('oficial_ajustes', (_G_USER, 'base.group_user'), self.company)
        otro = self._usuario('otro_ajustes', ('base.group_user',), self.company)
        regla = self._regla('CO_SALUD_EMP')
        ajuste = self.Ajuste.with_user(gerente).create({'slip_id': recibo.id, 'salary_rule_id': regla.id, 'amount': 0.0})
        ajuste.with_user(gerente).write({'amount': 1.0})
        self.assertEqual(self.Ajuste.with_user(oficial).search([('id', '=', ajuste.id)]), ajuste, 'El oficial lee')
        with self.assertRaises(AccessError):
            ajuste.with_user(oficial).write({'amount': 2.0})
        with self.assertRaises(AccessError):
            self.Ajuste.with_user(oficial).create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_PENSION_EMP').id, 'amount': 0.0})
        with self.assertRaises(AccessError):
            ajuste.with_user(oficial).unlink()
        with self.assertRaises(AccessError):
            self.Ajuste.with_user(otro).search([])
        ajuste.with_user(gerente).unlink()
        self.assertFalse(ajuste.exists())

    # ── 10. rechazos ───────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_10_se_rechaza_la_regla_no_ajustable_la_de_otra_estructura_y_la_de_varias_novedades(self):
        recibo = self._recibo()
        with self.assertRaises(ValidationError):                              # NETO es derivado: no es ajustable
            self.Ajuste.create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_NETO').id, 'amount': 1.0})
        with self.assertRaises(ValidationError):                              # regla de la estructura de prima
            self.Ajuste.create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_PRIMA_VALOR', self.prima).id, 'amount': 1.0})
        for monto in (100000.0, 50000.0):
            self.env['hr.payslip.input'].create({
                'payslip_id': recibo.id, 'input_type_id': self.tipo_bonif_nosal.id, 'code': 'CO_BONIF_NOSAL', 'amount': monto})
        with self.assertRaises(ValidationError):                              # dos novedades del mismo código: se editan las novedades
            self.Ajuste.create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_BONIF_NOSAL').id, 'amount': 1.0})

    # ── 11. copia ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_11_la_copia_del_recibo_no_copia_los_ajustes(self):
        recibo = self._recibo()
        self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        self.assertFalse(self.env['hr.payslip']._fields['l10n_co_ajuste_ids'].copy)
        self.assertNotIn('l10n_co_ajuste_ids', recibo.copy_data()[0])

    # ── 12. rastro en el chatter ───────────────────────────────────────────────────────────────────────────────────────────────
    def test_12_el_chatter_trae_regla_sugerido_anterior_nuevo_y_usuario(self):
        recibo = self._recibo()
        sugerido = self._total(recibo, 'CO_SALUD_EMP')
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        moneda = recibo.company_id.currency_id
        notas = self._notas(recibo)
        self.assertIn('Ajuste creado', notas)
        self.assertIn('CO_SALUD_EMP', notas)
        # .293: los importes salen con el formato monetario de la compañía (símbolo, separadores y decimales de la moneda), como en pantalla.
        self.assertIn('Sugerido: %s' % moneda.format(sugerido), notas)
        self.assertIn('Nuevo: %s' % moneda.format(0.0), notas)
        self.assertNotIn('%.2f' % sugerido, notas, 'Sin el formato crudo «%.2f» (sin separadores de miles)')
        self.assertIn(self.env.user.name, notas)
        ajuste.write({'amount': round(sugerido / 2.0 / ajuste.quantity * 100.0 / ajuste.rate, 2)})
        self.assertIn('Ajuste cambiado', self._notas(recibo))
        self.assertIn('Anterior: %s' % moneda.format(0.0), self._notas(recibo))
        ajuste.unlink()
        self.assertIn('Ajuste eliminado', self._notas(recibo))

    # ── 13. (TL a) aislamiento por compañía ────────────────────────────────────────────────────────────────────────────────────
    def test_13_el_ajuste_de_un_recibo_de_la_compania_a_es_invisible_e_inaplicable_desde_la_compania_b(self):
        recibo = self._recibo()
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        usuario_b = self._usuario('gerente_ajustes_b', (_G_MANAGER, 'base.group_user'), self.company_b)
        usuario_ab = self._usuario('gerente_ajustes_ab', (_G_MANAGER, 'base.group_user'), self.company | self.company_b)
        self.assertFalse(self.Ajuste.with_user(usuario_b).search([('id', '=', ajuste.id)]), 'Invisible desde la compañía B')
        self.assertFalse(self.Ajuste.with_user(usuario_b).with_context(allowed_company_ids=[self.company_b.id]).search([]))
        with self.assertRaises(AccessError):                                  # ni leerlo, ni cambiarlo
            ajuste.with_user(usuario_b).read(['amount'])
        with self.assertRaises(AccessError):
            ajuste.with_user(usuario_b).write({'amount': 5.0})
        with self.assertRaises(AccessError):                                  # ni crear uno en un recibo de la compañía A
            self.Ajuste.with_user(usuario_b).create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_PENSION_EMP').id, 'amount': 0.0})
        con_ambas = self.Ajuste.with_user(usuario_ab).with_context(allowed_company_ids=[self.company.id, self.company_b.id])
        self.assertEqual(con_ambas.search([('id', '=', ajuste.id)]), ajuste, 'Con acceso a la compañía A sí se ve')
        solo_b = self.Ajuste.with_user(usuario_ab).with_context(allowed_company_ids=[self.company_b.id])
        self.assertFalse(solo_b.search([('id', '=', ajuste.id)]), 'Con solo la compañía B activa en el selector tampoco')
        self.assertEqual(ajuste.company_id, self.company)

    # ── 14. un ajuste por regla y recibo (Q7 de TL) ────────────────────────────────────────────────────────────────────────────
    def test_14_solo_un_ajuste_por_regla_y_recibo(self):
        recibo = self._recibo()
        self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Ajuste.create({'slip_id': recibo.id, 'salary_rule_id': self._regla('CO_SALUD_EMP').id, 'amount': 1.0})

    # ── 15. dos cálculos en la misma transacción (N2 «co» de .289: test_02 y test_03 caían en el cálculo siguiente al ajuste) ────
    def test_15_el_sugerido_se_registra_en_cada_calculo_aunque_ya_exista_un_entorno_con_el_mismo_contexto(self):
        """``Environment.__new__`` (``odoo/api.py:570``) recorre ``transaction.envs`` y devuelve el entorno que ya existe si
        ``(cr, uid, su, uid_origin, context)`` es IGUAL POR VALOR (``:584-587``): un ``{}`` nuevo es igual a un ``{}`` viejo. Sin el token
        ``ne_calculo`` de ``compute_sheet`` el cálculo recibía el entorno del cálculo anterior con SU diccionario ``ne_sugeridos``: el gancho
        escribía allí, ``_ne_registrar_ajustes`` leía otro, vacío, y el ajuste quedaba «sin línea» aunque sí se aplicaba. ``previo`` mantiene VIVO
        a propósito un entorno con el contexto que dejaba el cálculo anterior (``with_company`` + ``ne_sugeridos={}``): así la prueba no depende de
        cuándo el recolector de basura suelte el entorno viejo."""
        recibo = self._recibo()                                  # cálculo 1, sin ajuste: su diccionario de sugeridos quedaba vacío
        sugerido = self._total(recibo, 'CO_SALUD_EMP')
        previo = recibo.with_company(recibo.company_id).with_context(ne_sugeridos={})
        ajuste = self._ajustar(recibo, 'CO_SALUD_EMP', amount=0.0)
        recibo.compute_sheet()                                   # cálculo 2: el primero que ve el ajuste
        self.assertEqual(ajuste.estado, 'aplicado', 'El gancho vio el ajuste y el registro halló lo sugerido')
        self.assertAlmostEqual(ajuste.sugerido_total, sugerido, delta=0.01)
        self.assertFalse(previo.env.context['ne_sugeridos'], 'El diccionario del entorno viejo no se usó')
        self.assertEqual(self._total(recibo, 'CO_SALUD_EMP'), 0.0)
        recibo.compute_sheet()                                   # cálculos 3 y 4, seguidos
        recibo.compute_sheet()
        self.assertEqual(ajuste.estado, 'aplicado')
        self.assertAlmostEqual(ajuste.sugerido_total, sugerido, delta=0.01)
        self.assertNotIn('no se aplicó en este cálculo', self._notas(recibo))
