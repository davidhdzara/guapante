from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_co_portal_payslip_publication_policy = fields.Selection(
        selection=[('accepted', 'Solo aceptadas por DIAN'), ('finalized', 'Finalizadas')],
        string='Publicación de colillas en Portal', default='accepted', required=True,
        help='Aceptadas exige estado DIAN aceptado. Finalizadas permite estados done o paid.',
    )
    # These remain optional at installation. Issuance validates the complete trio.
    l10n_co_portal_certificate_signatory_name = fields.Char(string='Nombre firmante certificado')
    l10n_co_portal_certificate_signatory_title = fields.Char(string='Cargo firmante certificado')
    l10n_co_portal_certificate_signatory_signature = fields.Binary(
        string='Firma del firmante de certificados', attachment=True,
    )
