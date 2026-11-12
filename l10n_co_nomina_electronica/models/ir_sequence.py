# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError

# Códigos de las secuencias de documentos que se transmiten a la DIAN.
# La temporal (PRE-NOM) no se transmite y puede seguir siendo estándar.
_CODIGOS_NE_TRANSMITIDOS = ('l10n_co_nomina.electronica', 'l10n_co_nomina.ajuste')


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    @api.model
    def _l10n_co_ne_asegurar_sin_huecos(self):
        """H-023: pasa a ``no_gap`` las secuencias NE/NA ya existentes.

        Una secuencia ``standard`` usa ``nextval()`` de PostgreSQL, que no se revierte con
        el rollback: un fallo después de asignar el consecutivo dejaba un hueco. ``no_gap``
        guarda el contador en una fila y lo bloquea, así que sí se revierte.

        Al cambiar de implementación Odoo descarta la secuencia de PostgreSQL y toma el
        contador de la columna ``number_next``, que en una ``standard`` está desactualizada:
        se escribe el siguiente número REAL junto con el cambio y se verifica, para no
        reutilizar nunca un consecutivo ya emitido."""
        secuencias = self.sudo().search([
            ('code', 'in', _CODIGOS_NE_TRANSMITIDOS),
            ('implementation', '=', 'standard'),
        ])
        for seq in secuencias:
            siguiente = seq.number_next_actual
            seq.write({'implementation': 'no_gap', 'number_next': siguiente})
            seq.invalidate_recordset()
            if seq.number_next_actual != siguiente:
                raise UserError(_(
                    'La secuencia "%(name)s" no conservó su siguiente número al pasar a '
                    '"sin huecos" (esperado %(esperado)s, quedó %(quedo)s). Se aborta para '
                    'no repetir consecutivos.',
                    name=seq.name, esperado=siguiente, quedo=seq.number_next_actual))
        return secuencias
