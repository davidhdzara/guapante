# -*- coding: utf-8 -*-
"""InSoTech DIAN Wizard — DIAN configuration for res.company.

This file handles DIAN-specific fields: credentials, certificate,
contingency config, RADIAN mode, and certificate expiry CRON.

License fields live in insotech_core/models/res_company.py.
"""
import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Thresholds for certificate expiry alerts (in days)
_CERT_ALERT_CRITICAL = 7
_CERT_ALERT_WARNING = 30
_CERT_ALERT_NOTICE = 90


class ResCompany(models.Model):
    """Extensión de res.company con campos de habilitación DIAN."""

    _inherit = 'res.company'

    insotech_dian_software_id = fields.Char(
        string="Software ID (DIAN)",
    )
    insotech_dian_software_pin = fields.Char(
        string="Software PIN (DIAN)",
    )
    insotech_dian_test_set_id = fields.Char(
        string="Test Set ID (DIAN)",
    )
    insotech_dian_config_state = fields.Selection(
        selection=[
            ('not_configured', 'Sin Configurar'),
            ('in_progress', 'En Proceso'),
            ('enabled', 'Habilitado'),
        ],
        string="Estado Configuración DIAN",
        default='not_configured',
    )
    insotech_dian_cert_file = fields.Binary(
        string="Certificado .p12 (DIAN)",
        attachment=True,
    )
    insotech_dian_cert_filename = fields.Char(
        string="Nombre archivo certificado",
    )
    insotech_dian_cert_password = fields.Char(
        string="Contraseña certificado (DIAN)",
    )
    insotech_dian_cert_expiry_date = fields.Date(
        string="Vencimiento Certificado DIAN",
        compute='_compute_cert_expiry_date',
        store=True,
        help="Fecha de vencimiento extraída automáticamente "
             "del certificado .p12 cargado.",
    )
    insotech_dian_cert_days_remaining = fields.Integer(
        string="Días restantes certificado",
        compute='_compute_cert_days_remaining',
        help="Días restantes antes del vencimiento del certificado.",
    )
    insotech_radian_mode = fields.Selection(
        selection=[
            ('disabled', 'Desactivado'),
            ('manual', 'Solo facturas marcadas (vocación de circulación)'),
            ('all_credit', 'Todas las facturas a crédito'),
        ],
        string="Modo RADIAN",
        default='manual',
        help="Controla cuándo se generan los eventos RADIAN:\n"
             "• Desactivado: No se generan eventos.\n"
             "• Solo facturas marcadas: El usuario decide qué "
             "facturas tienen vocación de circulación.\n"
             "• Todas las facturas a crédito: Se generan eventos "
             "automáticamente para toda factura con plazo de pago.",
    )

    # -----------------------------------------------------------------
    # CONTINGENCY CONFIGURATION (multi-tenant)
    # -----------------------------------------------------------------

    insotech_contingency_retries = fields.Integer(
        string="Reintentos de envío DIAN",
        default=4,
        help="Número total de intentos antes de activar "
             "contingencia Tipo 04 (protocolo DIAN: 4).",
    )
    insotech_contingency_interval = fields.Integer(
        string="Intervalo entre reintentos (seg)",
        default=20,
        help="Segundos de espera entre cada reintento "
             "(protocolo DIAN: 20 segundos).",
    )
    insotech_contingency_deadline_hours = fields.Integer(
        string="Horas límite retransmisión",
        default=48,
        help="Horas máximas para retransmitir facturas en "
             "contingencia una vez DIAN se recupere "
             "(protocolo DIAN: 48 horas).",
    )
    insotech_radian_tacit_days = fields.Integer(
        string="Días hábiles aceptación tácita",
        default=3,
        help="Días hábiles para aceptación tácita RADIAN "
             "(Proyecto de Decreto MinCIT: 3 días).",
    )

    @api.depends('insotech_dian_cert_file', 'insotech_dian_cert_password')
    def _compute_cert_expiry_date(self) -> None:
        """Extracts the expiry date from the .p12 certificate."""
        for company in self:
            company.insotech_dian_cert_expiry_date = False
            if not company.insotech_dian_cert_file:
                continue
            if not company.insotech_dian_cert_password:
                continue
            try:
                p12_bytes = base64.b64decode(company.insotech_dian_cert_file)
                from cryptography.hazmat.primitives.serialization import pkcs12
                _, certificate, _ = pkcs12.load_key_and_certificates(
                    p12_bytes,
                    company.insotech_dian_cert_password.encode(),
                )
                if certificate:
                    # not_valid_after_utc added in cryptography 42.0
                    # fallback to not_valid_after for older versions
                    expiry = getattr(
                        certificate, 'not_valid_after_utc',
                        certificate.not_valid_after,
                    )
                    company.insotech_dian_cert_expiry_date = expiry.date()
            except Exception as e:
                _logger.debug(
                    "Insotech: Could not parse certificate "
                    "expiry for company %s: %s",
                    company.name, e,
                )

    @api.depends('insotech_dian_cert_expiry_date')
    def _compute_cert_days_remaining(self) -> None:
        """Calculates days remaining until certificate expiry."""
        today = fields.Date.context_today(self)
        for company in self:
            if company.insotech_dian_cert_expiry_date:
                delta = company.insotech_dian_cert_expiry_date - today
                company.insotech_dian_cert_days_remaining = delta.days
            else:
                company.insotech_dian_cert_days_remaining = -1

    @api.model
    def _cron_check_certificate_expiry(self) -> None:
        """CRON: Check certificate expiry for all companies.

        Runs daily. Posts an activity on the company and logs:
        - CRITICAL: <= 7 days remaining
        - WARNING: <= 30 days remaining
        - NOTICE: <= 90 days remaining
        """
        companies = self.search([
            ('insotech_dian_cert_file', '!=', False),
            ('insotech_dian_cert_password', '!=', False),
        ])
        today = fields.Date.context_today(self)

        for company in companies:
            # Force recompute
            company._compute_cert_expiry_date()
            expiry = company.insotech_dian_cert_expiry_date
            if not expiry:
                continue

            days = (expiry - today).days

            if days <= 0:
                level = 'BLOQUEADO'
                emoji = '🔴'
                msg = (
                    f"{emoji} CERTIFICADO DIAN VENCIDO "
                    f"(venció el {expiry}). La facturación "
                    f"electrónica está BLOQUEADA. "
                    f"Renueve el certificado inmediatamente."
                )
            elif days <= _CERT_ALERT_CRITICAL:
                level = 'CRÍTICO'
                emoji = '🔴'
                msg = (
                    f"{emoji} ALERTA CRÍTICA: Certificado DIAN "
                    f"vence en {days} días ({expiry}). "
                    f"Renueve URGENTEMENTE."
                )
            elif days <= _CERT_ALERT_WARNING:
                level = 'ADVERTENCIA'
                emoji = '🟡'
                msg = (
                    f"{emoji} Certificado DIAN vence en "
                    f"{days} días ({expiry}). "
                    f"Programe la renovación."
                )
            elif days <= _CERT_ALERT_NOTICE:
                level = 'AVISO'
                emoji = '🟢'
                msg = (
                    f"{emoji} Certificado DIAN vence en "
                    f"{days} días ({expiry}). "
                    f"Considere programar la renovación."
                )
            else:
                # More than 90 days — no alert needed
                continue

            _logger.warning(
                "Insotech [%s] Cert Expiry %s: %s — %s",
                level, company.name, expiry, msg,
            )

            # Post as a note in the company chatter
            try:
                company.message_post(
                    body=msg,
                    subject=f"Certificado DIAN — {level}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
            except Exception as e:
                _logger.debug(
                    "Insotech: Could not post cert alert "
                    "to chatter for %s: %s",
                    company.name, e,
                )

    def _register_hook(self) -> None:
        """Ensure product.product_category_goods XML ID exists.

        Runs on every server start. Prevents ValueError in
        l10n_co_dian's certification process on databases
        without demo data.
        """
        super()._register_hook()
        try:
            self.env['ir.model.data']._xmlid_to_res_model_res_id(
                'product.product_category_goods',
                raise_if_not_found=True,
            )
        except ValueError:
            Category = self.env['product.category']
            category = Category.search(
                [('parent_id', '=', False)],
                limit=1, order='id ASC',
            )
            if not category:
                category = Category.search(
                    [], limit=1, order='id ASC',
                )
            if category:
                self.env['ir.model.data'].create({
                    'module': 'product',
                    'name': 'product_category_goods',
                    'model': 'product.category',
                    'res_id': category.id,
                    'noupdate': True,
                })
                _logger.info(
                    "Insotech: Created product.product_category_goods "
                    "→ '%s' (id=%s)", category.name, category.id,
                )
            else:
                _logger.warning(
                    "Insotech: No product categories found. "
                    "Cannot create product.product_category_goods.",
                )
