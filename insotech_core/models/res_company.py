# -*- coding: utf-8 -*-
"""InSoTech Core — License management for res.company.

This file ONLY handles SaaS licensing fields and validation.
DIAN-specific fields live in insotech_dian_wizard/models/res_company.py.

Fields defined here:
- insotech_license_token          → Token de licencia SaaS
- insotech_usage_count            → Contador de usos (reset on ping)
- insotech_last_successful_ping   → Último ping exitoso al license server
"""
import logging
from datetime import timedelta

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'


    insotech_license_token = fields.Char(string="Token de Licencia Insotech")
    insotech_usage_count = fields.Integer(string="Contador de Uso Insotech", default=0, copy=False)
    insotech_last_successful_ping = fields.Datetime(string="Último Ping Exitoso Insotech", copy=False)

    def _validate_and_report_license(self) -> bool:
        self.ensure_one()

        token = self.insotech_license_token
        vat = self.vat
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        if not token:
            return False

        payload = {
            'token': token,
            'vat': vat,
            'url': url,
            'usage_count': self.insotech_usage_count,
            'reset_counter': True,
        }

        def _check_grace_period() -> bool:
            if self.insotech_last_successful_ping:
                limit_date = fields.Datetime.now() - timedelta(hours=72)
                if self.insotech_last_successful_ping >= limit_date:
                    _logger.warning("Insotech: Operando bajo período de gracia (último ping: %s)", self.insotech_last_successful_ping)
                    return True
            _logger.error("Insotech: Período de gracia expirado o nulo.")
            return False

        try:
            response = requests.post(
                'https://www.insotech.it/insotech/api/v1/verify',
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    status = data.get('status')
                    _logger.info(
                        "Insotech: License API response for %s — "
                        "status=%s, http=%d",
                        vat, status, response.status_code,
                    )
                    if status == 'active':
                        self.sudo().write({
                            'insotech_usage_count': 0,
                            'insotech_last_successful_ping': fields.Datetime.now()
                        })
                        return True
                    elif status in ['blocked', 'exhausted']:
                        _logger.error("Insotech: Licencia rechazada por la API (status: %s)", status)
                        return False
                    else:
                        _logger.warning("Insotech: Status desconocido '%s'. Evaluando gracia.", status)
                        return _check_grace_period()
                except ValueError:
                    _logger.warning("Insotech: Respuesta no válida (JSON inválido).")
                    return _check_grace_period()
            else:
                _logger.warning(
                    "Insotech: API respondió con código %s — body: %s",
                    response.status_code,
                    response.text[:200] if response.text else '(vacío)',
                )
                return _check_grace_period()
                
        except requests.exceptions.Timeout:
            _logger.warning("Insotech: Timeout de 10s al validar la licencia.")
            return _check_grace_period()
        except requests.exceptions.RequestException as e:
            _logger.warning("Insotech: Error de red al validar la licencia: %s", e)
            return _check_grace_period()
        except Exception as e:
            _logger.warning("Insotech: Error inesperado al validar la licencia: %s", e)
            return _check_grace_period()

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    insotech_license_token = fields.Char(
        related='company_id.insotech_license_token',
        readonly=False,
        string="Token de Licencia Insotech"
    )
