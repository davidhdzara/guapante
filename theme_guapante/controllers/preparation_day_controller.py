# -*- coding: utf-8 -*-
import io
import logging
import xlsxwriter
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PreparationDayExport(http.Controller):

    @http.route('/web/guapante/preparation_day/<int:session_id>/export_excel', type='http', auth='user')
    def export_preparation_excel(self, session_id, **kwargs):
        """Genera y descarga el consolidado de compras en formato Excel plano (sin colores)."""
        session = request.env['guapante.preparation.day'].sudo().browse(session_id)
        if not session.exists():
            return request.not_found()

        # Agrupar las líneas de preparación
        demand = {}
        for line in session.line_ids:
            pid = line.product_product_id.id
            if not pid:
                continue
            desc = line.product_description or ''
            uom_mode = line.uom_mode or 'unit'
            pkg_name = line.packaging_name or ''

            key = (pid, desc, uom_mode, pkg_name)
            if key not in demand:
                demand[key] = {
                    'product_id': line.product_product_id,
                    'description': desc,
                    'uom_mode': uom_mode,
                    'packaging_name': pkg_name,
                    'total_kg': 0.0,
                    'lines': [],
                }
            demand[key]['total_kg'] += line.estimated_kg
            demand[key]['lines'].append(line)

        # Calcular cantidades visuales (pedidas por el cliente)
        weight_categ = request.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False).sudo()
        for key, data in demand.items():
            total_visual_qty = 0.0
            clients_summary = {}
            for line in data['lines']:
                cust_name = line.main_customer_name or 'Sin Cliente'
                line_visual_qty = 0.0

                sol = line.sale_line_id
                if not sol:
                    try:
                        line_visual_qty = float(line.customer_qty_display)
                    except (ValueError, TypeError):
                        pass
                else:
                    qty = sol.product_uom_qty
                    mode = sol.uom_mode or 'unit'
                    is_weight = weight_categ and sol.product_id.uom_id.category_id == weight_categ

                    if mode == 'g':
                        line_visual_qty = qty * 1000.0
                    elif mode == 'kg':
                        line_visual_qty = qty
                    else: # unit
                        if is_weight:
                            packaging = sol.product_packaging_id
                            if not packaging:
                                packaging = sol.product_id.packaging_ids.filtered(
                                    lambda p: p.sales and p.qty > 0
                                )[:1]
                            if packaging and packaging.qty > 0:
                                line_visual_qty = round(qty / packaging.qty)
                            else:
                                line_visual_qty = qty
                        else:
                            line_visual_qty = qty

                total_visual_qty += line_visual_qty
                if cust_name not in clients_summary:
                    clients_summary[cust_name] = 0.0
                clients_summary[cust_name] += line_visual_qty

            data['total_visual_qty'] = total_visual_qty
            
            client_strings = []
            for client, c_qty in clients_summary.items():
                c_qty_formatted = str(int(c_qty)) if c_qty == int(c_qty) else str(round(c_qty, 2))
                client_strings.append(f"{client} ({c_qty_formatted})")
            data['clients_str'] = ", ".join(client_strings)

        # Crear archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Demanda de Compras')

        # Asegurar líneas de cuadrícula visibles
        worksheet.hide_gridlines(0) # 0 = mostrar cuadrícula

        # Formatos planos (Negro / Blanco / Gris estándar para bordes)
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#FFFFFF',
            'font_name': 'Arial',
            'font_size': 10,
        })

        bold_title_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 11,
        })

        cell_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'border': 1,
            'align': 'left',
        })

        cell_center_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'border': 1,
            'align': 'center',
        })

        number_format_kg = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'border': 1,
            'num_format': '#,##0.000',
            'align': 'right',
        })

        number_format_qty = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right',
        })

        # Escribir título
        title_str = f"CONSOLIDADO DE COMPRAS - PREPARACIÓN DEL DÍA: {session.date.strftime('%Y-%m-%d')}"
        worksheet.write('A1', title_str, bold_title_format)

        # Encabezados de tabla
        headers = [
            'Producto', 
            'Especificaciones / Atributos', 
            'Cantidad Pedida (Cliente)', 
            'UdM Cliente', 
            'Total en Kilogramos', 
            'Disponible en Bodega (Kg)', 
            'Cantidad de Pedidos',
            'Clientes (Detalle)'
        ]
        
        for col_num, header in enumerate(headers):
            worksheet.write(2, col_num, header, header_format)

        # Ordenar datos: Primero por nombre de producto, luego por especificación
        sorted_demand = sorted(demand.values(), key=lambda x: (x['product_id'].name or '', x['description'] or ''))

        # Rellenar datos
        row_idx = 3
        for data in sorted_demand:
            product = data['product_id']
            desc = data['description']
            pkg = data['packaging_name']
            
            spec = desc
            if pkg and pkg not in desc:
                spec = f"{desc} ({pkg})"

            uom_mode = data['uom_mode']
            if uom_mode == 'unit':
                uom_label = 'unidades'
            elif uom_mode == 'g':
                uom_label = 'g'
            else:
                uom_label = 'kg'

            worksheet.write(row_idx, 0, product.name or '', cell_format)
            worksheet.write(row_idx, 1, spec or '', cell_format)
            worksheet.write(row_idx, 2, data['total_visual_qty'], number_format_qty)
            worksheet.write(row_idx, 3, uom_label, cell_center_format)
            worksheet.write(row_idx, 4, data['total_kg'], number_format_kg)
            # virtual_available del producto
            worksheet.write(row_idx, 5, product.virtual_available, number_format_kg)
            # Cantidad de órdenes únicas
            order_count = len(set(line.sale_order_id.id for line in data['lines']))
            worksheet.write(row_idx, 6, order_count, cell_center_format)
            worksheet.write(row_idx, 7, data.get('clients_str', ''), cell_format)
            
            row_idx += 1

        # Ajustar ancho de las columnas automáticamente al contenido
        col_widths = [len(h) for h in headers]
        for data in sorted_demand:
            product_name = data['product_id'].name or ''
            desc = data['description']
            pkg = data['packaging_name']
            spec = f"{desc} ({pkg})" if pkg and pkg not in desc else desc

            col_widths[0] = max(col_widths[0], len(product_name))
            col_widths[1] = max(col_widths[1], len(spec))
            col_widths[2] = max(col_widths[2], len(str(round(data['total_visual_qty'], 2))))
            col_widths[3] = max(col_widths[3], 10) # 'unidades' o 'kg'
            col_widths[4] = max(col_widths[4], len(str(round(data['total_kg'], 3))))
            col_widths[5] = max(col_widths[5], len(str(round(data['product_id'].virtual_available, 3))))
            col_widths[6] = max(col_widths[6], 15)
            col_widths[7] = max(col_widths[7], len(data.get('clients_str', '')))

        for col_num, width in enumerate(col_widths):
            worksheet.set_column(col_num, col_num, width + 3)

        workbook.close()
        output.seek(0)
        excel_data = output.read()

        file_name = f"Compras_{session.date.strftime('%Y%m%d')}.xlsx"
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename="{file_name}"'),
            ('Content-Length', len(excel_data)),
        ]
        return request.make_response(excel_data, headers=headers)
