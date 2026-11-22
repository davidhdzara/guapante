# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Filas de «Cálculo del salario» del recibo (E11 pieza 4a, .294, doc 74 §3): soporte de auditoría (UGPP), de SOLO LECTURA.

.298 (decisión de David, 22-nov): la pestaña lleva SOLO lo que no está en «Conceptos de pago»: las BASES de cotización, los APORTES DE LA EMPRESA y las
PROVISIONES (con el total «Costo empresa» al pie). Los conceptos (sueldo, devengos y deducciones) se ven y se editan en «Conceptos de pago»: se MUEVEN
allí y este cálculo los sigue, de manera informativa.

Igual que «Conceptos de pago» (``l10n.co.payslip.concepto``), es una VISTA de lo ya calculado y no una fuente de datos: se regenera al final de cada
``compute_sheet`` a partir de ``hr.payslip.line`` y nada la lee para calcular. ``hr.payslip.line`` no tiene ``display_type`` (``hr_payroll/models/
hr_payslip_line.py:8-39``), así que las secciones necesitan filas propias para usar el widget nativo ``section_and_note_one2many``.

A diferencia de la pestaña de conceptos, aquí NO se edita nada: no hay ``create``/``write``/``unlink`` de usuario (solo la regeneración, con sudo y el
contexto ``ne_regenerar_calculo``) y el campo de la vista es de solo lectura. NO EJECUTADO EN ODOO al escribirlo."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

# Secciones de categoría que muestra esta pestaña (``hr.salary.rule.category.l10n_co_ne_seccion_concepto``). ``costo_empresa`` entra con una sección
# POR CATEGORÍA (aportes de la empresa, provisiones), titulada con el nombre de la categoría. Los devengados y las deducciones NO: van en «Conceptos de pago».
SECCIONES_DE_CATEGORIA = ('bases', 'costo_empresa')


class L10nCoPayslipCalculo(models.Model):
    _name = 'l10n.co.payslip.calculo'
    _description = 'Fila de «Cálculo del salario» del recibo (solo lectura)'
    _order = 'slip_id, sequence, id'

    slip_id = fields.Many2one('hr.payslip', string='Recibo', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='slip_id.company_id', store=True, index=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    display_type = fields.Selection(
        selection=[('line_section', 'Sección'), ('line_note', 'Nota')], default=False,
        help='Lo lee el widget de secciones y notas de la lista (títulos de sección y la nota de los conceptos ajustados).')
    name = fields.Text(string='Concepto')
    line_id = fields.Many2one('hr.payslip.line', string='Línea del recibo', ondelete='set null')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Regla', ondelete='set null')
    quantity = fields.Float(string='Cantidad', digits='Payroll')
    unidad = fields.Selection(selection=[('dias', 'Días'), ('horas', 'Horas')], string='Unidad')
    rate = fields.Float(string='%', digits='Payroll Rate', default=100.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    total = fields.Float(string='Total', digits='Payroll')
    ajustado = fields.Boolean(string='Ajustado por la empresa')

    # ── solo lectura: nadie lo escribe fuera de la regeneración ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('ne_regenerar_calculo'):
            raise UserError(_('«Cálculo del salario» es de solo lectura: se actualiza solo al calcular la hoja.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('ne_regenerar_calculo'):
            raise UserError(_('«Cálculo del salario» es de solo lectura: se actualiza solo al calcular la hoja.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('ne_regenerar_calculo'):
            raise UserError(_('«Cálculo del salario» es de solo lectura: se actualiza solo al calcular la hoja.'))
        return super().unlink()

    # ── regeneración ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
    @api.model
    def _regenerar_de_recibos(self, recibos):
        """Borra y vuelve a crear las filas de los recibos cuya estructura usa «Conceptos de pago» (el mismo interruptor). Con sudo y sin las acciones
        de usuario."""
        Calculo = self.sudo().with_context(ne_regenerar_calculo=True)
        for recibo in recibos.sudo().filtered('l10n_co_ne_usa_conceptos'):
            Calculo.search([('slip_id', '=', recibo.id)]).unlink()
            valores = self._valores_del_recibo(recibo)
            if valores:
                Calculo.create(valores)

    @api.model
    def _secciones_del_recibo(self, recibo, lineas):
        """``[(clave, titulo, [líneas])]`` en el orden de la pestaña: Bases, «Aportes del empleado» (informativa: salud, pensión y FSP; ajuste de David del 22-nov) y, después,
        una sección por categoría de «Costo empresa» (aportes de la empresa, provisiones; en el orden de su primera línea). Sin líneas, la sección no sale.

        Se decide por configuración, sin códigos de regla: la sección de la categoría de la línea (.298: ya no hay Básico, Devengos ni Deducciones)."""
        fijas = {'bases': (0, _('Bases')), 'aportes_empleado': (1, _('Aportes del empleado'))}
        grupos = {}
        for linea in lineas:
            categoria = linea.category_id
            if categoria.l10n_co_ne_seccion_concepto == 'bases':
                clave = 'bases'
            elif categoria.l10n_co_ne_aportes_empleado:
                clave = 'aportes_empleado'                       # informativa: no suma al «Costo empresa» (su categoría es de deducciones)
            else:
                clave = 'costo_%s' % categoria.id
            if clave not in grupos:
                orden, titulo = fijas.get(clave) or (2, categoria.name)
                grupos[clave] = {'clave': clave, 'orden': orden, 'primera': (linea.sequence, linea.id), 'titulo': titulo, 'lineas': []}
            grupos[clave]['lineas'].append(linea)
        return [(g['clave'], g['titulo'], g['lineas']) for g in sorted(grupos.values(), key=lambda g: (g['orden'], g['primera']))]

    @api.model
    def _valores_del_recibo(self, recibo):
        """Filas (lista de diccionarios) del recibo: cada sección con su título y sus conceptos; tras un concepto ajustado, una fila de nota con su
        valor sugerido (soporte de auditoría: la colilla NO la lleva; hoy ninguna regla de estas secciones es ajustable, la nota queda por si una empresa
        marca alguna). Solo líneas con valor (o ajustadas): sin ceros, y sin las líneas nativas BASIC/GROSS/NET ni los totales, porque sus categorías no
        tienen sección. Los días cotizados son acumuladores cuyo importe ES un número de días: se muestran como cualquier otra fila (en la columna Total,
        que no lleva símbolo de moneda)."""
        ajustes = {a.salary_rule_id.id: a for a in recibo.l10n_co_ajuste_ids}
        # Ajuste de David (22-nov): las bases de la retención solo si el recibo TIENE retención (una línea con valor de una regla cuyo tercero es la DIAN).
        con_retencion = any(l.total and l.salary_rule_id.l10n_co_tercero_origen == 'company_dian' for l in recibo.line_ids)
        lineas = recibo.line_ids.filtered(
            lambda l: (l.category_id.l10n_co_ne_seccion_concepto in SECCIONES_DE_CATEGORIA or l.category_id.l10n_co_ne_aportes_empleado)
            and (l.total or l.salary_rule_id.id in ajustes)
            and (con_retencion or not l.salary_rule_id.l10n_co_ne_calculo_si_retencion)).sorted(lambda l: (l.sequence, l.id))
        valores, secuencia = [], 0

        def siguiente():
            nonlocal secuencia
            secuencia += 10
            return secuencia

        for clave, titulo, de_la_seccion in self._secciones_del_recibo(recibo, lineas):
            valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_section', 'name': titulo})
            for linea in de_la_seccion:
                regla = linea.salary_rule_id
                ajuste = ajustes.get(regla.id)
                valores.append({
                    'slip_id': recibo.id, 'sequence': siguiente(), 'name': linea.name, 'line_id': linea.id, 'salary_rule_id': regla.id,
                    'quantity': linea.quantity, 'unidad': regla.l10n_co_ne_unidad or False, 'rate': linea.rate, 'amount': linea.amount,
                    'total': linea.total, 'ajustado': bool(ajuste)})
                if ajuste:
                    texto = _('Ajustado por la empresa.')
                    if ajuste.con_sugerido:
                        texto = _('Ajustado por la empresa. Sugerido: %s', formatLang(self.env, ajuste.sugerido_total, digits=2))
                    valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_note', 'name': texto})
            if clave == 'bases':
                valores.extend(self._fila_del_exceso(recibo, siguiente))
        return valores

    @api.model
    def _fila_del_exceso(self, recibo, siguiente):
        """.299 (c): fila informativa del EXCESO DEL 40 % de los pagos no salariales pactados (Ley 1393/2010 art. 30) que pasa al IBC de salud, pensión y ARL,
        al final de «Bases». Solo si el recibo tiene pagos pactados (``CO_IBC_PACTADOS`` con valor); con 0 en el exceso se muestra igual: el auditor ve que se
        revisó el límite. No es una línea del recibo (``line_id`` vacío) y sale de la MISMA función que el IBC (``_ne_exceso_no_salarial``). Los códigos de las
        dos bases son identificadores internos del módulo."""
        por_codigo = {linea.code: linea.total for linea in recibo.line_ids.filtered(lambda l: l.code in ('CO_IBC_REMUN', 'CO_IBC_PACTADOS'))}
        pactados = por_codigo.get('CO_IBC_PACTADOS', 0.0)
        if not pactados:
            return []
        exceso = recibo._ne_exceso_no_salarial(por_codigo.get('CO_IBC_REMUN', 0.0), pactados)
        return [{
            'slip_id': recibo.id, 'sequence': siguiente(), 'quantity': 1.0, 'rate': 100.0, 'amount': exceso, 'total': exceso,
            'name': _('Exceso del 40 % de los pagos no salariales pactados (pasa al IBC)')}]
