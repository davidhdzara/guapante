# -*- coding: utf-8 -*-
"""H-QA-034: «Días trabajados» de la colilla = los días con que se PAGÓ el recibo (cantidad GUARDADA de su línea de sueldo).

Defecto (QA, recibo SLIP/17525, 01 al 16-nov-2026): la colilla decía «Días trabajados: 11,0» y Sueldo Básico se pagaba por 16 días. La
plantilla imprimía la línea nativa ``WORK100`` (horas del calendario del contrato / horas por día: lun-vie), mientras que ``CO_BASICO`` y
el ``DiasTrabajados`` del XML usan ``HrPayslip._ne_dias_pagables()`` (mes comercial). AUD-DIAN-34 (2026-10-05, ``test_dias_trabajados.py``) ya
había corregido esa doble fuente en el XML; la colilla conservó la vieja.

Ahora ``report.l10n_co_nomina_electronica.report_payslip_ne`` entrega la línea ``CO_BASICO`` (nómina general) o ``CO_LIQ_SALARIOS``
(liquidación) y la plantilla imprime su ``quantity``. Sin esa línea (prima, bonificación) el campo no sale; nunca se cae a ``WORK100``.

Valores a mano: septiembre de 2026 completo = 30 días del mes comercial (``CO_BASICO.quantity`` = 30); sus lunes a viernes son 22
(el 1.º es martes: 8 días de fin de semana: 5, 6, 12, 13, 19, 20, 26, 27). Con el contrato desde el 11-sep, 11 al 30 = 20 días.
NO ejecutadas en Odoo.
"""

import re
from datetime import date

from odoo.tests.common import TransactionCase, tagged

REPORTE = 'l10n_co_nomina_electronica.action_report_payslip_ne'
MODELO_INFORME = 'report.l10n_co_nomina_electronica.report_payslip_ne'


@tagged('post_install', '-at_install')
class TestColillaDiasPagados(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Colilla Días'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Colilla Días', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.est_general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.est_liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.est_prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.est_bonificacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')

    def _recibo(self, estructura, name='Recibo', date_from=date(2026, 9, 1), date_to=date(2026, 9, 30)):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00',
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date_from, 'date_to': date_to})

    def _linea(self, slip, code, total, quantity=1.0):
        regla = self.env['hr.salary.rule'].search([('code', '=', code), ('struct_id', '=', slip.struct_id.id)], limit=1)
        self.assertTrue(regla, 'Falta la regla %s en %s' % (code, slip.struct_id.name))
        return self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': regla.id, 'code': code, 'name': code,
            'contract_id': slip.contract_id.id, 'employee_id': slip.employee_id.id,
            'quantity': quantity, 'rate': 100.0, 'amount': total / quantity, 'total': total})

    def _con_work100(self, slip, dias):
        """Una línea de días trabajados WORK100 (la fuente que imprimía la colilla antes) con el valor ``dias``."""
        tipo = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)
        self.assertTrue(tipo, 'Falta el tipo de entrada de trabajo WORK100 (hr_work_entry)')
        return self.env['hr.payslip.worked_days'].create({
            'payslip_id': slip.id, 'work_entry_type_id': tipo.id, 'number_of_days': dias, 'number_of_hours': dias * 8})

    def _html(self, slip):
        html, _tipo = self.env['ir.actions.report']._render_qweb_html(REPORTE, [slip.id])
        return html.decode().replace('\xa0', ' ')

    def _dias_impresos(self, html):
        """Lo que el encabezado imprime tras «Días trabajados:» como número (sin depender del idioma), o None si el campo no sale."""
        encontrado = re.search(r'Días trabajados:</strong>\s*<span[^>]*>([^<]+)</span>', html)
        if not encontrado:
            return None
        return float(encontrado.group(1).strip().replace('\xa0', '').replace(' ', '').replace(',', '.'))

    def test_general_imprime_la_cantidad_guardada_de_co_basico(self):
        """Septiembre completo: CO_BASICO se paga por 30 días del mes comercial y la colilla imprime 30. Desde .280 (doc 68, Fase 1) la línea
        de días «Asistencia» (WORK100) ya es esa misma cantidad (antes eran los 22 días lun-vie del calendario): la colilla sigue leyendo la
        línea de sueldo guardada, no WORK100 (``test_sin_linea_de_sueldo_no_cae_a_work100``), y las dos fuentes ahora coinciden."""
        slip = self._recibo(self.est_general, 'General')
        slip.compute_sheet()
        basico = slip.line_ids.filtered(lambda l: l.code == 'CO_BASICO')
        self.assertEqual(len(basico), 1)
        self.assertEqual(basico.quantity, 30.0)
        # .284 (E2a): «Asistencia» son los días laborados; con los festivos trabajados, los descansos y el ajuste del mes suman los pagados.
        pagados = sum(slip.worked_days_line_ids.filtered(
            lambda w: w.code in ('WORK100', 'CO_FEST_TRAB', 'CO_DESCANSO_REM', 'CO_AJUSTE_MES')).mapped('number_of_days'))
        self.assertEqual(pagados, 30.0, 'Las líneas del desglose suman los días pagados (.280, .284)')
        self.assertEqual(self._dias_impresos(self._html(slip)), 30.0)

    def test_liquidacion_imprime_la_cantidad_guardada_de_co_liq_salarios(self):
        """Con líneas sintéticas: CO_LIQ_SALARIOS por 7 días y un WORK100 de 20 días que NO debe usarse."""
        slip = self._recibo(self.est_liquidacion, 'Liquidacion')
        self._linea(slip, 'CO_LIQ_SALARIOS', 700000.0, quantity=7.0)
        self._linea(slip, 'CO_LIQ_NETO', 700000.0)
        self._con_work100(slip, 20.0)
        self.assertEqual(self._dias_impresos(self._html(slip)), 7.0)
        dias = self.env[MODELO_INFORME]._get_report_values([slip.id])['dias_pagados']
        self.assertEqual(dias[slip.id].code, 'CO_LIQ_SALARIOS')

    def test_prima_y_bonificacion_no_imprimen_el_campo(self):
        """Sin línea de sueldo el campo se OCULTA, aunque exista una línea WORK100 (no se cae a ella)."""
        prima = self._recibo(self.est_prima, 'Prima')
        self._linea(prima, 'CO_PRIMA_VALOR', 1500000.0)
        self._linea(prima, 'CO_PRIMA_NETO', 1500000.0)
        self._con_work100(prima, 20.0)
        bon = self._recibo(self.est_bonificacion, 'Bonificacion')
        self._linea(bon, 'CO_BON_VALOR', 500000.0)
        self._linea(bon, 'CO_BON_NETO', 500000.0)
        self._con_work100(bon, 20.0)
        for slip in (prima, bon):
            html = self._html(slip)
            self.assertNotIn('Días trabajados', html)
            self.assertIsNone(self._dias_impresos(html))
            self.assertFalse(self.env[MODELO_INFORME]._get_report_values([slip.id])['dias_pagados'][slip.id])

    def test_un_cambio_posterior_en_el_contrato_no_altera_lo_impreso(self):
        """La colilla muestra lo PAGADO (línea guardada), no lo que hoy recalcularía ``_ne_dias_pagables()``: con el contrato desde el
        11-sep el recálculo daría 20 días (11 al 30), pero el recibo ya se pagó por 30 y lo impreso sigue en 30."""
        slip = self._recibo(self.est_general, 'Cambio posterior')
        slip.compute_sheet()
        self.assertEqual(self._dias_impresos(self._html(slip)), 30.0)
        slip.contract_id.date_start = date(2026, 9, 11)
        self.assertEqual(slip._ne_dias_pagables(), 20.0, 'Premisa: el recálculo ya daría otra cifra')
        self.assertEqual(slip.line_ids.filtered(lambda l: l.code == 'CO_BASICO').quantity, 30.0)
        self.assertEqual(self._dias_impresos(self._html(slip)), 30.0)

    def test_sin_linea_de_sueldo_no_cae_a_work100(self):
        """Un recibo general sin la línea CO_BASICO (solo el neto) y con WORK100 de 11 días: el campo no sale."""
        slip = self._recibo(self.est_general, 'Sin sueldo')
        self._linea(slip, 'CO_NETO', 1000.0)
        self._con_work100(slip, 11.0)
        self.assertIsNone(self._dias_impresos(self._html(slip)))

    def test_las_reglas_de_la_constante_calculan_su_cantidad_con_ne_dias_pagables(self):
        """Guarda estructural: las líneas que nombra la constante son las reglas cuya cantidad es ``_ne_dias_pagables()`` (AUD-DIAN-34).
        Si alguien cambia la fuente de la cantidad de una de ellas, la colilla dejaría de mostrar lo pagado."""
        codigos = self.env[MODELO_INFORME]._NE_LINEAS_DIAS_PAGADOS
        self.assertEqual(set(codigos), {'CO_BASICO', 'CO_LIQ_SALARIOS'})
        for codigo in codigos:
            reglas = self.env['hr.salary.rule'].search([
                ('code', '=', codigo), ('struct_id', 'in', (self.est_general | self.est_liquidacion).ids)])
            self.assertTrue(reglas, 'Falta la regla %s' % codigo)
            for regla in reglas:
                self.assertIn('result_qty = ', regla.amount_python_compute)
                self.assertIn('_ne_dias_pagables()', regla.amount_python_compute, codigo)
