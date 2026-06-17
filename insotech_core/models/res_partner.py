from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('city_id')
    def _onchange_city_id_zip(self):
        """
        Asigna automáticamente el código postal (zip) de la ciudad seleccionada
        al contacto, cumpliendo con la exigencia cbc:PostalZone de la DIAN.
        """
        for partner in self:
            if partner.city_id and hasattr(partner.city_id, 'zipcode') and partner.city_id.zipcode:
                partner.zip = partner.city_id.zipcode
