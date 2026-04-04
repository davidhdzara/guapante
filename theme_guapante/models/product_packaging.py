# -*- coding: utf-8 -*-
from odoo import models


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'
    # VIP B2B fields removed — exclusivity now lives on product.template.
    # See product_template.py: is_b2b_exclusive, b2b_exclusive_customer_ids.
