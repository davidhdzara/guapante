import base64
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.image import Image


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_co_portal_certificate_signatory_employee_id = fields.Many2one(
        'hr.employee', string='Responsable firmante de certificados',
        help='Empleado activo de esta compañía que firma las certificaciones laborales.',
        groups='hr.group_hr_manager',
    )
    l10n_co_portal_certificate_signatory_signature = fields.Binary(
        string='Firma gráfica del responsable', attachment=False,
        help='Imagen gráfica institucional; no sustituye una firma electrónica certificada.',
        groups='hr.group_hr_manager',
    )

    @api.constrains('l10n_co_portal_certificate_signatory_employee_id')
    def _check_portal_certificate_signatory_employee(self):
        for company in self:
            employee = company.l10n_co_portal_certificate_signatory_employee_id
            if employee and (not employee.active or employee.company_id != company):
                raise ValidationError(_(
                    'El responsable firmante debe ser un empleado activo de la misma compañía.'
                ))

    @api.constrains('l10n_co_portal_certificate_signatory_signature')
    def _check_portal_certificate_signature(self):
        allowed_formats = {'PNG', 'JPEG', 'GIF', 'WEBP'}
        maximum_size = 2 * 1024 * 1024
        maximum_pixels = 16 * 1024 * 1024
        for company in self:
            signature = company.l10n_co_portal_certificate_signatory_signature
            if not signature:
                continue
            try:
                raw = base64.b64decode(signature, validate=True)
            except (ValueError, TypeError):
                raise ValidationError(_('La firma debe ser una imagen válida.'))
            if not raw or len(raw) > maximum_size:
                raise ValidationError(_(
                    'La firma debe ser una imagen PNG, JPEG, GIF o WEBP de máximo 2 MB.'
                ))
            try:
                with Image.open(BytesIO(raw)) as image:
                    image_format = image.format
                    width, height = image.size
                    image.verify()
            except Exception as error:
                raise ValidationError(_('La firma debe ser una imagen válida.')) from error
            if image_format not in allowed_formats or width * height > maximum_pixels:
                raise ValidationError(_(
                    'La firma debe ser una imagen PNG, JPEG, GIF o WEBP de máximo 2 MB.'
                ))
