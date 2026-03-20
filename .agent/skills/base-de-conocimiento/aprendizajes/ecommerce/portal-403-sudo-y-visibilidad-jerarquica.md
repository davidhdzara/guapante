# Portal Odoo: Solución 403 con `sudo()` y Visibilidad Jerárquica de Facturas

**Fecha de Registro:** 2026-03-20
**Contexto del Problema:**
En la sección personalizada "Mis facturas" del portal (`theme_guapante/controllers/customer_portal.py`), los usuarios finales obtenían un error 403 Forbidden al intentar acceder a la vista. El controlador intentaba consultar los registros de `account.payment` (Pagos) para calcular el "Último Pago", a los cuales el grupo `Portal` no tiene permiso de acceso por defecto en Odoo. Adicionalmente, era necesario aplicar una regla negocio donde las direcciones de entrega (hijos) solo pudieran ver sus propias facturas, mientras que el contacto principal (padre) pudiera ver las de todos sus hijos.

## 🚨 El Problema o Error
1. **Error 403 Forbidden:** Generado por intentar hacer `.search()` sobre `account.payment` con un usuario tipo portal.  La regla del proyecto es **no** otorgar permisos de backend explícitos (ej. Mostrar funciones de contabilidad) a los usuarios del portal para evitar fugas de información.
2. **Visibilidad incorrecta:** El dominio de facturas utilizaba `child_of`, `[partner.commercial_partner_id.id]`. Esto provocaba que si ingresaba una dirección de entrega (hijo), Odoo resolviera el `commercial_partner_id` al padre, mostrándole a la dirección hija *todas* las facturas de la empresa y saltándose la restricción.

## 🔍 Causa Raíz
* **Permisos Base de Datos:** Los usuarios del portal no pueden consultar `account.payment` bajo ninguna circunstancia sin elevar sus privilegios en la base de datos (lo cual es inseguro).
* **Operador `child_of` en vistas Portal:** El operador `child_of` busca hacia abajo en el árbol jerárquico. Si se le pasa el ID del padre supremo (`commercial_partner_id`), mostrará siempre todo el árbol, sin importar quién inició la sesión.

## ✅ Solución Adoptada

**Para el error 403:**
Se empleó el uso de `.sudo()` **única y exclusivamente en el código Python** del controlador, asegurándolo estrictamente con un filtro por el propio `partner_id` del usuario en sesión.

```python
# Usamos sudo() porque los usuarios del portal no tienen permiso de acceso a pagos,
# pero restringimos el dominio estrictamente a su partner_id para que sea seguro.
AccountPayment = request.env['account.payment'].sudo()
payment_domain = [
    ('partner_id', 'child_of', [partner.id]),
    ('state', '=', 'posted')
]
last_payment = AccountPayment.search(payment_domain, order='date desc', limit=1)
```

**Para la visibilidad jerárquica padre/hijo:**
Se modificó el dominio general de búsqueda de facturas para que el operador `child_of` reciba el **`partner.id`** del usuario actualmente logueado.

```python
# Si es el contacto padre (empresa o persona principal), ve todo (inclusive hijos).
# Si es una dirección de entrega (hijo), solo ve sus propias facturas registradas.
domain += [('partner_id', 'child_of', [partner.id])]
```

## 💡 Buenas Prácticas / Cómo evitarlo
1. **No otorgar permisos contables a perfiles Portal:** Siempre resuelve bloqueos como el 403 de lectura temporal en el backend mediante `.sudo()`, bajo la condición estricta de **filtrar la consulta** con los IDs del usuario en sesión (`request.env.user.partner_id.id`).
2. **Analizar con cuidado `commercial_partner_id`:** En el portal B2B, si un nodo hijo debe tener acceso particionado (solo lo suyo), no utilices `commercial_partner_id.id` como ancla de los dominios `child_of`. Utiliza el `partner.id` de la sesión actual: el padre automáticamente abarcará a los hijos, y los hijos se limitarán a sí mismos.
