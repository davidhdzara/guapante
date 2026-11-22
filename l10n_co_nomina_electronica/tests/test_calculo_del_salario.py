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
    def test_04_solo_bases_aportes_de_la_empresa_y_provisiones_sin_las_nativas_ni_los_totales(self):
        recibo = self._recibo()
        filas = self._filas(recibo)
        titulos = [f.name for f in filas if f.display_type == 'line_section']
        self.assertEqual(titulos[0], 'Bases', 'Las bases van primero')
        for fuera in ('Básico', 'Devengos', 'Deducciones'):
            self.assertNotIn(fuera, titulos, '.298: %s ya no está aquí: es de «Conceptos de pago»' % fuera)
        costo = titulos[1:]
        self.assertTrue(costo, 'Los aportes de la empresa y las provisiones salen cada uno en su sección (el nombre de su categoría)')
        codigos = set(filas.filtered('line_id').mapped('line_id.code'))
        for ausente in ('BASIC', 'GROSS', 'NET', 'CO_BRUTO', 'CO_NETO', 'CO_BASICO', 'CO_AUX_TRANS', 'CO_SALUD_EMP', 'CO_PENSION_EMP'):
            self.assertNotIn(ausente, codigos, '%s no se muestra (es de «Conceptos de pago» o su categoría no tiene sección)' % ausente)
        self.assertIn('CO_IBC_SP', codigos, 'Las bases (acumuladores) sí se muestran')
        for linea in filas.filtered('line_id').mapped('line_id'):
            self.assertIn(linea.category_id.l10n_co_ne_seccion_concepto, ('bases', 'costo_empresa'), linea.code)

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

    # ── .298: los conceptos se MUEVEN y el cálculo es informativo (regla de David) ─────────────────────────────────────────────
    def test_14_los_conceptos_se_mueven_y_el_calculo_los_sigue_con_las_cifras_de_un_calculo_manual(self):
        """Regla de David (22-nov): se agrega una bonificación SALARIAL y se ajusta un devengado desde «Conceptos de pago»; en «Cálculo del salario» cambian el
        IBC y los aportes de la empresa, y las cifras coinciden con las de un cálculo manual equivalente (mes completo de septiembre: 30 días de 30, sin
        ausencias; sueldo 3.000.000 → 100.000 por día).

        Las PROVISIONES se comparan también con el cálculo manual, pero HOY no se mueven: las reglas CO_PROV_* se calculan sobre el sueldo y el auxilio del
        CONTRATO, no sobre lo pagado. Si deben seguir una bonificación o un ajuste (base prestacional con salario variable) es una decisión normativa que
        cambia esas reglas, no esta pestaña."""
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
                fila.input_type_id = ref('l10n_co_nomina_electronica.input_co_bonif_sal')
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
        # Provisiones: cálculo manual sobre el sueldo y el auxilio del contrato (un mes completo: factor 1). Hoy no se mueven.
        sueldo = contrato.wage
        auxilio = parametro('l10n_co_aux_transporte') if sueldo <= parametro('l10n_co_smmlv') * parametro('l10n_co_aux_transporte_tope_smmlv') else 0.0
        base = sueldo + auxilio
        cesantias = base / 12.0
        provisiones = {
            'CO_PROV_PRIMA': base / 12.0, 'CO_PROV_CESANTIAS': cesantias,
            'CO_PROV_INT_CES': cesantias * parametro('l10n_co_pct_intereses_cesantias') / 100.0,
            'CO_PROV_VACACIONES': sueldo * parametro('l10n_co_dias_mes_comercial') / parametro('l10n_co_divisor_vacaciones')}
        for codigo, esperado in provisiones.items():
            self.assertAlmostEqual(despues[codigo], esperado, delta=0.01, msg=codigo)
            self.assertAlmostEqual(despues[codigo], antes[codigo], delta=0.01, msg='%s hoy no depende de lo pagado' % codigo)
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
        calculo = set(self._filas(recibo).filtered('line_id').mapped('line_id'))
        self.assertFalse(calculo & set(f['linea'] for f in filas), 'Ninguna línea está en la colilla y en «Cálculo del salario» a la vez')
