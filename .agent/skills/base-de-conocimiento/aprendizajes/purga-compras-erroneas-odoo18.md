# Purga Completa de Compras Erróneas en Odoo 18 (Producción)

**Fecha de Registro:** 2026-04-15
**Contexto del Problema:**
Se realizaron 16 órdenes de compra (P00010-P00025) erróneas en producción que generaron recepciones, movimientos de almacén, capas de valoración y asientos contables automáticos (STJ) que debían ser eliminados.

## 🚨 El Problema o Error
Las compras erróneas generaron un efecto cascada en múltiples módulos:
- 16 `purchase.order` con líneas
- 27 `stock.picking` (recepciones WH/IN + almacenamiento WH/STOR) en estado `done`
- 60 `stock.move` vinculados a compras
- 50 `stock.valuation.layer` (capas de valoración)
- 47 `account.move` (asientos STJ de valoración automática, estado `posted`)

## 🔍 Causa Raíz
Compras registradas erróneamente. No estaban vinculadas a facturas de proveedor (invoice_origin = N/A).

## ✅ Solución Adoptada

### Orden de ejecución (CRÍTICO respetar este orden):

**Fase 1: Revertir asientos contables (STJ)**
- NO se pueden borrar por la **Pista de Auditoría** (Audit Trail)
- Se usa el wizard `account.move.reversal` para crear contrasientos
- Los originales quedan intactos pero neutralizados

```python
from datetime import date
stj_moves = svl.mapped('account_move_id').filtered(lambda m: m.state == 'posted')
journals = stj_moves.mapped('journal_id')
for journal in journals:
    j_moves = stj_moves.filtered(lambda m: m.journal_id == journal)
    reversal = env['account.move.reversal'].with_context(
        active_model='account.move',
        active_ids=j_moves.ids,
    ).create({
        'reason': 'Purga compras erroneas',
        'date': date.today(),
        'journal_id': journal.id,
    })
    reversal.reverse_moves()
```

**Fase 2: Eliminar capas de valoración (SVL)**
- Limpiar `account_move_id` antes de borrar
```python
svl.sudo().write({'account_move_id': False})
svl.sudo().unlink()
```

**Fase 3: Eliminar Purchase Orders**
- Forzar estado `cancel` via SQL, luego `unlink()` via ORM
- Las líneas se borran en cascada
- `stock.move.purchase_line_id` pasa a NULL automáticamente (ondelete='set null')

```python
env.cr.execute("UPDATE purchase_order SET state = 'cancel' WHERE id IN %s", [tuple(pos.ids)])
env.invalidate_all()
pos.sudo().unlink()
```

**Fase 4 (opcional): Eliminar pickings y stock moves**
- Forzar estado `cancel` via SQL en: stock_move_line → stock_move → stock_picking
- Luego `unlink()` via ORM en el mismo orden
- Si quedan pickings huérfanos (devoluciones de pickings eliminados), usar SQL directo:

```python
env.cr.execute("DELETE FROM stock_move_line WHERE id IN %s", [tuple(ml_ids)])
env.cr.execute("DELETE FROM stock_move WHERE id IN %s", [tuple(move_ids)])
env.cr.execute("DELETE FROM stock_picking WHERE id = %s", [pick_id])
```

## 💡 Buenas Prácticas / Cómo evitarlo

1. **SIEMPRE hacer backup** antes de ejecutar en producción.
2. **NO hacer `env.cr.commit()` hasta verificar** que todas las fases completaron sin errores.
3. **Respetar el orden de eliminación**: Contabilidad → Valoración → Stock → Compras.
4. **Pista de Auditoría**: NUNCA intentar borrar `account.move` posted. Siempre revertir con `account.move.reversal`.
5. **Pickings en `done`**: No se pueden cancelar via ORM. Usar SQL para forzar `state = 'cancel'`, luego ORM para `unlink()`.
6. **Error `MissingError` post-invalidate**: Si `env.invalidate_all()` causa MissingError al hacer `unlink()`, usar SQL directo (`DELETE FROM`) en su lugar.
7. **Verificar vínculos PO ↔ Facturas**: Si las POs tienen facturas vinculadas, el tratamiento es diferente. Verificar con `po.invoice_ids`.
8. **Pickings huérfanos**: Después de eliminar pickings de compras, verificar si quedaron devoluciones (`Devolución de WH/STOR/xxxx`) en estado `waiting` que ya nunca se completarán.
