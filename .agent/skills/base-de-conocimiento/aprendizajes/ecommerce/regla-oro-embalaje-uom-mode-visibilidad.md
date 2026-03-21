# Regla de Oro del Embalaje: Consistencia en toda la cadena del pedido

**Fecha de Registro:** 2026-03-20
**Contexto del Problema:**
Al integrar los embalajes B2B con el módulo de "Preparación del Día", se detectó que el mismo bug
de mostrar embalajes incorrectos en el carrito también existía en el módulo de picking interno.
Además, la regla de visibilidad del embalaje no se había aplicado consistentemente en toda la cadena.

---

## 🚨 El Problema o Error

**Punto 1 — Bug del "primer empaque" replicado:**
La función `_get_display_qty()` en `preparation_day.py` usaba:
```python
packaging = line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
```
Esto siempre toma el **primer empaque de la lista**, ignorando el que eligió el cliente.
Ejemplo: cliente pidió "2 Paquetes 500g" pero la pantalla de preparación mostraba "10 unidades"
porque dividía 1.0kg por el primer empaque (0.1kg = Unidad).

**Punto 2 — Regla de visibilidad incompleta:**
La corrección de ocultar el nombre del embalaje a usuarios no B2B se aplicó solo en `cart.xml`,
pero no en `preparation_day.py`. Esto significaba que si Odoo asignaba internamente un
`product_packaging_id` a una línea pedida en kg/g, el personal de bodega veía "Paquete 500g"
aunque el cliente solo hubiese pedido gramos libres.

---

## 🔍 Causa Raíz

Los bugs del embalaje se repiten en cada punto donde se calcula o muestra información
sobre embalajes porque:
1. Se copió el patrón `packaging_ids.filtered(...)[:1]` sin saber que era incorrecto.
2. La regla de visibilidad (`uom_mode == 'unit'`) no estaba documentada como una regla
   sistémica — solo se había aplicado como un fix puntual en el carrito.

---

## ✅ Solución Adoptada

### Regla 1: Siempre usar el packaging de la línea primero

En CUALQUIER función que necesite la cantidad de un empaque para calcular unidades:

```python
# ✅ CORRECTO: Usar el packaging asignado a la línea, con fallback al primero
packaging = line.product_packaging_id  # El que eligió el cliente
if not packaging:
    packaging = line.product_id.packaging_ids.filtered(
        lambda p: p.sales and p.qty > 0
    )[:1]  # Fallback solo si no hay ninguno asignado
```

```python
# ❌ INCORRECTO: Siempre tomar el primero de la lista
packaging = line.product_id.packaging_ids.filtered(lambda p: p.sales and p.qty > 0)[:1]
```

### Regla 2: La Regla de Oro del Embalaje — solo mostrar si `uom_mode == 'unit'`

En TODO punto del sistema donde se muestre el nombre de un embalaje:

**Backend Python (al cargar datos):**
```python
'packaging_name': (
    line.product_packaging_id.name
    if line.product_packaging_id and (line.uom_mode or 'unit') == 'unit'
    else False
),
```

**Frontend XML (QWeb):**
```xml
<!-- ✅ CORRECTO: Condición doble — packaging existe Y modo es unit -->
<t t-if="line.product_packaging_id and line_display.get('mode') == 'unit'">
    <span t-esc="line.product_packaging_id.name"/>
</t>

<!-- ❌ INCORRECTO: Solo verificar que packaging existe -->
<t t-if="line.product_packaging_id">
    <span t-esc="line.product_packaging_id.name"/>
</t>
```

---

## 💡 Buenas Prácticas / Cómo evitarlo

### Checklist de "Puntos de visualización de embalajes"

Antes de desplegar cualquier desarrollo que muestre información de embalajes,
verificar TODOS los puntos de la cadena:

| Punto | Archivo | ¿Aplica Regla de Oro? |
|---|---|---|
| Página de producto (eCommerce) | `unit_selector.js` | Ya controlado (solo muestra botones autorizados) |
| Carrito de compras (frontend) | `cart.xml` | ✅ Condición `mode == 'unit'` aplicada |
| Cálculo de cantidad visible en carrito | `shop.py → _build_uom_display` | ✅ `line.product_packaging_id` primero |
| Pantalla de Preparación del Día | `preparation_day.py → action_load` | ✅ `uom_mode == 'unit'` aplicado |
| Cálculo de cantidad en Preparación | `preparation_day.py → _get_display_qty` | ✅ `line.product_packaging_id` primero |
| PDF de Pedido de Venta | *(pendiente)* | Verificar en próximo sprint |
| Correo de confirmación de pedido | *(pendiente)* | Verificar en próximo sprint |

### Regla Heurística de Aplicación

> **Si una función o template accede a `product_packaging_id` o `packaging_ids`
> para mostrar información al usuario, SIEMPRE aplicar:**
> 1. `line.product_packaging_id` antes de `packaging_ids[:1]`
> 2. `uom_mode == 'unit'` como puerta de visibilidad

### Por qué `uom_mode == 'unit'` es la clave

Odoo puede asignar automáticamente un `product_packaging_id` a una línea de pedido
basándose en la cantidad (ej. si el cliente pide exactamente 0.5kg y hay un empaque de
0.5kg, Odoo puede "sugerirlo" internamente). Esto hace que `product_packaging_id`
**no sea indicador confiable** de que el cliente conscientemente eligió ese embalaje.

El campo `uom_mode` sí es el indicador confiable: lo escribimos explícitamente en el
controlador y solo llega como `'unit'` cuando el cliente usó el selector de embalaje.
