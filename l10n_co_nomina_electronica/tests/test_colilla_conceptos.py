# -*- coding: utf-8 -*-
"""E11 pieza 5a (.291, doc 74 §4): la colilla por recibo con el diseño de «Conceptos de pago», de MEDIA PÁGINA.

Reglas que se prueban (decisiones de David del 21-nov, vía el Tech Lead):
- La colilla es SIEMPRE de media página (A5 horizontal; nunca carta completa) y cada recibo va en su propia media página (cada recibo llama a su
  propio ``web.external_layout``): se afirma sobre el formato de papel y sobre el HTML.
- Tabla COMPACTA: letra menor, solo filas con valor y solo las columnas que alguna fila usa (sin Cantidad y Unidad si ninguna fila lleva unidad,
  sin «%» si todas son 100). Deducciones con su signo, en una sola columna. Con los datos de la empresa (nombre, NIT y dirección). Sin
  «Observaciones» (nota interna), sin ajuste de la empresa ni costo de la empresa, sin nada de la DIAN.
- Un recibo que no cuadra con el neto IMPRIME la diferencia (criterio del Frente 5): no la oculta ni falla.
- Las filas salen de ``HrPayslip._ne_filas_de_concepto``, la MISMA fuente de la pestaña «Conceptos de pago»: el refactor de la pieza 3 no cambia
  ni una fila (oráculo: copia literal del armado anterior). El total por sección coincide con ``_ne_desglose`` (que clasifica por signo) en las 4
  estructuras. NO EJECUTADAS en Odoo al escribirlas."""

from collections import defaultdict
from datetime import date

from odoo import _
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import formatLang

from .common_importes import valores_monetarios

REPORTE = 'l10n_co_nomina_electronica.action_report_payslip_ne'
REPORTE_AGRUPADO = 'l10n_co_nomina_electronica.action_report_comprobante_pago'
PROHIBIDOS = ('DIAN', 'Resolucion', 'Resolución', 'CUNE', 'Estado NE', '/report/barcode', 'QR', 'Firma del empleado')


@tagged('post_install', '-at_install')
class TestColillaConceptos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        valores = {
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.company = cls.env['res.company'].create(dict(valores, name='Compañía Colilla Conceptos'))
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Colilla Conceptos', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.bonificacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')
        cls.tipo_bonif_nosal = ref('l10n_co_nomina_electronica.input_co_bonif_nosal')
        cls.tipo_bon_valor = ref('l10n_co_nomina_electronica.input_co_bon_valor')
        cls.Concepto = cls.env['l10n.co.payslip.concepto']
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, estructura=None, desde=date(2026, 9, 1), hasta=date(2026, 9, 15), calcular=True):
        """Recibo de un empleado nuevo; con ``calcular`` queda con la hoja real. La bonificación lleva su novedad CO_BON_VALOR (sin ella no genera línea)."""
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Colilla Conceptos %s' % self.n,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato Colilla Conceptos %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Colilla Conceptos %s' % self.n, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})
        if estructura == self.bonificacion:
            self.env['hr.payslip.input'].create({
                'payslip_id': recibo.id, 'input_type_id': self.tipo_bon_valor.id, 'code': 'CO_BON_VALOR', 'amount': 500000.0})
        if calcular:
            recibo.compute_sheet()
        return recibo

    def _cuatro_recibos(self):
        return (
            self._recibo(self.general),
            self._recibo(self.prima, desde=date(2026, 7, 1), hasta=date(2026, 12, 31)),
            self._recibo(self.liquidacion, desde=date(2024, 3, 1), hasta=date(2026, 8, 15)),
            self._recibo(self.bonificacion),
        )

    def _sintetico(self, estructura, lineas, **kw):
        """Recibo SIN calcular con las líneas dadas ``(código, total[, porcentaje])``: valores fijos a mano (cantidad 1, porcentaje 100 salvo indicación)."""
        recibo = self._recibo(estructura, calcular=False, **kw)
        for linea in lineas:
            codigo, total = linea[0], linea[1]
            porcentaje = linea[2] if len(linea) > 2 else 100.0
            regla = self.env['hr.salary.rule'].search([('code', '=', codigo), ('struct_id', '=', estructura.id)], limit=1)
            self.assertTrue(regla, 'Falta la regla %s en %s' % (codigo, estructura.name))
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name, 'contract_id': recibo.contract_id.id,
                'employee_id': recibo.employee_id.id, 'quantity': 1.0, 'rate': porcentaje, 'amount': total / (porcentaje / 100.0), 'total': total})
        return recibo

    def _html(self, *recibos):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [r.id for r in recibos])
        return html.decode().replace('\xa0', ' ')

    def _cuerpo(self, *recibos):
        """Solo lo que viene después de la primera página abierta (sin el encabezado y el pie del layout nativo de la compañía)."""
        return self._html(*recibos).split('class="page"', 1)[-1]

    # ── la pieza 3 no cambió: el armado anterior de las filas es el oráculo ────────────────────────────────────────────────────────
    def _valores_anteriores(self, recibo):
        """COPIA LITERAL de ``l10n.co.payslip.concepto._valores_del_recibo`` de .289/.290 (antes de extraer ``_ne_filas_de_concepto``): el oráculo de
        la prueba de equivalencia."""
        ajustes = {a.salary_rule_id.id: a for a in recibo.l10n_co_ajuste_ids}
        entradas = defaultdict(list)
        for entrada in recibo.input_line_ids.sorted(lambda i: (i.sequence, i.id)):
            entradas[entrada.code].append(entrada)
        secciones = (('devengados', 'Devengados'), ('deducciones', 'Deducciones'))
        lineas = recibo.line_ids.filtered(
            lambda l: l.appears_on_payslip and l.category_id.l10n_co_ne_seccion_concepto in dict(secciones)
            and (l.total or l.salary_rule_id.id in ajustes)).sorted(lambda l: (l.sequence, l.id))
        titulos = {'devengados': _('Devengados'), 'deducciones': _('Deducciones')}
        valores, secuencia = [], 0

        def siguiente():
            nonlocal secuencia
            secuencia += 10
            return secuencia

        vistos_por_codigo = defaultdict(int)
        for seccion, _titulo in secciones:
            de_la_seccion = lineas.filtered(lambda l: l.category_id.l10n_co_ne_seccion_concepto == seccion)
            if not de_la_seccion:
                continue
            valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_section', 'name': titulos[seccion], 'origen': 'calculado'})
            dias_puestos = False
            for linea in de_la_seccion:
                regla = linea.salary_rule_id
                ajuste = ajustes.get(regla.id)
                posicion = vistos_por_codigo[regla.code]
                vistos_por_codigo[regla.code] += 1
                candidatas = entradas.get(regla.code, [])
                entrada = candidatas[posicion] if posicion < len(candidatas) else False
                origen = 'novedad' if entrada else 'calculado'
                tipo = entrada.input_type_id if entrada else self.env['hr.payslip.input.type']
                unidad = (tipo.l10n_co_ne_unidad if (tipo and tipo.is_quantity) else False) or regla.l10n_co_ne_unidad or False
                valores.append({
                    'slip_id': recibo.id, 'sequence': siguiente(), 'name': linea.name, 'origen': origen, 'line_id': linea.id,
                    'salary_rule_id': regla.id, 'input_id': entrada.id if entrada else False, 'input_type_id': tipo.id if tipo else False,
                    'quantity': linea.quantity, 'rate': linea.rate, 'amount': linea.amount, 'total': linea.total, 'unidad': unidad,
                    'ajustado': bool(ajuste)})
                if ajuste:
                    texto = _('Ajustado por la empresa.')
                    if ajuste.con_sugerido:
                        texto = _('Ajustado por la empresa. Sugerido: %s', formatLang(self.env, ajuste.sugerido_total, digits=2))
                    valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_note', 'name': texto, 'origen': 'calculado'})
                if (not dias_puestos and seccion == 'devengados' and regla.l10n_co_ne_dian_concept == 'Sueldo'
                        and recibo.struct_id.use_worked_day_lines):
                    dias_puestos = True
                    for dia in recibo.worked_days_line_ids.sorted(lambda w: (w.sequence, w.id)):
                        if not (dia.number_of_days or dia.number_of_hours):
                            continue
                        valores.append({
                            'slip_id': recibo.id, 'sequence': siguiente(), 'name': dia.name or dia.work_entry_type_id.name, 'origen': 'dias',
                            'worked_day_id': dia.id, 'quantity': dia.number_of_days, 'unidad': 'dias', 'rate': 0.0})
        return valores

    def test_01_las_filas_de_la_pestana_son_las_mismas_que_antes_del_refactor_en_las_cuatro_estructuras(self):
        general, prima, liquidacion, bonificacion = self._cuatro_recibos()
        # La general con una novedad y un ajuste: cubre el enlace a la novedad, la nota del ajuste y las filas de días.
        self.env['hr.payslip.input'].create({
            'payslip_id': general.id, 'input_type_id': self.tipo_bonif_nosal.id, 'code': 'CO_BONIF_NOSAL', 'amount': 300000.0})
        linea = general.line_ids.filtered(lambda l: l.code == 'CO_BASICO')         # .298: la salud, el auxilio y lo de ley ya no se ajustan; el sueldo sí
        self.env['l10n.co.payslip.ajuste'].create({
            'slip_id': general.id, 'salary_rule_id': linea.salary_rule_id.id, 'quantity': linea.quantity, 'rate': linea.rate, 'amount': 0.0})
        general.compute_sheet()
        for recibo in (general, prima, liquidacion, bonificacion):
            self.assertTrue(recibo.line_ids, recibo.struct_id.name)
            self.assertEqual(self.Concepto._valores_del_recibo(recibo), self._valores_anteriores(recibo),
                             'Las filas de «%s» cambiaron con el método compartido' % recibo.struct_id.name)
        self.assertTrue(general.l10n_co_ajuste_ids and general.input_line_ids, 'Premisa: la general lleva ajuste y novedad')

    def test_02_cada_fila_de_la_pestana_sale_de_una_fila_compartida_y_en_el_mismo_orden(self):
        recibo = self._recibo(self.general)
        self.assertTrue(recibo.l10n_co_ne_usa_conceptos)
        de_la_pestana = recibo.l10n_co_concepto_ids.filtered(lambda f: not f.display_type and f.origen != 'dias').mapped('line_id').ids
        compartidas = [f['linea'].id for f in recibo._ne_filas_de_concepto()]
        self.assertTrue(compartidas, 'Premisa: el recibo tiene conceptos')
        self.assertEqual(de_la_pestana, compartidas)      # listas de ids: la comparación de recordsets ignora el orden

    # ── la tabla: secciones, columnas, signos, datos de la empresa ───────────────────────────────────────────────────────────────
    def test_03_la_tabla_trae_secciones_totales_y_neto_sin_codigo(self):
        recibo = self._recibo(self.general)
        cuerpo = self._cuerpo(recibo)
        for texto in ('Devengados', 'Deducciones', 'Total devengado', 'Total deducciones', 'Neto a pagar', 'Concepto', 'Importe', 'Total'):
            self.assertIn(texto, cuerpo)
        self.assertNotIn('>Código<', cuerpo, 'Sin columna de código')
        self.assertNotIn('>Devengado<', cuerpo, 'Sin la columna aparte de devengado')
        self.assertNotIn('>Deducción<', cuerpo, 'Sin la columna aparte de deducción')
        colilla = recibo._ne_colilla()
        self.assertEqual([s['seccion'] for s in colilla['secciones']], ['devengados', 'deducciones'])
        self.assertLess(colilla['total_deducciones'], 0.0, 'Las deducciones van con su signo')
        valores = valores_monetarios(cuerpo)
        self.assertIn(recibo._ne_pdf_neto(), valores)
        self.assertIn(colilla['total_deducciones'], valores, 'El total de deducciones se imprime NEGATIVO, en la misma columna Total')

    def test_04_cantidad_y_unidad_solo_con_unidad_y_porcentaje_solo_si_no_es_100(self):
        recibo = self._recibo(self.general)
        filas = recibo._ne_filas_de_concepto()
        planas = [f for s in recibo._ne_colilla()['secciones'] for f in s['filas']]
        self.assertEqual(len(planas), len(filas), 'La colilla imprime exactamente las filas compartidas')
        for fila, impresa in zip(filas, planas):
            self.assertEqual(impresa['nombre'], fila['nombre'])
            self.assertEqual(impresa['cantidad'] is False, not fila['unidad'], 'Cantidad solo si la fila lleva unidad: %s' % fila['nombre'])
            self.assertEqual(impresa['porcentaje'] is False, abs(fila['porcentaje'] - 100.0) < 0.0001, '%% solo si no es 100: %s' % fila['nombre'])
        sueldo = next(i for f, i in zip(filas, planas) if f['regla'].code == 'CO_BASICO')
        self.assertEqual(sueldo['unidad'], 'Días')
        self.assertIsNot(sueldo['cantidad'], False)
        salud = next(i for f, i in zip(filas, planas) if f['regla'].code == 'CO_SALUD_EMP')
        self.assertIs(salud['cantidad'], False)

    def test_05_las_columnas_opcionales_se_omiten_si_ninguna_fila_las_usa(self):
        # Liquidación sintética: sin unidades y todo al 100 %: la tabla queda con Concepto, Importe y Total.
        sin = self._sintetico(self.liquidacion, [('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_SALUD', -36000.0), ('CO_LIQ_NETO', 864000.0)])
        cuerpo = self._cuerpo(sin)
        for texto in ('>Cantidad<', '>Unidad<', '>%<'):
            self.assertNotIn(texto, cuerpo, 'Sin %s cuando ninguna fila la usa' % texto)
        # Con una fila con porcentaje distinto de 100 aparece «%», y con una fila con unidad (el sueldo de la general, en días) aparecen Cantidad y Unidad.
        con_pct = self._sintetico(self.liquidacion, [('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_SALUD', -36000.0, 4.0), ('CO_LIQ_NETO', 864000.0)])
        self.assertIn('>%<', self._cuerpo(con_pct))
        self.assertNotIn('>Unidad<', self._cuerpo(con_pct))
        con_unidad = self._sintetico(self.general, [('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_NETO', 2880000.0)])
        cuerpo = self._cuerpo(con_unidad)
        self.assertIn('>Cantidad<', cuerpo)
        self.assertIn('>Unidad<', cuerpo)

    # ── MEDIA PÁGINA: restricción dura de David ─────────────────────────────────────────────────────────────────────────────────────
    def test_06_la_colilla_es_de_media_pagina_a5_horizontal_igual_que_el_comprobante_agrupado(self):
        colilla = self.env.ref(REPORTE)
        agrupado = self.env.ref(REPORTE_AGRUPADO)
        papel = colilla.paperformat_id
        self.assertTrue(papel, 'La colilla tiene formato de papel propio: sin él usaría el de la compañía (carta/A4 completo)')
        self.assertEqual((papel.format, papel.orientation), ('A5', 'Landscape'))
        self.assertEqual(papel, agrupado.paperformat_id, 'Un solo formato de media página para la colilla y el comprobante')
        self.assertFalse(papel.default, 'No cambia el formato de papel de la compañía ni el de otros informes')

    def test_07_cada_recibo_va_en_su_propia_media_pagina_y_la_tabla_es_compacta(self):
        a = self._sintetico(self.general, [('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_NETO', 2880000.0)])
        b = self._sintetico(self.prima, [('CO_PRIMA_VALOR', 1500000.0), ('CO_PRIMA_RETE', -60000.0), ('CO_PRIMA_NETO', 1440000.0)],
                            desde=date(2026, 7, 1), hasta=date(2026, 12, 31))
        html = self._html(a, b)
        self.assertEqual(html.count('class="page"'), 2, 'Un recibo = una media página (un layout y un bloque de página por recibo)')
        self.assertEqual(html.count('Neto a pagar'), 2)
        self.assertEqual(self._html(a).count('class="page"'), 1)
        self.assertIn('table table-sm table-bordered small', html, 'Tabla compacta: clase nativa de letra menor')
        self.assertNotIn('style=', self._cuerpo(a), 'Sin estilos en línea')

    def test_08_solo_filas_con_valor(self):
        recibo = self._sintetico(self.liquidacion, [
            ('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_CESANTIAS', 0.0), ('CO_LIQ_SALUD', -36000.0), ('CO_LIQ_NETO', 864000.0)])
        cuerpo = self._cuerpo(recibo)
        regla = self.env['hr.salary.rule']
        salarios = regla.search([('code', '=', 'CO_LIQ_SALARIOS'), ('struct_id', '=', self.liquidacion.id)], limit=1)
        cesantias = regla.search([('code', '=', 'CO_LIQ_CESANTIAS'), ('struct_id', '=', self.liquidacion.id)], limit=1)
        nombres = [f['nombre'] for s in recibo._ne_colilla()['secciones'] for f in s['filas']]
        self.assertIn(salarios.name, nombres)
        self.assertNotIn(cesantias.name, nombres, 'Una línea en cero no se imprime')
        self.assertEqual(len(nombres), 2, 'Solo las dos filas con valor: salarios y salud')
        self.assertNotIn('>%s<' % cesantias.name, cuerpo)

    # ── datos de la empresa, sin observaciones, sin ajuste ni costo de la empresa, sin DIAN ──────────────────────────────────────────
    def test_09_lleva_nombre_nit_y_direccion_de_la_empresa_del_recibo(self):
        partner = self.company.partner_id
        partner.with_context(no_vat_validation=True).write({'vat': '901797249-5', 'street': 'Calle 12 # 34-56', 'city': 'Bogotá'})
        recibo = self._sintetico(self.general, [('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_NETO', 2880000.0)])
        cuerpo = self._cuerpo(recibo)
        self.assertIn('Empleador:', cuerpo)
        self.assertIn('Compañía Colilla Conceptos', cuerpo)
        self.assertIn('NIT:', cuerpo)
        self.assertIn('901797249-5', cuerpo)
        self.assertIn('Calle 12 # 34-56', cuerpo)

    def test_10_no_imprime_observaciones_ni_el_ajuste_ni_el_costo_de_la_empresa_ni_nada_de_la_dian(self):
        recibo = self._recibo(self.general)
        recibo.note = 'NOTA INTERNA DE PRUEBA'
        linea = recibo.line_ids.filtered(lambda l: l.code == 'CO_BASICO')          # .298: la salud, el auxilio y lo de ley ya no se ajustan; el sueldo sí
        ajuste = self.env['l10n.co.payslip.ajuste'].create({
            'slip_id': recibo.id, 'salary_rule_id': linea.salary_rule_id.id, 'quantity': linea.quantity, 'rate': linea.rate, 'amount': 0.0})
        recibo.compute_sheet()
        self.assertTrue(ajuste.exists() and ajuste.estado == 'aplicado', 'Premisa: el sueldo quedó ajustado a 0')
        cuerpo = self._cuerpo(recibo)
        for texto in ('Observaciones', 'NOTA INTERNA DE PRUEBA', 'Ajustado', 'Sugerido', 'Costo empresa', 'Costo de la empresa') + PROHIBIDOS:
            self.assertNotIn(texto, cuerpo, '"%s" no debe aparecer en la colilla' % texto)
        self.assertNotIn('<img', cuerpo)
        sueldo = next(f for f in recibo._ne_filas_de_concepto() if f['regla'].code == 'CO_BASICO')
        self.assertEqual(sueldo['total'], 0.0, 'Lo ajustado se imprime con su valor: la fila del sueldo sigue visible en 0')
        self.assertIn(sueldo['nombre'], cuerpo)

    # ── cuadra con el neto y con el desglose ────────────────────────────────────────────────────────────────────────────────────────
    def test_11_la_tabla_cuadra_con_el_neto_y_con_el_desglose_en_las_cuatro_estructuras(self):
        for recibo in self._cuatro_recibos():
            colilla = recibo._ne_colilla()
            desglose = recibo._ne_desglose()
            etiqueta = recibo.struct_id.name
            self.assertEqual(colilla['diferencia'], 0.0, '%s: la tabla debe cuadrar con el neto' % etiqueta)
            self.assertAlmostEqual(colilla['total_devengado'] + colilla['total_deducciones'], colilla['neto'], delta=1.0, msg=etiqueta)
            self.assertAlmostEqual(colilla['total_devengado'], desglose['devengado'], delta=1.0,
                                   msg='%s: «Total devengado» por sección = por signo (_ne_desglose)' % etiqueta)
            self.assertAlmostEqual(-colilla['total_deducciones'], desglose['deducciones'], delta=1.0,
                                   msg='%s: «Total deducciones» por sección = por signo (_ne_desglose)' % etiqueta)

    def test_12_un_recibo_que_no_cuadra_imprime_la_diferencia_y_no_falla(self):
        recibo = self._sintetico(self.general, [('CO_BASICO', 3000000.0), ('CO_NETO', 2900000.0)])
        colilla = recibo._ne_colilla()
        self.assertEqual(colilla['diferencia'], -100000.0)
        cuerpo = self._cuerpo(recibo)
        self.assertIn('Diferencia sin clasificar', cuerpo)
        self.assertIn(-100000.0, valores_monetarios(cuerpo))
        self.assertIn(2900000.0, valores_monetarios(cuerpo), 'El neto impreso sigue siendo el de la línea de neto')
        # menos de un peso es redondeo: no se imprime
        redondeo = self._sintetico(self.general, [('CO_BASICO', 3000000.0), ('CO_NETO', 3000000.4)])
        self.assertEqual(redondeo._ne_colilla()['diferencia'], 0.0)
        self.assertNotIn('Diferencia sin clasificar', self._cuerpo(redondeo))
