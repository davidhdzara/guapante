# Cancelación Forzada de Pedidos con Movimientos Done en Odoo.sh

**Fecha de Registro:** 2026-04-06

**Contexto del Problema:**
En el proyecto Guapante (Odoo 18), se requería cancelar el pedido de venta **S00296**. Sin embargo, el pedido tenía múltiples transferencias de inventario (`stock.picking`), una de las cuales era una devolución que ya figuraba en estado **"Hecho" (Done)**.

## 🚨 El Problema o Error
Odoo impide nativamente la cancelación de un Pedido de Venta si posee movimientos de stock bloqueados en estado `done`. Al intentar cancelar desde la interfaz, el sistema arroja un error prohibiendo la acción para proteger la integridad del inventario. 

En este caso particular, el flujo era complejo:
- Un picking de salida parcialmente procesado.
- Una devolución ya confirmada (estado `done`) que compensaba parte de la salida.
- El botón de cancelación del SO estaba inhabilitado o arrojaba error.

## 🔍 Causa Raíz
La limitación técnica reside en el método `action_cancel()` de los modelos `sale.order` y `stock.picking`. Una vez que un movimiento alcanza el estado `done`, el flujo contable y de inventario se cierra. Odoo no permite "echar atrás" un estado `done` por ORM estándar para evitar descuadres entre los movimientos (`stock.move`) y las existencias físicas (`stock.quant`).

## ✅ Solución Adoptada
Se utilizó el **Odoo Shell** para realizar una intervención de bajo nivel mediante SQL (`env.cr.execute`). Esto permite saltar las validaciones del `write()` del ORM y forzar el estado de los registros.

**Snippet de la Solución:**

```python
# Identificar pedido y sus componentes
order = env['sale.order'].search([('name', '=', 'S00296')])
pickings = order.picking_ids
moves = pickings.move_ids
move_lines = moves.move_line_ids

# 1. Forzar estados a 'cancel' en DB
if move_lines:
    env.cr.execute("UPDATE stock_move_line SET state = 'cancel' WHERE id IN %s", (tuple(move_lines.ids),))
if moves:
    env.cr.execute("UPDATE stock_move SET state = 'cancel' WHERE id IN %s", (tuple(moves.ids),))
if pickings:
    env.cr.execute("UPDATE stock_picking SET state = 'cancel' WHERE id IN %s", (tuple(pickings.ids),))

# 2. Resetear entregas en el SO
for line in order.order_line:
    line.write({'qty_delivered': 0.0})

# 3. Ejecutar cancelación del pedido
order.action_cancel()
env.cr.commit()
```

## 💡 Buenas Prácticas / Cómo evitarlo
- **Verificación de Inventarios**: Antes de forzar una cancelación, siempre hay que auditar si las cantidades "Hechas" de salida tienen una contraparte "Hecha" de entrada (Devolución). Si el balance es neto 0, la cancelación forzada es segura.
- **Reseteo de `qty_delivered`**: Es vital limpiar el campo `qty_delivered` en las líneas del pedido (`sale.order.line`) antes de cancelar, para que el historial del producto no quede con entregas fantasma.
- **No abusar de SQL**: Esta técnica debe reservarse para casos de bloqueo terminal donde el flujo estándar de Odoo no permita retroceder y se haya validado manualmente el inventario físico.
