# -*- coding: utf-8 -*-
"""E11 pieza 2a (.287, doc 71c §2, §4 y §7): configuración de «Conceptos de pago» sembrada en el XML, sin código fijo y SIN cambios en dinero.

- ``hr.salary.rule.category.l10n_co_ne_seccion_concepto``: sección (devengados / deducciones / costo_empresa) de cada categoría del módulo.
- ``hr.salary.rule.l10n_co_ne_ajustable``: qué reglas admiten el ajuste de la empresa. Por defecto, toda regla de una estructura con «Usa Conceptos de pago»
  (hoy solo la general) cuya categoría tenga sección devengados o deducciones; editable por regla (campo calculado y editable).
- ``hr.salary.rule.l10n_co_ne_unidad`` y ``hr.payslip.input.type.l10n_co_ne_unidad``: unidad (días u horas) de la cantidad.

Las tablas de abajo son el CONTRATO de la siembra (lo aprobado por TL): una categoría o regla nueva sin decisión hace fallar la prueba.
NO EJECUTADAS en Odoo al escribirlas (el N1 necesita ``-u``: datos y vistas nuevos)."""

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

_PREFIJO = 'hr_salary_rule_category_'
_SECCIONES = {
    'devengados_salariales': 'devengados', 'devengados_no_salariales': 'devengados', 'horas_extra': 'devengados',
    'prestaciones': 'devengados', 'vacaciones': 'devengados', 'incapacidades': 'devengados',
    'deducciones': 'deducciones', 'seguridad_social_emp': 'deducciones',
    'seguridad_social_cia': 'costo_empresa', 'provisiones': 'costo_empresa',
}
# Sin sección a propósito: la raíz «Devengados» (trae la línea del neto), los totales de solo display y los acumuladores internos.
_SIN_SECCION = ('devengados', 'totales_display', 'acumuladores_internos')
# Ejemplos de lo que TL pidió (no es la regla, solo una red de seguridad legible): ajustables / derivados que NO lo son.
_EJEMPLOS_AJUSTABLES = ('CO_BASICO', 'CO_AUX_TRANS', 'CO_INC_COMUN', 'CO_LIC_MAT', 'CO_HED', 'CO_HRNDF', 'CO_SALUD_EMP', 'CO_PENSION_EMP', 'CO_FSP',
                        'CO_RETEFUENTE', 'CO_SINDICATO', 'CO_EMBARGO')
_EJEMPLOS_DERIVADOS = ('CO_NETO', 'CO_BRUTO', 'CO_SALUD_CIA', 'CO_PROV_PRIMA', 'CO_IBC_SP', 'CO_RETEFUENTE_BASE_GROSS')
_UNIDAD_REGLAS = {
    'CO_BASICO': 'dias', 'CO_AUX_TRANS': 'dias', 'CO_INC_COMUN': 'dias', 'CO_INC_LABORAL': 'dias', 'CO_LIC_MAT': 'dias',
    'CO_LIC_PAT': 'dias', 'CO_LIC_REM': 'dias', 'CO_VAC': 'dias',
    'CO_HED': 'horas', 'CO_HEN': 'horas', 'CO_HRN': 'horas', 'CO_HEDDF': 'horas', 'CO_HENDF': 'horas', 'CO_HRDDF': 'horas', 'CO_HRNDF': 'horas',
}
_UNIDAD_TIPOS = {
    'CO_HED': 'horas', 'CO_HEN': 'horas', 'CO_HRN': 'horas', 'CO_HEDDF': 'horas', 'CO_HENDF': 'horas', 'CO_HRDDF': 'horas', 'CO_HRNDF': 'horas',
    'CO_INC_COMUN': 'dias', 'CO_INC_LABORAL': 'dias', 'CO_LIC_MAT': 'dias', 'CO_LIC_PAT': 'dias', 'CO_LIC_REM': 'dias', 'CO_LIC_NR': 'dias',
    'CO_VAC': 'dias',
}


@tagged('post_install', '-at_install')
class TestE11Pieza2a(TransactionCase):

    def _del_modulo(self, modelo):
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', modelo)])
        return self.env[modelo].with_context(active_test=False).browse(datos.mapped('res_id')).exists()

    # ── categorías: sección ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_cada_categoria_del_modulo_trae_su_seccion(self):
        for nombre, seccion in _SECCIONES.items():
            categoria = self.env.ref('l10n_co_nomina_electronica.%s%s' % (_PREFIJO, nombre))
            self.assertEqual(categoria.l10n_co_ne_seccion_concepto, seccion, nombre)
        for nombre in _SIN_SECCION:
            categoria = self.env.ref('l10n_co_nomina_electronica.%s%s' % (_PREFIJO, nombre))
            self.assertFalse(categoria.l10n_co_ne_seccion_concepto, nombre)

    def test_no_hay_categoria_del_modulo_sin_decision(self):
        """Una categoría nueva del módulo debe entrar a una de las dos tablas de arriba (con sección o sin ella a propósito)."""
        decididas = {_PREFIJO + n for n in list(_SECCIONES) + list(_SIN_SECCION)}
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule.category')])
        self.assertEqual({d.name for d in datos}, decididas)

    def test_la_seccion_es_de_cada_categoria_y_no_se_hereda_del_padre(self):
        """«Devengados» (raíz) no tiene sección aunque sus hijas sí: la línea del neto cuelga de la raíz y no debe salir como un devengado."""
        raiz = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_devengados')
        hija = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_devengados_salariales')
        self.assertEqual(hija.parent_id, raiz)
        self.assertFalse(raiz.l10n_co_ne_seccion_concepto)
        neto = self._del_modulo('hr.salary.rule').filtered(lambda r: r.code == 'CO_NETO' and r.struct_id == self.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina'))
        self.assertEqual(neto.category_id, raiz, 'Premisa: CO_NETO cuelga de la raíz')

    # ── reglas: ajustable y unidad ───────────────────────────────────────────────────────────────────────────────────────────────
    def test_la_regla_es_ajustable_por_defecto_segun_su_estructura_y_la_seccion_de_su_categoria(self):
        """La REGLA de siembra (no una lista): estructura con «Usa Conceptos de pago» y categoría con sección devengados o deducciones."""
        reglas = self._del_modulo('hr.salary.rule')
        self.assertTrue(reglas)
        for regla in reglas:
            seccion = regla.category_id.l10n_co_ne_seccion_concepto
            esperado = bool(regla.struct_id.l10n_co_ne_conceptos_de_pago and seccion in ('devengados', 'deducciones'))
            self.assertEqual(regla.l10n_co_ne_ajustable, esperado, '%s (%s)' % (regla.code, regla.struct_id.name))

    def test_los_ejemplos_de_tl_en_la_estructura_general(self):
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        reglas = self._del_modulo('hr.salary.rule').filtered(lambda r: r.struct_id == general)
        for codigo in _EJEMPLOS_AJUSTABLES:
            esas = reglas.filtered(lambda r: r.code == codigo)
            self.assertTrue(esas, codigo)
            self.assertTrue(all(esas.mapped('l10n_co_ne_ajustable')), '%s debe ser ajustable' % codigo)
        for codigo in _EJEMPLOS_DERIVADOS:
            esas = reglas.filtered(lambda r: r.code == codigo)
            self.assertTrue(esas, codigo)
            self.assertFalse(any(esas.mapped('l10n_co_ne_ajustable')), '%s es derivado: no es ajustable' % codigo)

    def test_solo_la_estructura_general_usa_conceptos_de_pago(self):
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        for estructura in self._del_modulo('hr.payroll.structure'):
            self.assertEqual(estructura.l10n_co_ne_conceptos_de_pago, estructura == general, estructura.name)

    def test_el_valor_por_defecto_sigue_a_la_categoria_y_la_decision_manual_se_conserva(self):
        """Campo calculado y editable: cambia al cambiar la categoría o el interruptor de la estructura, no por otras escrituras."""
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        regla = self._del_modulo('hr.salary.rule').filtered(lambda r: r.code == 'CO_OTRAS_DED' and r.struct_id == general)[:1]
        self.assertTrue(regla.l10n_co_ne_ajustable)
        sin_seccion = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_acumuladores_internos')
        con_seccion = regla.category_id
        regla.category_id = sin_seccion
        self.assertFalse(regla.l10n_co_ne_ajustable, 'Una categoría sin sección no se ajusta')
        regla.category_id = con_seccion
        self.assertTrue(regla.l10n_co_ne_ajustable)
        regla.l10n_co_ne_ajustable = False                      # decisión de la empresa
        regla.sequence = regla.sequence + 1                     # otra escritura: no cambia ninguna dependencia
        self.assertFalse(regla.l10n_co_ne_ajustable, 'La decisión manual se conserva')
        general.l10n_co_ne_conceptos_de_pago = False
        self.assertFalse(any(self._del_modulo('hr.salary.rule').filtered(lambda r: r.struct_id == general).mapped('l10n_co_ne_ajustable')),
                         'Sin el interruptor de la estructura ninguna regla se ajusta')

    def test_la_unidad_de_las_reglas_de_la_estructura_general(self):
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        reglas = self._del_modulo('hr.salary.rule').filtered(lambda r: r.struct_id == general)
        for regla in reglas:
            esperada = _UNIDAD_REGLAS.get(regla.code, False)
            self.assertEqual(regla.l10n_co_ne_unidad, esperada, regla.code)
        for codigo in _UNIDAD_REGLAS:
            regla = reglas.filtered(lambda r: r.code == codigo)
            self.assertTrue(regla, codigo)
            self.assertIn('result_qty', regla[:1].amount_python_compute or '', '%s: una regla con unidad devuelve cantidad' % codigo)

    def test_las_reglas_de_otras_estructuras_no_cambian_en_esta_pieza(self):
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        otras = self._del_modulo('hr.salary.rule').filtered(lambda r: r.struct_id != general)
        self.assertTrue(otras)
        self.assertFalse(otras.filtered('l10n_co_ne_ajustable'), 'Q3: las demás estructuras no usan Conceptos de pago todavía')
        self.assertFalse(otras.filtered('l10n_co_ne_unidad'))

    # ── tipos de novedad: cantidad y unidad ──────────────────────────────────────────────────────────────────────────────────────
    def test_los_tipos_de_novedad_de_cantidad_traen_su_unidad(self):
        tipos = self._del_modulo('hr.payslip.input.type')
        for tipo in tipos:
            if tipo.code in _UNIDAD_TIPOS:
                self.assertTrue(tipo.is_quantity, tipo.code)
                self.assertEqual(tipo.l10n_co_ne_unidad, _UNIDAD_TIPOS[tipo.code], tipo.code)
            else:
                self.assertFalse(tipo.is_quantity, '%s es un valor en pesos' % tipo.code)
                self.assertFalse(tipo.l10n_co_ne_unidad, tipo.code)
        self.assertEqual(set(tipos.filtered('is_quantity').mapped('code')), set(_UNIDAD_TIPOS))

    def test_la_siembra_no_pisa_lo_que_el_usuario_configuro_y_rellena_lo_vacio(self):
        Tipo = self.env['hr.payslip.input.type']
        vacaciones = self.env.ref('l10n_co_nomina_electronica.input_co_vac')
        vacaciones.l10n_co_ne_unidad = 'horas'                       # decisión del usuario: no se toca
        hed = self.env.ref('l10n_co_nomina_electronica.input_co_hed')
        hed.write({'l10n_co_ne_unidad': False, 'is_quantity': False})  # vacía: se vuelve a sembrar
        Tipo._l10n_co_cargar_unidad()
        self.assertEqual(vacaciones.l10n_co_ne_unidad, 'horas')
        self.assertEqual((hed.is_quantity, hed.l10n_co_ne_unidad), (True, 'horas'))

    def test_la_unidad_sin_marca_de_cantidad_es_un_error(self):
        Tipo = self.env['hr.payslip.input.type']
        with self.assertRaises(ValidationError):
            Tipo.create({'name': 'Tipo de prueba sin cantidad', 'code': 'PRUEBA_2A_A', 'l10n_co_ne_unidad': 'dias'})
        tipo = Tipo.create({'name': 'Tipo de prueba con cantidad', 'code': 'PRUEBA_2A_B', 'is_quantity': True, 'l10n_co_ne_unidad': 'dias'})
        with self.assertRaises(ValidationError):
            tipo.is_quantity = False

    # ── vistas (Form: mismo camino que el cliente web) ───────────────────────────────────────────────────────────────────────────
    def test_el_formulario_del_tipo_muestra_cantidad_y_unidad_aunque_no_sea_de_asignaciones(self):
        with Form(self.env['hr.payslip.input.type']) as formulario:
            formulario.name = 'Tipo desde el formulario'
            formulario.code = 'PRUEBA_2A_C'
            formulario.is_quantity = True                              # el nativo solo la muestra con «asignaciones»
            formulario.l10n_co_ne_unidad = 'horas'
        tipo = self.env['hr.payslip.input.type'].search([('code', '=', 'PRUEBA_2A_C')])
        self.assertEqual((tipo.is_quantity, tipo.l10n_co_ne_unidad), (True, 'horas'))
        with Form(tipo) as formulario:
            formulario.is_quantity = False
            self.assertFalse(formulario.l10n_co_ne_unidad, 'Quitar «Es cantidad?» vacía la unidad')
        self.assertFalse(tipo.l10n_co_ne_unidad)

    def test_el_formulario_de_la_categoria_trae_su_seccion(self):
        with Form(self.env['hr.salary.rule.category']) as formulario:
            formulario.name = 'Categoría de prueba 2a'
            formulario.code = 'PRUEBA_2A'
            formulario.l10n_co_ne_seccion_concepto = 'deducciones'
        categoria = self.env['hr.salary.rule.category'].search([('code', '=', 'PRUEBA_2A')])
        self.assertEqual(categoria.l10n_co_ne_seccion_concepto, 'deducciones')

    def test_el_formulario_de_la_regla_trae_ajustable_y_unidad(self):
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        regla = self._del_modulo('hr.salary.rule').filtered(lambda r: r.code == 'CO_OTRAS_DED' and r.struct_id == general)[:1]
        self.assertTrue(regla)
        with Form(regla) as formulario:
            formulario.l10n_co_ne_ajustable = False             # editable aunque tenga valor por defecto
            formulario.l10n_co_ne_unidad = 'dias'
        self.assertEqual((regla.l10n_co_ne_ajustable, regla.l10n_co_ne_unidad), (False, 'dias'))

    def test_el_formulario_de_la_estructura_trae_el_interruptor(self):
        estructura = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        self.assertFalse(estructura.l10n_co_ne_conceptos_de_pago)
        with Form(estructura) as formulario:
            formulario.l10n_co_ne_conceptos_de_pago = True
        self.assertTrue(estructura.l10n_co_ne_conceptos_de_pago)
        categoria_dev = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_category_incapacidades')
        reglas = self._del_modulo('hr.salary.rule').filtered(lambda r: r.struct_id == estructura and r.category_id == categoria_dev)
        self.assertTrue(reglas, 'Premisa: la liquidación tiene reglas de incapacidades')
        for regla in reglas:
            self.assertTrue(regla.l10n_co_ne_ajustable, 'Al activar la estructura sus reglas con sección pasan a ser ajustables por defecto')
