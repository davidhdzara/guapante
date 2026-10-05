# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de res.config.settings para exponer la configuración de Nómina
Electrónica DIAN dentro de Ajustes > Nómina, en vez de una pestaña en la
ficha de la compañía (Ajustes Generales).

El dato real sigue viviendo en res.company -- este modelo solo lo expone
en otro lugar de la UI vía `related` + `readonly=False` (sin esto último,
un related es de solo lectura por defecto en Odoo). Mismo patrón que
l10n_co_dian/models/res_config_settings.py (Contabilidad > Facturación
Electrónica (CO)), doc 19.

Sin `help=` en ningún campo: el texto de ayuda visible viene del atributo
`help=` de cada `<setting>` en la vista, no de que el campo lo herede del
related (confirmado por Tech Lead contra el mismo ejemplo de l10n_co_dian).

`domain=` SÍ hay que declararlo explícito en cada Many2one related que lo
necesite (doc 21 §1.2/1.3) -- a diferencia de `help=`, un related NO
hereda el `domain=` del campo destino en res.company. Sin esto, el
picker del campo trae CUALQUIER registro del modelo (verificado: sin
domain, `l10n_co_ne_sequence_id` mostraba secuencias de otros módulos
como Batch Transfer o Blanket Order).

Doc 22: "Software DIAN" (3 Char planos) y "Ambiente" (Selection) se
reemplazaron por la tabla `l10n_co_ne_operation_mode_ids` y los 2
checkboxes `l10n_co_ne_test_environment`/`_certification_process`, para
replicar la estructura de Facturación Electrónica (CO). Se agregó
también `l10n_co_ne_certificate_ids` (O2M, paridad literal con
`l10n_co_dian_certificate_ids`).

2026-09-12: retirado `l10n_co_ne_certificate_id` (Many2one de selección
explícita) -- verificado que Facturación Electrónica no tiene equivalente,
toma siempre el último certificado de la lista. `res.company._get_ne_certificate()`
reemplaza su uso en el flujo de firma con el mismo criterio.

2026-09-12 (doc 36 v2): "Cuentas Predeterminadas" -- 4 campos de diario
contable, uno por estructura salarial colombiana (`journal_id` de
`hr.payroll.structure`, company_dependent). NO son `related=`: `journal_id`
vive en hr.payroll.structure, no hay cadena de relación simple desde
company_id hasta ahí (a diferencia de todos los campos de arriba, que sí
cuelgan de res.company). Se exponen con el mecanismo nativo de Odoo para
este caso -- override de get_values()/set_values() -- mismo patron que usa
`account` para varios de sus propios campos de "Default Accounts".
"""

from odoo import _, api, fields, models

_NE_STRUCTURE_JOURNAL_FIELDS = {
    'l10n_co_ne_journal_nomina_id': 'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina',
    'l10n_co_ne_journal_prima_id': 'l10n_co_nomina_electronica.hr_payroll_structure_co_prima',
    'l10n_co_ne_journal_liquidacion_id': 'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion',
    'l10n_co_ne_journal_bonificacion_id': 'l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion',
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Modos de Operación DIAN (doc 22 §1)
    l10n_co_ne_operation_mode_ids = fields.One2many(
        related='company_id.l10n_co_ne_operation_mode_ids', readonly=False,
    )
    l10n_co_ne_payroll_prefix = fields.Char(related='company_id.l10n_co_ne_payroll_prefix', readonly=False)
    l10n_co_ne_adjust_prefix = fields.Char(related='company_id.l10n_co_ne_adjust_prefix', readonly=False)
    l10n_co_ne_sequence_id = fields.Many2one(
        related='company_id.l10n_co_ne_sequence_id', readonly=False,
        domain="[('code', 'like', 'l10n_co_nomina.')]",
    )
    l10n_co_ne_pre_sequence_id = fields.Many2one(
        related='company_id.l10n_co_ne_pre_sequence_id', readonly=False,
        domain="[('code', 'like', 'l10n_co_nomina.')]",
    )

    # Ambiente (doc 22 §3)
    l10n_co_ne_test_environment = fields.Boolean(related='company_id.l10n_co_ne_test_environment', readonly=False)
    l10n_co_ne_certification_process = fields.Boolean(related='company_id.l10n_co_ne_certification_process', readonly=False)
    l10n_co_ne_demo_mode = fields.Boolean(related='company_id.l10n_co_ne_demo_mode', readonly=False)
    l10n_co_ne_num_nomina_certificar = fields.Integer(related='company_id.l10n_co_ne_num_nomina_certificar', readonly=False)
    l10n_co_ne_num_ajuste_certificar = fields.Integer(related='company_id.l10n_co_ne_num_ajuste_certificar', readonly=False)

    # Certificado Digital -- retirado el Many2one de selección explícita
    # 2026-09-12 (paridad real con Facturación Electrónica, que no tiene
    # ninguno; ver res_company.py: _get_ne_certificate()). Queda solo la
    # lista, gestionable desde esta pantalla.
    l10n_co_ne_certificate_ids = fields.One2many(
        related='company_id.l10n_co_ne_certificate_ids', readonly=False,
    )

    # UGPP
    l10n_co_ugpp_legal_nature = fields.Selection(related='company_id.l10n_co_ugpp_legal_nature', readonly=False)
    l10n_co_ugpp_contributor_type = fields.Selection(related='company_id.l10n_co_ugpp_contributor_type', readonly=False)
    l10n_co_ugpp_special_autoretention = fields.Boolean(related='company_id.l10n_co_ugpp_special_autoretention', readonly=False)

    # Parámetros Nómina Colombia
    l10n_co_ne_exoneration_1607 = fields.Boolean(related='company_id.l10n_co_ne_exoneration_1607', readonly=False)

    # PILA
    l10n_co_pila_tipo_aportante = fields.Selection(related='company_id.l10n_co_pila_tipo_aportante', readonly=False)
    l10n_co_pila_arl_code = fields.Char(related='company_id.l10n_co_pila_arl_code', readonly=False)
    l10n_co_pila_arl_name = fields.Char(related='company_id.l10n_co_pila_arl_name', readonly=False)
    l10n_co_pila_forma_presentacion = fields.Selection(related='company_id.l10n_co_pila_forma_presentacion', readonly=False)
    l10n_co_pila_codigo_sucursal = fields.Char(related='company_id.l10n_co_pila_codigo_sucursal', readonly=False)
    l10n_co_pila_nombre_sucursal = fields.Char(related='company_id.l10n_co_pila_nombre_sucursal', readonly=False)
    l10n_co_pila_operador_code = fields.Char(related='company_id.l10n_co_pila_operador_code', readonly=False)

    # Cuentas Predeterminadas -- Diarios por Estructura Salarial (doc 36 v2)
    l10n_co_ne_journal_nomina_id = fields.Many2one('account.journal', string='Diario — Nómina General')
    l10n_co_ne_journal_prima_id = fields.Many2one('account.journal', string='Diario — Prima de Servicios')
    l10n_co_ne_journal_liquidacion_id = fields.Many2one('account.journal', string='Diario — Liquidación de Contrato')
    l10n_co_ne_journal_bonificacion_id = fields.Many2one('account.journal', string='Diario — Bonificaciones Extraordinarias')

    def get_values(self):
        res = super().get_values()
        for fname, xmlid in _NE_STRUCTURE_JOURNAL_FIELDS.items():
            structure = self.env.ref(xmlid, raise_if_not_found=False)
            res[fname] = structure.journal_id.id if structure else False
        return res

    def set_values(self):
        super().set_values()
        for fname, xmlid in _NE_STRUCTURE_JOURNAL_FIELDS.items():
            structure = self.env.ref(xmlid, raise_if_not_found=False)
            if structure:
                structure.journal_id = self[fname]

    # Habilitación DIAN automática (ver l10n_co_ne_habilitacion.py): estado y avance en pantalla.
    l10n_co_ne_hab_state = fields.Selection(related='company_id.l10n_co_ne_hab_state')
    l10n_co_ne_hab_message = fields.Char(related='company_id.l10n_co_ne_hab_message')
    l10n_co_ne_hab_progress = fields.Float(compute='_compute_l10n_co_ne_hab_progress')
    l10n_co_ne_hab_summary = fields.Char(compute='_compute_l10n_co_ne_hab_progress')

    @api.depends('company_id', 'company_id.l10n_co_ne_hab_state')
    def _compute_l10n_co_ne_hab_progress(self):
        engine = self.env['l10n.co.ne.habilitacion']
        for settings in self:
            progress = engine.progress(settings.company_id)
            (acc_i, rej_i, tgt_i), (acc_a, rej_a, tgt_a) = progress['ind'], progress['aj']
            summary = _('Nómina %(ai)d/%(ti)d · Nota de ajuste %(aa)d/%(ta)d aceptadas',
                        ai=acc_i, ti=tgt_i, aa=acc_a, ta=tgt_a)
            if rej_i + rej_a:
                summary += _(' · %d rechazada(s)', rej_i + rej_a)
            settings.l10n_co_ne_hab_progress = progress['percent']
            settings.l10n_co_ne_hab_summary = summary

    def action_iniciar_habilitacion_nomina(self):
        """Habilitación DIAN en 1 clic: prepara, envía y consulta sola (un cron la va avanzando).

        Reemplaza el flujo del asistente (que enviaba todo en un solo ZIP y dependía de que el
        usuario regenerara a mano); el asistente sigue existiendo y el motor lo reutiliza.
        """
        self.ensure_one()
        return self.env['l10n.co.ne.habilitacion'].start(self.company_id)

    def action_refresh_habilitacion(self):
        return {'type': 'ir.actions.client', 'tag': 'reload'}
