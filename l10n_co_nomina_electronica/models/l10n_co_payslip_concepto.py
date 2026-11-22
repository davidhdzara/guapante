# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Filas de «Conceptos de pago» del recibo (E11 pieza 3, .289, doc 71c §4 y §5).

Es una VISTA de lo ya calculado, no una fuente de datos: se regenera al final de cada ``compute_sheet`` a partir de ``hr.payslip.line`` (más los
días trabajados y las novedades) y nada la lee para calcular (el XML DIAN, el asiento, la PILA, la UGPP y la colilla siguen leyendo las líneas).
Tiene ``display_type`` para que la lista use el widget nativo ``section_and_note_one2many`` del módulo ``account`` (títulos de sección y filas de
nota como una orden de venta).

Editar una fila es una ACCIÓN que se traduce a la fuente real: en una fila calculada crea o cambia el ajuste de la empresa (pieza 2b); en una fila
de novedad cambia la novedad (``hr.payslip.input``); «Agregar concepto» crea una novedad; borrar una fila de novedad borra la novedad. El recálculo
y la regeneración los hace ``HrPayslip.write`` UNA vez, después de ``super()`` (el mismo camino de .286); el One2many de filas NO es calculado, así
que no sufre la protección de ``BaseModel.write``. El ORDEN de las filas lo fija el sistema: la lista no ofrece el arrastre (sin el widget ``handle``) y
el modelo rechaza escribir ``sequence`` fuera de la regeneración. NO EJECUTADO EN ODOO al escribirlo."""


from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .hr_payslip import NE_SECCIONES_CONCEPTO

SECCIONES = NE_SECCIONES_CONCEPTO     # una sola fuente con la colilla (``models/hr_payslip.py``, E11 pieza 5a)
GRUPO_GERENTE = 'hr_payroll.group_hr_payroll_manager'
CAMPOS_DE_VALOR = ('quantity', 'rate', 'amount')
SECUENCIA_DE_FILA_NUEVA = 9999        # una novedad agregada desde la tabla va al final hasta que el siguiente cálculo regenere el orden


class L10nCoPayslipConcepto(models.Model):
    _name = 'l10n.co.payslip.concepto'
    _description = 'Fila de «Conceptos de pago» del recibo'
    _order = 'slip_id, sequence, id'

    slip_id = fields.Many2one('hr.payslip', string='Recibo', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='slip_id.company_id', store=True, index=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    display_type = fields.Selection(
        selection=[('line_section', 'Sección'), ('line_note', 'Nota')], default=False,
        help='Lo lee el widget de secciones y notas de la lista (títulos «Devengados» y «Deducciones» y la nota de los conceptos ajustados).')
    name = fields.Text(string='Descripción')
    origen = fields.Selection(
        selection=[('calculado', 'Calculado'), ('novedad', 'Novedad'), ('dias', 'Días trabajados')], string='Origen', required=True,
        default='novedad', help='De dónde sale la fila: una regla calculada, una novedad del recibo o el detalle de días trabajados.')
    line_id = fields.Many2one('hr.payslip.line', string='Línea del recibo', ondelete='set null')
    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string='Concepto', ondelete='set null',
        help='La regla salarial del concepto. En una fila NUEVA se elige entre las reglas de la estructura del recibo que se alimentan de una novedad (mismo código que un tipo de '
             'novedad): el tipo se deduce solo. En una fila ya guardada no se cambia.')
    worked_day_id = fields.Many2one('hr.payslip.worked_days', string='Línea de días', ondelete='set null')
    input_id = fields.Many2one('hr.payslip.input', string='Novedad', ondelete='set null')
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de novedad', ondelete='set null')
    quantity = fields.Float(string='Cantidad', digits='Payroll')
    unidad = fields.Selection(selection=[('dias', 'Días'), ('horas', 'Horas')], string='Unidad')
    rate = fields.Float(string='%', digits='Payroll Rate', default=100.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    total = fields.Float(string='Total', digits='Payroll')
    ajustado = fields.Boolean(string='Ajustado por la empresa')
    cuenta = fields.Char(string='Cuenta', help='Cuenta contable de la regla en la compañía del recibo (débito si el valor es positivo, crédito si es negativo), como en los apuntes contables. Solo informativa.')

    edita_cantidad = fields.Boolean(compute='_compute_edita')
    edita_porcentaje = fields.Boolean(compute='_compute_edita')
    edita_importe = fields.Boolean(compute='_compute_edita')

    # ── qué se puede editar en cada fila ────────────────────────────────────────────────────────────────────────────────────────
    @api.depends('display_type', 'origen', 'slip_id.state', 'slip_id.l10n_co_ne_documento_state', 'salary_rule_id.l10n_co_ne_ajustable',
                 'input_type_id.is_quantity')
    @api.depends_context('uid')
    def _compute_edita(self):
        es_gerente = self.env.su or self.env.user.has_group(GRUPO_GERENTE)
        for fila in self:
            cantidad = porcentaje = importe = False
            recibo = fila.slip_id
            abierto = bool(recibo) and recibo.state in ('draft', 'verify') and recibo.l10n_co_ne_documento_state not in (
                'sent', 'uncertain', 'accepted')
            if abierto and not fila.display_type:
                if fila.origen == 'calculado' and es_gerente and fila.salary_rule_id.l10n_co_ne_ajustable:
                    cantidad = porcentaje = importe = True
                elif fila.origen == 'novedad' and fila.input_type_id:
                    cantidad = bool(fila.input_type_id.is_quantity)
                    importe = not cantidad
            fila.edita_cantidad, fila.edita_porcentaje, fila.edita_importe = cantidad, porcentaje, importe

    @api.onchange('quantity', 'rate', 'amount')
    def _onchange_total(self):
        for fila in self:
            fila.total = fila.quantity * fila.amount * fila.rate / 100.0

    @api.onchange('input_type_id')
    def _onchange_input_type_id(self):
        for fila in self:
            if fila.input_type_id and not fila.name:
                fila.name = fila.input_type_id.name

    @api.model
    def _tipo_de_la_regla(self, regla):
        """El tipo de novedad de una regla: el de SU MISMO ``code``. Sin tipo (la regla no se alimenta de una novedad) es un error claro: no se inventa uno."""
        tipo = self.env['hr.payslip.input.type'].search([('code', '=', regla.code)], limit=1)
        if not tipo:
            raise UserError(_('El concepto «%(concepto)s» no se alimenta de una novedad: no se agrega a mano en «Conceptos de pago».', concepto=regla.name))
        return tipo

    @api.onchange('salary_rule_id')
    def _onchange_salary_rule_id(self):
        """Selector del concepto: elegir la regla deduce el tipo de novedad (el de su mismo código) y el nombre. Una regla sin tipo no se puede elegir (el dominio de la vista no la
        ofrece; aquí se limpia por si llega por otra vía)."""
        for fila in self:
            if not fila.salary_rule_id:
                fila.input_type_id = False
                continue
            tipo = self.env['hr.payslip.input.type'].search([('code', '=', fila.salary_rule_id.code)], limit=1)
            fila.input_type_id = tipo
            if tipo:
                fila.name = fila.salary_rule_id.name

    # ── crear, editar y borrar desde la tabla ───────────────────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('ne_regenerar_conceptos'):
            return super().create(vals_list)
        Ajuste = self.env['l10n.co.payslip.ajuste']
        for vals in vals_list:
            if vals.get('display_type'):
                raise UserError(_('En «Conceptos de pago» solo se agregan conceptos: las secciones y las notas las genera el sistema.'))
            recibo = self.env['hr.payslip'].browse(vals['slip_id'])
            regla = self.env['hr.salary.rule'].browse(vals.get('salary_rule_id'))
            tipo = self.env['hr.payslip.input.type'].browse(vals.get('input_type_id'))
            if regla and not tipo:
                tipo = self._tipo_de_la_regla(regla)           # selector del concepto: el tipo sale de la regla
            if not tipo:
                raise UserError(_('Elija el concepto que va a agregar.'))
            if regla and tipo.code != regla.code:
                raise UserError(_('El concepto «%(concepto)s» no corresponde al tipo de novedad «%(tipo)s».', concepto=regla.name, tipo=tipo.name))
            if regla and regla.struct_id != recibo.struct_id:
                raise UserError(_('El concepto «%(concepto)s» no es de la estructura salarial del recibo (%(estructura)s).', concepto=regla.name, estructura=recibo.struct_id.name))
            if not regla:                                      # agregado por el tipo (compatibilidad): la regla del mismo código en la estructura del recibo, si hay
                regla = recibo.struct_id.rule_ids.filtered(lambda r: r.code == tipo.code)[:1]
                if regla:
                    vals['salary_rule_id'] = regla.id
            Ajuste._validar_recibos_ajustables(recibo)
            valor = vals.get('quantity') if tipo.is_quantity else vals.get('amount')
            entrada = self.env['hr.payslip.input'].with_context(ne_sin_recalculo_hoja=True).create({
                'payslip_id': recibo.id, 'input_type_id': tipo.id, 'amount': valor or 0.0, 'name': vals.get('name') or tipo.name})
            # El orden de las filas lo fija el sistema (se regenera en cada cálculo): una fila nueva va al final, sin importar la secuencia que mande el cliente.
            vals.update({'origen': 'novedad', 'input_id': entrada.id, 'sequence': SECUENCIA_DE_FILA_NUEVA})
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('ne_regenerar_conceptos'):
            return super().write(vals)
        if 'salary_rule_id' in vals:
            raise UserError(_('El concepto de una fila ya guardada no se cambia: borre la novedad y agregue otra.'))
        if 'sequence' in vals:
            # Mover una fila (la secuencia que escribe el arrastre del widget de la lista) no es una edición de datos: no cambia ningún valor, pero deja la tabla
            # fuera de orden (un título de sección en medio de los conceptos) hasta el siguiente cálculo. La vista ya no ofrece el arrastre; esto cierra la
            # vía por el servidor (importación, RPC) y también en recibos hechos.
            raise UserError(_('El orden de «Conceptos de pago» lo fija el sistema: las filas no se mueven.'))
        for fila in self:
            fila._aplicar_edicion(vals)
        return super().write(vals)

    def _aplicar_edicion(self, vals):
        """Traduce la edición de una fila a su fuente real (novedad o ajuste). No recalcula: lo hace ``HrPayslip.write`` después."""
        self.ensure_one()
        if self.display_type or self.origen == 'dias':
            raise UserError(_('Esta fila no se edita.'))
        self.env['l10n.co.payslip.ajuste']._validar_recibos_ajustables(self.slip_id)
        if self.origen == 'novedad':
            if not self.input_id:
                raise UserError(_('La fila "%s" no tiene novedad para editar.', self.name))
            escribir = {}
            if 'name' in vals:
                escribir['name'] = vals['name']
            if self.input_id.input_type_id.is_quantity:
                if 'quantity' in vals:
                    escribir['amount'] = vals['quantity']
            elif 'amount' in vals:
                escribir['amount'] = vals['amount']
            if escribir:
                self.input_id.with_context(ne_sin_recalculo_hoja=True).write(escribir)
            return
        if 'name' in vals:
            raise UserError(_('El nombre de un concepto calculado no se edita: se cambia su cantidad, porcentaje o importe.'))
        if not self.salary_rule_id.l10n_co_ne_ajustable:
            raise UserError(_('El concepto "%s" no admite ajuste de la empresa.', self.name))
        nuevos = {campo: vals.get(campo, self[campo]) for campo in CAMPOS_DE_VALOR}
        Ajuste = self.env['l10n.co.payslip.ajuste']
        ajuste = self.slip_id.l10n_co_ajuste_ids.filtered(lambda a: a.salary_rule_id == self.salary_rule_id)
        if ajuste:
            ajuste.write(nuevos)
        else:
            Ajuste.create(dict(nuevos, slip_id=self.slip_id.id, salary_rule_id=self.salary_rule_id.id))

    def unlink(self):
        if self.env.context.get('ne_regenerar_conceptos'):
            return super().unlink()
        for fila in self:
            # QA sobre .298 (pedido del TL): al borrar una sección el mensaje hablaba de «concepto calculado»; las secciones y las notas tienen su propio texto.
            if fila.display_type == 'line_section':
                raise UserError(_('Las secciones no se pueden borrar.'))
            if fila.display_type == 'line_note':
                raise UserError(_('Las notas no se pueden borrar.'))
            if fila.origen != 'novedad' or not fila.input_id:
                raise UserError(_(
                    'Solo se borran las novedades que usted agregó. Para quitar el efecto de un concepto calculado, ajústelo (por ejemplo a 0).'))
            self.env['l10n.co.payslip.ajuste']._validar_recibos_ajustables(fila.slip_id)
            fila.input_id.with_context(ne_sin_recalculo_hoja=True).unlink()
        return super().unlink()

    # ── regeneración ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    @api.model
    def _regenerar_de_recibos(self, recibos):
        """Borra y vuelve a crear las filas de los recibos cuya estructura usa «Conceptos de pago». Con sudo y sin las acciones de usuario."""
        Concepto = self.sudo().with_context(ne_regenerar_conceptos=True)
        for recibo in recibos.sudo().filtered('l10n_co_ne_usa_conceptos'):
            Concepto.search([('slip_id', '=', recibo.id)]).unlink()
            valores = self._valores_del_recibo(recibo)
            if valores:
                Concepto.create(valores)

    @api.model
    def _filas_de_dias(self, recibo, siguiente):
        """Filas de días bajo la del sueldo. Ajuste de David (22-nov, decisión del TL: opción B): el descanso remunerado NO se desagrega aquí: UNA sola fila de días, «Asistencia»,
        con los días pagados con el sueldo (asistencia + festivos trabajados + descansos remunerados + ajuste del mes comercial: ``_ne_tipos_dias_de_asistencia``), sin importe. Es
        la cantidad del «Sueldo Básico» (``_ne_dias_pagables``); el desglose por fecha de E2a sigue en la pestaña de días trabajados. Las demás líneas de días (ausencias) salen
        como antes, cada una en su fila. Las filas de días no se editan: «sin mecanismo nuevo»."""
        lineas = recibo.worked_days_line_ids.sorted(lambda w: (w.sequence, w.id)).filtered(lambda w: w.number_of_days or w.number_of_hours)
        tipos = recibo._ne_tipos_dias_de_asistencia()
        de_asistencia = lineas.filtered(lambda w: w.work_entry_type_id in tipos)
        filas = []
        if de_asistencia:
            principal = de_asistencia[0]                      # la primera: «Asistencia» (WORK100) va primero en el desglose
            filas.append({
                'slip_id': recibo.id, 'sequence': siguiente(), 'name': principal.name or principal.work_entry_type_id.name, 'origen': 'dias',
                'worked_day_id': principal.id, 'quantity': sum(de_asistencia.mapped('number_of_days')), 'unidad': 'dias', 'rate': 0.0})
        for dia in lineas - de_asistencia:
            filas.append({
                'slip_id': recibo.id, 'sequence': siguiente(), 'name': dia.name or dia.work_entry_type_id.name, 'origen': 'dias',
                'worked_day_id': dia.id, 'quantity': dia.number_of_days, 'unidad': 'dias', 'rate': 0.0})
        return filas

    @api.model
    def _valores_del_recibo(self, recibo):
        """Filas (lista de diccionarios) del recibo: sección «Devengados», sus conceptos con los días trabajados bajo el sueldo, sección
        «Deducciones» y sus conceptos; tras un concepto ajustado, una fila de nota con su valor sugerido.

        .291 (E11 pieza 5a): las filas de conceptos salen de ``HrPayslip._ne_filas_de_concepto`` (fuente ÚNICA con la colilla: qué líneas, en qué
        orden, con qué unidad, enlace a la novedad); aquí solo se les agregan los títulos de sección, la nota del ajuste, las filas de días y los
        vínculos propios de esta tabla."""
        titulos = {'devengados': _('Devengados'), 'deducciones': _('Deducciones')}
        valores, secuencia = [], 0

        def siguiente():
            nonlocal secuencia
            secuencia += 10
            return secuencia

        seccion_actual, dias_puestos = None, False
        for fila in recibo._ne_filas_de_concepto():
            seccion, linea, regla, ajuste, entrada, tipo = (
                fila['seccion'], fila['linea'], fila['regla'], fila['ajuste'], fila['entrada'], fila['tipo'])
            if seccion != seccion_actual:
                seccion_actual, dias_puestos = seccion, False
                valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_section', 'name': titulos[seccion], 'origen': 'calculado'})
            valores.append({
                'slip_id': recibo.id, 'sequence': siguiente(), 'name': fila['nombre'], 'origen': 'novedad' if entrada else 'calculado', 'line_id': linea.id,
                'salary_rule_id': regla.id, 'input_id': entrada.id if entrada else False, 'input_type_id': tipo.id if tipo else False,
                'quantity': fila['cantidad'], 'rate': fila['porcentaje'], 'amount': fila['importe'], 'total': fila['total'], 'unidad': fila['unidad'],
                'ajustado': bool(ajuste), 'cuenta': regla._ne_cuenta_contable(fila['total'], recibo.company_id)})
            if ajuste:
                texto = _('Ajustado por la empresa.')
                if ajuste.con_sugerido:
                    texto = _('Ajustado por la empresa. Sugerido: %s', formatLang(self.env, ajuste.sugerido_total, digits=2))
                valores.append({'slip_id': recibo.id, 'sequence': siguiente(), 'display_type': 'line_note', 'name': texto, 'origen': 'calculado'})
            if (not dias_puestos and seccion == 'devengados' and regla.l10n_co_ne_dian_concept == 'Sueldo'
                    and recibo.struct_id.use_worked_day_lines):
                dias_puestos = True
                valores.extend(self._filas_de_dias(recibo, siguiente))
        return valores
