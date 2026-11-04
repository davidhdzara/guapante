# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .preparation_day_product_claim import STOP_REASONS

CLOSE_REASONS = [
    ('left', 'Salió de Nivel 2'),
    ('switched', 'Cambió de producto'),
    ('stopped', 'Detenido'),
    ('released', 'Liberado'),
    ('finished', 'Producto terminado'),
    ('idle', 'Inactividad (cierre por cron)'),
    ('session_closed', 'Cerró sesión'),
]


class PreparationInterval(models.Model):
    """Fase 2 (Tech Lead, 2026-11-02, diseño revisado con Odoo Engineer
    2026-11-04) — un registro por periodo continuo en que UN operario
    trabaja (o un producto queda detenido) sobre UN producto de UNA
    sesión. Insumo de las pantallas de tiempo (L1/L2) y de los reportes
    de Fase 2; nunca lo toca el operario ni ninguna pantalla por ORM
    directo — todo se abre/cierra desde los mismos puntos del servidor
    que ya existen para asignar/detener/liberar/terminar (ver
    preparation_day_product_claim.py y preparation_day_line.py).

    `kind='stopped'` NO es el reloj personal de nadie — "Detenido" es un
    estado del PRODUCTO (claim), no de un operario (cualquiera puede
    detener el claim de cualquiera, Tech Lead/David 2026-11-03). Por
    eso employee_id es informativo en ese caso (quién lo detuvo) y
    queda fuera de la restricción "un solo intervalo working abierto
    por operario" — ver el índice único parcial en init().
    """
    _name = 'guapante.preparation.interval'
    _description = 'Intervalo de trabajo/detención de Picking (Fase 2)'
    _order = 'start_dt desc'

    wizard_id = fields.Many2one(
        'guapante.preparation.day',
        string='Sesión',
        required=True,
        ondelete='cascade',
        index=True,
    )
    claim_id = fields.Many2one(
        'guapante.preparation.day.product.claim',
        string='Producto (Nivel 1)',
        required=True,
        ondelete='cascade',
        index=True,
    )
    # Stored (no solo related en memoria): los 5 reportes de Fase 2 leen
    # este campo por SQL directo sobre esta tabla — sin store=True cada
    # reporte tendría que unir contra el claim para algo que no cambia
    # una vez creado el intervalo.
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        related='claim_id.product_tmpl_id',
        store=True,
        index=True,
        readonly=True,
    )
    # Nullable (ver docstring de la clase): obligatorio solo para
    # kind='working', exigido por _check_employee_required_for_working.
    # ondelete='restrict' (Fase 2, punto 4, David 2026-11-04): un
    # empleado archivado sigue siendo historia — nunca se borra: ver
    # hr_employee.py para el mensaje claro antes de que esto reviente
    # como un IntegrityError crudo.
    employee_id = fields.Many2one(
        'hr.employee',
        string='Operario',
        ondelete='restrict',
        index=True,
    )
    kind = fields.Selection(
        selection=[('working', 'Trabajando'), ('stopped', 'Detenido')],
        string='Tipo',
        required=True,
    )
    stop_reason = fields.Selection(STOP_REASONS, string='Motivo de detención')
    start_dt = fields.Datetime(string='Inicio', required=True)
    # Nulo = abierto. El índice único parcial de init() es el que
    # garantiza "un solo working abierto por operario" — ver ahí el
    # motivo de por qué un check Python solo no basta bajo concurrencia
    # real (mismo riesgo que el incidente de numeración de cajas,
    # 2026-11-03: nada se decide sin releer bajo lock).
    end_dt = fields.Datetime(string='Fin')
    # Última acción REAL de este operario dentro del intervalo (pesar o
    # corregir una línea) — NUNCA un refresco de pantalla ni una nota
    # (action_add_note ya decide, para el claim, que una nota no cuenta
    # como "sigo trabajando"; se aplica la misma regla acá). Arranca en
    # start_dt (entrar a Nivel 2 ya es una acción real) y es lo que se
    # copia a end_dt en cualquier cierre que NO sea una salida explícita
    # del operario (switched/idle/cron) — nunca now() ni la hora del
    # cron, para no inflar el tiempo de alguien que se fue sin avisar.
    last_touched_dt = fields.Datetime(string='Última actividad real', required=True)
    # Se fija una sola vez, al cerrar — no es compute: a esta escala
    # (cientos de filas por sesión, pero se acumula sesión tras sesión)
    # recalcular en cada lectura no aporta nada sobre un valor que ya no
    # cambia.
    duration_s = fields.Integer(string='Duración (s)', readonly=True)
    close_reason = fields.Selection(CLOSE_REASONS, string='Motivo de cierre')
    # Se fija una sola vez (Fase 2: "100% transparente, cero clics
    # nuevos") — si ya tiene valor, ninguna escritura posterior lo
    # toca.
    first_weigh_dt = fields.Datetime(string='Primer pesaje')
    # Solo cuenta una línea la PRIMERA vez que queda is_done=True dentro
    # de este intervalo (Fase 2: "corregir y volver a pesar una caja...
    # no cuenta como una nueva") — una corrección posterior sobre una
    # línea ya Terminada NO incrementa nada de esto.
    lines_done = fields.Integer(string='Líneas terminadas', default=0)
    # E7 (despacho en 0, "sin stock"): aparte de lines_done, para que
    # los reportes de tiempo por kilo/caja puedan excluirlas sin perder
    # el conteo de líneas hechas.
    zero_lines_done = fields.Integer(string='Líneas en 0 (sin stock)', default=0)
    kg_done = fields.Float(string='Kg pesados', digits=(10, 3), default=0.0)

    @api.constrains('kind', 'employee_id')
    def _check_employee_required_for_working(self):
        for interval in self:
            if interval.kind == 'working' and not interval.employee_id:
                raise ValidationError(
                    'Un intervalo de trabajo necesita un operario — '
                    'solo un intervalo de detención puede quedar sin uno.'
                )

    def init(self):
        """Índice único parcial — backstop de base de datos para "un
        solo intervalo working abierto por operario" (Tech Lead,
        2026-11-04, condición (a)). El candado real en caliente es un
        pg_advisory_xact_lock por employee_id que toma el código que
        abre/cierra intervalos (ver el método de apertura, próximo
        commit) — este índice nunca debería saltar en operación normal;
        si lo hace (ej. un fallo del advisory lock), es la única razón
        por la que puede fallar un INSERT acá, nunca un UserError visible
        al operario por un intervalo huérfano (principio rector).
        IF NOT EXISTS: idempotente ante un -u repetido, mismo criterio
        que el resto de los índices que Odoo ya crea solo por
        index=True en los campos de arriba.
        """
        self.env.cr.execute(
            '''
            CREATE UNIQUE INDEX IF NOT EXISTS
                guapante_preparation_interval_one_working_per_employee
            ON guapante_preparation_interval (employee_id)
            WHERE end_dt IS NULL AND kind = 'working'
            '''
        )
