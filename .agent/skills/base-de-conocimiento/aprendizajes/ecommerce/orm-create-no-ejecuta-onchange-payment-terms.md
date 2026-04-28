# eCommerce: ORM create() NO ejecuta onchange — Términos de pago y campos dependientes

**Fecha de Registro:** 2026-04-28
**Contexto del Problema:**
El 21% de las órdenes de venta (370 de 1,710) tenían términos de pago incorrectos. La dueña reportaba que el plazo configurado en el contacto no se aplicaba en las facturas.

## 🚨 El Problema o Error

Cuando un cliente compra por el eCommerce, Odoo crea la orden de venta via `sale.order.create()` ejecutado por **OdooBot**. El método `create()` del ORM **no dispara los onchange** definidos en el modelo.

El onchange `_onchange_partner_id` en `sale.order` es el responsable de copiar `partner.property_payment_term_id` → `order.payment_term_id`. Como no se ejecuta en `create()`, el término de pago del contacto se perdía.

**Datos del diagnóstico:**
- 277 de 370 errores (75%) eran en órdenes sin vendedor asignado (= OdooBot = eCommerce)
- 296 de 1,362 órdenes eCommerce tenían discrepancia (21.7%)
- No había defaults, server actions ni automated actions que causaran el problema

## 🔍 Causa Raíz

En Odoo 18, los `@api.onchange` solo se ejecutan en la **interfaz de usuario** (formularios web). Las creaciones por ORM (`Model.create()`) son "crudas" — escriben los vals directamente sin pasar por la capa de UI.

El eCommerce (módulo `website_sale`) crea las órdenes por ORM, por lo que:
- ✅ Se asigna el `partner_id` correctamente
- ❌ NO se copia `property_payment_term_id`
- ❌ NO se copia `property_product_pricelist` (cuando no viene en vals)
- ❌ Cualquier otro campo que dependa de un onchange se pierde

## ✅ Solución Adoptada

Override de `create()` en `sale.order` (`theme_guapante/models/sale_order.py`):

```python
@api.model_create_multi
def create(self, vals_list):
    Partner = self.env['res.partner']
    for vals in vals_list:
        if vals.get('payment_term_id'):
            continue  # Explícito — respetar
        partner_id = vals.get('partner_id')
        if not partner_id:
            continue
        partner = Partner.browse(partner_id)
        commercial = partner.commercial_partner_id or partner
        term = commercial.property_payment_term_id
        if term:
            vals['payment_term_id'] = term.id
    return super().create(vals_list)
```

**Puntos clave:**
- Usa `commercial_partner_id` (padre empresa), no el `partner_id` directo (que puede ser un hijo tipo delivery)
- Respeta el valor si viene explícito en vals (`vals.get('payment_term_id')`)
- No afecta otros módulos — solo agrega cuando falta

## 💡 Buenas Prácticas / Cómo evitarlo

1. **Regla universal:** Si un campo se llena por `onchange` en la UI, verificar si también se llena en creaciones por ORM (eCommerce, API, imports). Si no → necesita override de `create()`.

2. **Siempre usar `commercial_partner_id`** para buscar propiedades fiscales/comerciales del contacto, especialmente cuando el eCommerce autentica con contactos hijos (type=delivery).

3. **Patrón de diagnóstico:** Para verificar si un onchange se ejecuta en create():
   ```python
   test = env['sale.order'].create({'partner_id': partner.id})
   print(test.payment_term_id)  # Vacío = el onchange NO se ejecuta
   ```
