# Duplicación de Líneas en el Carrito por Doble Binding de Evento JS

**Fecha de Registro:** 2026-03-17
**Contexto del Problema:**
Al agregar un producto a la tienda online de Guapante (eCommerce Odoo 18), cada clic en "Agregar al Pedido" creaba SIEMPRE exactamente 2 líneas idénticas en el carrito de venta, sin importar el producto, sus atributos, o la cantidad.

## 🚨 El Problema o Error

Cada producto agregado aparecía duplicado en el carrito con información idéntica:

```
--- LÍNEA 208 ---
Producto : [FRUT-0063] Mango Tommy
Cantidad : 5.0 kg

--- LÍNEA 210 ---  ← DUPLICADO EXACTO
Producto : [FRUT-0063] Mango Tommy
Cantidad : 5.0 kg
```

El problema afectaba a TODOS los productos, incluyendo los que no tienen atributos (Cilantro).

## 🔍 Causa Raíz

En `theme_guapante/static/src/js/unit_selector.js`, el botón `.guapante-add-to-cart-btn` tenía **DOS bindings de evento de clic activos al mismo tiempo**:

```javascript
// BINDING 1: En el diccionario 'events' del publicWidget (línea 15)
events: {
    'click .guapante-add-to-cart-btn': '_onAddToCart',   // ← DISPARO #1
},

// BINDING 2: En la función start() vía jQuery document-level (línea 45)
$(document).on('click.guapante_cart', '.guapante-add-to-cart-btn', ...); // ← DISPARO #2
```

Cada clic disparaba **dos peticiones AJAX simultáneas** al servidor. Ambas llegaban antes de que ninguna hiciese commit en la BD. Por tanto ambas veían el carrito "vacío" y ambas creaban una nueva línea.

**¿Por qué existía el doble binding?**
El binding via `$(document).on()` fue añadido para sobrevivir los movimientos del DOM que realiza `product_layout_fix.js`. Sin embargo, se olvidó eliminar el binding original del `events: {}`, dejando ambos activos.

## ✅ Solución Adoptada

Eliminar el binding del botón del diccionario `events`:

```javascript
// ANTES (INCORRECTO):
events: {
    'click .guapante-qty-plus': '_onQuantityPlus',
    'click .guapante-qty-minus': '_onQuantityMinus',
    'click .guapante-add-to-cart-btn': '_onAddToCart',  // ← ELIMINAR ESTO
},

// DESPUÉS (CORRECTO):
events: {
    'click .guapante-qty-plus': '_onQuantityPlus',
    'click .guapante-qty-minus': '_onQuantityMinus',
    // .guapante-add-to-cart-btn está gestionado por $(document).on en start()
},
```

El binding en `start()` permanece y es el correcto porque verifica que el clic vino del elemento correcto con `$.contains()`.

## 💡 Buenas Prácticas / Cómo evitarlo

1. **Regla de oro:** Si un evento se migra de `events: {}` a `$(document).on()`, el entry en `events` DEBE eliminarse en el mismo commit.

2. **Señal de alerta — La Regla del "exactamente 2":** Si un producto siempre se agrega exactamente 2 veces (nunca 1, nunca 3), la causa es casi siempre un doble binding de evento JS, NO un problema de backend.

3. **Verificación rápida en consola del navegador:**
   ```javascript
   // Inspeccionar los event listeners del botón
   $._data($('.guapante-add-to-cart-btn')[0], 'events')
   // Si 'click' aparece múltiples veces → doble binding
   ```

4. **Orden de diagnóstico de carrito duplicado:**
   - Primero: ¿hay doble binding JS? (este documento)
   - Luego: ¿hay problemas de matching de atributos en backend? (ver `odoo18-cart-find-product-line-list-vs-set.md`)
