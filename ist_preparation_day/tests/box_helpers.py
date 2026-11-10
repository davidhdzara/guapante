# -*- coding: utf-8 -*-
"""Helpers de pruebas para sembrar números de caja respetando el candado
(lote 4): nada de `order.daily_sequence = n` directo."""
from odoo.addons.ist_preparation_day.models.box_number import (
    CTX_ORIGIN,
    ORIGIN_ALTA,
    ORIGIN_REUBICACION,
    box_origin,
)


def set_box(order, value):
    """Deja el pedido con `value` pasando por 0 si ya tenía número."""
    order = order.sudo()
    if order.daily_sequence and order.daily_sequence != value:
        order.with_context(
            **{CTX_ORIGIN: box_origin(ORIGIN_REUBICACION)}
        ).write({'daily_sequence': 0})
    if value:
        order.with_context(
            **{CTX_ORIGIN: box_origin(ORIGIN_ALTA)}
        ).write({'daily_sequence': value})
    return order
