from odoo import fields, models


class ResBank(models.Model):
    """
    Extiende res.bank con el codigo ACH Colombia.
    Este codigo es el que exigen los portales bancarios colombianos
    en el campo 'Codigo del Banco' del archivo plano.
    El administrador puede configurarlo directamente desde
    Contabilidad > Configuracion > Bancos.
    """
    _inherit = 'res.bank'

    l10n_co_ach_code = fields.Char(
        string='Codigo ACH Colombia',
        size=6,
        help=(
            'Codigo del banco en el sistema ACH Colombia. '
            'Requerido para generar archivos planos bancarios. '
            'Ejemplo: Davivienda=051, Bancolombia=007, Bogota=001.'
        ),
    )
