# Embalajes Exclusivos B2B: Separación de Líneas en el Carrito

**Fecha de Registro:** 2026-03-20
**Contexto del Problema:**
Implementación de embalajes (product.packaging) visibles solo para clientes B2B autorizados en el eCommerce de Guapante. El requerimiento central: diferentes embalajes del mismo producto (ej. "Cilantro Paquete 200g" y "Cilantro Paquete 500g") deben crear líneas SEPARADAS en el carrito, sin fusionarse.

---

## 🚨 El Problema o Error

El carrito fusionaba todos los embalajes del mismo producto en una sola línea. Al seleccionar 2×Paquete200g y 2×Paquete500g, el resultado era una sola línea sumada con la cantidad incorrecta (ej. "12 unidades").

Adicionalmente, el `_build_uom_display` siempre usaba el **primer embalaje de la lista** del producto para calcular la cantidad visual, en vez del embalaje real de la línea.

---

## 🔍 Causa Raíz

**Problema 1 — Fusión de líneas:**
`_cart_find_product_line` de Odoo 18 fusiona todas las adiciones del mismo `product_id`, sin diferenciar por `product_packaging_id`.

**Problema 2 — Cantidad visual incorrecta:**
`_build_uom_display` en `shop.py` hacía:
```python
packaging = line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
```
Tomaba siempre el primer embalaje de la lista sin respetar cuál eligió el usuario.

**Problema 3 — Persistencia del packaging_id:**
Odoo no siempre guarda el `product_packaging_id` en la línea del pedido al crearla por eCommerce. El campo quedaba como `False` aunque el usuario hubiese elegido un embalaje específico.

**Problema 4 — `_inverse_visual_qty` sobreescribía el packaging:**
La función `_inverse_visual_qty` en `sale_order_line.py` asignaba ciegamente `line.product_packaging_id = packaging_ids.filtered(...)[:1]`, borrando cualquier packaging asignado correctamente.

---

## ✅ Solución Adoptada

### 1. Separación quirúrgica en `_cart_find_product_line` (`sale_order.py`):

```python
def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
    lines = super()._cart_find_product_line(product_id, line_id, **kwargs)

    # Solo separar por empaque cuando se envía un ID real y no-cero
    target_pkg_id = kwargs.get('product_packaging_id')
    if target_pkg_id and int(target_pkg_id) > 0:
        lines = lines.filtered(
            lambda l: l.product_packaging_id.id == int(target_pkg_id)
        )

    if lines:
        return lines
    # ... fallback set-based para atributos
```

**Regla de oro:** Solo filtra si `target_pkg_id > 0`. El botón +/- del carrito NO envía packaging_id → usa comportamiento nativo → no crea líneas nuevas.

### 2. Persistencia explícita en `cart_update_json` (`shop.py`):

```python
# DESPUÉS de llamar a super(), escribir el packaging_id en el DB:
if product_packaging_id and int(product_packaging_id) > 0:
    pkg = request.env['product.packaging'].sudo().browse(int(product_packaging_id))
    if pkg.exists():
        line.sudo().write({'product_packaging_id': pkg.id})
```

### 3. Fix en `_build_uom_display` (`shop.py`):

```python
# Usar el packaging de la línea, NO el primero de la lista
packaging = line.product_packaging_id
if not packaging:
    packaging = line.product_id.packaging_ids.filtered(
        lambda p: p.sales and p.qty > 0
    )[:1]
```

### 4. Fix en `_inverse_visual_qty` (`sale_order_line.py`):

```python
# Respetar el packaging existente antes de asignar el primero
packaging = line.product_packaging_id
if not packaging:
    packaging = line.product_id.packaging_ids.filtered(...)[:1]
```

### 5. Ocultar label de packaging en el carrito para modo kg/g:

```xml
<!-- Solo mostrar si modo es 'unit'. Si el usuario pidió por kg/g, ocultar. -->
<t t-if="line.product_packaging_id and line_display.get('mode') == 'unit'">
    <small class="text-success fw-semibold">
        <i class="fa fa-cube me-1"/>
        <span t-esc="line.product_packaging_id.name"/>
    </small>
</t>
```

---

## 💡 Buenas Prácticas / Cómo evitarlo

1. **Regla de separación condicional:** Cuando se quiera separar líneas de carrito por algún criterio, hacerlo SOLO cuando ese criterio venga explícitamente (no-nulo, no-cero) en `kwargs`. Aplicar el filtro a las líneas devueltas por `super()`, no reemplazar su lógica.

2. **Persistencia del packaging_id:** Nunca confiar en que Odoo nativo guarde un m2o en la línea del pedido cuando viene de un endpoint de eCommerce. Siempre escribirlo explícitamente con `sudo()` después de que `super()` cree la línea.

3. **`_inverse_visual_qty` es peligrosa:** Si existe un computed field con inverse, que accede a la base de datos con `product_id.packaging_ids.filtered(...)[:1]`, puede sobreescribir valores legítimos. Siempre verificar primero si ya hay un valor antes de asignar el fallback.

4. **El display y la lógica son independientes:** La visibilidad del label en el carrito (`cart.xml`) debe depender del `uom_mode` almacenado, no solo de la presencia del `product_packaging_id`, ya que Odoo puede asignar un packaging internamente aunque el usuario haya pedido por kg.

5. **No tocar `_cart_find_product_line` de forma agresiva:** El método es el núcleo de la fusión de líneas. Cambios agresivos (como filtrar también las líneas SIN packaging) rompen el flujo de todos los productos normales (Mango Tommy, pedidos por kg). Siempre mantener el camino "por defecto" intacto.
