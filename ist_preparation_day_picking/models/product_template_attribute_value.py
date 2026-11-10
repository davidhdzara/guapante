# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CHIP_COLORS_PARAM = 'ist_preparation_day_picking.attribute_chip_colors'


class ProductTemplateAttributeValue(models.Model):
    """Color del chip de Nivel 2 POR VALOR (punto 3, David 2026-11-10).

    El `color` nativo de este modelo es un índice aleatorio por producto
    (el mismo «Verde» sale con 9 colores): no sirve. El color con
    significado vive en un parámetro del sistema JSON {nombre del valor:
    índice 0-11 de las clases nativas o_tag_color_N}, igual para todos los
    productos. Valor sin mapear → 0 (neutro)."""
    _inherit = 'product.template.attribute.value'

    guapante_chip_color = fields.Integer(
        string='Color del chip (Picking)', compute='_compute_guapante_chip_color',
    )

    @api.model
    def _guapante_chip_color_map(self) -> dict:
        raw = self.env['ir.config_parameter'].sudo().get_param(
            CHIP_COLORS_PARAM, '{}')
        try:
            data = json.loads(raw or '{}')
            return {
                str(k): int(v) for k, v in data.items() if 0 <= int(v) <= 11
            }
        except (ValueError, TypeError, AttributeError):
            _logger.warning(
                'Guapante: %s no es un JSON válido {nombre: 0-11}; los chips '
                'quedan neutros.', CHIP_COLORS_PARAM)
            return {}

    @api.depends('product_attribute_value_id.name')
    def _compute_guapante_chip_color(self):
        colors = self._guapante_chip_color_map()
        for ptav in self:
            ptav.guapante_chip_color = colors.get(
                ptav.product_attribute_value_id.name or '', 0)
