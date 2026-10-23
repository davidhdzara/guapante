# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.ist_preparation_day.models.const_preparation import (
    get_active_prep_operator_id,
)

STOP_REASONS = [
    ('sin_stock', 'Sin stock'),
    ('mal_estado', 'Producto en mal estado'),
    ('esperando_proveedor', 'Esperando proveedor'),
    ('otro', 'Otro'),
]

# Umbral de historia mínima para confiar en la mediana de kg/unidad de una
# plantilla (Fase C, punto 1 de Tech Lead). Dato real de producción
# (2026-10-22, 23,227 líneas needs_weighing=True terminadas): con >=10
# líneas de historia, 91 de 140 plantillas quedan cubiertas y quedan
# cubiertas el 99.4% de las líneas — por debajo de eso no hay alerta,
# nunca un valor inventado.
MIN_WEIGHT_HISTORY_LINES = 10


class PreparationDayProductClaim(models.Model):
    """Nivel 1 de Picking (Fase B) — estado de trabajo por producto base
    (plantilla), una fila por (wizard_id, product_tmpl_id).

    Separado de guapante.preparation.day.summary (que es por VARIANTE, para
    la pestaña Productos) a propósito: asignar/detener/liberar es una
    operación sobre la unidad de trabajo del Nivel 1 — la plantilla, no la
    variante — y Summary ya tiene su propio ciclo de vida (se recrea en
    cada action_load) que no es el dueño natural de "quién lo tiene tomado
    ahora mismo".
    """
    _name = 'guapante.preparation.day.product.claim'
    _description = 'Nivel 1 de Picking — estado por producto base'
    _order = 'status, product_tmpl_id'
    _sql_constraints = [
        (
            'wizard_product_tmpl_uniq',
            'unique(wizard_id, product_tmpl_id)',
            'Ya existe un registro de Nivel 1 para este producto en esta sesión.',
        ),
    ]

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
    )
    assigned_employee_id = fields.Many2one(
        'hr.employee', string='Asignado a',
    )
    assigned_date = fields.Datetime(string='Asignado el')
    stop_reason = fields.Selection(STOP_REASONS, string='Motivo de detención')
    stopped_by_employee_id = fields.Many2one(
        'hr.employee', string='Detenido por',
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pendiente'),
            ('in_progress', 'En progreso'),
            ('stopped', 'Detenido'),
            ('done', 'Terminado'),
        ],
        compute='_compute_status',
        store=True,
    )
    # No almacenado: depende de quién está identificado AHORA en esta
    # sesión de navegador (request.session), no de un dato del registro —
    # tiene que recalcularse en cada lectura, igual que el resto de la
    # identificación por PIN en este proyecto.
    is_mine = fields.Boolean(compute='_compute_is_mine')
    pending_line_count = fields.Integer(compute='_compute_line_counts')
    total_line_count = fields.Integer(compute='_compute_line_counts')
    expected_kg_per_unit = fields.Float(
        string='Kg esperado por unidad',
        digits=(10, 4),
        readonly=True,
        help=(
            'Mediana histórica de actual_kg/estimated_kg de esta plantilla, '
            'calculada solo con líneas Terminadas y con repesaje de OTRAS '
            'sesiones (Fase C). En 0.0 cuando esa plantilla no llega a '
            f'{MIN_WEIGHT_HISTORY_LINES} líneas de historia — en ese caso la '
            'tarjeta de Nivel 2 no muestra alerta de peso, nunca un valor '
            'inventado.'
        ),
    )

    def _get_lines(self):
        self.ensure_one()
        return self.wizard_id.line_ids.filtered(
            lambda l: l.product_id == self.product_tmpl_id
        )

    @api.depends(
        'wizard_id.line_ids.is_done',
        'wizard_id.line_ids.product_id',
        'assigned_employee_id',
        'stop_reason',
    )
    def _compute_status(self) -> None:
        for claim in self:
            Lines = claim._get_lines()
            if Lines and all(line.is_done for line in Lines):
                claim.status = 'done'
            elif claim.stop_reason:
                claim.status = 'stopped'
            elif claim.assigned_employee_id:
                claim.status = 'in_progress'
            else:
                claim.status = 'pending'

    @api.depends('wizard_id.line_ids.is_done', 'wizard_id.line_ids.product_id')
    def _compute_line_counts(self) -> None:
        for claim in self:
            Lines = claim._get_lines()
            claim.total_line_count = len(Lines)
            claim.pending_line_count = len(Lines.filtered(lambda l: not l.is_done))

    def _compute_is_mine(self) -> None:
        current_employee_id = (
            get_active_prep_operator_id(request.session, refresh=False)
            if request else False
        )
        for claim in self:
            claim.is_mine = bool(
                current_employee_id
                and claim.assigned_employee_id.id == current_employee_id
            )

    # ── Infraestructura compartida ──

    def _check_picking_access(self) -> None:
        if not self.env.user.has_group(
            'ist_preparation_day_picking.group_preparation_picking_operator'
        ):
            raise AccessError('No tienes acceso a la pantalla de Picking.')

    def _require_active_operator(self) -> int:
        employee_id = (
            get_active_prep_operator_id(request.session, refresh=True)
            if request else False
        )
        if not employee_id:
            raise UserError(
                'Tu sesión de operario expiró por inactividad. '
                'Ingresa tu NIP de nuevo.'
            )
        return employee_id

    def _check_single_claim_per_operator(self, employee_id, exclude_self=True) -> None:
        """Un operario no puede tener dos productos "En progreso" al mismo
        tiempo (decisión de David, vía Tech Lead, Fase B)."""
        domain = [
            ('wizard_id', '=', self.wizard_id.id),
            ('assigned_employee_id', '=', employee_id),
            ('status', '=', 'in_progress'),
        ]
        if exclude_self:
            domain.append(('id', '!=', self.id))
        Other = self.search(domain, limit=1)
        if Other:
            raise UserError(
                f'Ya tienes asignado {Other.product_tmpl_id.name} — '
                'termínalo o libéralo primero.'
            )

    def _notify_bus(self) -> None:
        self.ensure_one()
        self.env['bus.bus']._sendone(
            f'guapante_preparation_day-{self.wizard_id.id}',
            'picking_claim_updated',
            {'claim_id': self.id},
        )

    # ── Acciones ──

    def action_assign(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        self._check_single_claim_per_operator(employee_id)

        # Postgres corre en REPEATABLE READ: este SELECT ... FOR UPDATE no
        # hace que un segundo tablet "vea" el valor recién escrito por el
        # primero en cuanto se libera el lock dentro de su misma
        # transacción — a ese nivel de aislamiento, Postgres le devuelve un
        # error de serialización ("could not serialize access due to
        # concurrent update"), que Odoo captura y reintenta el request
        # completo. Es en ESE reintento (una ejecución nueva de este mismo
        # método, con una transacción nueva) donde la lectura de abajo ya
        # ve assigned_employee_id puesto y lanza el UserError — no es que
        # este SELECT vea el dato fresco dentro de la transacción actual.
        # El resultado neto es el mismo (el segundo tablet nunca pisa al
        # primero), pero el mecanismo real es "falla y reintenta", no
        # "espera y lee fresco".
        #
        # flush_recordset() antes del SQL crudo: el write() del ORM no
        # manda el UPDATE a la base de inmediato, lo deja en el caché en
        # memoria hasta el próximo flush — sin esto, un SELECT crudo justo
        # después de otra acción de este mismo método (ej. la propia
        # action_assign() de un test, dentro de la misma transacción)
        # puede leer el valor viejo de la tabla real y dar un falso
        # negativo (bug encontrado por los tests de la Fase B).
        #
        # El SELECT bloqueado tiene que leer TODO lo que decide si este
        # claim es tomable — no solo assigned_employee_id (hallazgo de
        # Tech Lead): un claim Detenido queda sin dueño, así que mirar
        # solo assigned_employee_id dejaba que "Asignarme" tomara un
        # producto detenido (saltándose Retomar y su chatter) o uno ya
        # Terminado.
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id, stop_reason FROM '
            'guapante_preparation_day_product_claim WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        locked_assigned_id, locked_stop_reason = row if row else (False, False)
        Lines = self._get_lines()
        is_done = bool(Lines) and all(line.is_done for line in Lines)
        if locked_assigned_id:
            self.invalidate_recordset(['assigned_employee_id'])
            raise UserError(
                f'{self.assigned_employee_id.name} ya se asignó '
                f'{self.product_tmpl_id.name} — actualiza la pantalla.'
            )
        if locked_stop_reason:
            raise UserError(
                f'{self.product_tmpl_id.name} está detenido — usa Retomar. '
                'Actualiza la pantalla.'
            )
        if is_done:
            raise UserError(
                f'{self.product_tmpl_id.name} ya está terminado — '
                'actualiza la pantalla.'
            )
        self.write({
            'assigned_employee_id': employee_id,
            'assigned_date': fields.Datetime.now(),
        })
        self._notify_bus()
        return self.action_open_lines_kanban()

    def action_resume(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        self._check_single_claim_per_operator(employee_id)

        # Misma protección, misma explicación y mismo flush_recordset()
        # previo que action_assign.
        self.flush_recordset()
        self.env.cr.execute(
            'SELECT stop_reason FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row or not row[0]:
            self.invalidate_recordset(['stop_reason'])
            raise UserError(
                f'{self.product_tmpl_id.name} ya no está detenido — '
                'actualiza la pantalla.'
            )
        # Caso borde (Tech Lead): si todas las líneas quedaron is_done por
        # otra vía (ej. edición directa en la pestaña Productos) mientras
        # el claim seguía con stop_reason puesto, el status computado ya
        # muestra 'done' — Retomar no debe revivirlo.
        Lines = self._get_lines()
        if Lines and all(line.is_done for line in Lines):
            raise UserError(
                f'{self.product_tmpl_id.name} ya está terminado — '
                'actualiza la pantalla.'
            )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        self.write({
            'assigned_employee_id': employee_id,
            'assigned_date': fields.Datetime.now(),
            'stop_reason': False,
            'stopped_by_employee_id': False,
        })
        self.wizard_id.sudo().message_post(
            body=f"Retomado — {self.product_tmpl_id.name}: por {Employee.name}.",
        )
        self._notify_bus()
        return self.action_open_lines_kanban()

    def action_release(self) -> bool:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()

        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        current_owner_id = row[0] if row else False
        if current_owner_id != employee_id:
            self.invalidate_recordset(['assigned_employee_id'])
            owner_name = (
                self.assigned_employee_id.name
                if self.assigned_employee_id else 'nadie'
            )
            raise UserError(
                f'No puedes liberar {self.product_tmpl_id.name} — '
                f'lo tiene {owner_name}.'
            )
        self.write({'assigned_employee_id': False, 'assigned_date': False})
        self._notify_bus()
        return True

    def action_stop(self, reason: str) -> bool:
        self.ensure_one()
        self._check_picking_access()
        employee_id = self._require_active_operator()
        if reason not in dict(STOP_REASONS):
            raise UserError('Motivo de detención inválido.')

        self.flush_recordset()
        self.env.cr.execute(
            'SELECT assigned_employee_id FROM guapante_preparation_day_product_claim '
            'WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        current_owner_id = row[0] if row else False
        if current_owner_id != employee_id:
            self.invalidate_recordset(['assigned_employee_id'])
            owner_name = (
                self.assigned_employee_id.name
                if self.assigned_employee_id else 'nadie'
            )
            raise UserError(
                f'No puedes detener {self.product_tmpl_id.name} — '
                f'lo tiene {owner_name}.'
            )
        Employee = self.env['hr.employee'].sudo().browse(employee_id)
        self.write({
            'assigned_employee_id': False,
            'assigned_date': False,
            'stop_reason': reason,
            'stopped_by_employee_id': employee_id,
        })
        self.wizard_id.sudo().message_post(
            body=(
                f"Detenido — {self.product_tmpl_id.name}: "
                f"{dict(STOP_REASONS)[reason]} (por {Employee.name})."
            ),
        )
        self._notify_bus()
        return True

    def action_open_stop_wizard(self) -> dict:
        self.ensure_one()
        self._check_picking_access()
        return {
            'name': f'¿Por qué se detiene {self.product_tmpl_id.name}?',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.product.claim.stop.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_claim_id': self.id},
        }

    def action_open_lines_kanban(self) -> dict:
        """Nivel 2 real (Fase C): abre el kanban de líneas de la
        plantilla de este claim — reutiliza el mismo xmlid que el
        kanban temporal de la Fase B, reescrito con t-name="card",
        botón Listo para needs_weighing=False y alerta de peso.
        """
        self.ensure_one()
        self._check_picking_access()
        return {
            'name': self.product_tmpl_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.preparation.day.line',
            'view_mode': 'kanban',
            'domain': [
                ('wizard_id', '=', self.wizard_id.id),
                ('product_id', '=', self.product_tmpl_id.id),
            ],
            'target': 'fullscreen',
            # picking_wizard_id: igual que en action_view_product_claims,
            # para que el controller del kanban de Nivel 2
            # (preparation_picking_lines_kanban.js) pueda suscribirse al
            # mismo canal de bus que Nivel 1 y enterarse de
            # picking_operation_finished sin esperar al próximo poll del
            # watchdog (Fase C, punto 4 de Tech Lead).
            'context': {
                'guapante_picking_flow': True,
                'picking_wizard_id': self.wizard_id.id,
            },
        }

    # ── Ciclo de vida (Tech Lead, Fase B: robusto en creación de líneas,
    #    no solo en action_load; nunca borrar un claim con líneas, aunque
    #    estén todas done — solo los que no tienen ninguna) ──

    @api.model
    def _refresh_expected_kg_per_unit(self, wizard, templates) -> None:
        """Recalcula expected_kg_per_unit de los claims de `templates` en
        `wizard` (Fase C, punto 1 de Tech Lead).

        Una sola consulta agrupada, acotada a las plantillas de ESTA
        sesión (10-30 típico, nunca las ~140 plantillas pesables del
        catálogo completo) — evita 1 query por tarjeta. Excluye
        explícitamente las líneas de `wizard` (wizard_id != %s): lo que se
        está pesando HOY no puede colarse en su propia referencia
        histórica (pedido explícito de Tech Lead) — si no, un operario
        quedaría comparado contra pesos que él mismo acaba de teclear en
        esta misma sesión.
        """
        if not templates:
            return
        # flush_model() sobre Line, no sobre self: lo que puede estar sin
        # bajar a la tabla real es el write() de action_save_line_weight
        # de otra línea en esta misma transacción (ej. action_load
        # corriendo justo después de un pesaje), no un write de Claim.
        self.env['guapante.preparation.day.line'].flush_model()
        self.env.cr.execute(
            '''
            SELECT product_id,
                   percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY actual_kg / estimated_kg
                   ) AS median_kg_per_unit
            FROM guapante_preparation_day_line
            WHERE is_done = true
              AND needs_weighing = true
              AND estimated_kg > 0
              AND actual_kg > 0
              AND wizard_id != %s
              AND product_id = ANY(%s)
            GROUP BY product_id
            HAVING count(*) >= %s
            ''',
            (wizard.id, templates.ids, MIN_WEIGHT_HISTORY_LINES),
        )
        medians = dict(self.env.cr.fetchall())
        Claims = self.sudo().search([
            ('wizard_id', '=', wizard.id),
            ('product_tmpl_id', 'in', templates.ids),
        ])
        for claim in Claims:
            claim.expected_kg_per_unit = medians.get(
                claim.product_tmpl_id.id, 0.0,
            )

    @api.model
    def _ensure_claims_for_templates(self, wizard, templates) -> None:
        if not templates:
            return
        # sudo(): la creación de claims es mantenimiento interno, no una
        # acción de UI — el ACL del grupo de Picking no da create (Tech
        # Lead, punto 10), a propósito, para que nadie cree uno a mano.
        Existing = self.sudo().search([
            ('wizard_id', '=', wizard.id),
            ('product_tmpl_id', 'in', templates.ids),
        ])
        existing_tmpl_ids = set(Existing.mapped('product_tmpl_id').ids)
        Missing = templates.filtered(lambda t: t.id not in existing_tmpl_ids)
        if Missing:
            self.sudo().create([
                {'wizard_id': wizard.id, 'product_tmpl_id': tmpl.id}
                for tmpl in Missing
            ])
