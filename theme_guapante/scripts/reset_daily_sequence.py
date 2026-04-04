#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reset daily_sequence para todas las órdenes de una fecha específica.

Uso en Odoo.sh Shell:
    1. Abrir shell: odoo-bin shell -d <db_name>
    2. Copiar y pegar este script completo
    3. Confirmar que los registros son correctos antes de hacer commit

O ejecutar directamente pegando el contenido en la consola shell.
"""

from datetime import timedelta
from odoo import fields

# ══════════════════════════════════════════════════════
# CONFIGURAR LA FECHA AQUÍ ↓↓↓
# ══════════════════════════════════════════════════════
TARGET_DATE = '2026-04-04'  # Fecha de entrega del Preparation Day
# ══════════════════════════════════════════════════════

delivery_date = fields.Date.from_string(TARGET_DATE)
dt_start = fields.Datetime.to_datetime(delivery_date)
dt_end = fields.Datetime.to_datetime(delivery_date + timedelta(days=1))

print(f"\n{'='*60}")
print(f"  RESET daily_sequence para fecha: {TARGET_DATE}")
print(f"  Rango UTC: {dt_start} → {dt_end}")
print(f"{'='*60}\n")

# 1. Encontrar órdenes con pickings PICK (internal) en esa fecha
Pickings = env['stock.picking'].sudo().search([
    ('scheduled_date', '>=', dt_start),
    ('scheduled_date', '<', dt_end),
    ('picking_type_code', '=', 'internal'),
    ('sale_id', '!=', False),
])
Orders = Pickings.mapped('sale_id').filtered(lambda o: o.daily_sequence > 0)

print(f"  Órdenes encontradas con daily_sequence > 0: {len(Orders)}")
for order in Orders.sorted('daily_sequence'):
    print(f"    {order.name} | Caja #{order.daily_sequence} | Estado: {order.state}")

# 2. Reset de daily_sequence a 0
if Orders:
    Orders.sudo().write({'daily_sequence': 0})
    print(f"\n  ✅ {len(Orders)} órdenes reseteadas a daily_sequence = 0")
else:
    print("\n  ℹ️  No hay órdenes para resetear")

# 3. Reset del ir.sequence diario
cid = env.company.id
seq_code = f'guapante.daily.{cid}.{delivery_date.strftime("%Y%m%d")}'
IrSeq = env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
if IrSeq:
    IrSeq.write({'number_next': 1})
    print(f"  ✅ ir.sequence '{seq_code}' reseteado a number_next = 1")
else:
    print(f"  ℹ️  No existe ir.sequence con código '{seq_code}'")

# 4. Commit
env.cr.commit()
print(f"\n  ✅ COMMIT realizado. Todo listo.")
print(f"  → Ahora elimina la sesión del Preparation Day y crea una nueva.")
print(f"{'='*60}\n")
