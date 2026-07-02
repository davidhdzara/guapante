from odoo import models, fields, api, tools

class SaleProfitAnalysis(models.Model):
    _name = 'sale.profit.analysis'
    _description = 'Análisis de Ganancia Diaria'
    _auto = False

    # Dimensiones
    date = fields.Date(string='Fecha', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría de Producto', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    user_id = fields.Many2one('res.users', string='Vendedor', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)

    # Métricas
    invoice_count = fields.Integer(string='# Facturas', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True)
    total_sales = fields.Float(string='Total Ventas (Ingreso)', readonly=True)
    total_cost = fields.Float(string='Total Compras (Costo)', readonly=True)
    profit = fields.Float(string='Ganancia del Día', readonly=True)
    margin_percent = fields.Float(string='Margen %', readonly=True, group_operator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    MIN(aml.id) AS id,
                    am.invoice_date AS date,
                    aml.product_id AS product_id,
                    pt.categ_id AS categ_id,
                    am.partner_id AS partner_id,
                    am.invoice_user_id AS user_id,
                    am.company_id AS company_id,
                    
                    COUNT(DISTINCT am.id) AS invoice_count,
                    
                    SUM(CASE 
                        WHEN am.move_type = 'out_invoice' THEN aml.quantity
                        WHEN am.move_type = 'out_refund'  THEN -aml.quantity
                        ELSE 0
                    END) AS quantity,

                    SUM(CASE 
                        WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal
                        WHEN am.move_type = 'out_refund'  THEN -am.price_subtotal -- aml.price_subtotal usually positive for refunds, so minus
                        ELSE 0
                    END) AS total_sales,
                    
                    SUM(CASE 
                        WHEN am.move_type = 'out_invoice' 
                            THEN COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity
                        WHEN am.move_type = 'out_refund'  
                            THEN -(COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity)
                        ELSE 0
                    END) AS total_cost,
                    
                    (SUM(CASE WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal ELSE -aml.price_subtotal END)
                    - SUM(CASE WHEN am.move_type = 'out_invoice' 
                          THEN COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity
                          ELSE -(COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity) 
                      END)) AS profit,
                      
                    -- Cálculo de Margen porcentual seguro
                    CASE WHEN SUM(CASE WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal ELSE -aml.price_subtotal END) != 0
                         THEN ((SUM(CASE WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal ELSE -aml.price_subtotal END)
                              - SUM(CASE WHEN am.move_type = 'out_invoice' 
                                    THEN COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity
                                    ELSE -(COALESCE(sol.purchase_price, CAST(pp.standard_price->>am.company_id::text AS numeric), 0) * aml.quantity) 
                                END)) / SUM(CASE WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal ELSE -aml.price_subtotal END)) * 100
                         ELSE 0
                    END AS margin_percent

                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN product_product pp ON pp.id = aml.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                LEFT JOIN sale_order_line sol ON sol.id = solir.order_line_id
                
                WHERE am.move_type IN ('out_invoice', 'out_refund')
                  AND am.state = 'posted'
                  AND aml.display_type = 'product'
                  
                GROUP BY
                    am.invoice_date,
                    aml.product_id,
                    pt.categ_id,
                    am.partner_id,
                    am.invoice_user_id,
                    am.company_id
            )
        """ % (self._table,))
