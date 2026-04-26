from odoo import api, fields, models


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

    accumulate_monthly = fields.Boolean(
        string='Topes Acumulados Mensuales',
        default=False,
        help='Si se marca, el tope UVT se evalúa sumando todas las facturas del mes.',
    )

    active = fields.Boolean(default=True)

    category_id = fields.Many2one(
        'insotech.retention.category',
        string='Categoría',
        help='Permite agrupar las retenciones en el árbol visual (Ej. Municipales / Bogotá)',
    )
    
    # ─── PREPARACIÓN PARA MÓDULO EXÓGENA ───
    dian_format = fields.Char(
        string='Formato DIAN',
        help='Ej. 1001 (Pagos o abonos en cuenta y retenciones). Dejar listo para el módulo de Exógena.',
    )
    dian_concept_code = fields.Char(
        string='Concepto DIAN',
        help='Ej. 5019 (Honorarios). Se usará para la consolidación automática en Medios Magnéticos.',
    )

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
        
        category_model = self.env['insotech.retention.category']
        # 1. Nacionales y Parafiscales
        cat_nac = category_model.search([('name', '=', 'Nacionales')], limit=1) or category_model.create({'name': 'Nacionales'})
        cat_par = category_model.search([('name', '=', 'Parafiscales')], limit=1) or category_model.create({'name': 'Parafiscales'})
        
        # 2. Departamentales (Padres)
        cat_dep = category_model.search([('name', '=', 'Departamentales')], limit=1) or category_model.create({'name': 'Departamentales'})
        
        # 3. Departamentos (Hijos)
        cat_ant = category_model.search([('name', 'ilike', 'Antioquia'), ('parent_id', '=', cat_dep.id)], limit=1) or category_model.create({'name': 'Antioquia', 'parent_id': cat_dep.id})
        cat_cun = category_model.search([('name', 'ilike', 'Cundinamarca'), ('parent_id', '=', cat_dep.id)], limit=1) or category_model.create({'name': 'Cundinamarca', 'parent_id': cat_dep.id})
        cat_val = category_model.search([('name', 'ilike', 'Valle del Cauca'), ('parent_id', '=', cat_dep.id)], limit=1) or category_model.create({'name': 'Valle del Cauca', 'parent_id': cat_dep.id})

        # 4. Municipios (Nietos)
        cat_med = category_model.search([('name', 'ilike', 'Medellín'), ('parent_id', '=', cat_ant.id)], limit=1) or category_model.create({'name': 'Medellín', 'parent_id': cat_ant.id})
        cat_bog = category_model.search([('name', 'ilike', 'Bogot'), ('parent_id', '=', cat_cun.id)], limit=1) or category_model.create({'name': 'Bogotá D.C.', 'parent_id': cat_cun.id})
        cat_cal = category_model.search([('name', 'ilike', 'Cali'), ('parent_id', '=', cat_val.id)], limit=1) or category_model.create({'name': 'Cali', 'parent_id': cat_val.id})
        
        # (Nombre Corto, Tipo, Dirección, Base UVT, %, Cuenta PUC, Categoría, Formato DIAN, Concepto DIAN)
        # Nota: Por defecto, si el tipo es diferente a retefuente venta, 
        # intentaremos crear un impuesto de compra si es compras o ambos.
        default_concepts = [
            ('Rte Paraf Asohofrucol', 'parafiscal', 'both', 0.0, 1.0, '52155001', cat_par.id, '', ''),
            ('Rte Paraf Cereales', 'parafiscal', 'both', 0.0, 1.0, '52155005', cat_par.id, '', ''),
            ('Rte Paraf Fedepapa', 'parafiscal', 'both', 0.0, 1.0, '52155003', cat_par.id, '', ''),
            ('Rte Paraf Leguminosas', 'parafiscal', 'both', 0.0, 1.0, '52155007', cat_par.id, '', ''),
            ('Rte Paraf Soya', 'parafiscal', 'both', 0.0, 1.0, '52155009', cat_par.id, '', ''),
            
            ('Autorretención Especial', 'retefuente', 'sale', 0.0, 1.2, '13551519', cat_nac.id, '', ''),
            ('RteFte General (1%)', 'retefuente', 'sale', 27.0, 1.0, '13551517', cat_nac.id, '1001', '5002'),
            ('RteFte No Producidos', 'retefuente', 'sale', 70.0, 1.5, '13551520', cat_nac.id, '1001', '5002'),
            ('RteFte Honorarios (10%)', 'retefuente', 'sale', 4.0, 10.0, '13551507', cat_nac.id, '1001', '5019'),
            ('RteFte Honorarios (11%)', 'retefuente', 'sale', 4.0, 11.0, '13551509', cat_nac.id, '1001', '5019'),
            ('RteFte Servicios (2%)', 'retefuente', 'sale', 27.0, 2.0, '13551515', cat_nac.id, '1001', '5016'),
            ('RteFte Compras', 'retefuente', 'sale', 27.0, 2.5, '13551501', cat_nac.id, '1001', '5002'),
            ('RteFte Arrendamiento', 'retefuente', 'both', 27.0, 3.5, '13551513', cat_nac.id, '1001', '5013'),
            ('RteFte Servicios (4%)', 'retefuente', 'sale', 27.0, 4.0, '13551503', cat_nac.id, '1001', '5016'),
            ('RteFte Servicios (6%)', 'retefuente', 'sale', 27.0, 6.0, '13551505', cat_nac.id, '1001', '5016'),
            ('RteFte General (7%)', 'retefuente', 'sale', 27.0, 7.0, '13551511', cat_nac.id, '1001', '5002'),
            ('RteFte Agrícola', 'retefuente', 'both', 92.0, 1.5, '13551520', cat_nac.id, '1001', '5002'),
            
            ('RteICA Alimentos (Medellín)', 'reteica', 'sale', 0.0, 0.414, '13551001', cat_med.id, '1001', '5016'),
            ('RteICA Comercio (Bogotá D.C.)', 'reteica', 'sale', 0.0, 0.966, '13551001', cat_bog.id, '1001', '5002'),
            ('RteICA Servicios (Cali)', 'reteica', 'sale', 0.0, 0.69, '13551001', cat_cal.id, '1001', '5016'),
            
            ('RteIVA (15% s/ 19%)', 'reteiva', 'both', 27.0, 2.85, '135517', cat_nac.id, '1001', '5016'),
            ('RteIVA (15% s/ 5%)', 'reteiva', 'both', 27.0, 0.75, '135517', cat_nac.id, '1001', '5016'),
        ]

        created_count = 0
        updated_count = 0

        for name, r_type, direction, uvt, pct, acc_code, cat_id, fmt, code in default_concepts:
            # 1. Buscar la cuenta PUC en la compañía actual
            account = account_model.search([
                ('code', '=', acc_code), 
                ('company_ids', 'in', company.id),
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
                    if 'Autorretención' in name:
                        # Crear impuesto agrupado (positivo y negativo)
                        tax_pos = tax_model.create({
                            'name': f"{name} (Débito)",
                            'amount_type': 'percent',
                            'amount': abs(pct),
                            'type_tax_use': 'purchase',
                            'company_id': company.id,
                        })
                        for rep_line in tax_pos.invoice_repartition_line_ids + tax_pos.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = account.id
                                
                        # Buscar cuenta 236575 para el crédito
                        acc_cred = account_model.search([('code', 'like', '236575%'), ('company_ids', 'in', company.id)], limit=1)
                        tax_neg = tax_model.create({
                            'name': f"{name} (Crédito)",
                            'amount_type': 'percent',
                            'amount': -abs(pct),
                            'type_tax_use': 'purchase',
                            'company_id': company.id,
                        })
                        for rep_line in tax_neg.invoice_repartition_line_ids + tax_neg.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = acc_cred.id if acc_cred else account.id

                        tax_vals = {
                            'name': name,
                            'amount_type': 'group',
                            'amount': 0.0,
                            'type_tax_use': 'purchase',
                            'company_id': company.id,
                            'children_tax_ids': [(6, 0, [tax_pos.id, tax_neg.id])],
                        }
                        tax = tax_model.create(tax_vals)
                    else:
                        tax_vals = {
                            'name': name,
                            'amount_type': 'percent',
                            'amount': -abs(pct),
                            'type_tax_use': 'purchase',
                            'company_id': company.id,
                            'include_base_amount': False, 
                        }
                        tax = tax_model.create(tax_vals)
                        for rep_line in tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = account.id

                purchase_tax_id = tax.id

            # 3. Gestionar el Impuesto de Venta (Solo si aplica para ventas)
            tax_id_val = False
            if direction in ('sale', 'both'):
                # Verificamos si ya existe el impuesto
                tax = tax_model.search([
                    ('name', '=', name),
                    ('type_tax_use', '=', 'sale'),
                    ('company_id', '=', company.id)
                ], limit=1)

                if not tax:
                    # Crear el impuesto con líneas de repartición
                    if 'Autorretención' in name:
                        tax_pos = tax_model.create({
                            'name': f"{name} (Débito)",
                            'amount_type': 'percent',
                            'amount': abs(pct),
                            'type_tax_use': 'sale',
                            'company_id': company.id,
                        })
                        for rep_line in tax_pos.invoice_repartition_line_ids + tax_pos.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = account.id
                                
                        acc_cred = account_model.search([('code', 'like', '236575%'), ('company_ids', 'in', company.id)], limit=1)
                        tax_neg = tax_model.create({
                            'name': f"{name} (Crédito)",
                            'amount_type': 'percent',
                            'amount': -abs(pct),
                            'type_tax_use': 'sale',
                            'company_id': company.id,
                        })
                        for rep_line in tax_neg.invoice_repartition_line_ids + tax_neg.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = acc_cred.id if acc_cred else account.id

                        tax_vals = {
                            'name': name,
                            'amount_type': 'group',
                            'amount': 0.0,
                            'type_tax_use': 'sale',
                            'company_id': company.id,
                            'children_tax_ids': [(6, 0, [tax_pos.id, tax_neg.id])],
                        }
                        tax = tax_model.create(tax_vals)
                    else:
                        tax_vals = {
                            'name': name,
                            'amount_type': 'percent',
                            'amount': -abs(pct),
                            'type_tax_use': 'sale',
                            'company_id': company.id,
                            'include_base_amount': False, 
                        }
                        tax = tax_model.create(tax_vals)
                        for rep_line in tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids:
                            if rep_line.repartition_type == 'tax':
                                rep_line.account_id = account.id

                tax_id_val = tax.id

            # 4. Crear o actualizar el Concepto
            existing = self.search([('name', '=', name)], limit=1)
            vals = {
                'name': name,
                'type': r_type,
                'direction': direction,
                'base_uvt': uvt,
                'percentage': pct,
                'account_id': account.id,
                'purchase_tax_id': purchase_tax_id,
                'tax_id': tax_id_val,
                'active': True,
                'category_id': cat_id,
                'dian_format': fmt,
                'dian_concept_code': code,
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
