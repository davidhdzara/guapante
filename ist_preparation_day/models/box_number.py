# -*- coding: utf-8 -*-
"""Control de numeración de cajas (lote 4, Tech Lead/David 2026-11-09).

Regla de fondo (sin cambios): el número de caja NUNCA se renumera; una caja
nueva toma MAX+1. Esto agrega blindaje y auditoría encima:

* candado: ``sale.order.daily_sequence`` solo cambia por los caminos del
  sistema (alta, reubicación, reinicio administrativo), identificados con
  ``BoxOrigin``;
* historial inalterable: ``guapante.box.number.log`` (solo create);
* revisión automática: ``guapante.box.number.issue``;
* reinicio administrativo con motivo obligatorio (wizard).
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

ORIGIN_ALTA = 'alta'
ORIGIN_REUBICACION = 'reubicacion'
ORIGIN_RESET = 'reset'
BOX_ORIGINS = [
    (ORIGIN_ALTA, 'Alta (asignación al cargar)'),
    (ORIGIN_REUBICACION, 'Reubicación de fecha'),
    (ORIGIN_RESET, 'Reinicio administrativo'),
]
CTX_ORIGIN = 'guapante_box_origin'
CTX_REASON = 'guapante_box_reason'


class BoxOrigin(str):
    """Valor del contexto ``guapante_box_origin``.

    Es literalmente el string que se guarda en ``origin`` del historial (una
    sola fuente de verdad, pedido del Tech Lead). Es una subclase de ``str``
    a propósito: el contexto que llega por JSON-RPC desde un navegador solo
    puede traer ``str`` planos, así que un cliente NO puede falsificar el
    candado enviando ``context={'guapante_box_origin': 'reset'}``.
    """
    __slots__ = ()


def box_origin(name):
    if name not in dict(BOX_ORIGINS):
        raise ValueError('Origen de caja desconocido: %r' % (name,))
    return BoxOrigin(name)


def get_box_origin(env):
    """Origen válido del contexto, o None si falta o no es del sistema."""
    value = env.context.get(CTX_ORIGIN)
    return value if isinstance(value, BoxOrigin) else None


class BoxNumberLog(models.Model):
    """Historial inalterable de cambios de ``daily_sequence``."""
    _name = 'guapante.box.number.log'
    _description = 'Historial de números de caja'
    _order = 'id desc'
    _log_access = True

    order_id = fields.Many2one(
        'sale.order', string='Pedido', ondelete='set null', index=True,
        readonly=True,
    )
    order_name = fields.Char(string='Pedido (nombre)', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    box_date = fields.Date(string='Jornada', readonly=True, index=True)
    old_sequence = fields.Integer(string='Caja anterior', readonly=True)
    new_sequence = fields.Integer(string='Caja nueva', readonly=True)
    origin = fields.Selection(
        BOX_ORIGINS, string='Origen', required=True, readonly=True,
    )
    reason = fields.Text(string='Motivo', readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario', readonly=True,
        default=lambda self: self.env.user,
    )

    def write(self, vals):
        raise UserError(
            'El historial de cajas es inalterable: no se puede modificar.'
        )

    def unlink(self):
        raise UserError(
            'El historial de cajas es inalterable: no se puede borrar.'
        )


class BoxNumberIssue(models.Model):
    """Inconsistencias detectadas por la revisión automática.

    Solo lectura para el administrador; las crea/cierra el sistema
    (``_guapante_check_box_numbering``). Sin botón de corregir: la
    corrección sigue por reinicio/reubicación, que quedan en el historial.
    """
    _name = 'guapante.box.number.issue'
    _description = 'Inconsistencia de numeración de cajas'
    _order = 'state, box_date desc, id desc'

    KINDS = [
        ('duplicate', 'Número duplicado'),
        ('missing', 'Pedido de la sesión sin número'),
        ('outside_log', 'Número cambiado fuera del historial'),
    ]

    kind = fields.Selection(KINDS, string='Tipo', required=True, readonly=True)
    box_date = fields.Date(string='Jornada', readonly=True, index=True)
    order_id = fields.Many2one(
        'sale.order', string='Pedido', ondelete='cascade', readonly=True,
    )
    sequence = fields.Integer(string='Caja #', readonly=True)
    detail = fields.Char(string='Detalle', readonly=True)
    state = fields.Selection(
        [('open', 'Abierta'), ('resolved', 'Resuelta')],
        string='Estado', default='open', required=True, readonly=True,
        index=True,
    )
    resolved_date = fields.Datetime(string='Resuelta el', readonly=True)


class BoxResetWizard(models.TransientModel):
    """Reinicio de cajas con motivo obligatorio (solo administrador)."""
    _name = 'guapante.box.reset.wizard'
    _description = 'Reinicio de números de caja'

    picking_ids = fields.Many2many('stock.picking', string='Recolecciones')
    reason = fields.Text(string='Motivo', required=True)
    order_count = fields.Integer(
        string='Pedidos con caja', compute='_compute_order_count',
    )

    @api.depends('picking_ids')
    def _compute_order_count(self):
        for wiz in self:
            wiz.order_count = len(wiz.picking_ids.mapped('sale_id').filtered(
                lambda o: o.daily_sequence > 0))

    def action_confirm(self):
        self.ensure_one()
        return self.picking_ids._guapante_reset_boxes(self.reason)
