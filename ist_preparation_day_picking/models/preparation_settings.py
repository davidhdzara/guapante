# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.ist_preparation_day.models.const_preparation import (
    IDLE_TIMEOUT_PARAM_KEY,
    get_idle_timeout_seconds,
)

# Fallback de minutos a mostrar cuando el parámetro está en 0 (bloqueo
# desactivado) y el usuario vuelve a marcar la casilla sin haber escrito
# nada todavía — mismo valor que PREP_OPERATOR_IDLE_TIMEOUT_SECONDS/60.
_DEFAULT_IDLE_LOCK_MINUTES = 5

_IDLE_LOCK_MINUTES_MIN = 1
_IDLE_LOCK_MINUTES_MAX = 1440

_SETTINGS_GROUP_XMLID = 'ist_preparation_day_picking.group_preparation_admin'


def _default_idle_lock_enabled(env):
    return bool(get_idle_timeout_seconds(env))


def _default_idle_lock_minutes(env):
    seconds = get_idle_timeout_seconds(env)
    if seconds:
        return max(_IDLE_LOCK_MINUTES_MIN, seconds // 60)
    return _DEFAULT_IDLE_LOCK_MINUTES


class GuapantePreparationSettings(models.TransientModel):
    """Pantalla propia de Ajustes de Preparación (menú Preparación ›
    Configuración › Ajustes — Tech Lead/David, 2026-11-02).

    NO hereda de res.config.settings (`_inherit`), a propósito: eso
    crearía una tabla nueva con una columna por cada campo que
    CUALQUIER módulo instalado le haya agregado a ese modelo — hoy
    247 columnas en staging_dev (`SELECT count(*) FROM
    information_schema.columns WHERE table_name =
    'res_config_settings'`) — desproporcionado para una pantalla de 2
    campos que no usa nada de esa plumbing (nuestra traducción
    segundos↔minutos es manual, no el kwarg config_parameter).

    Tampoco reutiliza la vista/acción compartida de Ajustes: esa
    pasa siempre por el menú "Ajustes" general, que el cliente
    condiciona a base.group_system — y Mauricio no lo tiene (decisión
    de David: no se le otorga, no es Administrador general, solo
    Administrador de Preparación).

    Se ve y comporta exactamente igual que un Ajustes nativo porque
    la vista usa el mismo js_class="base_settings" — confirmado en
    web/static/.../settings_form_controller.js (líneas ~102-106): el
    botón Guardar llama al método "execute" dinámicamente sobre
    resModel, no está amarrado al nombre 'res.config.settings'.
    """
    _name = 'guapante.preparation.settings'
    _description = 'Ajustes de Preparación'

    prep_idle_lock_enabled = fields.Boolean(
        string='Bloquear por inactividad',
        default=lambda self: _default_idle_lock_enabled(self.env),
    )
    prep_idle_lock_minutes = fields.Integer(
        string='Minutos de inactividad',
        default=lambda self: _default_idle_lock_minutes(self.env),
    )

    def execute(self):
        """Mismo nombre que res.config.settings.execute() a propósito
        (lo que llama el botón Guardar, ver docstring de la clase).
        En el modelo nativo el único chequeo de administrador vive
        ahí (`self.env.is_admin()`, exige base.group_system) — acá se
        cambia por group_preparation_admin. sudo() nunca se usa para
        saltarse ESTE chequeo, solo más abajo para escribir el
        parámetro, una vez que ya se confirmó el grupo."""
        self.ensure_one()
        if not self.env.user.has_group(_SETTINGS_GROUP_XMLID):
            raise AccessError(_(
                'No tienes acceso a los Ajustes de Preparación.'
            ))
        self._save_idle_lock_param()
        # Reabre el mismo formulario con el valor recién guardado en
        # vez del "reload" nativo (que recarga menú + vista completa)
        # — esta pantalla no instala/desinstala módulos, no hace
        # falta ese costo (Tech Lead, 2026-11-02).
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'inline',
        }

    def _save_idle_lock_param(self) -> None:
        """Única lectura/escritura de IDLE_TIMEOUT_PARAM_KEY —
        get_idle_timeout_seconds(env) sigue siendo la única fuente de
        verdad en todo Picking, esto solo la traduce. sudo() acotado
        a este parámetro, nada más."""
        if self.prep_idle_lock_enabled:
            minutes = self.prep_idle_lock_minutes
            if not (_IDLE_LOCK_MINUTES_MIN <= minutes <= _IDLE_LOCK_MINUTES_MAX):
                raise ValidationError(_(
                    'Ingresa entre %(min)s y %(max)s minutos.',
                    min=_IDLE_LOCK_MINUTES_MIN, max=_IDLE_LOCK_MINUTES_MAX,
                ))
            seconds = minutes * 60
        else:
            seconds = 0
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, str(seconds),
        )
