# -*- coding: utf-8 -*-
"""Frente 5, C3 (doc 58): informe "Comprobante de pago por fecha de pago": una página por (empleado, fecha de pago),
una sección por recibo con el nombre de su estructura, neto total pagado, A5 horizontal con formato de papel propio,
interno (sin DIAN/CUNE/QR), nativo y multicliente.

E11 pieza 5b (.292; doc 58 §5(a) y §9 D5-1/D5-5/D5-7): cada sección por origen (quincena, prima...) trae la tabla compacta de la colilla (``ne_colilla_tabla``)
con SU subtotal de devengado, deducciones y neto, y al pie va el neto total pagado; todo en UNA sola media página (``class="page"``) por grupo."""
from datetime import date
from html import escape

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common_importes import valores_monetarios

REPORTE = 'l10n_co_nomina_electronica.action_report_comprobante_pago'
PROHIBIDOS = ('DIAN', 'Resolucion', 'Resolución', 'CUNE', 'Estado NE', '/report/barcode', 'QR', 'Firma del empleado')


@tagged('post_install', '-at_install')
class TestComprobantePago(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Comprobante', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.nomina = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.a, cls.emp_a, cls.con_a = cls._compania('Empresa Alfa Pago', 'Empleado Alfa Pago')
        cls.b, cls.emp_b, cls.con_b = cls._compania('Empresa Beta Pago', 'Empleado Beta Pago')

    @classmethod
    def _compania(cls, nombre, empleado):
        company = cls.env['res.company'].create({
            'name': nombre, 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        emp = cls.env['hr.employee'].create({
            'name': empleado, 'company_id': company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = cls.env['hr.contract'].create({
            'name': 'Contrato %s' % empleado, 'employee_id': emp.id, 'company_id': company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        return company, emp, contrato

    def _recibo(self, company, emp, contrato, estructura, lineas, pagado, nombre, desde=date(2026, 6, 1),
                hasta=date(2026, 6, 15)):
        recibo = self.env['hr.payslip'].create({
            'name': nombre, 'employee_id': emp.id, 'contract_id': contrato.id, 'company_id': company.id,
            'struct_id': estructura.id, 'date_from': desde, 'date_to': hasta})
        for codigo, total in lineas:
            regla = self.env['hr.salary.rule'].search(
                [('code', '=', codigo), ('struct_id', '=', estructura.id)], limit=1)
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                'contract_id': contrato.id, 'employee_id': emp.id, 'quantity': 1.0, 'rate': 100.0,
                'amount': total, 'total': total})
        recibo.write({'state': 'done', 'paid_date': pagado})
        return recibo

    def _quincena(self, pagado=date(2026, 6, 15), compania=None):
        c, e, k = compania or (self.a, self.emp_a, self.con_a)
        return self._recibo(c, e, k, self.nomina, (('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0),
                                                   ('CO_PENSION_EMP', -120000.0), ('CO_NETO', 2760000.0)),
                            pagado, 'Quincena %s' % e.name)

    def _prima(self, pagado=date(2026, 6, 15)):
        return self._recibo(self.a, self.emp_a, self.con_a, self.prima,
                            (('CO_PRIMA_VALOR', 1500000.0), ('CO_PRIMA_RETE', -60000.0), ('CO_PRIMA_NETO', 1440000.0)),
                            pagado, 'Prima Alfa', desde=date(2026, 1, 1))

    def _html(self, *recibos):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [r.id for r in recibos])
        return html.decode().replace('\xa0', ' ')

    def _cuerpo(self, html):
        return html.split('class="page"', 1)[-1]

    def test_quincena_y_prima_del_mismo_dia_en_una_sola_pagina_con_dos_secciones_y_neto_total(self):
        q, p = self._quincena(), self._prima()
        html = self._html(q, p)
        self.assertEqual(html.count('class="page"'), 1, 'UNA página por (empleado, fecha de pago), con las dos secciones de origen')
        # una sección por origen, en orden (quincena y luego prima), cada una con el nombre de su estructura
        self.assertIn(self.nomina.name, html)
        self.assertIn(self.prima.name, html)
        self.assertLess(html.index(self.nomina.name), html.index(self.prima.name))
        # cada sección trae la tabla compacta de la colilla con SU subtotal (devengado, deducciones y neto de esa sección)...
        self.assertEqual(html.count('Total devengado'), 2)
        self.assertEqual(html.count('Total deducciones'), 2)
        self.assertEqual(html.count('Neto a pagar'), 2)
        valores = valores_monetarios(html)
        absolutos = {abs(v) for v in valores}
        for esperado in (3000000.0, 240000.0, 2760000.0,      # quincena: devengado, deducciones (salud + pensión), neto
                         1500000.0, 60000.0, 1440000.0):       # prima: devengado, retención, neto
            self.assertIn(esperado, absolutos, esperado)
        # ... y al pie, UNA vez y DESPUÉS de las dos secciones, el neto total pagado (2.760.000 + 1.440.000)
        self.assertEqual(html.count('Neto total pagado'), 1)
        self.assertGreater(html.index('Neto total pagado'), html.rindex('Neto a pagar'))
        self.assertIn(4200000.0, valores)
        # la retención de la prima sale como fila de Deducciones de su sección (la tabla compacta ya no lleva el párrafo de resumen)
        retencion = self.env['hr.salary.rule'].search([('code', '=', 'CO_PRIMA_RETE'), ('struct_id', '=', self.prima.id)], limit=1).name
        self.assertTrue(retencion in html or escape(retencion) in html)
        self.assertNotIn('Salud:', html)
        # encabezado del grupo: la fecha de pago del grupo UNA vez; el «No.» y el periodo son de cada origen (van en el título de su sección)
        self.assertEqual(html.count('Fecha de pago:'), 1)
        self.assertNotIn('No.:', html)
        self.assertNotIn('Periodo:', html)
        self.assertEqual(html.count('table table-sm table-bordered small'), 3, 'Dos tablas compactas (una por origen) y la del neto total')

    def test_un_grupo_de_un_solo_recibo_trae_su_seccion_y_el_neto_total(self):
        html = self._html(self._quincena())
        self.assertEqual(html.count('class="page"'), 1)
        self.assertEqual(html.count('Neto a pagar'), 1)
        self.assertEqual(html.count('Neto total pagado'), 1)
        self.assertIn(2760000.0, valores_monetarios(html))

    def test_el_encabezado_de_la_colilla_por_recibo_no_cambia(self):
        """El modo ``agrupado`` del encabezado compartido solo aplica al comprobante agrupado: la colilla individual conserva «No.» y periodo."""
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(
            'l10n_co_nomina_electronica.action_report_payslip_ne', [self._quincena().id])
        html = html.decode().replace('\xa0', ' ')
        self.assertEqual(html.count('class="page"'), 1)
        self.assertIn('No.:', html)
        self.assertIn('Periodo:', html)

    def test_pagos_en_dias_distintos_son_paginas_distintas(self):
        html = self._html(self._quincena(), self._prima(pagado=date(2026, 6, 20)))
        self.assertEqual(html.count('class="page"'), 2)

    def test_imprimir_desde_un_solo_recibo_trae_el_pago_completo(self):
        q, p = self._quincena(), self._prima()
        html = self._html(p)
        self.assertEqual(html.count('class="page"'), 1)
        self.assertIn(self.nomina.name, html)       # la quincena del mismo pago
        self.assertIn(4200000.0, valores_monetarios(html))

    def test_un_recibo_sin_fecha_de_pago_hace_fallar_el_informe_y_lo_nombra(self):
        sin_fecha = self._quincena(pagado=False)
        with self.assertRaises(UserError) as exc:
            self._html(sin_fecha)
        self.assertIn(sin_fecha.display_name, str(exc.exception))
        self.assertIn('fecha de pago', str(exc.exception))

    def test_es_un_comprobante_interno_sin_dian_cune_ni_qr(self):
        cuerpo = self._cuerpo(self._html(self._quincena(), self._prima()))
        for texto in PROHIBIDOS:
            self.assertNotIn(texto, cuerpo, '"%s" no debe aparecer' % texto)
        self.assertNotIn('<img', cuerpo)
        self.assertNotIn('style=', cuerpo)

    def test_multicliente_cada_comprobante_lleva_solo_los_datos_de_su_compania(self):
        html_a = self._html(self._quincena())
        html_b = self._html(self._quincena(compania=(self.b, self.emp_b, self.con_b)))
        self.assertIn('Empleado Alfa Pago', html_a)
        self.assertNotIn('Empleado Beta Pago', html_a)
        self.assertNotIn('Empresa Beta Pago', html_a)
        self.assertIn('Empleado Beta Pago', html_b)
        self.assertNotIn('Empleado Alfa Pago', html_b)
        self.assertNotIn('Empresa Alfa Pago', html_b)

    def test_los_importes_usan_la_moneda_de_la_compania(self):
        euro = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'EUR')], limit=1)
        euro.active = True
        self.b.currency_id = euro
        html = self._html(self._quincena(compania=(self.b, self.emp_b, self.con_b)))
        self.assertIn('€', html)
        self.assertIn(2760000.0, valores_monetarios(html))

    def test_media_hoja_a4_horizontal_con_formato_de_papel_propio(self):
        accion = self.env.ref(REPORTE)
        formato = accion.paperformat_id
        self.assertEqual((formato.format, formato.orientation), ('A5', 'Landscape'))
        self.assertFalse(formato.default)                          # no se vuelve el formato de papel por defecto
        self.assertEqual(formato, self.env.ref('l10n_co_nomina_electronica.paperformat_comprobante_pago'))
        self.assertNotEqual(formato, self.a.paperformat_id)        # no cambia el de la compañía
        # E11 pieza 5a (.291, decisión de David del 21-nov): la colilla por recibo TAMBIÉN es de media página, con el mismo formato (antes usaba el de la
        # compañía); nunca carta completa.
        self.assertEqual(formato, self.env.ref(
            'l10n_co_nomina_electronica.action_report_payslip_ne').paperformat_id)
