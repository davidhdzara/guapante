# Pricelist: Desbloqueo en Órdenes Confirmadas y Botón Nativo "Update Prices"

**Fecha de Registro:** 2026-04-28
**Contexto del Problema:**
La dueña necesitaba cambiar listas de precios en órdenes confirmadas sin cancelar y re-confirmar. El 80% de las órdenes llegan por eCommerce ya confirmadas.

## 🚨 El Problema o Error

Odoo 18 bloquea el cambio de `pricelist_id` en órdenes confirmadas desde **dos capas**:

1. **Vista XML:** `readonly="state in ['cancel', 'sale']"` en el campo `pricelist_id`
2. **Python:** `sale.order.write()` línea 1018:
   ```python
   if 'pricelist_id' in vals and any(so.state == 'sale' for so in self):
       raise UserError(_("You cannot change the pricelist of a confirmed order !"))
   ```
3. **Botón nativo:** `invisible="not show_update_pricelist or state in ['sale', 'cancel']"` — el botón "Update Prices" se oculta en estado sale

## 🔍 Causa Raíz

Es un bloqueo intencional de Odoo para evitar que se cambien precios en órdenes ya comprometidas. Pero en el modelo de negocio de Guapante (eCommerce → confirmación automática → preparación), las órdenes siempre llegan confirmadas y la dueña necesita ajustar precios según el cliente.

## ✅ Solución Adoptada

### Python (`theme_guapante/models/sale_order.py`):

Override de `write()` que:
1. Detecta si se intenta cambiar `pricelist_id`
2. Separa órdenes confirmadas de las demás
3. **Safety check:** Si hay facturas emitidas (posted) → BLOQUEA con error claro
4. Strip `pricelist_id` de vals → llama `super().write()` sin él
5. Escribe pricelist directamente via `models.Model.write()` (bypass del check nativo)
6. Recalcula precios automáticamente

### Vista XML (`theme_guapante/views/sale_order_views.xml`):

```xml
<!-- Campo editable en state=sale -->
<xpath expr="//field[@name='pricelist_id']..." position="attributes">
    <attribute name="readonly">state == 'cancel'</attribute>
</xpath>

<!-- Botón "Update Prices" visible en state=sale -->
<xpath expr="//button[@name='action_update_prices']" position="attributes">
    <attribute name="invisible">not show_update_pricelist or state == 'cancel'</attribute>
</xpath>
```

### Flujo de la dueña:
1. Abre orden confirmada → campo pricelist desbloqueado
2. Cambia la lista → aparece botón "🔄 Update Prices" (nativo de Odoo)
3. Click → Odoo recalcula con `_recompute_prices()` (método nativo)
4. Si tiene factura emitida → error claro "debe anularlas primero"

## 💡 Buenas Prácticas / Cómo evitarlo

1. **Siempre verificar ambas capas** (Python + XML) al desbloquear un campo protegido.
2. **Usar `models.Model.write()`** para bypass limpio del `write()` de un modelo específico sin afectar la cadena de herencia completa.
3. **El método nativo `action_update_prices` + `_recompute_prices()` ya existe en v18** — no reinventar el recálculo de precios.
4. **Siempre agregar safety checks** al desbloquear restricciones: en este caso, bloquear si hay facturas posted.
