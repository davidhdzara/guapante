# -*- coding: utf-8 -*-
"""E11 pieza 4a (.294, doc 74 §3): pestaña «Cálculo del salario» por secciones, de SOLO LECTURA (soporte de auditoría UGPP).

.298 (decisión de David, 22-nov): la pestaña lleva SOLO Bases, Aportes de la empresa y Provisiones, con el total «Costo empresa» al pie; el sueldo, los
devengos y las deducciones están en «Conceptos de pago». Regla de David: los conceptos se MUEVEN (se agrega una bonificación, se ajusta un devengado) y el
cálculo es informativo: lo sigue. La prueba 14 lo verifica con las cifras de un cálculo manual.

Qué se prueba: la vista (página por @name, solo para estructuras con el interruptor, sin estilos propios, de solo lectura y con el costo de la empresa al
pie); las secciones y su orden; lo que NO aparece (BASIC/GROSS/NET, los conceptos, totales y filas en cero); los días cotizados como número; que las filas se
actualizan solas y nunca cambian el cálculo; que nadie las escribe (ni un gerente: solo la regeneración); la visibilidad por compañía; la función de datos
para los recibos que ya existen; los datos nuevos (sección «bases» de los acumuladores, nombres sin «(interno)»); y que la colilla sigue la estructura de
«Conceptos de pago» sin bases ni costo de la empresa. NO EJECUTADAS en Odoo al escribirlas."""

from datetime import date

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged
from .common_diario import fijar_diario_de_salarios

_GRUPO_GERENTE = 'hr_payroll.group_hr_payroll_manager'
_GRUPO_USUARIO = 'hr_payroll.group_hr_payroll_user'


@tagged('post_install', '-at_install')
class TestCalculoDelSalario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Cálculo A'))
        cls.company_b = cls.env['res.company'].create(dict(valores, name='Compañía Cálculo B'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Cálculo', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.Calculo = cls.env['l10n.co.payslip.calculo']
        fijar_diario_de_salarios(cls.env, cls.general)      # .296: ``Form`` exige el diario; no se toma de la base
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, estructura=None, desde=date(2026, 9, 1), hasta=date(2026, 9, 15), compania=None):
        type(self).n += 1
        compania = compania or self.company
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Cálculo %s' % self.n,
            'company_id': compania.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Cálculo %s' % self.n, 'employee_id': empleado.id, 'company_id': compania.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Cálculo %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': compania.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        return recibo

    def _filas(self, recibo):
        return recibo.l10n_co_calculo_ids.sorted(lambda f: (f.sequence, f.id))

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _usuario(self, login, grupos, companias):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': companias[0].id,
            'company_ids': [(6, 0, companias.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    # ── la vista ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_01_la_vista_carga_con_la_pagina_por_nombre_de_solo_lectura_y_sin_estilos_propios(self):
        vista = self.env['hr.payslip'].get_view(view_type='form')
        arch = etree.fromstring(vista['arch'].encode('utf-8') if isinstance(vista['arch'], str) else vista['arch'])
        paginas = arch.xpath("//page[@name='calculo_del_salario']")
        self.assertEqual(len(paginas), 1, 'Falta la pestaña «Cálculo del salario» en la vista del recibo')
        pagina = paginas[0]
        self.assertEqual(pagina.get('invisible'), 'not l10n_co_ne_usa_conceptos')
        nativa = arch.xpath("//page[@name='salary_computation']")
        self.assertEqual(len(nativa), 1)
        self.assertEqual(nativa[0].get('invisible'), 'l10n_co_ne_usa_conceptos', 'La pestaña nativa solo se oculta en estructuras con conceptos')
        campo = pagina.xpath(".//field[@name='l10n_co_calculo_ids']")[0]
        self.assertEqual(campo.get('widget'), 'section_and_note_one2many')
        self.assertIn(campo.get('readonly'), ('1', 'True', 'true'), 'Solo lectura: sin «Agregar», sin papelera, sin edición')
        self.assertFalse(campo.xpath(".//control"), 'Sin acciones de agregar')
        self.assertTrue(campo.xpath(".//list/field[@name='display_type']"))
        self.assertFalse(pagina.xpath(".//*[@style]"), 'Sin estilos propios')
        self.assertFalse(pagina.xpath(".//i"), 'Sin íconos propios')
        texto = etree.tostring(pagina, encoding='unicode')
        for prohibido in ('text-muted', 'decoration-', 'fa fa-'):
            self.assertNotIn(prohibido, texto)
        # .298: el pie lleva SOLO el total «Costo empresa» (los totales de devengado, deducciones y neto son de «Conceptos de pago»)
        pie = [c.get('name') for c in pagina.xpath(".//group[@name='calculo_totales']/field")]
        self.assertEqual(pie, ['l10n_co_costo_empresa'])

    def _columnas_de(self, pagina_name, lista='l10n_co_calculo_ids'):
        arch = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode('utf-8'))
        campo = arch.xpath("//page[@name='%s']//field[@name='%s']" % (pagina_name, lista))[0]
        return {c.get('name'): c for c in campo.xpath('.//list/field')}, [c.get('name') for c in campo.xpath('.//list/field')]

    def test_01b_columna_cuenta_visible_en_calculo_y_oculta_en_conceptos_y_sin_ruido_en_las_filas_de_uno_y_cien_por_ciento(self):
        """Ajuste de David (22-nov): columna «Cuenta» (optional="show" en «Cálculo del salario», "hide" en «Conceptos de pago», sin el diario), «Concepto | Cuenta | Importe |
        Total» y sin Cantidad, Unidad ni % en las filas de cantidad 1 y 100 %."""
        calculo, orden = self._columnas_de('calculo_del_salario')
        self.assertEqual(calculo['cuenta'].get('optional'), 'show')
        self.assertLess(orden.index('name'), orden.index('cuenta'))
        self.assertLess(orden.index('cuenta'), orden.index('amount'))
        for nombre in ('quantity', 'unidad'):
            self.assertEqual(calculo[nombre].get('invisible'), 'quantity == 1 and rate == 100', nombre)
        self.assertEqual(calculo['rate'].get('invisible'), 'rate == 100')
        conceptos, orden_c = self._columnas_de('conceptos_de_pago', 'l10n_co_concepto_ids')
        self.assertEqual(conceptos['cuenta'].get('optional'), 'hide')
        self.assertLess(orden_c.index('salary_rule_id'), orden_c.index('cuenta'), 'Con el selector, «Concepto» es la regla: Concepto | Cuenta | Importe | Total')
        self.assertLess(orden_c.index('cuenta'), orden_c.index('amount'))
        for nombre in ('quantity', 'unidad'):
            self.assertEqual(conceptos[nombre].get('invisible'), 'quantity == 1 and rate == 100 and not edita_cantidad', 'Una fila editable sí muestra la cantidad: %s' % nombre)
        self.assertIn('rate == 100', conceptos['rate'].get('invisible'))
        self.assertNotIn('journal_id', calculo)
        self.assertNotIn('journal_id', conceptos)

    def test_17_la_cuenta_es_la_de_debito_si_el_valor_es_positivo_y_la_de_credito_si_es_negativo_de_la_compania_del_recibo(self):
        recibo = self._recibo()
        Cuenta = self.env['account.account'].with_company(self.company)
        gasto = Cuenta.create({'code': '510506', 'name': 'Sueldos de prueba', 'account_type': 'expense'})
        por_pagar = Cuenta.create({'code': '250501', 'name': 'Salarios por pagar de prueba', 'account_type': 'liability_current', 'reconcile': True})
        sueldo = self.env['hr.salary.rule'].search([('code', '=', 'CO_BASICO'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        salud = self.env['hr.salary.rule'].search([('code', '=', 'CO_SALUD_EMP'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        sueldo.with_company(self.company).write({'account_debit': gasto.id, 'account_credit': por_pagar.id})
        salud.with_company(self.company).write({'account_debit': False, 'account_credit': por_pagar.id})
        self.assertEqual(sueldo._ne_cuenta_contable(100.0, self.company), gasto.display_name, 'Positivo: la de débito')
        self.assertEqual(sueldo._ne_cuenta_contable(-100.0, self.company), por_pagar.display_name, 'Negativo: la de crédito')
        self.assertEqual(salud._ne_cuenta_contable(100.0, self.company), por_pagar.display_name, 'Positivo sin débito: la otra')
        self.assertEqual(salud._ne_cuenta_contable(-100.0, self.company), por_pagar.display_name)
        sin_cuentas = self.env['hr.salary.rule'].search([('code', '=', 'CO_AUX_TRANS'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        self.assertFalse(sin_cuentas.with_company(self.company).account_debit or sin_cuentas.with_company(self.company).account_credit, 'Premisa')
        self.assertFalse(sin_cuentas._ne_cuenta_contable(100.0, self.company), 'Sin cuenta: vacío, no se inventa')
        self.assertFalse(sueldo._ne_cuenta_contable(100.0, self.company_b), 'Las cuentas son de cada compañía: la otra no tiene')
        # en las filas de las dos pestañas, al calcular
        self.Calculo._regenerar_de_recibos(recibo)
        self.env['l10n.co.payslip.concepto']._regenerar_de_recibos(recibo)
        fila_sueldo = recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id == sueldo)
        self.assertEqual(fila_sueldo.cuenta, gasto.display_name)
        fila_salud = recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id == salud)
        self.assertEqual(fila_salud.cuenta, por_pagar.display_name)
        en_calculo = self._filas(recibo).filtered(lambda f: f.salary_rule_id == salud)
        self.assertEqual(en_calculo.cuenta, por_pagar.display_name, 'También en «Cálculo del salario» (aportes del empleado)')
        sin_regla = recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'dias' or f.display_type)
        self.assertFalse(any(sin_regla.mapped('cuenta')), 'Las filas de días y los títulos no llevan cuenta')

    def test_02_la_vista_heredada_no_selecciona_por_string(self):
        arch = etree.fromstring(self.env.ref('l10n_co_nomina_electronica.view_payslip_form_ne_calculo').arch_db.encode('utf-8'))
        for xpath in arch.xpath('//xpath'):
            self.assertNotIn('@string', xpath.get('expr') or '', 'La herencia debe anclar por @name')
            self.assertNotIn('@help', xpath.get('expr') or '')

    def test_03_solo_las_estructuras_con_el_interruptor_tienen_filas(self):
        general = self._recibo()
        self.assertTrue(general.l10n_co_ne_usa_conceptos)
        self.assertTrue(general.l10n_co_calculo_ids)
        prima = self._recibo(estructura=self.prima, desde=date(2026, 7, 1), hasta=date(2026, 12, 31))
        self.assertFalse(prima.l10n_co_calculo_ids, 'La estructura de prima no usa «Conceptos de pago»: la pestaña nativa queda igual')
        self.prima.l10n_co_ne_conceptos_de_pago = True
        prima.compute_sheet()
        self.assertTrue(prima.l10n_co_calculo_ids, 'Al activar el interruptor de la estructura, el siguiente cálculo genera las filas')

    # ── las filas ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_04_solo_bases_aportes_del_empleado_aportes_de_la_empresa_y_provisiones_sin_las_nativas_ni_los_totales(self):
        recibo = self._recibo()
        filas = self._filas(recibo)
        titulos = [f.name for f in filas if f.display_type == 'line_section']
        self.assertEqual(titulos[0], 'Bases', 'Las bases van primero')
        for fuera in ('Básico', 'Devengos', 'Deducciones'):
            self.assertNotIn(fuera, titulos, '.298: %s ya no está aquí: es de «Conceptos de pago»' % fuera)
        self.assertEqual(titulos[1], 'Aportes del empleado', 'Ajuste de David (22-nov): los aportes del empleado, informativos, entre las bases y los de la empresa')
        costo = titulos[2:]
        self.assertTrue(costo, 'Los aportes de la empresa y las provisiones salen cada uno en su sección (el nombre de su categoría)')
        codigos = set(filas.filtered('line_id').mapped('line_id.code'))
        for ausente in ('BASIC', 'GROSS', 'NET', 'CO_BRUTO', 'CO_NETO', 'CO_BASICO', 'CO_AUX_TRANS'):
            self.assertNotIn(ausente, codigos, '%s no se muestra (es de «Conceptos de pago» o su categoría no tiene sección)' % ausente)
        self.assertIn('CO_IBC_SP', codigos, 'Las bases (acumuladores) sí se muestran')
        for linea in filas.filtered('line_id').mapped('line_id'):
            if linea.category_id.l10n_co_ne_aportes_empleado:
                continue
            self.assertIn(linea.category_id.l10n_co_ne_seccion_concepto, ('bases', 'costo_empresa'), linea.code)

    def test_04b_los_aportes_del_empleado_salen_informativos_en_su_seccion_y_no_suman_al_costo_empresa(self):
        """Ajuste de David (22-nov): salud, pensión y FSP del EMPLEADO en «Cálculo del salario», sección propia entre Bases y Aportes de la empresa. Siguen también como
        deducción en «Conceptos de pago» y no suman al «Costo empresa»."""
        categoria = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_seguridad_social_emp')
        self.assertTrue(categoria.l10n_co_ne_aportes_empleado, 'La siembra marca la categoría de seguridad social del empleado')
        otras = self.env['hr.salary.rule.category'].search([('l10n_co_ne_aportes_empleado', '=', True), ('id', '!=', categoria.id)])
        self.assertFalse(otras, 'Solo esa categoría')
        recibo = self._recibo()
        filas = self._filas(recibo)
        seccion_de, titulo = {}, None
        for fila in filas:
            if fila.display_type == 'line_section':
                titulo = fila.name
            elif fila.line_id:
                seccion_de[fila.line_id.code] = titulo
        lineas = recibo.line_ids.filtered(lambda l: l.total and l.category_id == categoria)
        self.assertTrue({'CO_SALUD_EMP', 'CO_PENSION_EMP'} <= set(lineas.mapped('code')), 'Premisa: salud y pensión del empleado con valor')
        for linea in lineas:
            self.assertEqual(seccion_de[linea.code], 'Aportes del empleado', linea.code)
            fila = filas.filtered(lambda f: f.line_id == linea)
            self.assertEqual(fila.total, linea.total, linea.code)
        # siguen en «Conceptos de pago» (deducciones) y NO suman al costo de la empresa
        en_conceptos = recibo.l10n_co_concepto_ids.filtered(lambda f: f.line_id in lineas)
        self.assertEqual(len(en_conceptos), len(lineas))
        costo = sum(l.total for l in recibo.line_ids if l.category_id.l10n_co_ne_seccion_concepto == 'costo_empresa')
        self.assertAlmostEqual(recibo.l10n_co_costo_empresa, costo, delta=0.01)

    def test_04d_las_bases_de_la_retencion_salen_solo_si_el_recibo_tiene_retencion(self):
        """Ajuste de David (22-nov): sin retención en la fuente ver «Retención Fuente - Base Bruto / Base salarial» confunde. Con una línea de retención con valor vuelven a salir."""
        marcadas = self.env['hr.salary.rule'].search([('l10n_co_ne_calculo_si_retencion', '=', True)])
        self.assertEqual(set(marcadas.mapped('code')), {'CO_RETEFUENTE_BASE_GROSS', 'CO_RETEFUENTE_BASE_IBC'}, 'La siembra marca solo las dos bases')
        recibo = self._recibo()
        bases = recibo.line_ids.filtered(lambda l: l.code in ('CO_RETEFUENTE_BASE_GROSS', 'CO_RETEFUENTE_BASE_IBC') and l.total)
        self.assertTrue(bases, 'Premisa: el recibo calcula las bases de la retención')
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_RETEFUENTE' and l.total), 'Premisa: con 3.000.000 no hay retención')
        codigos = set(self._filas(recibo).filtered('line_id').mapped('line_id.code'))
        self.assertFalse(codigos & {'CO_RETEFUENTE_BASE_GROSS', 'CO_RETEFUENTE_BASE_IBC'}, 'Sin retención no salen las bases de la retención')
        self.assertIn('CO_IBC_SP', codigos, 'Las demás bases salen igual')
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_RETEFUENTE'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        self.assertEqual(regla.l10n_co_tercero_origen, 'company_dian', 'Premisa: la retención es de la DIAN')
        self.env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': 'CO_RETEFUENTE', 'name': regla.name, 'category_id': regla.category_id.id,
            'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id, 'quantity': 1.0, 'rate': 100.0, 'amount': -50000.0, 'total': -50000.0})
        self.Calculo._regenerar_de_recibos(recibo)
        codigos = set(self._filas(recibo).filtered('line_id').mapped('line_id.code'))
        self.assertTrue({'CO_RETEFUENTE_BASE_GROSS', 'CO_RETEFUENTE_BASE_IBC'} <= codigos, 'Con retención vuelven a salir')

    def test_04c_el_fsp_sale_en_la_seccion_de_aportes_del_empleado_solo_si_aplica(self):
        """Con un sueldo bajo no hay fondo de solidaridad pensional: la sección lleva solo salud y pensión. Con una línea de FSP con valor, sale ahí."""
        recibo = self._recibo()
        self.assertFalse(recibo.line_ids.filtered(lambda l: l.code == 'CO_FSP' and l.total), 'Premisa: con 3.000.000 no aplica el FSP')
        self.assertNotIn('CO_FSP', self._filas(recibo).filtered('line_id').mapped('line_id.code'))
        fsp = self.env['hr.salary.rule'].search([('code', '=', 'CO_FSP'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        linea = self.env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': fsp.id, 'code': 'CO_FSP', 'name': fsp.name, 'category_id': fsp.category_id.id,
            'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id, 'quantity': 1.0, 'rate': 100.0, 'amount': -30000.0, 'total': -30000.0})
        self.Calculo._regenerar_de_recibos(recibo)
        fila = self._filas(recibo).filtered(lambda f: f.line_id == linea)
        self.assertEqual(len(fila), 1)
        orden = self._filas(recibo)
        titulo = [f.name for f in orden[:list(orden.ids).index(fila.id)] if f.display_type == 'line_section'][-1]
        self.assertEqual(titulo, 'Aportes del empleado')

    def test_05_las_bases_los_aportes_de_la_empresa_y_las_provisiones_van_en_su_seccion(self):
        recibo = self._recibo()
        filas = self._filas(recibo)
        seccion_de = {}
        titulo = None
        for fila in filas:
            if fila.display_type == 'line_section':
                titulo = fila.name
            elif fila.line_id:
                seccion_de[fila.line_id.code] = titulo
        self.assertEqual(seccion_de['CO_IBC_SALARIAL'], 'Bases')
        categoria_aportes = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_seguridad_social_cia')
        categoria_provisiones = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_provisiones')
        for linea in recibo.line_ids.filtered(lambda l: l.total and l.category_id == categoria_aportes):
            self.assertEqual(seccion_de[linea.code], categoria_aportes.name, linea.code)
        for linea in recibo.line_ids.filtered(lambda l: l.total and l.category_id == categoria_provisiones):
            self.assertEqual(seccion_de[linea.code], categoria_provisiones.name, linea.code)

    def test_06_solo_filas_con_valor_o_ajustadas_y_cada_una_con_los_valores_de_su_linea(self):
        recibo = self._recibo()
        for fila in self._filas(recibo).filtered('line_id'):
            self.assertTrue(fila.total or fila.ajustado, '%s: una fila en cero no se muestra' % fila.name)
            linea = fila.line_id
            self.assertEqual((fila.name, fila.quantity, fila.rate, fila.amount, fila.total), (linea.name, linea.quantity, linea.rate, linea.amount, linea.total))

    def test_07_los_dias_cotizados_se_muestran_como_numero_y_coinciden_con_su_linea(self):
        recibo = self._recibo()
        linea = self._linea(recibo, 'CO_DIAS_SP')
        self.assertTrue(linea and linea.total, 'Premisa: el recibo tiene días cotizados')
        fila = self._filas(recibo).filtered(lambda f: f.line_id == linea)
        self.assertEqual(len(fila), 1)
        self.assertEqual(fila.total, linea.total)
        self.assertFalse(fila.unidad, 'No se cambia la fórmula de los acumuladores ni se les pone unidad: el número de días va en el Total')
        self.assertNotIn('(interno)', fila.name)

    def test_08_las_filas_guardadas_son_lo_que_arma_el_modelo_despues_de_ajustar_un_concepto(self):
        recibo = self._recibo()
        fila_concepto = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.salary_rule_id.code == 'CO_BASICO')
        indice = recibo.l10n_co_concepto_ids.ids.index(fila_concepto.id)
        with Form(recibo) as formulario:
            with formulario.l10n_co_concepto_ids.edit(indice) as editada:
                editada.amount = fila_concepto.amount + 1000.0
        filas = self._filas(recibo)
        esperado = self.Calculo._valores_del_recibo(recibo)
        guardado = [(f.display_type, f.name, f.line_id.id, f.total) for f in filas]
        self.assertEqual(guardado, [(v.get('display_type', False), v['name'], v.get('line_id', False), v.get('total', 0.0)) for v in esperado])

    def test_09_regenerar_las_filas_no_cambia_ningun_valor_del_recibo(self):
        recibo = self._recibo()

        def foto():
            return sorted((l.code, l.amount, l.quantity, l.rate, l.total) for l in recibo.line_ids), recibo._ne_pdf_neto(), recibo.net_wage

        antes = foto()
        recibo._ne_regenerar_conceptos()
        self.assertEqual(antes, foto())
        recibo.compute_sheet()
        self.assertEqual(antes, foto(), 'Recalcular tampoco: las filas son una vista, nada las lee para calcular')

    # ── solo lectura y permisos ───────────────────────────────────────────────────────────────────────────────────────────────
    def test_10_nadie_escribe_las_filas_ni_un_gerente_solo_la_regeneracion(self):
        recibo = self._recibo()
        fila = self._filas(recibo).filtered('line_id')[:1]
        with self.assertRaises(UserError):
            self.Calculo.create({'slip_id': recibo.id, 'name': 'Concepto a mano'})
        with self.assertRaises(UserError):
            fila.write({'name': 'Otro nombre'})
        with self.assertRaises(UserError):
            fila.unlink()
        with self.assertRaises(UserError):
            recibo.write({'l10n_co_calculo_ids': [(0, 0, {'name': 'Desde el recibo'})]})
        gerente = self._usuario('calculo_gerente', [_GRUPO_GERENTE], self.company)
        # ``assertRaises`` de Odoo 18 no acepta una tupla (``odoo/tests/common.py:490`` hace ``issubclass(exception, AccessError)``: TypeError). ``AccessError`` es
        # subclase de ``UserError`` (``odoo/exceptions.py:64``): ``UserError`` cubre el error del modelo y el de acceso.
        with self.assertRaises(UserError):
            self.Calculo.with_user(gerente).create({'slip_id': recibo.id, 'name': 'Gerente a mano'})
        self.assertEqual(len(self.Calculo.with_user(gerente).search([('slip_id', '=', recibo.id)])), len(self._filas(recibo)), 'El gerente sí las lee')

    def test_11_el_usuario_de_nomina_las_lee_y_no_las_escribe_y_la_otra_compania_no_las_ve(self):
        recibo = self._recibo()
        usuario = self._usuario('calculo_usuario', [_GRUPO_USUARIO], self.company)
        self.assertTrue(self.Calculo.with_user(usuario).search([('slip_id', '=', recibo.id)]))
        with self.assertRaises(UserError):                       # ``AccessError`` hereda de ``UserError``: ver la prueba anterior
            self.Calculo.with_user(usuario).search([('slip_id', '=', recibo.id)], limit=1).write({'name': 'x'})
        usuario_b = self._usuario('calculo_otra_compania', [_GRUPO_GERENTE], self.company_b)
        self.assertFalse(self.Calculo.with_user(usuario_b).search([('slip_id', '=', recibo.id)]), 'Las filas de la compañía A no se ven desde la B')
        self.assertEqual(self._filas(recibo).mapped('company_id'), self.company)

    def test_12_la_funcion_de_datos_genera_las_filas_de_los_recibos_que_no_las_tienen_incluso_hechos(self):
        recibo = self._recibo()
        antes = [(f.display_type, f.name, f.total) for f in self._filas(recibo)]
        self.assertTrue(antes)
        self.Calculo.sudo().with_context(ne_regenerar_calculo=True).search([('slip_id', '=', recibo.id)]).unlink()
        recibo.invalidate_recordset(['l10n_co_calculo_ids'])
        self.assertFalse(recibo.l10n_co_calculo_ids)
        recibo.write({'state': 'done'})
        neto = recibo._ne_pdf_neto()
        self.env['hr.payslip']._ne_generar_conceptos_pendientes()
        self.assertEqual([(f.display_type, f.name, f.total) for f in self._filas(recibo)], antes, 'Las filas vuelven a ser las mismas')
        self.assertEqual((recibo.state, recibo._ne_pdf_neto()), ('done', neto), 'Sin recalcular ni cambiar el estado')

    def test_12b_la_funcion_de_datos_regenera_el_calculo_de_los_recibos_en_borrador_y_en_espera_y_no_toca_los_hechos(self):
        """H-QA-040 (QA sobre .298, pedido del TL): un recibo en borrador o en espera con filas de una versión anterior las recibe nuevas en el -u; los hechos y pagados son
        históricos y se quedan como están (aunque tengan filas viejas), porque la función solo genera lo que les falta."""
        borrador, espera, hecho, pagado = self._recibo(), self._recibo(), self._recibo(), self._recibo()
        espera.write({'state': 'verify'})
        hecho.write({'state': 'done'})
        pagado.write({'state': 'paid'})
        recibos = borrador | espera | hecho | pagado
        actuales = {r.id: [(f.display_type, f.name, f.total) for f in self._filas(r)] for r in recibos}
        for recibo in recibos:
            self.assertTrue(actuales[recibo.id], 'Premisa: tiene filas')
            self.Calculo.sudo().with_context(ne_regenerar_calculo=True).search([('slip_id', '=', recibo.id)]).unlink()
            self.Calculo.sudo().with_context(ne_regenerar_calculo=True).create({'slip_id': recibo.id, 'name': 'Fila de una versión anterior', 'sequence': 10})
        neto = {r.id: r._ne_pdf_neto() for r in recibos}
        self.env['hr.payslip']._ne_generar_conceptos_pendientes()
        for recibo in borrador | espera:
            self.assertEqual([(f.display_type, f.name, f.total) for f in self._filas(recibo)], actuales[recibo.id], 'Borrador y en espera: regenerado')
        for recibo in hecho | pagado:
            self.assertEqual([f.name for f in self._filas(recibo)], ['Fila de una versión anterior'], 'Hecho y pagado: histórico, queda como está')
        for recibo in recibos:
            self.assertEqual(recibo._ne_pdf_neto(), neto[recibo.id], 'Nada se recalcula')

    # ── datos nuevos ───────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_13_los_acumuladores_son_la_seccion_bases_y_sus_nombres_no_dicen_interno(self):
        acumuladores = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_acumuladores_internos')
        self.assertEqual(acumuladores.l10n_co_ne_seccion_concepto, 'bases')
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        reglas = self.env['hr.salary.rule'].with_context(active_test=False).browse(datos.mapped('res_id')).exists()
        self.assertTrue(reglas)
        for regla in reglas:
            self.assertNotIn('(interno)', regla.name, regla.code)
            self.assertNotIn('(acumulador interno)', regla.name, regla.code)
        self.assertFalse(reglas.filtered(lambda r: r.category_id == acumuladores).filtered('l10n_co_ne_ajustable'),
                         'Las bases no son ajustables: solo devengados y deducciones')

    def test_13b_las_bases_salariales_no_se_llaman_ibc_de_seguridad_social_junto_al_ibc_de_los_aportes(self):
        """H-QA-042 (QA sobre .298): «Base IBC Seguridad Social» (875.452,50) y «Retención Fuente - Base IBC» se veían junto a «IBC Salud y Pensión» (945.271,50): un
        auditor no debe ver dos IBC de seguridad social distintos sin explicación. Son bases SALARIALES (antes del exceso del 40 %, que la fila de .299-1 explica) y se
        llaman así; el único «IBC Salud y Pensión» es el de los aportes."""
        regla = self.env['hr.salary.rule']
        ss = regla.search([('code', '=', 'CO_SS_BASE_IBC')], limit=1)
        rete = regla.search([('code', '=', 'CO_RETEFUENTE_BASE_IBC')], limit=1)
        aportes = regla.search([('code', '=', 'CO_IBC_SP')], limit=1)
        self.assertIn('Base salarial', ss.name)
        self.assertIn('40 %', ss.name)
        self.assertIn('Base salarial', rete.name)
        for r in (ss, rete):
            self.assertNotIn('IBC', r.name, 'Sin la palabra IBC: la ve el auditor junto al IBC de los aportes')
            self.assertIn('CO_IBC_SP', r.note, 'La nota dice cuál es el IBC de los aportes')
        self.assertEqual(aportes.name, 'IBC Salud y Pension')
        recibo = self._recibo()
        nombres = [f.name for f in self._filas(recibo) if f.line_id]
        self.assertNotIn('Base IBC Seguridad Social', nombres)
        self.assertNotIn('Retención Fuente - Base IBC', nombres)
        self.assertEqual([n for n in nombres if 'IBC Salud' in n], [aportes.name], 'Un solo IBC de seguridad social en la pestaña')

    # ── .298: los conceptos se MUEVEN y el cálculo es informativo (regla de David) ─────────────────────────────────────────────
    def test_14_los_conceptos_se_mueven_y_el_calculo_los_sigue_con_las_cifras_de_un_calculo_manual(self):
        """Regla de David (22-nov): se agrega una bonificación SALARIAL y se ajusta un devengado desde «Conceptos de pago»; en «Cálculo del salario» cambian el
        IBC y los aportes de la empresa, y las cifras coinciden con las de un cálculo manual equivalente (mes completo de septiembre: 30 días de 30, sin
        ausencias; sueldo 3.000.000 → 100.000 por día).

        Las PROVISIONES también se mueven (.303, doc 78, decisión del TL del 22-nov): se calculan sobre la base prestacional DEVENGADA del recibo (el sueldo ajustado, la
        bonificación salarial y el auxilio de transporte para prima y cesantías; sin auxilio para vacaciones), no sobre el sueldo y el auxilio del contrato. Hasta .302 esta
        prueba afirmaba lo contrario («hoy no se mueven»)."""
        ref = self.env.ref
        recibo = self._recibo(desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
        fecha = recibo.date_from
        contrato = recibo.contract_id

        def parametro(codigo):
            return recibo._rule_parameter(codigo, fecha)

        def en_calculo():
            return {f.line_id.code: f.total for f in self._filas(recibo) if f.line_id}

        antes = en_calculo()
        self.assertAlmostEqual(antes['CO_IBC_SALARIAL'], contrato.wage, delta=0.01, msg='Premisa: sin movimientos el IBC es el sueldo')

        # 1. Bonificación salarial: fila nueva en «Conceptos de pago» con su tipo de novedad.
        bonificacion = 500000.0
        with Form(recibo) as formulario:
            with formulario.l10n_co_concepto_ids.new() as fila:
                fila.salary_rule_id = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_SAL'), ('struct_id', '=', recibo.struct_id.id)], limit=1)   # selector del concepto
                fila.amount = bonificacion
        # 2. Ajustar un devengado: el importe diario del sueldo básico pasa de 100.000 a 110.000.
        basico = recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id.code == 'CO_BASICO')
        self.assertEqual(len(basico), 1)
        indice = recibo.l10n_co_concepto_ids.ids.index(basico.id)
        with Form(recibo) as formulario:
            with formulario.l10n_co_concepto_ids.edit(indice) as fila:
                fila.amount = 110000.0
        basico = recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id.code == 'CO_BASICO')
        basico_nuevo = basico.quantity * 110000.0
        self.assertAlmostEqual(basico.total, basico_nuevo, delta=0.01)
        self.assertAlmostEqual(
            sum(recibo.l10n_co_concepto_ids.filtered(lambda f: f.salary_rule_id.code == 'CO_BONIF_SAL').mapped('total')), bonificacion, delta=0.01)

        despues = en_calculo()
        # Los conceptos NO se repiten aquí: se ven y se editan en «Conceptos de pago».
        for codigo in ('CO_BASICO', 'CO_BONIF_SAL'):
            self.assertNotIn(codigo, despues)

        # Cálculo manual. IBC = sueldo ajustado + bonificación salarial (sin ausencias, sin pagos no salariales pactados: no hay excedente del 40 %).
        ibc = basico_nuevo + bonificacion
        self.assertAlmostEqual(despues['CO_IBC_SALARIAL'], ibc, delta=0.01)
        self.assertAlmostEqual(despues['CO_IBC_SP'], ibc, delta=0.01)
        self.assertGreater(despues['CO_IBC_SP'], antes['CO_IBC_SP'], 'El IBC se movió con los conceptos')
        # Aportes de la empresa: IBC x porcentaje del parámetro.
        esperados = {
            'CO_PENSION_CIA': ibc * parametro('l10n_co_pct_pension_empleador') / 100.0,
            'CO_ARL_CIA': ibc * recibo._ne_pct_arl() / 100.0,
            'CO_CCF_CIA': ibc * parametro('l10n_co_pct_ccf') / 100.0}
        exonerado = recibo.company_id._is_exonerado_parafiscales(ibc, fecha)
        for codigo, pct in (('CO_SALUD_CIA', 'l10n_co_pct_salud_empleador'), ('CO_SENA_CIA', 'l10n_co_pct_sena'), ('CO_ICBF_CIA', 'l10n_co_pct_icbf')):
            if exonerado:
                self.assertNotIn(codigo, despues, '%s: exonerado (Ley 1607/2012)' % codigo)
            else:
                esperados[codigo] = ibc * parametro(pct) / 100.0
        for codigo, esperado in esperados.items():
            self.assertAlmostEqual(despues[codigo], esperado, delta=0.01, msg=codigo)
        for codigo in ('CO_PENSION_CIA', 'CO_ARL_CIA', 'CO_CCF_CIA'):
            self.assertGreater(despues[codigo], antes[codigo], '%s se movió con los conceptos' % codigo)
        # Provisiones (.303): cálculo manual sobre lo DEVENGADO del recibo. Prima y cesantías: sueldo ajustado + bonificación salarial + el auxilio de transporte que paga la
        # línea (Ley 1/1963 art. 7); vacaciones: sueldo ajustado + bonificación (sin auxilio, CST art. 192); intereses: sobre las cesantías. Todas se movieron respecto de antes.
        auxilio = sum(recibo.line_ids.filtered(lambda l: l.code == 'CO_AUX_TRANS').mapped('total'))
        base_prima_cesantias = basico_nuevo + bonificacion + auxilio
        base_vacaciones = basico_nuevo + bonificacion
        cesantias = base_prima_cesantias / parametro('l10n_co_divisor_prov_cesantias')
        provisiones = {
            'CO_PROV_PRIMA': base_prima_cesantias / parametro('l10n_co_divisor_prov_prima'), 'CO_PROV_CESANTIAS': cesantias,
            'CO_PROV_INT_CES': cesantias * parametro('l10n_co_pct_intereses_cesantias') / 100.0,
            'CO_PROV_VACACIONES': base_vacaciones * parametro('l10n_co_dias_mes_comercial') / parametro('l10n_co_divisor_vacaciones')}
        for codigo, esperado in provisiones.items():
            self.assertAlmostEqual(despues[codigo], esperado, delta=0.01, msg=codigo)
            self.assertGreater(despues[codigo], antes[codigo], '%s se movió con lo pagado' % codigo)
        # El total «Costo empresa» del pie es la suma de los aportes y las provisiones que muestra la pestaña.
        costo = sum(f.total for f in self._filas(recibo) if f.line_id and f.line_id.category_id.l10n_co_ne_seccion_concepto == 'costo_empresa')
        self.assertAlmostEqual(recibo.l10n_co_costo_empresa, costo, delta=0.01)
        self.assertGreater(costo, 0.0)

    def test_15_la_colilla_sigue_la_estructura_de_conceptos_de_pago_sin_bases_ni_costo_de_la_empresa(self):
        """Regla de David: la colilla tiene la MISMA estructura que «Conceptos de pago» (devengados y deducciones, con los totales y el neto): sin las
        bases ni el costo de la empresa, que son de «Cálculo del salario»."""
        recibo = self._recibo()
        colilla = recibo._ne_colilla()
        self.assertEqual([s['seccion'] for s in colilla['secciones']], ['devengados', 'deducciones'])
        filas = recibo._ne_filas_de_concepto()
        for fila in filas:
            self.assertIn(fila['linea'].category_id.l10n_co_ne_seccion_concepto, ('devengados', 'deducciones'), fila['linea'].code)
        self.assertEqual(sum(len(s['filas']) for s in colilla['secciones']), len(filas), 'Las mismas filas que «Conceptos de pago»')
        self.assertAlmostEqual(colilla['total_devengado'], recibo.l10n_co_total_devengado, delta=0.01)
        self.assertAlmostEqual(colilla['total_deducciones'], recibo.l10n_co_total_deducciones, delta=0.01)
        self.assertAlmostEqual(colilla['neto'], recibo.net_wage, delta=0.01)
        # Ajuste de David (22-nov): salud, pensión y FSP del empleado se muestran TAMBIÉN, a nivel informativo, en «Cálculo del salario»; el resto sigue sin repetirse.
        calculo = {l for l in self._filas(recibo).filtered('line_id').mapped('line_id') if not l.category_id.l10n_co_ne_aportes_empleado}
        self.assertFalse(calculo & set(f['linea'] for f in filas), 'Ninguna línea (salvo los aportes del empleado, informativos) está en la colilla y en «Cálculo del salario» a la vez')

    # ── .299 (c): la fila del exceso del 40 % ─────────────────────────────────────────────────────────────────────────────────
    def _fila_exceso(self, recibo):
        return self._filas(recibo).filtered(lambda f: not f.display_type and (f.name or '').startswith('Exceso del 40'))

    def test_16_la_fila_del_exceso_del_40_sale_al_final_de_bases_con_el_valor_manual(self):
        """Sueldo 3.000.000 + 3.000.000 de pagos no salariales POR PACTO (CO_BONIF_NOSAL): el 40 % de 6.000.000 son 2.400.000 y el exceso, 600.000, pasa al IBC de
        salud, pensión y ARL. Sin pactados no hay fila."""
        recibo = self._recibo(desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
        self.assertFalse(self._fila_exceso(recibo), 'Sin pagos pactados no hay fila del exceso')
        self.env['hr.payslip.input'].create({
            'payslip_id': recibo.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal').id,
            'code': 'CO_BONIF_NOSAL', 'amount': 3000000.0})
        recibo.compute_sheet()
        fila = self._fila_exceso(recibo)
        self.assertEqual(len(fila), 1)
        pct = recibo._rule_parameter('l10n_co_pct_tope_no_salarial', recibo.date_from)
        esperado = 3000000.0 - pct / 100.0 * (3000000.0 + 3000000.0)          # pactados - 40 % x (remuneración + pactados)
        self.assertAlmostEqual(fila.total, esperado, delta=0.01)
        self.assertGreater(fila.total, 0.0)
        self.assertFalse(fila.line_id, 'No es una línea del recibo: es informativa')
        filas = self._filas(recibo)
        siguiente = filas[list(filas.ids).index(fila.id) + 1]
        self.assertEqual(siguiente.display_type, 'line_section', 'Va al final de la sección «Bases»: lo que sigue es otra sección')
        # y es justo lo que suma al IBC de salud y pensión
        valores = {f.line_id.code: f.total for f in filas if f.line_id}
        self.assertAlmostEqual(valores['CO_IBC_SP'], valores['CO_IBC_SALARIAL'] + fila.total, delta=0.01)

    def test_17_con_pactados_bajo_el_40_la_fila_se_muestra_en_cero(self):
        recibo = self._recibo(desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
        self.env['hr.payslip.input'].create({
            'payslip_id': recibo.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_bonif_nosal').id,
            'code': 'CO_BONIF_NOSAL', 'amount': 500000.0})
        recibo.compute_sheet()
        fila = self._fila_exceso(recibo)
        self.assertEqual(len(fila), 1, 'Hay pagos pactados: la fila se muestra aunque el exceso sea cero (se revisó el límite)')
        self.assertEqual(fila.total, 0.0)

