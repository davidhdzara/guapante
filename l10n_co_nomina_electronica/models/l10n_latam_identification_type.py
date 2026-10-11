# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Código DIAN de nómina electrónica para el tipo de documento de identidad.

UX-02 (2026-10-11, decisión de David + Tech Lead): el atributo TipoDocumento
del nodo <Trabajador> debe salir del tipo de identificación nativo del
contacto (l10n_latam.identification.type, ya usado en Contactos), no de un
Selection propio en hr.employee (ver hr_employee.py). l10n_co ya extiende
este modelo con l10n_co_document_code, pero ese es un slug textual (ej.
'national_citizen_id'), no el código numérico que exige la tabla 5.1 del
Anexo Técnico de Nómina Electrónica (Resolución 000013 de 2021) -- este
campo nuevo sí lo es, poblado por datos
(data/l10n_latam_identification_type_dian_code_data.xml), nunca por un
diccionario en Python (regla "nada hardcodeado").
"""

from odoo import fields, models


class L10nLatamIdentificationType(models.Model):
    _inherit = 'l10n_latam.identification.type'

    l10n_co_ne_dian_document_code = fields.Char(
        string='Código DIAN Nómina Electrónica',
        help='Código del tipo de documento según la tabla 5.1 del Anexo '
             'Técnico de Nómina Electrónica (Resolución 000013 de 2021). '
             'Vacío para tipos sin equivalente DIAN (ej. tipos genéricos de '
             'otros países LATAM, como "Cédula Extranjera" o "VAT") -- en '
             'ese caso, HrPayslip._ne_trabajador() falla con UserError, '
             'nunca inventa un código.',
    )
