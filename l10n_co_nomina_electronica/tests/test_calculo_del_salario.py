# -*- coding: utf-8 -*-
"""E11 pieza 4a (.294, doc 74 §3): pestaña «Cálculo del salario» por secciones, de SOLO LECTURA (soporte de auditoría UGPP).

Qué se prueba: la vista (página por @name, solo para estructuras con el interruptor, sin estilos propios y de solo lectura); las secciones en su orden
(Básico, Devengos, Bases, Deducciones y una por categoría de costo de la empresa); lo que NO aparece (BASIC/GROSS/NET, totales y filas en cero); la nota
del ajuste con su sugerido; los días cotizados como número; que las filas se actualizan solas (al ajustar un concepto) y nunca cambian el cálculo; que nadie
las escribe (ni un gerente: solo la regeneración); la visibilidad por compañía; la función de datos para los recibos que ya existen; y los datos nuevos
(sección «bases» de los acumuladores, nombres sin «(interno)»). NO EJECUTADAS en Odoo al escribirlas."""

from datetime import date

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

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
    def test_04_secciones_en_orden_y_sin_las_nativas_ni_los_totales(self):
        recibo = self._recibo()
        filas = self._filas(recibo)
        titulos = [f.name for f in filas if f.display_type == 'line_section']
        canonico = ['Básico', 'Devengos', 'Bases', 'Deducciones']
        self.assertEqual([t for t in titulos if t in canonico], [t for t in canonico if t in titulos], 'Orden: Básico, Devengos, Bases, Deducciones')
        for obligatoria in ('Básico', 'Bases', 'Deducciones'):
            self.assertIn(obligatoria, titulos)
        costo = [t for t in titulos if t not in canonico]
        self.assertTrue(costo, 'Los aportes de la empresa y las provisiones salen cada uno en su sección (el nombre de su categoría)')
        self.assertEqual(titulos.index(costo[0]), len([t for t in canonico if t in titulos]),
                         'Las secciones de costo de la empresa van DESPUÉS de las deducciones')
        codigos = set(filas.filtered('line_id').mapped('line_id.code'))
        for ausente in ('BASIC', 'GROSS', 'NET', 'CO_BRUTO', 'CO_NETO'):
            self.assertNotIn(ausente, codigos, '%s no se muestra (su categoría no tiene sección)' % ausente)
        self.assertIn('CO_BASICO', codigos)
        self.assertIn('CO_IBC_SP', codigos, 'Las bases (acumuladores) sí se muestran')

    def test_05_el_sueldo_va_solo_en_basico_y_los_aportes_de_la_empresa_y_provisiones_en_su_categoria(self):
        recibo = self._recibo()
        filas = self._filas(recibo)
        seccion_de = {}
        titulo = None
        for fila in filas:
            if fila.display_type == 'line_section':
                titulo = fila.name
            elif fila.line_id:
                seccion_de[fila.line_id.code] = titulo
        self.assertEqual(seccion_de['CO_BASICO'], 'Básico')
        self.assertEqual(seccion_de.get('CO_AUX_TRANS'), 'Devengos')
        self.assertEqual(seccion_de['CO_SALUD_EMP'], 'Deducciones')
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

    def test_08_se_actualiza_al_ajustar_un_concepto_desde_conceptos_de_pago_y_muestra_el_sugerido(self):
        recibo = self._recibo()
        fila_concepto = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.salary_rule_id.code == 'CO_SALUD_EMP')
        sugerido = fila_concepto.total
        self.assertLess(sugerido, 0.0, 'Premisa: la deducción de salud es negativa')
        indice = recibo.l10n_co_concepto_ids.ids.index(fila_concepto.id)
        with Form(recibo) as formulario:
            with formulario.l10n_co_concepto_ids.edit(indice) as editada:
                editada.amount = 0.0
        salud = self._filas(recibo).filtered(lambda f: f.line_id.code == 'CO_SALUD_EMP')
        self.assertEqual((salud.total, salud.ajustado), (0.0, True), 'La línea ajustada a 0 sigue visible y marcada')
        filas = self._filas(recibo)
        siguiente = filas[list(filas.ids).index(salud.id) + 1]
        self.assertEqual(siguiente.display_type, 'line_note')
        self.assertTrue(siguiente.name.startswith('Ajustado por la empresa. Sugerido:'))
        # las filas guardadas son exactamente lo que genera el armado sobre las líneas actuales
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
        with self.assertRaises((AccessError, UserError)):
            self.Calculo.with_user(gerente).create({'slip_id': recibo.id, 'name': 'Gerente a mano'})
        self.assertEqual(len(self.Calculo.with_user(gerente).search([('slip_id', '=', recibo.id)])), len(self._filas(recibo)), 'El gerente sí las lee')

    def test_11_el_usuario_de_nomina_las_lee_y_no_las_escribe_y_la_otra_compania_no_las_ve(self):
        recibo = self._recibo()
        usuario = self._usuario('calculo_usuario', [_GRUPO_USUARIO], self.company)
        self.assertTrue(self.Calculo.with_user(usuario).search([('slip_id', '=', recibo.id)]))
        with self.assertRaises((AccessError, UserError)):
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
