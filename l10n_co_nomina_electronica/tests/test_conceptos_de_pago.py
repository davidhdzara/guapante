# -*- coding: utf-8 -*-
"""E11 pieza 3 (.289, doc 71c §4 y §5): pestaña y filas de «Conceptos de pago» del recibo. NO EJECUTADAS en Odoo al escribirlas (el N1 necesita
``-u``: tabla, permisos, reglas de registro y vista nuevos).

- Carga de la vista (``get_view`` del formulario del recibo) y reglas de UX: selectores por @name, sin ``@string``, sin colores ni íconos propios,
  solo «Agregar concepto».
- La pestaña y las filas solo existen en estructuras con ``l10n_co_ne_conceptos_de_pago``; en las demás la vista nativa queda igual.
- Las filas son una VISTA: se regeneran en cada cálculo, no se copian y nada las lee para calcular.
- Con ``odoo.tests.Form`` (el mismo camino ``web_save`` → ``write`` del cliente): editar el importe de una fila ajustable crea el ajuste y recalcula
  UNA vez; editar, agregar y borrar una novedad desde la misma tabla siguen el camino de .286 (una sola llamada de ``compute_sheet`` por guardado y
  el neto igual al de «Calcular hoja»)."""

import json
from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged
from .common_diario import fijar_diario_de_salarios

_G_MANAGER = 'hr_payroll.group_hr_payroll_manager'
_G_USER = 'hr_payroll.group_hr_payroll_user'


@tagged('post_install', '-at_install')
class TestConceptosDePago(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Conceptos A'))
        cls.company_b = cls.env['res.company'].create(dict(valores, name='Compañía Conceptos B'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Conceptos', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.tipo_bonif_nosal = ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.Concepto = cls.env['l10n.co.payslip.concepto']
        fijar_diario_de_salarios(cls.env, cls.general)      # .296: ``Form`` exige el diario; no se toma de la base
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, estructura=None, desde=date(2026, 9, 1), hasta=date(2026, 9, 15), compania=None):
        type(self).n += 1
        compania = compania or self.company
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Conceptos %s' % self.n,
            'company_id': compania.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Conceptos %s' % self.n, 'employee_id': empleado.id, 'company_id': compania.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Conceptos %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': compania.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        return recibo

    def _fila(self, recibo, codigo):
        fila = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.salary_rule_id.code == codigo)
        self.assertEqual(len(fila), 1, 'Debe haber una fila para %s' % codigo)
        return fila

    def _indice(self, recibo, fila):
        return recibo.l10n_co_concepto_ids.ids.index(fila.id)

    def _total(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def _contando_calculos(self, recibo):
        original = type(recibo).compute_sheet
        llamadas = []

        def espia(slip):
            llamadas.append(slip.ids)
            return original(slip)

        return patch.object(type(recibo), 'compute_sheet', espia), llamadas

    def _usuario(self, login, grupos, companias):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': companias[0].id,
            'company_ids': [(6, 0, companias.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    # ── la vista ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_01_la_vista_del_recibo_carga_con_la_pestana_por_nombre_y_sin_estilos_propios(self):
        vista = self.env['hr.payslip'].get_view(view_type='form')
        arch = etree.fromstring(vista['arch'].encode('utf-8') if isinstance(vista['arch'], str) else vista['arch'])
        paginas = arch.xpath("//page[@name='conceptos_de_pago']")
        self.assertEqual(len(paginas), 1, 'Falta la pestaña «Conceptos de pago» en la vista del recibo')
        pagina = paginas[0]
        self.assertEqual(pagina.get('invisible'), 'not l10n_co_ne_usa_conceptos')
        nativa = arch.xpath("//page[@name='worked_days_input']")
        self.assertEqual(len(nativa), 1)
        self.assertEqual(nativa[0].get('invisible'), 'l10n_co_ne_oculta_pagina_novedades', 'La pestaña nativa solo se oculta donde «Conceptos de pago» la reemplaza')
        campo = pagina.xpath(".//field[@name='l10n_co_concepto_ids']")[0]
        self.assertEqual(campo.get('widget'), 'section_and_note_one2many')
        self.assertEqual(len(campo.xpath(".//control/create")), 1, 'Solo «Agregar concepto»')
        self.assertEqual(campo.xpath(".//control/create")[0].get('name'), 'add_concepto_control')
        self.assertFalse(campo.xpath(".//create[@context]"), 'Sin «Agregar sección» ni «Agregar nota»')
        for columna in ('display_type', 'slip_id', 'edita_cantidad', 'edita_porcentaje', 'edita_importe'):
            self.assertTrue(campo.xpath(".//list/field[@name='%s']" % columna), columna)
        self.assertFalse(pagina.xpath(".//*[@style]"), 'Sin estilos propios')
        self.assertFalse(pagina.xpath(".//i"), 'Sin íconos propios')
        texto = etree.tostring(pagina, encoding='unicode')
        for prohibido in ('text-muted', 'decoration-', 'fa fa-'):
            self.assertNotIn(prohibido, texto)

    def test_02_la_vista_heredada_no_selecciona_por_string(self):
        arch = etree.fromstring(self.env.ref('l10n_co_nomina_electronica.view_payslip_form_ne_conceptos').arch_db.encode('utf-8'))
        for xpath in arch.xpath('//xpath'):
            self.assertNotIn('@string', xpath.get('expr') or '', 'La herencia debe anclar por @name o posición')
            self.assertNotIn('@help', xpath.get('expr') or '')

    def _columna(self, nombre):
        vista = self.env['hr.payslip'].get_view(view_type='form')
        arch = etree.fromstring(vista['arch'].encode('utf-8') if isinstance(vista['arch'], str) else vista['arch'])
        columnas = arch.xpath("//field[@name='l10n_co_concepto_ids']//list/field[@name='%s']" % nombre)
        self.assertEqual(len(columnas), 1, nombre)
        return columnas[0]

    def test_la_columna_porcentaje_se_muestra_solo_si_es_distinta_de_100_y_con_dos_decimales(self):
        """.297 (pedido del TL tras la captura de QA sobre .290): el % salía «100,0000» (4 decimales, la precisión «Payroll Rate»). Misma regla que aprobó David
        para la colilla: solo si es distinto de 100 y con 2 decimales, con atributos nativos de la vista (``digits`` y ``invisible`` por fila)."""
        columna = self._columna('rate')
        self.assertEqual(json.loads(columna.get('digits')), [16, 2])
        invisible = columna.get('invisible') or ''
        self.assertIn('rate == 100', invisible, 'Con 100 el porcentaje no se muestra')
        self.assertIn("origen == 'dias'", invisible, 'Se conserva que la fila de días no lo muestra')
        self.assertIsNone(columna.get('style'))
        self.assertEqual(self.env['l10n.co.payslip.concepto']._fields['rate']._digits, 'Payroll Rate',
                         'El campo del modelo conserva su precisión: el cambio es solo de presentación')

    def test_la_primera_columna_es_el_concepto_el_nombre_y_la_segunda_la_regla_editable_solo_en_la_fila_nueva(self):
        """Presentación (22-nov, decisión del TL tras el re-test de QA; doc 74 §19): la PRIMERA columna es «Concepto» (el nombre de la fila: en los días, «Asistencia»; el
        widget de secciones la necesita visible) y la SEGUNDA «Regla», el selector (Many2one), editable solo en la fila nueva y requerida allí, solo en las novedades, con el dominio
        de la estructura del recibo, las reglas que se alimentan de una novedad y las secciones de devengados o deducciones; el tipo de novedad queda como columna INVISIBLE (lo leen la
        edición y los cálculos)."""
        vista = self.env['hr.payslip'].get_view(view_type='form')
        arch = etree.fromstring(vista['arch'].encode('utf-8') if isinstance(vista['arch'], str) else vista['arch'])
        columnas = arch.xpath("//field[@name='l10n_co_concepto_ids']//list/field")
        visibles = [c.get('name') for c in columnas if not c.get('column_invisible')]
        self.assertEqual(visibles[:2], ['name', 'salary_rule_id'], '«Concepto» primero y «Regla» segunda')
        self.assertLess(visibles.index('salary_rule_id'), visibles.index('cuenta'))
        nombre = self._columna('name')
        self.assertEqual(nombre.get('string'), 'Concepto')
        self.assertEqual(nombre.get('widget'), 'section_and_note_text')
        self.assertFalse(nombre.get('optional'), 'Siempre visible: el widget de secciones la necesita')
        self.assertFalse(nombre.get('invisible'), 'También en las calculadas y en los días: es lo que se lee como concepto')
        self.assertIn('calculado', nombre.get('readonly'))
        self.assertIn('dias', nombre.get('readonly'))
        regla = self._columna('salary_rule_id')
        self.assertEqual(regla.get('string'), 'Regla')
        self.assertEqual(regla.get('readonly'), 'id', 'Solo se elige en la fila nueva')
        self.assertIn('not id', regla.get('required'), 'Requerida en la fila nueva')
        self.assertEqual(regla.get('invisible'), "origen != 'novedad'", 'Solo en las novedades: en las calculadas repetiría el nombre y en los días no hay regla')
        dominio = regla.get('domain')
        for texto in ('parent.struct_id', 'l10n_co_ne_alimentada_por_novedad', 'l10n_co_ne_seccion_concepto'):
            self.assertIn(texto, dominio)
        self.assertIn('no_create', regla.get('options'))
        tipo = self._columna('input_type_id')
        self.assertTrue(tipo.get('column_invisible'), 'La columna «Tipo de novedad» desaparece')
        self.assertFalse(tipo.get('optional'))

    def test_la_regla_se_alimenta_de_una_novedad_si_hay_un_tipo_con_su_mismo_codigo_y_la_estructura_general_es_uno_a_uno(self):
        """Doc 74 §19: 38 de los 44 tipos tienen exactamente una regla de su mismo código en la estructura general; los otros 6 son de otras estructuras (liquidación y bonificación)
        o de las asignaciones salariales y NO se ofrecen en la nómina general."""
        Regla = self.env['hr.salary.rule']
        tipos = self.env['hr.payslip.input.type'].search([])
        por_codigo = {}
        for tipo in tipos:
            por_codigo.setdefault(tipo.code, []).append(tipo)
        self.assertFalse({c for c, t in por_codigo.items() if len(t) > 1}, 'Ningún código de tipo repetido')
        sin_regla = set()
        for codigo in por_codigo:
            reglas = Regla.search([('code', '=', codigo), ('struct_id', '=', self.general.id)])
            self.assertLessEqual(len(reglas), 1, 'Una sola regla por código en la estructura general: %s' % codigo)
            if not reglas:
                sin_regla.add(codigo)
        self.assertTrue({'CO_LIQ_INDEMNIZ', 'CO_BON_VALOR', 'L10N_CO_EMBARGO_ALIMENTOS', 'L10N_CO_EMBARGO_CIVIL', 'L10N_CO_EMBARGO_COOPERATIVA', 'L10N_CO_LIBRANZA'} <= sin_regla,
                        'Los 6 tipos de otras estructuras o de las asignaciones no tienen regla en la general')
        ofrecidas = Regla.search([('struct_id', '=', self.general.id), ('l10n_co_ne_alimentada_por_novedad', '=', True)])
        self.assertEqual(set(ofrecidas.mapped('code')), set(por_codigo) - sin_regla)
        self.assertEqual(len(ofrecidas), len(set(ofrecidas.mapped('code'))), 'Una regla por código')
        no_ofrecidas = Regla.search([('struct_id', '=', self.general.id), ('l10n_co_ne_alimentada_por_novedad', '=', False)])
        self.assertFalse(set(no_ofrecidas.mapped('code')) & set(por_codigo))
        self.assertIn('CO_SALUD_EMP', no_ofrecidas.mapped('code'), 'La salud del empleado no se agrega a mano')
        self.assertIn('CO_BONIF_NOSAL', ofrecidas.mapped('code'))
        self.assertTrue(Regla.search([('code', '=', 'CO_BONIF_NOSAL')], limit=1).l10n_co_ne_alimentada_por_novedad)

    def test_agregar_por_la_regla_deduce_el_tipo_y_el_nombre_y_rechaza_lo_que_no_es_de_la_estructura_ni_de_una_novedad(self):
        recibo = self._recibo()
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL'), ('struct_id', '=', self.general.id)], limit=1)
        nueva = self.Concepto.new({'slip_id': recibo.id, 'salary_rule_id': regla.id})
        nueva._onchange_salary_rule_id()
        self.assertEqual(nueva.input_type_id, self.tipo_bonif_nosal, 'El tipo sale de la regla (mismo código)')
        self.assertEqual(nueva.name, regla.name)
        nueva.salary_rule_id = False
        nueva._onchange_salary_rule_id()
        self.assertFalse(nueva.input_type_id)
        fila = self.Concepto.create({'slip_id': recibo.id, 'salary_rule_id': regla.id, 'amount': 80000.0})
        self.assertEqual((fila.origen, fila.input_type_id, fila.salary_rule_id), ('novedad', self.tipo_bonif_nosal, regla))
        self.assertEqual(recibo.input_line_ids.mapped('amount'), [80000.0])
        with self.assertRaisesRegex(UserError, 'no corresponde al tipo'):
            self.Concepto.create({'slip_id': recibo.id, 'salary_rule_id': regla.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_hed').id, 'amount': 1.0})
        salud = self.env['hr.salary.rule'].search([('code', '=', 'CO_SALUD_EMP'), ('struct_id', '=', self.general.id)], limit=1)
        with self.assertRaisesRegex(UserError, 'no se alimenta de una novedad'):
            self.Concepto.create({'slip_id': recibo.id, 'salary_rule_id': salud.id, 'amount': 1.0})
        de_liquidacion = self.env['hr.salary.rule'].search([('code', '=', 'CO_INC_COMUN'), ('struct_id', '=', self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion').id)], limit=1)
        self.assertTrue(de_liquidacion, 'Premisa: la liquidación tiene su regla CO_INC_COMUN')
        with self.assertRaisesRegex(UserError, 'no es de la estructura salarial del recibo'):
            self.Concepto.create({'slip_id': recibo.id, 'salary_rule_id': de_liquidacion.id, 'amount': 1.0})
        with self.assertRaisesRegex(UserError, 'Elija el concepto'):
            self.Concepto.create({'slip_id': recibo.id, 'amount': 5.0})
        with self.assertRaisesRegex(UserError, 'ya guardada no se cambia'):
            fila.write({'salary_rule_id': salud.id})

    def test_el_pie_de_conceptos_de_pago_no_lleva_el_costo_de_la_empresa(self):
        """.298 (David): el «Costo empresa» pasa al pie de «Cálculo del salario»; aquí quedan Total devengado, Total deducciones y Neto."""
        vista = self.env['hr.payslip'].get_view(view_type='form')
        arch = etree.fromstring(vista['arch'].encode('utf-8') if isinstance(vista['arch'], str) else vista['arch'])
        pagina = arch.xpath("//page[@name='conceptos_de_pago']")[0]
        pie = [c.get('name') for c in pagina.xpath(".//group[@name='conceptos_totales']/field")]
        self.assertEqual(pie, ['l10n_co_total_devengado', 'l10n_co_total_deducciones', 'net_wage'])

    # ── estructuras con y sin el interruptor ──────────────────────────────────────────────────────────────────────────────────
    def test_03_solo_las_estructuras_con_el_interruptor_tienen_filas(self):
        general = self._recibo()
        self.assertTrue(general.l10n_co_ne_usa_conceptos)
        self.assertTrue(general.l10n_co_concepto_ids)
        self.prima.l10n_co_ne_conceptos_de_pago = False          # desde .328 la prima nace con el interruptor encendido
        prima = self._recibo(estructura=self.prima, desde=date(2026, 7, 1), hasta=date(2026, 12, 31))
        self.assertFalse(prima.l10n_co_ne_usa_conceptos)
        self.assertFalse(prima.l10n_co_concepto_ids, 'La estructura de prima no usa Conceptos de pago: sin filas')
        self.prima.l10n_co_ne_conceptos_de_pago = True
        prima.compute_sheet()
        self.assertTrue(prima.l10n_co_concepto_ids, 'Al activar el interruptor de la estructura, el siguiente cálculo genera las filas')

    # ── las filas ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_04_las_filas_traen_secciones_en_orden_y_una_fila_por_linea_con_valor(self):
        recibo = self._recibo()
        filas = recibo.l10n_co_concepto_ids
        self.assertEqual(filas[0].display_type, 'line_section')
        self.assertEqual(filas[0].name, 'Devengados')
        secciones = filas.filtered(lambda f: f.display_type == 'line_section')
        self.assertEqual(secciones.mapped('name'), ['Devengados', 'Deducciones'])
        self.assertEqual(len(set(filas.mapped('sequence'))), len(filas), 'Cada fila con su propia secuencia')
        con_linea = filas.filtered(lambda f: f.line_id)
        for fila in con_linea:
            self.assertEqual(fila.total, fila.line_id.total, fila.name)
            self.assertEqual((fila.quantity, fila.rate, fila.amount), (fila.line_id.quantity, fila.line_id.rate, fila.line_id.amount))
        self.assertFalse(filas.filtered(lambda f: f.salary_rule_id.code in ('CO_NETO', 'CO_BRUTO')), 'Los totales no son conceptos')
        self.assertFalse(filas.filtered(lambda f: f.salary_rule_id.code.endswith('_CIA') if f.salary_rule_id else False))
        self.assertTrue(self._fila(recibo, 'CO_BASICO'))
        self.assertTrue(self._fila(recibo, 'CO_SALUD_EMP'))
        deducciones = filas[list(filas.ids).index(secciones[1].id) + 1:]
        self.assertTrue(all(f.line_id.category_id.l10n_co_ne_seccion_concepto == 'deducciones' for f in deducciones if f.line_id))

    def test_05_los_dias_trabajados_salen_bajo_el_sueldo_en_una_sola_fila_asistencia_solo_con_cantidad_y_unidad(self):
        """Ajuste de David (22-nov, decisión del TL: opción B): el descanso remunerado NO se desagrega en «Conceptos de pago». Bajo el sueldo sale UNA fila de días,
        «Asistencia», con la suma de asistencia + festivos trabajados + descansos remunerados + ajuste del mes comercial (los días pagados con el sueldo), solo con cantidad y
        unidad. El desglose por fecha de E2a sigue en la pestaña de días trabajados."""
        recibo = self._recibo()
        filas = recibo.l10n_co_concepto_ids
        sueldo = self._fila(recibo, 'CO_BASICO')
        siguientes = filas[list(filas.ids).index(sueldo.id) + 1:]
        dias = siguientes.filtered(lambda f: f.origen == 'dias')
        self.assertTrue(dias, 'Premisa: el recibo trae líneas de días trabajados')
        self.assertEqual(siguientes[0].origen, 'dias', 'La fila de días va JUSTO bajo el sueldo')
        tipos = recibo._ne_tipos_dias_de_asistencia()
        lineas = recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id in tipos and (w.number_of_days or w.number_of_hours))
        self.assertTrue(lineas, 'Premisa: hay líneas de asistencia')
        asistencia = dias[0]
        self.assertEqual(asistencia.quantity, sum(lineas.mapped('number_of_days')), 'La suma de los días pagados con el sueldo')
        self.assertEqual(asistencia.quantity, sueldo.quantity, 'Es la cantidad del Sueldo Básico: la fila que lo representa')
        self.assertEqual(asistencia.name, lineas[0].name or lineas[0].work_entry_type_id.name)
        nombres = [(f.name or '').lower() for f in filas]
        self.assertFalse([n for n in nombres if 'descanso' in n or 'ajuste mes' in n or 'festivo' in n], 'Sin el desagregado en esta pestaña')
        for fila in dias:
            self.assertEqual((fila.unidad, fila.amount, fila.total, fila.edita_cantidad, fila.edita_importe), ('dias', 0.0, 0.0, False, False))
            self.assertTrue(fila.quantity or fila.worked_day_id.number_of_hours)

    def test_05b_asistencia_y_descansos_remunerados_se_juntan_en_una_fila_y_las_ausencias_siguen_aparte(self):
        """El caso de la captura de David: «Asistencia 11 días» y «Descansos remunerados 4 días» salían como DOS filas; ahora una sola «Asistencia» con 15. Una línea de
        vacaciones NO se junta (es otro concepto). La pestaña de días trabajados no cambia."""
        recibo = self._recibo()
        ref = self.env.ref
        asistencia = recibo._ne_tipo_asistencia()
        descanso = ref('l10n_co_nomina_electronica.hr_work_entry_type_co_descanso_remunerado')
        vacaciones = self.env['hr.work.entry.type'].search([('code', '=', 'CO_VAC')], limit=1)
        recibo.worked_days_line_ids.unlink()
        Dia = self.env['hr.payslip.worked_days']
        valores = lambda tipo, dias, secuencia: {'payslip_id': recibo.id, 'work_entry_type_id': tipo.id, 'number_of_days': dias, 'number_of_hours': dias * 7.0, 'sequence': secuencia}
        Dia.create([valores(asistencia, 11.0, 1), valores(descanso, 4.0, 2)] + ([valores(vacaciones, 3.0, 3)] if vacaciones else []))
        self.Concepto._regenerar_de_recibos(recibo)
        dias = recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'dias')
        asistencias = dias.filtered(lambda f: f.quantity == 15.0)
        self.assertEqual(len(asistencias), 1, 'UNA fila con 15 días: asistencia + descansos remunerados')
        self.assertEqual(asistencias.name, asistencia.name)
        self.assertFalse(dias.filtered(lambda f: 'descanso' in (f.name or '').lower()))
        if vacaciones:
            self.assertEqual(len(dias), 2, 'Asistencia y las vacaciones, cada una en su fila')
            self.assertIn(3.0, dias.mapped('quantity'))
        else:
            self.assertEqual(len(dias), 1)
        self.assertEqual(len(recibo.worked_days_line_ids), 2 + (1 if vacaciones else 0), 'La pestaña de días trabajados sigue desglosada')

    def test_05c_la_fila_unida_se_llama_asistencia_sin_importar_el_nombre_de_la_primera_linea(self):
        """N2 «cu»: la fila unida tomaba el nombre de la PRIMERA línea de días (el nativo agrega « (Half-Day)»; si «Asistencia» no tiene días la primera es otro tipo). Siempre lleva el
        nombre del tipo «Asistencia» (traducible), con las líneas en cualquier orden y con nombres explícitos de otro tipo."""
        recibo = self._recibo()
        asistencia = recibo._ne_tipo_asistencia()
        descanso = self.env.ref('l10n_co_nomina_electronica.hr_work_entry_type_co_descanso_remunerado')
        festivo = self.env.ref('l10n_co_nomina_electronica.hr_work_entry_type_co_festivo_trabajado')
        recibo.worked_days_line_ids.unlink()
        Dia = self.env['hr.payslip.worked_days']
        # el descanso va PRIMERO (secuencia menor) y con nombre explícito; «Asistencia» después; un festivo trabajado también se junta
        Dia.create([
            {'payslip_id': recibo.id, 'work_entry_type_id': descanso.id, 'number_of_days': 4.0, 'number_of_hours': 28.0, 'sequence': 1, 'name': 'Descansos remunerados'},
            {'payslip_id': recibo.id, 'work_entry_type_id': festivo.id, 'number_of_days': 1.0, 'number_of_hours': 7.0, 'sequence': 2, 'name': 'Festivos trabajados'},
            {'payslip_id': recibo.id, 'work_entry_type_id': asistencia.id, 'number_of_days': 10.0, 'number_of_hours': 70.0, 'sequence': 3}])
        self.Concepto._regenerar_de_recibos(recibo)
        dias = recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'dias')
        self.assertEqual(len(dias), 1)
        self.assertEqual(dias.quantity, 15.0)
        self.assertEqual(dias.name, asistencia.name)
        self.assertEqual(recibo._ne_nombre_dias_de_asistencia(), asistencia.name)

    def test_06_los_totales_del_pie_salen_de_las_lineas_y_coinciden_con_las_filas(self):
        recibo = self._recibo()
        por_seccion = {}
        for linea in recibo.line_ids:
            seccion = linea.category_id.l10n_co_ne_seccion_concepto
            if seccion and (seccion == 'costo_empresa' or linea.appears_on_payslip):
                por_seccion[seccion] = por_seccion.get(seccion, 0.0) + linea.total
        self.assertAlmostEqual(recibo.l10n_co_total_devengado, por_seccion.get('devengados', 0.0), delta=0.005)
        self.assertAlmostEqual(recibo.l10n_co_total_deducciones, por_seccion.get('deducciones', 0.0), delta=0.005)
        self.assertAlmostEqual(recibo.l10n_co_costo_empresa, por_seccion.get('costo_empresa', 0.0), delta=0.005)
        self.assertGreater(recibo.l10n_co_costo_empresa, 0.0, 'Aportes de la empresa y provisiones')
        filas = recibo.l10n_co_concepto_ids.filtered(lambda f: f.line_id)
        self.assertAlmostEqual(
            sum(filas.filtered(lambda f: f.line_id.category_id.l10n_co_ne_seccion_concepto == 'devengados').mapped('total')),
            recibo.l10n_co_total_devengado, delta=0.005)
        self.assertAlmostEqual(
            sum(filas.filtered(lambda f: f.line_id.category_id.l10n_co_ne_seccion_concepto == 'deducciones').mapped('total')),
            recibo.l10n_co_total_deducciones, delta=0.005)
        self.assertEqual(recibo.net_wage, recibo._ne_pdf_neto())

    def test_07_las_filas_son_una_vista_no_se_copian_ni_alimentan_el_calculo(self):
        recibo = self._recibo()
        antes = sorted((l.code, l.total) for l in recibo.line_ids)
        self.assertNotIn('l10n_co_concepto_ids', recibo.copy_data()[0])
        self.assertFalse(self.env['hr.payslip']._fields['l10n_co_concepto_ids'].copy)
        self.Concepto.sudo().with_context(ne_regenerar_conceptos=True).search([('slip_id', '=', recibo.id)]).unlink()
        recibo.compute_sheet()
        self.assertEqual(sorted((l.code, l.total) for l in recibo.line_ids), antes, 'El cálculo no depende de las filas')
        self.assertTrue(recibo.l10n_co_concepto_ids, 'Y las filas se vuelven a generar')

    # ── editar con Form (el mismo camino del cliente web) ──────────────────────────────────────────────────────────────────────
    def test_08_editar_el_importe_de_una_fila_ajustable_crea_el_ajuste_y_recalcula_una_vez(self):
        recibo = self._recibo()
        fila = self._fila(recibo, 'CO_BASICO')
        self.assertTrue(fila.edita_importe and fila.edita_cantidad and fila.edita_porcentaje, 'Gerente: la fila ajustable se edita')
        sugerido, neto0 = fila.total, recibo._ne_pdf_neto()
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.edit(self._indice(recibo, fila)) as editada:
                    editada.amount = 0.0
        self.assertEqual(llamadas, [recibo.ids], 'UN recálculo por guardado')
        ajuste = recibo.l10n_co_ajuste_ids
        self.assertEqual((len(ajuste), ajuste.salary_rule_id.code, ajuste.amount, ajuste.estado), (1, 'CO_BASICO', 0.0, 'aplicado'))
        self.assertAlmostEqual(ajuste.sugerido_total, sugerido, delta=0.01)
        self.assertEqual(self._total(recibo, 'CO_BASICO'), 0.0)
        fila = self._fila(recibo, 'CO_BASICO')
        self.assertEqual((fila.total, fila.ajustado), (0.0, True), 'La fila se regeneró con el valor ajustado')
        siguiente = recibo.l10n_co_concepto_ids[self._indice(recibo, fila) + 1]
        self.assertEqual(siguiente.display_type, 'line_note', 'La nota va como fila nativa line_note, justo debajo')
        self.assertTrue(siguiente.name.startswith('Ajustado por la empresa. Sugerido:'))
        neto_formulario = recibo._ne_pdf_neto()
        self.assertNotEqual(neto_formulario, neto0)
        recibo.compute_sheet()
        self.assertEqual(recibo._ne_pdf_neto(), neto_formulario, 'Igual que «Calcular hoja»')

    def test_09_editar_una_novedad_desde_la_tabla_sigue_el_camino_de_286(self):
        recibo = self._recibo()
        self.env['hr.payslip.input'].create({
            'payslip_id': recibo.id, 'input_type_id': self.tipo_bonif_nosal.id, 'code': 'CO_BONIF_NOSAL', 'amount': 100000.0})
        fila = self._fila(recibo, 'CO_BONIF_NOSAL')
        self.assertEqual((fila.origen, fila.input_id.amount, fila.edita_importe, fila.edita_cantidad), ('novedad', 100000.0, True, False))
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.edit(self._indice(recibo, fila)) as editada:
                    editada.amount = 250000.0
        self.assertEqual(llamadas, [recibo.ids], 'UN recálculo por guardado, no cero ni dos')
        self.assertEqual(recibo.input_line_ids.amount, 250000.0)
        self.assertEqual(self._total(recibo, 'CO_BONIF_NOSAL'), 250000.0)
        self.assertFalse(recibo.l10n_co_ajuste_ids, 'Una novedad se edita en la novedad, no con un ajuste')
        neto_formulario = recibo._ne_pdf_neto()
        recibo.compute_sheet()
        self.assertEqual(recibo._ne_pdf_neto(), neto_formulario, 'Igual que «Calcular hoja»')

    def test_10_agregar_y_borrar_un_concepto_desde_la_tabla(self):
        recibo = self._recibo()
        neto0 = recibo._ne_pdf_neto()
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.new() as nueva:
                    nueva.salary_rule_id = self.env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL'), ('struct_id', '=', recibo.struct_id.id)], limit=1)   # selector del concepto
                    nueva.amount = 80000.0
        self.assertEqual(llamadas, [recibo.ids], 'Agregar: UN recálculo')
        self.assertEqual(recibo.input_line_ids.mapped('amount'), [80000.0])
        self.assertEqual(self._total(recibo, 'CO_BONIF_NOSAL'), 80000.0)
        fila = self._fila(recibo, 'CO_BONIF_NOSAL')
        self.assertEqual(fila.origen, 'novedad')
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            with Form(recibo) as formulario:
                formulario.l10n_co_concepto_ids.remove(self._indice(recibo, fila))
        self.assertEqual(llamadas, [recibo.ids], 'Borrar: UN recálculo')
        self.assertFalse(recibo.input_line_ids)
        self.assertFalse(self._total(recibo, 'CO_BONIF_NOSAL'))
        self.assertEqual(recibo._ne_pdf_neto(), neto0)

    # ── lo que NO se puede hacer ───────────────────────────────────────────────────────────────────────────────────────────────
    def test_11_las_filas_de_dias_secciones_y_calculadas_no_se_editan_ni_se_borran(self):
        recibo = self._recibo()
        dias = recibo.l10n_co_concepto_ids.filtered(lambda f: f.origen == 'dias')[:1]
        self.assertTrue(dias)
        with self.assertRaises(AssertionError):                            # el modificador readonly de la vista
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.edit(self._indice(recibo, dias)) as editada:
                    editada.quantity = 5.0
        with self.assertRaises(UserError):
            dias.write({'quantity': 5.0})
        calculada = self._fila(recibo, 'CO_SALUD_EMP')
        with self.assertRaises(UserError):
            calculada.unlink()
        with self.assertRaises(UserError):
            calculada.write({'name': 'Otro nombre'})
        seccion = recibo.l10n_co_concepto_ids.filtered(lambda f: f.display_type == 'line_section')[:1]
        with self.assertRaisesRegex(UserError, 'Las secciones no se pueden borrar'):       # QA sobre .298: sin hablar de «concepto calculado»
            seccion.unlink()
        with self.assertRaisesRegex(UserError, 'Solo se borran las novedades'):
            calculada.unlink()
        with self.assertRaises(UserError):
            self.Concepto.create({'slip_id': recibo.id, 'display_type': 'line_note', 'name': 'Nota a mano'})
        with self.assertRaises(UserError):
            self.Concepto.create({'slip_id': recibo.id, 'amount': 5.0})   # sin tipo de novedad

    def test_11b_el_orden_de_las_filas_lo_fija_el_sistema_no_se_mueven_ni_en_la_vista_ni_por_el_servidor(self):
        """.300b (pedido del TL, revisión de la v19 del widget de secciones): en Odoo 18 el widget ``section_and_note_one2many`` no trae menú de filas (duplicar,
        borrar y mover son de v19); lo que sí había era el arrastre del widget ``handle`` de ``sequence`` y el modelo dejaba escribir ``sequence`` sin revisar
        nada (ni el estado del recibo). Duplicar una sección (crear con ``display_type``) y borrarla ya estaban bloqueados (``test_11``)."""
        columna = self._columna('sequence')
        self.assertTrue(columna.get('column_invisible'), 'La secuencia no se muestra')
        self.assertNotEqual(columna.get('widget'), 'handle', 'Sin el arrastre de filas')
        recibo = self._recibo()
        seccion = recibo.l10n_co_concepto_ids.filtered(lambda f: f.display_type == 'line_section')[:1]
        calculada = self._fila(recibo, 'CO_SALUD_EMP')
        antes = {fila.id: fila.sequence for fila in recibo.l10n_co_concepto_ids}
        for fila in (seccion, calculada):
            with self.assertRaises(UserError):
                fila.write({'sequence': 5})
        hecho = self._recibo()
        hecho.write({'state': 'done'})
        with self.assertRaises(UserError):
            hecho.l10n_co_concepto_ids[:1].write({'sequence': 5})
        recibo.invalidate_recordset()
        self.assertEqual({fila.id: fila.sequence for fila in recibo.l10n_co_concepto_ids}, antes, 'Ninguna fila cambió de lugar')
        # La regeneración del sistema sí conserva su camino
        nuevas = self.Concepto.sudo().with_context(ne_regenerar_conceptos=True).search([('slip_id', '=', recibo.id)])
        nuevas.write({'sequence': 7})
        self.assertEqual(set(nuevas.mapped('sequence')), {7})

    def test_11c_una_fila_nueva_va_al_final_sin_importar_la_secuencia_que_mande_el_cliente(self):
        """El cliente manda ``sequence`` (10, el valor por defecto) al crear una fila desde la tabla: el modelo la ignora y la deja al final."""
        recibo = self._recibo()
        fila = self.Concepto.create({'slip_id': recibo.id, 'input_type_id': self.tipo_bonif_nosal.id, 'amount': 80000.0, 'sequence': 10})
        self.assertEqual(fila.sequence, 9999)
        self.assertGreater(fila.sequence, max((recibo.l10n_co_concepto_ids - fila).mapped('sequence')))

    def test_12_una_regla_no_ajustable_deja_su_fila_de_solo_lectura(self):
        """.298: se desmarca una regla que venía ajustable (el sueldo): su fila queda de solo lectura. La salud ya viene así sembrada (siguiente prueba)."""
        recibo = self._recibo()
        regla = self._fila(recibo, 'CO_BASICO').salary_rule_id
        regla.l10n_co_ne_ajustable = False
        recibo.compute_sheet()
        fila = self._fila(recibo, 'CO_BASICO')
        self.assertEqual((fila.edita_cantidad, fila.edita_porcentaje, fila.edita_importe), (False, False, False))
        with self.assertRaises(AssertionError):
            with Form(recibo) as formulario:
                with formulario.l10n_co_concepto_ids.edit(self._indice(recibo, fila)) as editada:
                    editada.amount = 0.0

    def test_12b_las_filas_de_ley_y_de_cuenta_de_la_empresa_vienen_de_solo_lectura_por_decision_de_david(self):
        """.298 (21-nov, riesgo UGPP): salud, pensión, FSP, retención y embargos del empleado no se ajustan, aunque el usuario sea gerente. Depende del XML sembrado
        (necesita ``-u``)."""
        recibo = self._recibo()
        for codigo in ('CO_SALUD_EMP', 'CO_PENSION_EMP'):
            fila = self._fila(recibo, codigo)
            self.assertTrue(fila, codigo)
            self.assertEqual((fila.edita_cantidad, fila.edita_porcentaje, fila.edita_importe), (False, False, False), codigo)
        self.assertTrue(self._fila(recibo, 'CO_BASICO').edita_importe, 'El sueldo sí se ajusta')

    def test_13_un_recibo_hecho_conserva_sus_filas_y_no_las_deja_editar(self):
        recibo = self._recibo()
        fila = self._fila(recibo, 'CO_BASICO')
        cantidad = len(recibo.l10n_co_concepto_ids)
        recibo.write({'state': 'done'})
        self.assertEqual(len(recibo.l10n_co_concepto_ids), cantidad)
        fila.invalidate_recordset()
        self.assertEqual((fila.edita_cantidad, fila.edita_porcentaje, fila.edita_importe), (False, False, False))
        with self.assertRaises(UserError):
            fila.write({'amount': 0.0})

    # ── permisos y compañía ────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_14_el_gerente_ajusta_y_el_usuario_de_nomina_solo_edita_novedades(self):
        recibo = self._recibo()
        self.env['hr.payslip.input'].create({
            'payslip_id': recibo.id, 'input_type_id': self.tipo_bonif_nosal.id, 'code': 'CO_BONIF_NOSAL', 'amount': 100000.0})
        gerente = self._usuario('gerente_conceptos', (_G_MANAGER, 'base.group_user'), self.company)
        oficial = self._usuario('oficial_conceptos', (_G_USER, 'base.group_user'), self.company)
        sueldo = self._fila(recibo, 'CO_BASICO')
        novedad = self._fila(recibo, 'CO_BONIF_NOSAL')
        self.assertTrue(sueldo.with_user(gerente).edita_importe)
        self.assertFalse(sueldo.with_user(oficial).edita_importe, 'El oficial no ajusta conceptos calculados')
        self.assertTrue(novedad.with_user(oficial).edita_importe, 'Pero sí edita novedades')
        with self.assertRaises(AccessError):
            sueldo.with_user(oficial).write({'amount': 0.0})
        novedad.with_user(oficial).write({'amount': 90000.0})
        self.assertEqual(novedad.input_id.amount, 90000.0)

    def test_15_las_filas_de_la_compania_a_son_invisibles_desde_la_compania_b(self):
        recibo = self._recibo()
        usuario_b = self._usuario('gerente_conceptos_b', (_G_MANAGER, 'base.group_user'), self.company_b)
        usuario_ab = self._usuario('gerente_conceptos_ab', (_G_MANAGER, 'base.group_user'), self.company | self.company_b)
        self.assertFalse(self.Concepto.with_user(usuario_b).search([('slip_id', '=', recibo.id)]))
        con_ambas = self.Concepto.with_user(usuario_ab).with_context(allowed_company_ids=[self.company.id, self.company_b.id])
        self.assertTrue(con_ambas.search([('slip_id', '=', recibo.id)]))
        solo_b = self.Concepto.with_user(usuario_ab).with_context(allowed_company_ids=[self.company_b.id])
        self.assertFalse(solo_b.search([('slip_id', '=', recibo.id)]))

    def test_16_la_funcion_de_datos_genera_las_filas_de_los_recibos_que_no_las_tienen_sin_recalcular(self):
        """Recibos calculados antes de la pieza (o de activar la estructura): al hacer -u su pestaña no queda vacía y el dinero no cambia."""
        recibo = self._recibo()
        otro = self._recibo()
        antes = sorted((l.code, l.total) for l in recibo.line_ids)
        propias = self.Concepto.sudo().with_context(ne_regenerar_conceptos=True)
        propias.search([('slip_id', 'in', (recibo | otro).ids)]).unlink()
        self.assertFalse(recibo.l10n_co_concepto_ids)
        otro.write({'state': 'done'})                              # un recibo hecho también recibe sus filas, de solo lectura
        espia, llamadas = self._contando_calculos(recibo)
        with espia:
            self.assertTrue(self.env['hr.payslip']._ne_generar_conceptos_pendientes())
        self.assertEqual(llamadas, [], 'No recalcula ningún recibo')
        self.assertTrue(recibo.l10n_co_concepto_ids)
        self.assertTrue(otro.l10n_co_concepto_ids)
        self.assertEqual(sorted((l.code, l.total) for l in recibo.line_ids), antes)
        filas = recibo.l10n_co_concepto_ids
        self._indice(recibo, self._fila(recibo, 'CO_SALUD_EMP'))
        self.assertEqual(len(filas), len(set(filas.ids)))
        cantidad = len(recibo.l10n_co_concepto_ids)
        self.env['hr.payslip']._ne_generar_conceptos_pendientes()
        self.assertEqual(len(recibo.l10n_co_concepto_ids), cantidad, 'Idempotente: no duplica filas')

    def test_17_la_funcion_de_datos_no_cambia_ninguna_linea_ni_el_neto_de_un_recibo_calculado_ni_de_uno_hecho(self):
        """TL: la función de datos solo genera filas. Las líneas (mismos registros, mismos valores), el neto, el básico y el bruto de un recibo
        ya calculado y de uno hecho quedan IGUALES, y no se publica ninguna nota ni se llama a ``compute_sheet``."""
        calculado = self._recibo()
        hecho = self._recibo()
        hecho.write({'state': 'done'})
        recibos = calculado | hecho

        def foto(recibo):
            return {
                'ids': sorted(recibo.line_ids.ids),
                'lineas': sorted((l.code, l.name, l.sequence, l.amount, l.quantity, l.rate, l.total) for l in recibo.line_ids),
                'neto': recibo._ne_pdf_neto(), 'net_wage': recibo.net_wage, 'basic_wage': recibo.basic_wage, 'gross_wage': recibo.gross_wage,
                'estado': recibo.state, 'notas': len(recibo.message_ids)}

        antes = {recibo.id: foto(recibo) for recibo in recibos}
        self.Concepto.sudo().with_context(ne_regenerar_conceptos=True).search([('slip_id', 'in', recibos.ids)]).unlink()
        self.assertFalse(recibos.l10n_co_concepto_ids)
        espia, llamadas = self._contando_calculos(calculado)
        with espia:
            self.env['hr.payslip']._ne_generar_conceptos_pendientes()
        self.assertEqual(llamadas, [], 'No recalcula ningún recibo')
        for recibo in recibos:
            recibo.invalidate_recordset()
            self.assertEqual(foto(recibo), antes[recibo.id], 'Cambió algo de %s' % recibo.name)
            self.assertTrue(recibo.l10n_co_concepto_ids, 'Y sí tiene sus filas')
