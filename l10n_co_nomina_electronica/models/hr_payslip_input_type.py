# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Tipo de novedad: unidad de la cantidad (E11 pieza 2a, .287, doc 71c §7).

El nativo ya distingue una novedad en cantidad de una en pesos con ``is_quantity`` (``hr_payroll/models/hr_payslip_input_type.py:19``); no
distingue días de horas. Aquí se agrega solo esa unidad, y solo cuando ``is_quantity``. Hasta .286 los tipos del módulo llevaban la unidad en
el nombre («(días)»); la siembra de abajo no cambia nombres ni toca lo que el usuario ya configuró."""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    l10n_co_ne_unidad = fields.Selection(
        selection=[('dias', 'Días'), ('horas', 'Horas')],
        string='Unidad de la cantidad',
        help='Solo para novedades que son una cantidad («Es cantidad?»): indica si la cantidad son días u horas. Se muestra en «Conceptos de '
             'pago». Vacío en las novedades que son un valor en pesos.')

    # Siembra inicial por código de tipo (los 7 de horas extra y recargos son horas; los 7 con «(días)» en el nombre son días). Solo escribe
    # donde la unidad está vacía: no pisa lo que configure el usuario. Los registros del módulo son ``noupdate``, por eso se siembra con una
    # función (igual que ``hr.salary.rule._l10n_co_cargar_origen_tercero``) y no con campos en el XML.
    _L10N_CO_UNIDAD_POR_CODIGO = {
        'CO_HED': 'horas', 'CO_HEN': 'horas', 'CO_HRN': 'horas', 'CO_HEDDF': 'horas', 'CO_HENDF': 'horas', 'CO_HRDDF': 'horas',
        'CO_HRNDF': 'horas',
        'CO_INC_COMUN': 'dias', 'CO_INC_LABORAL': 'dias', 'CO_LIC_MAT': 'dias', 'CO_LIC_PAT': 'dias', 'CO_LIC_REM': 'dias',
        'CO_LIC_NR': 'dias', 'CO_VAC': 'dias',
    }

    @api.constrains('l10n_co_ne_unidad', 'is_quantity')
    def _check_l10n_co_ne_unidad_con_cantidad(self):
        for tipo in self:
            if tipo.l10n_co_ne_unidad and not tipo.is_quantity:
                raise ValidationError(_(
                    'El tipo de novedad "%(tipo)s" tiene unidad (días u horas) pero no está marcado como cantidad. Marque «Es cantidad?» o '
                    'vacíe la unidad.', tipo=tipo.display_name))

    @api.onchange('is_quantity')
    def _onchange_is_quantity_l10n_co_ne_unidad(self):
        if not self.is_quantity:
            self.l10n_co_ne_unidad = False

    @api.model
    def _l10n_co_cargar_unidad(self):
        """Marca como cantidad y asigna su unidad a los tipos del módulo (por código) que aún no tienen unidad."""
        propios = self.env['ir.model.data'].search(
            [('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.payslip.input.type')]).mapped('res_id')
        for codigo, unidad in self._L10N_CO_UNIDAD_POR_CODIGO.items():
            self.with_context(active_test=False).search(
                [('id', 'in', propios), ('code', '=', codigo), ('l10n_co_ne_unidad', '=', False)]
            ).write({'is_quantity': True, 'l10n_co_ne_unidad': unidad})
        return True

    # Tipos de novedad que dejaron de usarse porque su dato tiene otra fuente: xmlid -> motivo (H-F1-09: el apoyo del aprendiz es el sueldo del contrato).
    _NE_TIPOS_REEMPLAZADOS = ('l10n_co_nomina_electronica.input_co_apoyo_sost',)

    @api.model
    def _ne_retirar_tipos_reemplazados(self):
        """Archiva (no borra) los tipos de ``_NE_TIPOS_REEMPLAZADOS`` en cada actualización. El nativo no permite archivar un tipo con un ajuste salarial en curso
        (``hr_payslip_input_type.py:30-33``): en ese caso no se archiva y queda anotado en el log; el cálculo igual rechaza la novedad."""
        for xmlid in self._NE_TIPOS_REEMPLAZADOS:
            tipo = self.env.ref(xmlid, raise_if_not_found=False)
            if not tipo or not tipo.active:
                continue
            en_curso = self.env['hr.salary.attachment'].sudo().search_count([('other_input_type_id', '=', tipo.id), ('state', 'not in', ('close', 'cancel'))])
            if en_curso:
                _logger.warning('No se archiva el tipo de novedad %s: tiene %s ajuste(s) salarial(es) en curso.', xmlid, en_curso)
                continue
            tipo.active = False
        return True
