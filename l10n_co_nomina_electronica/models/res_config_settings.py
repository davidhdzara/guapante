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
como Batch Transfer o Blanket Order). El domain de
`l10n_co_ne_certificate_id` cambia además de `id` (id de la compañía en
res.company) a `company_id` (el campo real que existe en este wizard).

Doc 22: "Software DIAN" (3 Char planos) y "Ambiente" (Selection) se
reemplazaron por la tabla `l10n_co_ne_operation_mode_ids` y los 2
checkboxes `l10n_co_ne_test_environment`/`_certification_process`, para
replicar la estructura de Facturación Electrónica (CO). Se agregó
también `l10n_co_ne_certificate_ids` (O2M, paridad literal con
`l10n_co_dian_certificate_ids`) -- ver res_company.py para por qué NO
reemplaza a `l10n_co_ne_certificate_id` como fuente de verdad funcional.
"""

from odoo import api, fields, models


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

    # Certificado Digital (doc 22 §2, Opción B)
    l10n_co_ne_certificate_id = fields.Many2one(
        related='company_id.l10n_co_ne_certificate_id', readonly=False,
        # Domain original en res.company usa `id` (id de la propia
        # compañía, porque el campo vive ahí) -- aquí `id` seria el id de
        # este TransientModel, hay que usar `company_id` (doc 21 §1.3).
        domain="[('company_id', '=', company_id)]",
    )
    l10n_co_ne_certificate_ids = fields.One2many(
        related='company_id.l10n_co_ne_certificate_ids', readonly=False,
    )

    @api.onchange('l10n_co_ne_certificate_ids')
    def _onchange_l10n_co_ne_certificate_ids(self):
        """Autoselecciona el certificado si hay exactamente 1 en la lista.

        Evita la ambigüedad de DIAN (que toma "el último de la lista" sin
        ningún campo que marque el activo, doc 22 §2) sin obligar al
        usuario a elegir manualmente cuando solo hay una opción real.
        """
        if not self.l10n_co_ne_certificate_id and len(self.l10n_co_ne_certificate_ids) == 1:
            self.l10n_co_ne_certificate_id = self.l10n_co_ne_certificate_ids

    # UGPP
    l10n_co_ugpp_legal_nature = fields.Selection(related='company_id.l10n_co_ugpp_legal_nature', readonly=False)
    l10n_co_ugpp_contributor_type = fields.Selection(related='company_id.l10n_co_ugpp_contributor_type', readonly=False)
    l10n_co_ugpp_special_autoretention = fields.Boolean(related='company_id.l10n_co_ugpp_special_autoretention', readonly=False)

    # Parámetros Nómina Colombia
    l10n_co_ne_exoneration_1607 = fields.Boolean(related='company_id.l10n_co_ne_exoneration_1607', readonly=False)

    # PILA
    l10n_co_pila_tipo_aportante = fields.Selection(related='company_id.l10n_co_pila_tipo_aportante', readonly=False)
    l10n_co_pila_arl_code = fields.Char(related='company_id.l10n_co_pila_arl_code', readonly=False)
    l10n_co_pila_forma_presentacion = fields.Selection(related='company_id.l10n_co_pila_forma_presentacion', readonly=False)
    l10n_co_pila_codigo_sucursal = fields.Char(related='company_id.l10n_co_pila_codigo_sucursal', readonly=False)
    l10n_co_pila_nombre_sucursal = fields.Char(related='company_id.l10n_co_pila_nombre_sucursal', readonly=False)
    l10n_co_pila_operador_code = fields.Char(related='company_id.l10n_co_pila_operador_code', readonly=False)
