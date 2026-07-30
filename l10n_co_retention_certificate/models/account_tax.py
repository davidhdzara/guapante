# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Regla 2 — prefijo de la cuenta PUC de repartición -> tipo de retención.
# Ver ESPEC §4 Fase 1. No alterar el orden ni los prefijos sin revisar
# de nuevo los datos reales del cliente.
ACCOUNT_PREFIX_TO_RETENTION_TYPE = [
    ('2367', 'reteiva'),
    ('2368', 'reteica'),
    ('2460', 'parafiscal'),
    ('2365', 'retefuente'),
]

# Regla 3 — patrón en el nombre del impuesto -> tipo de retención.
# Se evalúa en este orden: 'parafiscal' primero porque nombres como
# "Rte Paraf Asohofrucol" no deben caer en ninguna otra regla por accidente.
#
# 'ICA'/'IVA'/'VAT' se buscan en MAYÚSCULAS y sin usar .lower(), porque
# así se escriben siempre en este dominio (RteICA, RteIVA/RteVAT) y
# buscarlas en minúsculas genera falsos positivos: la subcadena 'ica'
# aparece dentro de palabras españolas comunes como "genérica",
# "básica", "técnica". Bug real encontrado en staging_dev el 2026-07-29
# (test_rule3_name_pattern_retefuente clasificaba "Retención en la
# Fuente Genérica" como reteica por culpa de "genÉRICA").
NAME_PATTERN_TO_RETENTION_TYPE_CI = [
    (
        ('paraf', 'fomento', 'asohofrucol', 'fedepapa', 'cereales', 'leguminosas', 'soya'),
        'parafiscal',
    ),
]
NAME_PATTERN_TO_RETENTION_TYPE_CS = [
    (('ICA',), 'reteica'),
    (('IVA', 'VAT'), 'reteiva'),
]
NAME_PATTERN_TO_RETENTION_TYPE_CI_TAIL = [
    (('rtefte', 'fuente'), 'retefuente'),
]


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_co_retention_type = fields.Selection(
        selection=[
            ('retefuente', 'Retención en la Fuente'),
            ('reteiva', 'Retención de IVA'),
            ('reteica', 'Retención de ICA'),
            ('parafiscal', 'Contribución Parafiscal'),
        ],
        string='Tipo de Retención (CO)',
        help='Clasifica el impuesto para el Certificado de Retenciones. '
             'Se autocompleta al instalar el módulo; editable manualmente '
             'si el clasificador se equivoca.',
    )

    def _l10n_co_compute_retention_type(self):
        """Clasifica los impuestos colombianos de retención de compras.

        Solo se evalúan impuestos con amount < 0 y type_tax_use = 'purchase'
        (lo que NOSOTROS retenemos a proveedores). Los de venta (retenciones
        que nos practican a nosotros) quedan fuera de alcance.

        Orden de reglas (no alterar, ver ESPEC §4 Fase 1 para la
        justificación con datos reales):
            1. Concepto vinculado en el motor InSoTech, si está instalado.
            2. Prefijo de la cuenta PUC de repartición.
            3. Patrón en el nombre del impuesto.
            4. Sin clasificar (queda vacío, se reporta en el log).
        """
        candidates = self.filtered(
            lambda t: t.amount < 0 and t.type_tax_use == 'purchase'
        )
        if not candidates:
            return

        concept_type_by_tax_id = candidates._l10n_co_get_insotech_concept_types()
        unclassified = self.env['account.tax']

        for tax in candidates:
            retention_type = (
                concept_type_by_tax_id.get(tax.id)
                or tax._l10n_co_retention_type_from_account()
                or tax._l10n_co_retention_type_from_name()
            )
            if retention_type:
                tax.l10n_co_retention_type = retention_type
            else:
                unclassified |= tax

        if unclassified:
            _logger.warning(
                "Certificado de Retenciones: %s impuesto(s) de compra sin "
                "clasificar automáticamente, revisar manualmente en "
                "Contabilidad > Configuración > Impuestos: %s",
                len(unclassified),
                ', '.join(unclassified.mapped('name')),
            )

    def _l10n_co_get_insotech_concept_types(self):
        """Regla 1: mapea id de account.tax -> tipo de retención usando
        insotech.retention.concept (motor InSoTech), si ese módulo está
        instalado. Devuelve {} si no lo está, para que el módulo funcione
        de forma independiente en otros clientes.
        """
        if 'insotech.retention.concept' not in self.env:
            return {}

        concepts = self.env['insotech.retention.concept'].search([
            '|',
            ('purchase_tax_id', 'in', self.ids),
            ('tax_id', 'in', self.ids),
        ])

        concept_type_by_tax_id = {}
        for concept in concepts:
            if concept.purchase_tax_id.id in self.ids:
                concept_type_by_tax_id[concept.purchase_tax_id.id] = concept.type
            if concept.tax_id.id in self.ids:
                concept_type_by_tax_id.setdefault(concept.tax_id.id, concept.type)
        return concept_type_by_tax_id

    def _l10n_co_retention_type_from_account(self):
        """Regla 2: infiere el tipo desde el prefijo de la cuenta PUC de la
        línea de repartición de tipo 'tax' en la factura (no en la nota
        crédito, y no la línea 'base').
        """
        self.ensure_one()
        repartition_line = self.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == 'tax'
        )[:1]
        account = repartition_line.account_id
        if not account or not account.code:
            return False

        code = account.code
        for prefix, retention_type in ACCOUNT_PREFIX_TO_RETENTION_TYPE:
            if code.startswith(prefix):
                return retention_type
        return False

    def _l10n_co_retention_type_from_name(self):
        """Regla 3: infiere el tipo desde patrones en el nombre del
        impuesto, como último recurso antes de dejarlo sin clasificar.

        Orden: parafiscal -> ICA -> IVA -> fuente (no alterar). ICA/IVA
        se buscan case-sensitive (ver comentario junto a las constantes);
        parafiscal y fuente se buscan case-insensitive porque no generan
        los mismos falsos positivos.
        """
        self.ensure_one()
        name = self.name or ''
        name_lower = name.lower()

        for keywords, retention_type in NAME_PATTERN_TO_RETENTION_TYPE_CI:
            if any(keyword in name_lower for keyword in keywords):
                return retention_type

        for keywords, retention_type in NAME_PATTERN_TO_RETENTION_TYPE_CS:
            if any(keyword in name for keyword in keywords):
                return retention_type

        for keywords, retention_type in NAME_PATTERN_TO_RETENTION_TYPE_CI_TAIL:
            if any(keyword in name_lower for keyword in keywords):
                return retention_type

        return False
