# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class PreparationDayProductClaimConflictWizard(models.TransientModel):
    """Diálogo nativo (target='new') cuando un operario que ya tiene un
    producto En progreso intenta tomar otro (plan f2, Tech Lead,
    2026-10-31) — reemplaza el UserError seco de
    _check_single_claim_per_operator por tres salidas: ir a terminar lo
    que ya tiene, liberarlo y tomar el nuevo de una vez, o detenerlo con
    motivo (mismo wizard de siempre). _check_single_claim_per_operator
    NO cambió — action_assign()/action_resume() siguen llamándola tal
    cual y atrapan SOLO ese error puntual para abrir este wizard en vez
    de dejarlo como mensaje seco (condición 1 de Tech Lead); cualquier
    otro conflicto (ej. que OTRO operario ya tenga el producto que se
    quiere tomar) sigue siendo un UserError normal, sin pasar por acá.
    """
    _name = 'guapante.preparation.day.product.claim.conflict.wizard'
    _description = 'Conflicto de un solo claim por operario — Nivel 1 de Picking'

    claim_id = fields.Many2one(
        'guapante.preparation.day.product.claim',
        string='Producto que se quería tomar', required=True, readonly=True,
    )
    other_claim_id = fields.Many2one(
        'guapante.preparation.day.product.claim',
        string='Producto que ya tiene', required=True, readonly=True,
    )
    message = fields.Char(compute='_compute_message')

    @api.depends('claim_id', 'other_claim_id')
    def _compute_message(self) -> None:
        for wizard in self:
            pending = wizard.other_claim_id.pending_line_count
            unidad = 'caja' if pending == 1 else 'cajas'
            wizard.message = (
                f'Ya tienes asignado «{wizard.other_claim_id.product_tmpl_name}» '
                f'({pending} {unidad} por pesar). Para tomar '
                f'«{wizard.claim_id.product_tmpl_name}» primero termínalo, '
                'libéralo o detenlo con un motivo.'
            )

    def _ensure_other_claim_still_mine(self) -> int:
        """Revalidación al hacer clic (condición 3 de Tech Lead): el
        wizard puede quedar abierto varios minutos — el operario puede
        haber expirado, o el producto puede haberse liberado/terminado/
        detenido por otra vía (cron de abandono, otro tablet) mientras
        tanto. Devuelve el employee_id vigente; levanta UserError claro
        si other_claim_id ya no es suyo para "Ir a terminarlo"/"Detener
        con motivo" (no hay nada sensible que hacer ahí si ya no es
        suyo) — "Liberar y tomar este" la usa distinto, ver su propio
        método."""
        self.ensure_one()
        employee_id = self.claim_id._require_active_operator()
        self.other_claim_id.invalidate_recordset(
            ['status', 'assigned_employee_id'],
        )
        if (
            self.other_claim_id.status != 'in_progress'
            or self.other_claim_id.assigned_employee_id.id != employee_id
        ):
            raise UserError(
                f'«{self.other_claim_id.product_tmpl_name}» ya no está '
                'asignado a ti — actualiza la pantalla.'
            )
        return employee_id

    def action_go_finish(self) -> dict:
        self.ensure_one()
        self._ensure_other_claim_still_mine()
        return self.other_claim_id.action_open_lines_kanban()

    def action_stop_other(self) -> dict:
        self.ensure_one()
        self._ensure_other_claim_still_mine()
        return self.other_claim_id.action_open_stop_wizard()

    def action_release_and_assign(self) -> dict:
        """Condición 2 de Tech Lead: liberar el que ya tiene y asignar
        el nuevo van en UN savepoint — si asignar el nuevo falla (otro
        operario se lo llevó mientras el wizard estaba abierto), la
        liberación también se deshace, nunca se queda sin ninguno de
        los dos.

        Condición 3, caso particular de este botón: si other_claim_id
        YA no es suyo (se liberó solo por el cron, por ejemplo, mientras
        el wizard seguía abierto), no hay nada que liberar — eso ya no
        es un error, simplemente se intenta asignar el nuevo directo
        (puede que ya no haya ningún conflicto en absoluto)."""
        self.ensure_one()
        employee_id = self.claim_id._require_active_operator()
        self.other_claim_id.invalidate_recordset(
            ['status', 'assigned_employee_id'],
        )
        other_still_mine = (
            self.other_claim_id.status == 'in_progress'
            and self.other_claim_id.assigned_employee_id.id == employee_id
        )
        other_product_name = self.other_claim_id.product_tmpl_name
        try:
            with self.env.cr.savepoint():
                if other_still_mine:
                    self.other_claim_id._release_claim()
                return self.claim_id.action_assign()
        except UserError as exc:
            if other_still_mine:
                raise UserError(
                    f'{exc.args[0]} Tu producto actual '
                    f'(«{other_product_name}») sigue asignado a ti.'
                ) from exc
            raise
