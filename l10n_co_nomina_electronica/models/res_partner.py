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

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Maestro de terceros de seguridad social y parafiscales (EPS, AFP, ARL,
    # CCF, SENA, ICBF, DIAN...). Una sola fuente por dato: el codigo PILA
    # vive en el contacto y el resto del modulo lo deriva de aqui.
    l10n_co_entity_type = fields.Selection(
        selection=[
            ('eps', 'EPS'),
            ('afp', 'AFP / Fondo de Pensiones'),
            ('arl', 'ARL'),
            ('ccf', 'Caja de Compensación Familiar'),
            ('sena', 'SENA'),
            ('icbf', 'ICBF'),
            ('dian', 'DIAN'),
            ('other', 'Otra entidad (sindicato, cooperativa, fondo, etc.)'),
        ],
        string='Tipo de Entidad (Nómina)',
        help='Clasifica el contacto como entidad a la que la nómina paga o '
             'retiene. Permite filtrar el contacto en los campos de EPS, '
             'AFP, ARL, caja, etc.',
    )
    l10n_co_pila_entity_code = fields.Char(
        string='Código PILA',
        help='Código de la administradora según la tabla PILA (ej: 14-11 '
             'para ARL). El módulo lo usa en la planilla PILA.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'vat' in vals:
            empleados = self.env['hr.employee'].sudo().search([
                ('work_contact_id', 'in', self.ids),
            ])
            for empleado in empleados._ne_solo_colombia():
                partner_vat = empleado.work_contact_id.vat
                if partner_vat and empleado.identification_id != partner_vat:
                    empleado.identification_id = partner_vat
        return res
