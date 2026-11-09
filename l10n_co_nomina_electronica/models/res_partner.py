# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Sincroniza vat (Contactos) -> identification_id (hr.employee), dirección
opuesta a la de hr_employee.py::create()/write() (UX-02, 2026-10-11, decisión
de David: "que el contacto y el empleado queden sincronizados en el número").

Guard de igualdad en ambos lados (aquí y en hr_employee.py) para no generar
un ciclo de escrituras -- ver test_sin_bucle_infinito_entre_employee_y_partner
en tests/test_identificacion_sincronizada.py. Nunca propagar un valor vacío/
False: si alguien borra el vat del contacto, el número del empleado (del que
depende NumeroDocumento del XML) no debe desaparecer con él.
"""

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        res = super().write(vals)
        if 'vat' in vals:
            empleados = self.env['hr.employee'].sudo().search([
                ('work_contact_id', 'in', self.ids),
            ])
            for empleado in empleados:
                partner_vat = empleado.work_contact_id.vat
                if partner_vat and empleado.identification_id != partner_vat:
                    empleado.identification_id = partner_vat
        return res
