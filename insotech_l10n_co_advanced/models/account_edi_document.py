# -*- coding: utf-8 -*-
"""DEPRECATED: DIAN response detection via account.edi.document.

.. deprecated:: 18.0.2.0.0
    Odoo 18 uses ``l10n_co_dian.document`` (not ``account.edi.document``)
    for DIAN electronic invoicing state management. The detection hook
    has been moved to ``l10n_co_dian_document.py``.

This file is kept to avoid ``__init__.py`` import errors during
module upgrade. The ``write()`` override has been removed.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountEdiDocument(models.Model):
    """Stub — detection moved to l10n_co_dian_document.py."""

    _inherit = 'account.edi.document'
