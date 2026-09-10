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
"""

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Software DIAN
    l10n_co_ne_software_id = fields.Char(related='company_id.l10n_co_ne_software_id', readonly=False)
    l10n_co_ne_software_pin = fields.Char(related='company_id.l10n_co_ne_software_pin', readonly=False)
    l10n_co_ne_test_set_id = fields.Char(related='company_id.l10n_co_ne_test_set_id', readonly=False)
    l10n_co_ne_environment = fields.Selection(related='company_id.l10n_co_ne_environment', readonly=False)
    l10n_co_ne_payroll_prefix = fields.Char(related='company_id.l10n_co_ne_payroll_prefix', readonly=False)
    l10n_co_ne_adjust_prefix = fields.Char(related='company_id.l10n_co_ne_adjust_prefix', readonly=False)
    l10n_co_ne_sequence_id = fields.Many2one(related='company_id.l10n_co_ne_sequence_id', readonly=False)
    l10n_co_ne_pre_sequence_id = fields.Many2one(related='company_id.l10n_co_ne_pre_sequence_id', readonly=False)

    # Certificado Digital
    l10n_co_ne_certificate_id = fields.Many2one(related='company_id.l10n_co_ne_certificate_id', readonly=False)

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
