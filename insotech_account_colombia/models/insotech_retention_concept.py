from odoo import models, fields


class InsotechRetentionConcept(models.Model):
    _name = 'insotech.retention.concept'
    _description = 'Conceptos de Retención Inteligentes'
    _order = 'type, name'

    name = fields.Char(
        string='Nombre del Concepto',
        required=True,
        help='Ej. Retención Compras Agrícolas',
    )
    type = fields.Selection(
        selection=[
            ('retefuente', 'Retención en la Fuente'),
            ('reteica', 'ReteICA'),
            ('reteiva', 'ReteIVA'),
            ('parafiscal', 'Parafiscal'),
        ],
        string='Tipo de Retención',
        required=True,
    )
    direction = fields.Selection(
        selection=[
            ('sale', 'Ventas (nos retienen)'),
            ('purchase', 'Compras (retenemos)'),
            ('both', 'Ambos'),
        ],
        string='Dirección',
        default='sale',
        required=True,
    )
    city_name = fields.Char(
        string='Municipio (ICA)',
        help='Opcional: Si es ReteICA, especifica la ciudad',
    )

    base_uvt = fields.Float(
        string='Base Mínima (UVT)',
        required=True,
        default=0.0,
        help='Tope mínimo en UVT para que aplique la retención',
    )
    percentage = fields.Float(
        string='Porcentaje (%)',
        required=True,
        digits=(5, 3),
        help='Ej. 1.5 para 1.5%%',
    )

    account_id = fields.Many2one(
        'account.account',
        string='Cuenta PUC (Ventas)',
        required=True,
        domain=[('deprecated', '=', False)],
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Venta',
        domain=[('type_tax_use', '=', 'sale')],
        help='Impuesto negativo de venta equivalente',
    )
    purchase_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Compra (a inyectar)',
        domain=[('type_tax_use', '=', 'purchase')],
        help='Impuesto negativo que se inyecta en facturas de proveedor',
    )

    active = fields.Boolean(default=True)

    @api.model
    def init_default_concepts(self):
        """
        Crea o actualiza los Conceptos de Retención por defecto, e inyecta los Impuestos
        de compra (account.tax) si no existen, vinculándolos automáticamente a las cuentas PUC.
        Diseñado para ejecutarse a través de una Acción de Servidor.
        """
        company = self.env.company
        account_model = self.env['account.account']
        tax_model = self.env['account.tax']
        
        # (Nombre Corto, Tipo, Dirección, Base UVT, %, Cuenta PUC)
        # Nota: Por defecto, si el tipo es diferente a retefuente venta, 
        # intentaremos crear un impuesto de compra si es compras o ambos.
        default_concepts = [
            ('Rte Paraf Asohofrucol', 'parafiscal', 'both', 0.0, 1.0, '52155001'),
            ('Rte Paraf Cereales', 'parafiscal', 'both', 0.0, 1.0, '52155005'),
            ('Rte Paraf Fedepapa', 'parafiscal', 'both', 0.0, 1.0, '52155003'),
            ('Rte Paraf Leguminosas', 'parafiscal', 'both', 0.0, 1.0, '52155007'),
            ('Rte Paraf Soya', 'parafiscal', 'both', 0.0, 1.0, '52155009'),
            
            ('Autorretención Especial', 'retefuente', 'sale', 0.0, 1.2, '13551519'),
            ('RteFte General (1%)', 'retefuente', 'sale', 27.0, 1.0, '13551517'),
            ('RteFte No Producidos', 'retefuente', 'sale', 70.0, 1.5, '13551520'),
            ('RteFte Honorarios (10%)', 'retefuente', 'sale', 4.0, 10.0, '13551507'),
            ('RteFte Honorarios (11%)', 'retefuente', 'sale', 4.0, 11.0, '13551509'),
            ('RteFte Servicios (2%)', 'retefuente', 'sale', 27.0, 2.0, '13551515'),
            ('RteFte Compras', 'retefuente', 'sale', 27.0, 2.5, '13551501'),
            ('RteFte Arrendamiento', 'retefuente', 'both', 27.0, 3.5, '13551513'),
            ('RteFte Servicios (4%)', 'retefuente', 'sale', 27.0, 4.0, '13551503'),
            ('RteFte Servicios (6%)', 'retefuente', 'sale', 27.0, 6.0, '13551505'),
            ('RteFte General (7%)', 'retefuente', 'sale', 27.0, 7.0, '13551511'),
            ('RteFte Agrícola', 'retefuente', 'both', 92.0, 1.5, '13551520'),
            
            ('RteICA Alimentos', 'reteica', 'sale', 0.0, 0.414, '13551001'),
            ('RteICA Comercio', 'reteica', 'sale', 0.0, 0.966, '13551001'),
            
            ('RteIVA (15% s/ 19%)', 'reteiva', 'sale', 27.0, 15.0, '135517'),
            ('RteIVA (15% s/ 5%)', 'reteiva', 'sale', 27.0, 15.0, '135517'),
        ]

        created_count = 0
        updated_count = 0

        for name, r_type, direction, uvt, pct, acc_code in default_concepts:
            # 1. Buscar la cuenta PUC en la compañía actual
            account = account_model.search([
                ('code', '=', acc_code), 
                ('company_id', '=', company.id),
                ('deprecated', '=', False)
            ], limit=1)

            if not account:
                continue

            # 2. Gestionar el Impuesto de Compra (Solo si aplica para compras)
            purchase_tax_id = False
            if direction in ('purchase', 'both'):
                # Verificamos si ya existe el impuesto
                tax = tax_model.search([
                    ('name', '=', name),
                    ('type_tax_use', '=', 'purchase'),
                    ('company_id', '=', company.id)
                ], limit=1)

                if not tax:
                    # Crear el impuesto con líneas de repartición (Base y Tax con la cuenta PUC)
                    tax_vals = {
                        'name': name,
                        'amount_type': 'percent',
                        'amount': -abs(pct),
                        'type_tax_use': 'purchase',
                        'company_id': company.id,
                        # Para retenciones se suele omitir en base imponible adicional
                        'include_base_amount': False, 
                    }
                    tax = tax_model.create(tax_vals)
                    # Asignar la cuenta PUC a la línea de tipo 'tax'
                    for rep_line in tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids:
                        if rep_line.repartition_type == 'tax':
                            rep_line.account_id = account.id

                purchase_tax_id = tax.id

            # 3. Crear o actualizar el Concepto
            existing = self.search([('name', '=', name)], limit=1)
            vals = {
                'name': name,
                'type': r_type,
                'direction': direction,
                'base_uvt': uvt,
                'percentage': pct,
                'account_id': account.id,
                'purchase_tax_id': purchase_tax_id,
                'active': True
            }

            if existing:
                existing.write(vals)
                updated_count += 1
            else:
                self.create(vals)
                created_count += 1

        # Mostrar notificación al usuario
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Conceptos Inicializados',
                'message': f'Se crearon {created_count} y actualizaron {updated_count} conceptos e impuestos.',
                'type': 'success',
                'sticky': False,
            }
        }
