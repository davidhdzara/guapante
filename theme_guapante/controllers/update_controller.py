from datetime import datetime
import re

file_path = '/home/david/odoo-projects/guapante/theme_guapante/controllers/customer_portal.py'

with open(file_path, 'r') as file:
    content = file.read()

# Replace month logic and add pager nums
month_names_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
month_injection = f"""
        # Pager offsets
        current_page = page
        items_per_page = self._items_per_page
        page_start_num = (current_page - 1) * items_per_page + 1 if invoice_count > 0 else 0
        page_end_num = min(current_page * items_per_page, invoice_count)
        
        mes_actual_es = month_names_es[today.month - 1]
        facturas_mes_str = f"Emisiones de {{mes_actual_es}} {{today.year}}"
"""

# Find where values.update is
target = "values.update({"
new_content = content.replace("values.update({", month_injection + "\n        values.update({\n            'page_start_num': page_start_num,\n            'page_end_num': page_end_num,\n            'invoice_count': invoice_count,\n            'facturas_mes_str': facturas_mes_str,")

with open(file_path, 'w') as file:
    file.write(new_content)
