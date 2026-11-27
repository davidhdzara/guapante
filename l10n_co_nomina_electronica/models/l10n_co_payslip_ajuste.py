# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Ajuste de la empresa a un concepto del recibo (E11 pieza 2b, .288, doc 71c §2, §3 y §13).

La empresa puede cambiar la cantidad, el porcentaje o el importe de una regla ajustable en un recibo en borrador o en espera; el sistema
conserva lo sugerido y quién lo cambió. El ajuste se aplica DENTRO del cálculo: ``hr.salary.rule._compute_rule`` (override en
``models/hr_salary_rule.py``) devuelve la tupla ajustada en vez de la sugerida y el bucle nativo de reglas
(``hr_payroll/models/hr_payslip.py:944-1018``) arrastra el resultado a todo lo que viene después (neto, bases, retención, IBC). Por eso el ajuste
sobrevive a ``compute_sheet``, a «Calcular hoja» y al recálculo por novedad, a diferencia de ``edited`` (que congela el recibo entero).

Después de cada ``compute_sheet`` (``HrPayslip._ne_registrar_ajustes``) cada ajuste guarda lo sugerido de ese cálculo, avisa si el sugerido cambió
(Q2 de TL: se conserva el valor ajustado, nunca en silencio) y se borra solo si quedó igual al sugerido.

Bloqueo (Q6 de TL): no se crea, cambia ni borra un ajuste si el recibo no está en borrador o en espera, o si su documento DIAN está enviado,
incierto o aceptado. Un recibo ``done`` conserva sus ajustes como rastro de solo lectura. NO EJECUTADO EN ODOO al escribirlo."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

# Estados del documento DIAN (``l10n.co.ne.documento.state``) con los que el recibo ya no admite ajustes: «uncertain» bloquea porque no se sabe
# si la DIAN lo aceptó.
ESTADOS_DOCUMENTO_QUE_BLOQUEAN = ('sent', 'uncertain', 'accepted')
CAMPOS_DE_VALOR = ('quantity', 'rate', 'amount')


class L10nCoPayslipAjuste(models.Model):
    _name = 'l10n.co.payslip.ajuste'
    _description = 'Ajuste de la empresa a un concepto del recibo'
    _order = 'slip_id, id'

    slip_id = fields.Many2one('hr.payslip', string='Recibo', required=True, ondelete='cascade', index=True)
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Concepto (regla)', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='slip_id.company_id', store=True, index=True)

    # Valor AJUSTADO (lo que reemplaza a lo sugerido en el cálculo). Mismos dígitos que ``hr.payslip.line``.
    quantity = fields.Float(string='Cantidad', digits='Payroll', default=1.0)
    rate = fields.Float(string='%', digits='Payroll Rate', default=100.0)
    amount = fields.Float(string='Importe', digits='Payroll')
    total = fields.Float(string='Total', digits='Payroll', compute='_compute_total')

    # Lo que dio la regla en el último cálculo sin ajuste. ``con_sugerido`` distingue «no se conoce todavía» de un sugerido en 0.
    con_sugerido = fields.Boolean(string='Sugerido conocido', default=False)
    sugerido_quantity = fields.Float(string='Cantidad sugerida', digits='Payroll')
    sugerido_rate = fields.Float(string='% sugerido', digits='Payroll Rate')
    sugerido_amount = fields.Float(string='Importe sugerido', digits='Payroll')
    sugerido_total = fields.Float(string='Total sugerido', digits='Payroll')
    sugerido_al_ajustar = fields.Float(
        string='Total sugerido al ajustar', digits='Payroll',
        help='Total que sugería la regla cuando la empresa hizo el ajuste.')

    estado = fields.Selection(
        selection=[
            ('aplicado', 'Aplicado'),
            ('sin_linea', 'Sin línea en el último cálculo'),
            ('no_aplicable', 'No aplicable'),
        ],
        string='Estado', default='aplicado', readonly=True,
        help='«Sin línea»: la regla no generó línea en el último cálculo (su condición dejó de cumplirse); el ajuste se conserva. '
             '«No aplicable»: la regla ya no admite ajuste o tiene varias novedades del mismo código.')
    motivo = fields.Char(string='Motivo', help='Observación opcional de la empresa. El ajuste es responsabilidad de la empresa.')
    user_id = fields.Many2one('res.users', string='Ajustado por', default=lambda self: self.env.user, readonly=True)
    fecha = fields.Datetime(string='Fecha del ajuste', default=fields.Datetime.now, readonly=True)

    _sql_constraints = [
        ('slip_regla_uniq', 'unique(slip_id, salary_rule_id)',
         'Ya hay un ajuste para esa regla en el recibo (un ajuste por regla y recibo).'),
    ]

    @api.depends('quantity', 'rate', 'amount')
    def _compute_total(self):
        for ajuste in self:
            ajuste.total = ajuste.quantity * ajuste.amount * ajuste.rate / 100.0

    # ── validaciones ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    @api.constrains('slip_id', 'salary_rule_id')
    def _check_regla_ajustable(self):
        for ajuste in self:
            regla, recibo = ajuste.salary_rule_id, ajuste.slip_id
            if regla.struct_id != recibo.struct_id:
                raise ValidationError(_(
                    'La regla "%(regla)s" no es de la estructura "%(estructura)s" del recibo "%(recibo)s".',
                    regla=regla.display_name, estructura=recibo.struct_id.display_name, recibo=recibo.display_name))
            if not regla.l10n_co_ne_ajustable:
                raise ValidationError(_(
                    'La regla "%(regla)s" no admite ajuste de la empresa: su valor sale de la ley o del cálculo (seguridad social, retención, '
                    'embargos, aportes de la empresa, provisiones, bases, incapacidades, licencias y vacaciones disfrutadas) y cambiarlo expone a la empresa a '
                    'inexactitud ante la UGPP. Solo se ajustan los conceptos de pago, las deducciones voluntarias o pactadas y, en los recibos de prima y liquidación, la prima, las cesantías, sus intereses y las '
                    'vacaciones compensadas.',
                    regla=regla.display_name))
            if len(recibo.input_line_ids.filtered(lambda i: i.code == regla.code)) > 1:
                raise ValidationError(_(
                    'La regla "%(regla)s" tiene varias novedades del mismo código en el recibo "%(recibo)s": se edita cada novedad, no la '
                    'regla.', regla=regla.display_name, recibo=recibo.display_name))

    @api.model
    def _validar_recibos_ajustables(self, recibos):
        """El recibo debe estar en borrador o en espera y su documento DIAN no puede estar enviado, incierto ni aceptado."""
        for recibo in recibos:
            if recibo.state not in ('draft', 'verify'):
                raise UserError(_(
                    'El recibo "%(recibo)s" está en estado "%(estado)s": ya no admite ajustes de la empresa.',
                    recibo=recibo.display_name, estado=dict(recibo._fields['state']._description_selection(self.env)).get(recibo.state)))
            if recibo._ne_estado_documento_ajuste() in ESTADOS_DOCUMENTO_QUE_BLOQUEAN:
                raise UserError(_(
                    'El recibo "%(recibo)s" ya tiene su documento DIAN enviado o aceptado (estado "%(estado)s"): no admite ajustes de la '
                    'empresa.', recibo=recibo.display_name, estado=recibo._ne_estado_documento_ajuste()))

    # ── reglas que dejan de ser ajustables (.298) ───────────────────────────────────────────────────────────────────────────────
    @api.model
    def _retirar_de_reglas_no_ajustables(self, reglas=None):
        """Borra los ajustes de la empresa sobre reglas que NO son ajustables (``reglas``, o todas si no se da): una regla que deja de ser ajustable
        no puede conservar un valor cambiado a mano. Solo en recibos en borrador o en espera cuyo documento DIAN no esté enviado, incierto ni
        aceptado; un recibo confirmado (hecho, pagado) o con documento enviado NO se toca (queda como se pagó). Cada recibo recibe una nota en el chatter
        que lo explica y se recalcula con el valor sugerido. Idempotente; con sudo y sin las validaciones de usuario (es un ajuste técnico)."""
        dominio = [('salary_rule_id.l10n_co_ne_ajustable', '=', False)]
        if reglas:
            dominio.append(('salary_rule_id', 'in', reglas.ids))
        buscados = self.sudo().with_context(active_test=False).search(dominio)
        por_recibo = {}
        for ajuste in buscados:
            recibo = ajuste.slip_id
            if recibo.state not in ('draft', 'verify') or recibo._ne_estado_documento_ajuste() in ESTADOS_DOCUMENTO_QUE_BLOQUEAN:
                continue
            por_recibo[recibo] = por_recibo.get(recibo, buscados.browse()) | ajuste
        for recibo, ajustes in por_recibo.items():
            for ajuste in ajustes:
                recibo.message_post(
                    body=_('Se retiró el ajuste de la empresa sobre «%(regla)s» (%(codigo)s): esta regla ya no admite ajustes porque su valor sale de la ley '
                           'o del cálculo (riesgo de inexactitud ante la UGPP). Ajustado: %(ajustado)s. Sugerido: %(sugerido)s. El recibo se recalcula con el '
                           'valor sugerido.', regla=ajuste.salary_rule_id.name, codigo=ajuste.salary_rule_id.code, ajustado=ajuste._monto(ajuste.total),
                           sugerido=ajuste._monto(ajuste.sugerido_total) if ajuste.con_sugerido else _('(sin calcular)')),
                    message_type='notification', subtype_xmlid='mail.mt_note')
            ajustes.with_context(ne_registro_sugeridos=True).unlink()
            recibo.compute_sheet()

    # ── crear, cambiar, borrar (con rastro en el chatter del recibo) ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('ne_registro_sugeridos'):
            recibos = self.env['hr.payslip'].browse([v['slip_id'] for v in vals_list if v.get('slip_id')])
            self._validar_recibos_ajustables(recibos)
        ajustes = super().create(vals_list)
        for ajuste in ajustes:
            ajuste._completar_sugerido_desde_la_linea()
            ajuste._nota_en_el_recibo(_('Ajuste creado'), anterior=None)
        return ajustes

    def write(self, vals):
        if self.env.context.get('ne_registro_sugeridos'):
            return super().write(vals)
        self._validar_recibos_ajustables(self.slip_id)
        if 'slip_id' in vals or 'salary_rule_id' in vals:
            raise UserError(_('No se puede cambiar el recibo ni la regla de un ajuste: bórrelo y cree otro.'))
        cambia = bool(set(CAMPOS_DE_VALOR) & set(vals))
        anteriores = {a.id: a.total for a in self}
        if cambia:
            vals = dict(vals, user_id=self.env.user.id, fecha=fields.Datetime.now())
        res = super().write(vals)
        if cambia:
            for ajuste in self:
                ajuste._nota_en_el_recibo(_('Ajuste cambiado'), anterior=anteriores[ajuste.id])
        return res

    def unlink(self):
        if not self.env.context.get('ne_registro_sugeridos'):
            self._validar_recibos_ajustables(self.slip_id)
            for ajuste in self:
                ajuste._nota_en_el_recibo(
                    _('Ajuste eliminado'), anterior=ajuste.total, nuevo=ajuste.sugerido_total, con_nuevo=ajuste.con_sugerido)
        return super().unlink()

    def _completar_sugerido_desde_la_linea(self):
        """Al crear un ajuste sin sugerido, lo sugerido es la línea que el recibo ya traía para esa regla (si es una sola)."""
        self.ensure_one()
        if self.con_sugerido:
            return
        linea = self.slip_id.line_ids.filtered(lambda l: l.salary_rule_id == self.salary_rule_id)
        if len(linea) == 1:
            self.sudo().with_context(ne_registro_sugeridos=True).write({
                'con_sugerido': True, 'sugerido_quantity': linea.quantity, 'sugerido_rate': linea.rate, 'sugerido_amount': linea.amount,
                'sugerido_total': linea.total, 'sugerido_al_ajustar': linea.total})

    def _monto(self, valor):
        """Un importe con el FORMATO MONETARIO de la compañía del recibo (símbolo, decimales de la moneda y separadores del idioma del usuario),
        como se ve en pantalla. Las notas del chatter lo usan en vez de ``%.2f`` (E11 pieza de pulido UX, .293: «-35018.10» sin separadores)."""
        self.ensure_one()
        return self.slip_id.company_id.currency_id.format(valor)

    def _nota_en_el_recibo(self, titulo, anterior=None, nuevo=None, con_nuevo=True):
        """Nota del chatter del recibo: regla, sugerido, anterior, nuevo y usuario (texto plano, sin colores propios); los importes con el formato
        monetario de la compañía (``_monto``)."""
        self.ensure_one()
        nuevo = self.total if nuevo is None else nuevo
        partes = [_('%(titulo)s: «%(regla)s» (%(codigo)s).', titulo=titulo, regla=self.salary_rule_id.name, codigo=self.salary_rule_id.code)]
        if self.con_sugerido:
            partes.append(_('Sugerido: %s.', self._monto(self.sugerido_total)))
        if anterior is not None:
            partes.append(_('Anterior: %s.', self._monto(anterior)))
        if con_nuevo:
            partes.append(_('Nuevo: %s.', self._monto(nuevo)))
        partes.append(_('Por: %s.', self.env.user.name))
        self.slip_id.message_post(body=' '.join(partes), message_type='notification', subtype_xmlid='mail.mt_note')

    # ── registro después de cada cálculo ────────────────────────────────────────────────────────────────────────────────────────
    def _registrar_calculo(self, sugeridos):
        """Se llama al terminar ``compute_sheet`` con ``sugeridos = {(recibo_id, regla_id): (amount, qty, rate)}``, lo que el gancho de
        ``_compute_rule`` vio como sugerido. Guarda el sugerido, deja la nota de Q2 si cambió, marca «sin línea» o «no aplicable» y borra el
        ajuste que quedó igual al sugerido. Escribe con sudo y sin las validaciones de usuario: es un registro técnico del cálculo."""
        self.ensure_one()
        ajuste = self.sudo().with_context(ne_registro_sugeridos=True)
        recibo, regla = ajuste.slip_id, ajuste.salary_rule_id
        sugerido = sugeridos.get((recibo.id, regla.id))
        if sugerido is None:
            varias_novedades = len(recibo.input_line_ids.filtered(lambda i: i.code == regla.code)) > 1
            estado = 'no_aplicable' if (not regla.l10n_co_ne_ajustable or varias_novedades) else 'sin_linea'
            if ajuste.estado != estado:
                ajuste.write({'estado': estado})
                recibo.message_post(body=_(
                    'El ajuste de «%(regla)s» (%(codigo)s) no se aplicó en este cálculo (%(motivo)s). Se conserva.',
                    regla=regla.name, codigo=regla.code,
                    motivo=_('la regla no generó línea') if estado == 'sin_linea' else _('la regla ya no admite ajuste o tiene varias novedades')),
                    message_type='notification', subtype_xmlid='mail.mt_note')
            return
        s_amount, s_quantity, s_rate = sugerido
        s_total = recibo._get_payslip_line_total(s_amount, s_quantity, s_rate, regla)
        # «Igual al sugerido» se compara con la precisión con que se guarda cada campo (importe y cantidad 2 decimales, porcentaje 4).
        if all(float_compare(actual, sugerido_i, precision_digits=digitos) == 0 for actual, sugerido_i, digitos in (
                (ajuste.amount, s_amount, 2), (ajuste.quantity, s_quantity, 2), (ajuste.rate, s_rate, 4))):
            recibo.message_post(body=_(
                'El ajuste de «%(regla)s» (%(codigo)s) quedó igual al valor sugerido (%(total)s): se quita.',
                regla=regla.name, codigo=regla.code, total=ajuste._monto(s_total)), message_type='notification', subtype_xmlid='mail.mt_note')
            ajuste.unlink()
            return
        if ajuste.con_sugerido and abs(s_total - ajuste.sugerido_total) > 0.005:
            recibo.message_post(body=_(
                'El sugerido de «%(regla)s» (%(codigo)s) cambió de %(antes)s a %(despues)s; se conserva el valor ajustado (%(ajustado)s).',
                regla=regla.name, codigo=regla.code, antes=ajuste._monto(ajuste.sugerido_total), despues=ajuste._monto(s_total),
                ajustado=ajuste._monto(ajuste.total)), message_type='notification', subtype_xmlid='mail.mt_note')
        ajuste.write({
            'con_sugerido': True, 'sugerido_quantity': s_quantity, 'sugerido_rate': s_rate, 'sugerido_amount': s_amount,
            'sugerido_total': s_total, 'estado': 'aplicado'})
