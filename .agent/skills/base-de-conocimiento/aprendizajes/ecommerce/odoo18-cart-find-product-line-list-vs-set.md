# Odoo 18: _cart_find_product_line Falla con Atributos en Diferente Orden

**Fecha de Registro:** 2026-03-17
**Contexto del Problema:**
Al agregar productos con atributos "No Variante" al eCommerce de Guapante en Odoo 18, el sistema podía crear líneas duplicadas si los IDs de atributos llegaban en diferente orden al que estaban almacenados en la BD.

## 🚨 El Problema o Error

Odoo 18 en `website_sale/models/sale_order.py` hace esta comparación en `_cart_find_product_line`:

```python
# Código nativo de Odoo 18 – VULNERABLE AL ORDEN:
filtered_sol = filtered_sol.filtered(
    lambda sol:
        sol.product_no_variant_attribute_value_ids.ids == no_variant_attribute_value_ids
        # [3716, 3790] == [3790, 3716]  →  ¡¡ FALSE !! → crea línea nueva
)
```

Si el JS envía `[3790, 3716]` y la BD tiene `[3716, 3790]`, Odoo no encuentra la línea existente y crea una duplicada.

## 🔍 Causa Raíz

Python compara listas con `==` respetando el orden: `[1, 2] != [2, 1]`. Los IDs de atributos pueden llegar en cualquier orden desde el frontend JS, pero `.ids` de un recordset de Odoo retorna los IDs en el orden en que fueron guardados en la BD.

## ✅ Solución Adoptada

Sobrescribir `_cart_find_product_line` con comparación por conjuntos (`set()`):

```python
# En theme_guapante/models/sale_order.py

def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
    """
    Override para arreglar sensibilidad al orden de IDs de atributos en Odoo 18.
    Odoo nativo usa comparación de lista (==), fallamos con set() comparando conjuntos.
    """
    self.ensure_one()

    # Primero dejar que la lógica nativa de Odoo intente encontrar la línea
    result = super()._cart_find_product_line(product_id, line_id, **kwargs)
    if result:
        return result

    # Fallback: reintentar con comparación por conjuntos (set)
    no_var_ids = kwargs.get('no_variant_attribute_value_ids') or []
    if not no_var_ids:
        return result

    target_set = set(no_var_ids)
    matched = self.env['sale.order.line']
    for line in self.order_line:
        if line.product_id.id != product_id:
            continue
        if line_id and line.id != line_id:
            continue
        if hasattr(line, 'product_no_variant_attribute_value_ids'):
            if set(line.product_no_variant_attribute_value_ids.ids) == target_set:
                matched |= line

    return matched
```

### ⚠️ FIRMA DEL MÉTODO: Odoo 18 vs Odoo 19 — CRÍTICO

| Versión | Segundo argumento | Tercer argumento |
|---------|-------------------|------------------|
| **Odoo 18** | `line_id=None` | `**kwargs` |
| **Odoo 19** | `uom_id` (requerido) | `linked_line_id=False` |

Usar la firma de Odoo 19 en Odoo 18 causa:
```
KeyError: 'product_uom_id'
# porque Odoo 18 pasa `line_id` como segundo arg posicional
# y nuestro código lo trata como `uom_id` → dominio inválido
```

**El traceback del servidor es la fuente de verdad definitiva para la firma:**
```
File ".../website_sale/models/sale_order.py", line 324, in _cart_update
    order_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]
                                                           ^^^^^^^^ ← segundo arg es line_id en Odoo 18
```

## 💡 Buenas Prácticas / Cómo evitarlo

1. **Nunca comparar IDs de atributos como listas.** Usar siempre `set(ids_a) == set(ids_b)`.

2. **Verificar la firma del método en el traceback.** Ante duda entre versiones, el traceback del servidor real es más confiable que cualquier documentación o código local de otra versión.

3. **No consultar código local de versiones diferentes.** La carpeta `insotech/tmp_odoo` contiene Odoo 19, que tiene APIs diferentes a Odoo 18 del servidor de producción. Verificar siempre la versión del código local antes de usarlo como referencia.

4. **Si `_cart_update` necesita fraccionarios** (ej. 500g = 0.5kg), Odoo 18 sí lo tiene. El override necesario es interceptar antes de que Odoo aplique `int()` a la cantidad y corregir el valor después:

```python
def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
    float_qty = float(add_qty or set_qty or 0)
    is_fractional = float_qty != int(float_qty)
    if not is_fractional:
        return super()._cart_update(product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs)
    # ... lógica de ceil() y corrección posterior
```
