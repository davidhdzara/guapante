import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _ensure_product_category_goods_xmlid(env):
    """Ensure product.product_category_goods XML ID exists.

    The l10n_co_dian module references this XML ID when running
    the DIAN certification process. In databases created without
    demo data, this XML ID doesn't exist and causes a ValueError
    that blocks the entire certification flow.

    This hook creates the XML ID pointing to the first available
    product category if it doesn't already exist.
    """
    imd = env['ir.model.data']
    try:
        imd._xmlid_to_res_model_res_id(
            'product.product_category_goods',
            raise_if_not_found=True,
        )
        _logger.info(
            "Insotech: product.product_category_goods XML ID "
            "already exists. No action needed."
        )
        return
    except ValueError:
        pass

    # Find the best candidate category
    Category = env['product.category']

    # Try to find a category named "All" or the root category
    category = Category.search(
        [('parent_id', '=', False)], limit=1, order='id ASC',
    )
    if not category:
        category = Category.search([], limit=1, order='id ASC')

    if not category:
        _logger.warning(
            "Insotech: No product categories found. Cannot "
            "create product.product_category_goods XML ID. "
            "The DIAN certification may fail."
        )
        return

    # Create the XML ID
    imd.create({
        'module': 'product',
        'name': 'product_category_goods',
        'model': 'product.category',
        'res_id': category.id,
        'noupdate': True,
    })

    _logger.info(
        "Insotech: Created product.product_category_goods XML ID "
        "pointing to category '%s' (id=%s). This prevents a "
        "ValueError in l10n_co_dian's certification process.",
        category.name, category.id,
    )


def post_init_hook(env):
    """Post-init hook for insotech_dian_wizard module."""
    _ensure_product_category_goods_xmlid(env)
