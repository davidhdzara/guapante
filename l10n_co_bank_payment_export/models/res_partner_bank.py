from odoo import fields, models


class ResPartnerBank(models.Model):
    """
    Extiende res.partner.bank con el tipo de cuenta colombiano.
    El campo acc_type no existe en Odoo estandar para Colombia;
    este modulo lo agrega para que el usuario lo configure
    directamente en la cuenta bancaria del proveedor o empleado.
    """
    _inherit = 'res.partner.bank'

    l10n_co_account_type = fields.Selection(
        selection=[
            ('CA', 'Cuenta de Ahorros'),
            ('CC', 'Cuenta Corriente'),
            ('DP', 'DaviPlata'),
            ('TP', 'Tarjeta Prepago Maestro'),
            ('DE', 'Depositos Electronicos'),
        ],
        string='Tipo de Cuenta (Colombia)',
        default='CA',
        help=(
            'Tipo de producto bancario requerido por los portales '
            'de pago masivo de bancos colombianos.\n'
            'CA: Cuenta de Ahorros\n'
            'CC: Cuenta Corriente\n'
            'DP: DaviPlata\n'
            'TP: Tarjeta Prepago Maestro\n'
            'DE: Depositos Electronicos'
        ),
    )
