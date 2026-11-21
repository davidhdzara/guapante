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
que no sufre la protección de ``BaseModel.write``. NO EJECUTADO EN ODOO al escribirlo."""


from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .hr_payslip import NE_SECCIONES_CONCEPTO

SECCIONES = NE_SECCIONES_CONCEPTO     # una sola fuente con la colilla (``models/hr_payslip.py``, E11 pieza 5a)
GRUPO_GERENTE = 'hr_payroll.group_hr_payroll_manager'
CAMPOS_DE_VALOR = ('quantity', 'rate', 'amount')


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
    name = fields.Text(string='Concepto')
    origen = fields.Selection(
        selection=[('calculado', 'Calculado'), ('novedad', 'Novedad'), ('dias', 'Días trabajados')], string='Origen', required=True,
        default='novedad', help='De dónde sale la fila: una regla calculada, una novedad del recibo o el detalle de días trabajados.')
    line_id = fields.Many2one('hr.payslip.line', string='Línea del recibo', ondelete='set null')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Regla', ondelete='set null')
    worked_day_id = fields.Many2one('hr.payslip.worked_days', string='Línea de días', ondelete='set null')
    input_id = fields.Many2one('hr.payslip.input', string='Novedad', ondelete='set null')
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de novedad', ondelete='set null')
    quantity = fields.Float(string='Cantidad', digits='Payroll')
    unidad = fields.Selection(selection=[('dias', 'Días'), ('horas', 'Horas')], string='Unidad')
    rate = fields.Float(string='%', digits='Payroll Rate', default=100.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    total = fields.Float(string='Total', digits='Payroll')
    ajustado = fields.Boolean(string='Ajustado por la empresa')

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

    # ── crear, editar y borrar desde la tabla ───────────────────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('ne_regenerar_conceptos'):
            return super().create(vals_list)
        Ajuste = self.env['l10n.co.payslip.ajuste']
        for vals in vals_list:
            if vals.get('display_type'):
                raise UserError(_('En «Conceptos de pago» solo se agregan conceptos: las secciones y las notas las genera el sistema.'))
            tipo = self.env['hr.payslip.input.type'].browse(vals.get('input_type_id'))
            if not tipo:
                raise UserError(_('Elija el tipo de concepto (novedad) que va a agregar.'))
            recibo = self.env['hr.payslip'].browse(vals['slip_id'])
            Ajuste._validar_recibos_ajustables(recibo)
            valor = vals.get('quantity') if tipo.is_quantity else vals.get('amount')
            entrada = self.env['hr.payslip.input'].with_context(ne_sin_recalculo_hoja=True).create({
                'payslip_id': recibo.id, 'input_type_id': tipo.id, 'amount': valor or 0.0, 'name': vals.get('name') or tipo.name})
            vals.update({'origen': 'novedad', 'input_id': entrada.id, 'sequence': vals.get('sequence', 9999)})
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('ne_regenerar_conceptos') or set(vals) <= {'sequence'}:
            return super().write(vals)
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
            if fila.display_type or fila.origen != 'novedad' or not fila.input_id:
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
