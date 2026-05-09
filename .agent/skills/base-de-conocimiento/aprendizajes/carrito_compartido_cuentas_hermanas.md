# Aprendizaje: Carrito compartido entre cuentas hermanas (sale_get_order)

**Fecha:** 2026-05-07  
**Módulo:** theme_guapante  
**Archivos:** `models/website.py` (nuevo)  
**Refs:** S02523, S02521 (LRFN FREEDOM CHASERS)

---

## Problema

Cuando un cliente con múltiples cuentas hijas (direcciones de entrega con usuario portal)
usa el **mismo navegador** para hacer pedidos desde diferentes cuentas, los productos
se agregan a la orden **equivocada** — incluso a órdenes ya confirmadas de otra cuenta.

**Caso real:** Usuario Cocina (uid=95) agregó 2 líneas a S02523 (orden confirmada del Bar)
1 minuto después de que el Bar (uid=89) la confirmó.

## Causa Raíz

### Falla 1: `Session.authenticate()` NO limpia `sale_order_id`

Al hacer login con otra cuenta en el mismo browser, la sesión HTTP mantiene el 
`sale_order_id` del usuario anterior.

### Falla 2: `sale_get_order()` no valida la orden de sesión

```python
# Odoo 18 nativo (website_sale/models/website.py:393)
sale_order_id = request.session.get('sale_order_id')
if sale_order_id:
    sale_order_sudo = SaleOrder.browse(sale_order_id).exists()
    # ↑ NO verifica:
    #   1. ¿La orden es draft? (podría ser state='sale' o 'cancel')
    #   2. ¿La orden pertenece al usuario logueado?
```

### Flujo del bug

```
1. Bar (uid=89) crea carrito → session['sale_order_id'] = S02523
2. Bar confirma S02523 → state='sale', sesión NO se limpia
3. Cocina (uid=95) hace login en MISMO browser
4. Session.authenticate() NO limpia sale_order_id
5. sale_get_order() recupera S02523 (confirmada, del Bar)
6. _update_address() cambia partner_shipping → Cocina
7. Productos van a S02523 ← BUG
```

## Solución

Override de `sale_get_order()` en `website` model con 2 guards:

```python
# Guard 1: Order must be draft
if order_sudo.state != 'draft':
    request.session.pop('sale_order_id', None)

# Guard 2: Order must belong to the authenticated partner
elif order_sudo.partner_id.id != partner.id:
    request.session.pop('sale_order_id', None)
```

**¿Se pierden órdenes?** NO. `session['sale_order_id']` es un puntero temporal (cookie).
La orden vive en PostgreSQL. Odoo la re-encuentra automáticamente vía `last_website_so_id`
(busca `partner_id + state=draft + website_id`).

## Lección Aprendida

> **`sale_get_order()` de Odoo confía ciegamente en la sesión.** Si tu proyecto tiene
> clientes B2B con múltiples cuentas portal bajo el mismo padre comercial, debes agregar
> guards de partner y state en el override de `sale_get_order()`.

> **`Session.authenticate()` NO limpia datos de eCommerce.** Al cambiar de cuenta en el
> mismo browser, la sesión HTTP hereda cookies del usuario anterior. Esto incluye
> `sale_order_id`, `website_sale_cart_quantity` y potencialmente otros.

> **Nunca asumas que `sale_order_id` en sesión apunta a una orden válida.** Puede ser:
> - Una orden confirmada (state='sale')
> - Una orden cancelada (state='cancel')
> - Una orden de otro partner (cambio de cuenta)
> - Una orden eliminada (no .exists())
