---
name: eCommerce Guapante (Odoo 18)
description: Skill obligatoria para agentes que desarrollen, debuggeen o modifiquen el módulo de tienda online (eCommerce) de Guapante en Odoo 18. Cubre la arquitectura personalizada de carrito, selección de UoM/embalaje, atributos de producto sin variantes y patrones seguros de desarrollo frontend/backend.
---

# eCommerce Guapante — Arquitectura y Guía de Desarrollo (Odoo 18)

Esta skill es **OBLIGATORIA** antes de modificar cualquier archivo relacionado con la tienda online de Guapante. El eCommerce tiene personalizaciones profundas que difieren del comportamiento nativo de Odoo 18.

---

## 1. Mapa de Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| `theme_guapante/static/src/js/unit_selector.js` | Widget principal de la página de producto: selector de UoM (kg/g/unidad), embalaje, cantidad y botón "Agregar al Pedido" |
| `theme_guapante/static/src/js/search_modal.js` | Buscador rápido de productos con modal. También puede añadir al carrito. |
| `theme_guapante/controllers/shop.py` | Override del controlador `WebsiteSale`. Intercepta `/shop/cart/update_json` para conversión de unidades y persistencia de `uom_mode` y `product_packaging_id`. |
| `theme_guapante/models/sale_order.py` | Override de `sale.order`: soporte de cantidades fraccionarias (`_cart_update`), matcher de líneas con separación por embalaje (`_cart_find_product_line`), y `cart_quantity` con `ceil()`. |
| `theme_guapante/models/sale_order_line.py` | Campo custom `uom_mode` (`g`, `kg`, `unit`) en la línea de venta. |
| `theme_guapante/models/product_packaging.py` | Extiende `product.packaging` con `is_b2b_exclusive` y `b2b_exclusive_customer_ids` para embalajes VIP. |
| `theme_guapante/views/shop/cart.xml` | Template del carrito personalizado. Muestra packaging name solo cuando `uom_mode == 'unit'`. |
| `theme_guapante/views/product_packaging_views.xml` | Inyecta columnas B2B en la tabla de embalaje del producto (toggle VIP + clientes permitidos). |

---

## 2. Arquitectura del Carrito de Compra

### Flujo Completo: El camino de un "Agrega al Pedido"

```
Usuario hace clic en botón
         ↓
[unit_selector.js] _onAddToCart()
  - Lee qty, uom_mode, packaging_id, no_variant_attribute_values
  - Convierte unidades si es necesario
  - POST /shop/cart/update_json (JSON-RPC)
         ↓
[shop.py] cart_update_json()
  - Convierte unidades (unit → kg vía packaging.qty)
  - Llama super().cart_update_json()
  - Persiste uom_mode en la línea y en sesión
         ↓
[Odoo nativo] WebsiteSale.cart_update_json()
  - Llama order._cart_update()
         ↓
[sale_order.py] _cart_update()
  - Si qty es fraccionaria: usa ceil() + corrige qty exacta después
  - Si qty es entera: delega directo a super()
         ↓
[sale_order.py] _cart_find_product_line()  ← PERSONALIZADO
  - super() nativo primero
  - Fallback con set() para IDs de atributos (evita duplicados por orden)
```

### La Regla del UoM Mode

Cada línea de pedido tiene un campo `uom_mode` que indica cómo el cliente eligió la cantidad:
- `kg` → el cliente escogió kg directamente
- `g` → el cliente escogió gramos; se convierte a kg al guardar
- `unit` → el cliente escogió unidades; se convierte a kg vía `packaging.qty`

Este campo se persiste en la línea de venta (no solo en sesión) para que el personal de preparación sepa cómo empacar.

---

## 3. 🚨 Antipatrones Críticos (Lo que NUNCA se debe hacer)

### ❌ ANTIPATRÓN 1: Doble Binding de Evento en publicWidget

**Síntoma:** El producto siempre se agrega exactamente 2 veces al carrito.

En `unit_selector.js`, el botón de "Agregar al Pedido" se maneja **ÚNICAMENTE** vía `$(document).on('click.guapante_cart', ...)` en `start()`. **NUNCA** agregar el mismo botón en el dict `events: {}` al mismo tiempo.

```javascript
// ❌ MAL: Doble binding → dos AJAX simultáneos → duplicado en carrito
events: {
    'click .guapante-add-to-cart-btn': '_onAddToCart',  // ELIMINAR
},
start() {
    $(document).on('click.guapante_cart', '.guapante-add-to-cart-btn', ...); // ya está aquí
}

// ✅ BIEN: Un solo binding vía document.on
events: {
    // .guapante-add-to-cart-btn NO va aquí
},
start() {
    $(document).on('click.guapante_cart', '.guapante-add-to-cart-btn', this._onAddToCartDelegate);
}
```

**¿Por qué document.on?** `product_layout_fix.js` mueve `#product_detail` en el DOM, rompiendo los bindings de jQuery ligados al `$el` del widget. El binding de document sobrevive ese movimiento.

**SIEMPRE** limpiar en `destroy()`:
```javascript
destroy: function() {
    $(document).off('click.guapante_cart');
    this._super.apply(this, arguments);
}
```

### ❌ ANTIPATRÓN 2: Comparar IDs de Atributos como Lista en Backend

Odoo 18 nativo en `_cart_find_product_line`:
```python
# ❌ MAL: sensible al orden → [3716, 3790] != [3790, 3716]
sol.product_no_variant_attribute_value_ids.ids == no_variant_attribute_value_ids
```

Nuestro override usa `set()`:
```python
# ✅ BIEN: ignora el orden
set(sol.product_no_variant_attribute_value_ids.ids) == set(no_variant_attribute_value_ids)
```

### ❌ ANTIPATRÓN 3: Truncar Cantidades Fraccionarias

Odoo 18 hace `int(qty)` internamente. Para productos de peso (ej: 0.5 kg = 500g), esto convierte la cantidad a 0 y elimina la línea. **Siempre** usar `ceil()` en el paso intermedio y corregir el valor exacto después:

```python
# ✅ BIEN:
ceil_qty = max(1, math.ceil(desired_qty))  # Odoo crea/mantiene la línea
result = super()._cart_update(..., set_qty=ceil_qty)
line.product_uom_qty = desired_qty  # Corrección al valor float real
```

### ❌ ANTIPATRÓN 4: Referenciar el Código Fuente Local de Odoo 19

La carpeta `/home/david/odoo-projects/insotech/tmp_odoo/` contiene **Odoo 19**, pero el servidor de producción/staging corre **Odoo 18**. Las firmas de métodos difieren:

| Método | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| `_cart_find_product_line` | `(product_id, line_id=None, **kwargs)` | `(product_id, uom_id, linked_line_id=False, ...)` |
| Campo UoM en sol | `product_uom` | `product_uom_id` |

**Fuente de verdad definitiva:** el traceback del servidor de Odoo.sh.

---

## 4. Cómo Diagnosticar Bugs del Carrito en Odoo.sh

Sin acceso a los logs del servidor, usa la **Técnica "Note Spy"**:

```python
# En cualquier método Python que quieras verficar que se ejecuta:
debug_msg = f"[DEBUG] método llamado con product_id={product_id}, kwargs={kwargs}\n"
self.sudo().write({'note': (self.note or '') + debug_msg})
```

Luego ejecuta `analyze_cart.py` (script de diagnóstico en la raíz del proyecto) en el shell de Odoo.sh para leer el campo `note` de la orden activa.

**Checklist de diagnóstico de carrito duplicado (en orden):**
1. ¿Siempre son exactamente 2 líneas? → Doble binding JS (ver Antipatrón 1)
2. ¿Las líneas tienen atributos diferentes a las esperadas? → Bug lista vs set (ver Antipatrón 2)
3. ¿La cantidad es incorrecta (ej. 0 o 1 en lugar de 0.5)? → Truncamiento fraccionario (ver Antipatrón 3)
4. ¿Hay un error 500 en el servidor? → **Lee el traceback del navegador completo antes de hacer nada más.**
5. ¿Diferentes embalajes del mismo producto se fusionan en una línea? → Ver Antipatrón 5 (Separación de líneas por packaging).

---

## 5. Convenciones de Código Activas

- **Selector del widget:** `.guapante-unit-selector-container`
- **Botón de agregar:** `.guapante-add-to-cart-btn`
- **Input de cantidad:** `.guapante-qty-input`
- **Modo UoM en línea:** campo `uom_mode` en `sale.order.line` (values: `'kg'`, `'g'`, `'unit'`)
- **Namespace de evento JS:** `click.guapante_cart` (para poder hacer off selectivo en destroy)
- **Logger Python:** `_logger = logging.getLogger(__name__)` en todos los modelos custom

---

## 5.5 Arquitectura B2B Exclusive Packagings

Los embalajes pueden marcarse como exclusivos B2B. El filtrado ocurre en:
- `get_product_packagings()` → selector de embalaje en página de producto
- `search_products()` → resultados del buscador rápido
- `_cart_find_product_line()` → separación de líneas en el carrito

**Regla de oro de separación de líneas:**
> Solo separar líneas por `product_packaging_id` cuando el valor recibido en `kwargs` sea un entero **mayor que cero**. Si es `None` o `0`, dejar que Odoo fusione normalmente.

**Regla de persistencia del packaging_id:**
> Odoo NO garantiza guardar un `product_packaging_id` de eCommerce en la línea del pedido. Siempre escribirlo explícitamente después de que `super()` retorne la respuesta.

**Regla del label en el carrito:**
> La etiqueta del embalaje en `cart.xml` debe condicionarse con `line_display.get('mode') == 'unit'`. Si el usuario pidió por kg/g, Odoo internamente puede asignar un packaging pero no debe mostrarse al usuario.

---

## 6. Referencias de Aprendizajes Documentados

La base de conocimiento tiene documentos detallados bajo `.agent/skills/base-de-conocimiento/aprendizajes/ecommerce/`:

- `duplicacion-carrito-doble-evento-js.md` — El bug de doble binding completo
- `odoo18-cart-find-product-line-list-vs-set.md` — Bug de comparación de lista vs set en Odoo 18
- `diagnostico-sin-acceso-logs-odoo-sh.md` — Técnicas de diagnóstico en Odoo.sh
- `portal-403-sudo-y-visibilidad-jerarquica.md` — Solución a Error 403 en Portal con sudo() seguro y filtrado child_of padre vs direcciones.
- `b2b-embalajes-exclusivos-cart-separation.md` — Separación de líneas de carrito por embalaje B2B y patrones seguros de persistencia del packaging_id.

---

## Directiva de Acción

1. **Antes de modificar el carrito:** Verificar si el cambio afecta a `unit_selector.js`, `shop.py` o `sale_order.py`. Si afecta JS, revisar que no se creen nuevos bindings duplicados para el mismo evento.

2. **Antes de sobrescribir un método de Odoo 18:** Buscar el método en el traceback real del servidor o en el código fuente de Odoo 18 (NO Odoo 19 local). Verificar la firma exacta de los parámetros.

3. **Si observas duplicación en el carrito:** Seguir el checklist de diagnóstico en orden (JS doble binding → atributos set vs list → fraccionarios → traceback 500).

4. **Si hay cantidades fraccionarias involucradas (`_cart_update`):** Siempre usar `ceil()` en la llamada a `super()` y corregir el quantity exacto después via `line.sudo().product_uom_qty = desired_qty`.

5. **Para toda modificación de backend:** Verificar que el método llamado en Odoo 18 siga existiendo con el mismo nombre (ej. `_cart_update` sí existe en Odoo 18; `_cart_add` es solo Odoo 19+).
