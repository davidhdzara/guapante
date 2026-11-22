# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-09 (doc 88; decisiones del TL del 22-nov): el aprendiz tiene un regimen propio que sale de UN metodo, ``HrPayslip._ne_regimen_cotizante``, y de una tabla versionada por fecha (parametro
``l10n_co_aprendiz_etapas``: tipo de cotizante, tipo de contrato, etapa, TipoTrabajador de la DIAN). Esquema PROVISIONAL «mientras el Ministerio de Salud expide el acto administrativo» (Concepto MinSalud
2025310001925691 y Circular MinTrabajo 083 del 18-jul-2025): hasta el 31-jul-2025 el 12 era la lectiva y el 19 la productiva; desde el 1-ago-2025 la lectiva es el tipo 19 y la practica o dual es el tipo 01 con el contrato
«4 - Aprendizaje»; el 12 se restringe."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from . import test_validacion_afiliacion as base


@tagged('post_install', '-at_install')
class TestAprendizRegimen(base.TestValidacionAfiliacion):

    def _regimen(self, nombre, tipo, tipo_contrato='2', desde=date(2026, 3, 1), hasta=date(2026, 3, 31)):
        _empleado, recibo = self._empleado_y_recibo(nombre, tipo=tipo, tipo_contrato=tipo_contrato, desde=desde, hasta=hasta)
        return recibo._ne_regimen_cotizante()

    def test_la_tabla_por_vigencia(self):
        casos = (
            # (nombre, tipo de cotizante, tipo de contrato, desde, hasta, etapa esperada, TipoTrabajador esperado)
            ('12 julio 2025', '12', '2', date(2025, 7, 1), date(2025, 7, 31), 'lectiva', '12'),
            ('19 julio 2025', '19', '2', date(2025, 7, 1), date(2025, 7, 31), 'practica', '19'),
            ('19 agosto 2025', '19', '2', date(2025, 8, 1), date(2025, 8, 31), 'lectiva', '12'),
            ('12 agosto 2025', '12', '2', date(2025, 8, 1), date(2025, 8, 31), False, False),
            ('01 aprendizaje agosto 2025', '01', '4', date(2025, 8, 1), date(2025, 8, 31), 'practica', '19'),
            ('01 aprendizaje julio 2025', '01', '4', date(2025, 7, 1), date(2025, 7, 31), False, False),
            ('01 dependiente 2026', '01', '2', date(2026, 3, 1), date(2026, 3, 31), False, False),
            ('01 aprendizaje 2026', '01', '4', date(2026, 3, 1), date(2026, 3, 31), 'practica', '19'),
            ('19 lectiva 2026', '19', '4', date(2026, 3, 1), date(2026, 3, 31), 'lectiva', '12'),
        )
        for nombre, tipo, tipo_contrato, desde, hasta, etapa, tipo_trabajador in casos:
            regimen = self._regimen(nombre, tipo, tipo_contrato, desde, hasta)
            self.assertEqual((regimen['etapa'], regimen['tipo_trabajador']), (etapa, tipo_trabajador), nombre)

    def test_un_dependiente_normal_no_es_aprendiz(self):
        """Tipo 01 con un contrato que no es de aprendizaje: sin etapa y sin TipoTrabajador derivado (se usa el de la ficha, como siempre)."""
        regimen = self._regimen('Normal', '01', '2')
        self.assertEqual(regimen, {'etapa': False, 'tipo_trabajador': False})

    def test_sin_el_parametro_un_error_que_lo_nombra(self):
        _empleado, recibo = self._empleado_y_recibo('Sin Tabla')
        self.env['hr.rule.parameter'].search([('code', '=', 'l10n_co_aprendiz_etapas')]).unlink()
        with self.assertRaisesRegex(UserError, 'l10n_co_aprendiz_etapas'):
            recibo._ne_regimen_cotizante()

    def test_la_tabla_sale_de_los_datos_no_del_codigo(self):
        """Agregar una fila con su fecha cambia el resultado sin tocar codigo: desde el 1-abr-2026 el tipo 01 con contrato «2» tambien es practica (el parametro es la unica fuente)."""
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_aprendiz_etapas')
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parametro.id, 'date_from': date(2026, 4, 1),
            'parameter_value': "[('19', '*', 'lectiva', '12'), ('01', '4', 'practica', '19'), ('01', '2', 'practica', '19')]"})
        self.assertFalse(self._regimen('Marzo', '01', '2', date(2026, 3, 1), date(2026, 3, 31))['etapa'])
        self.assertEqual(self._regimen('Abril', '01', '2', date(2026, 4, 1), date(2026, 4, 30))['etapa'], 'practica')
