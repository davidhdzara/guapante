# Aprendizaje: Búsqueda eCommerce Odoo 18 — Falsos positivos por campo `description`

**Fecha:** 2026-05-07  
**Módulo:** theme_guapante  
**Archivos:** `models/product_template.py`, `controllers/shop.py`

---

## Problema

El buscador de la tienda online retornaba productos **completamente irrelevantes** para la búsqueda del usuario.

- Buscar **"ajo"** → retornaba 20 productos (Banano, Mandarina, Guisantes, etc.)
- Buscar **"manzana"** → retornaba Papa Nevada

**Impacto:** 90% de ruido en los resultados de búsqueda. El usuario debía buscar visualmente entre decenas de productos irrelevantes.

## Causa Raíz

### El motor de búsqueda fuzzy de Odoo 18 (`_search_with_fuzzy`)

El método `_search_get_detail` en `website_sale/models/product_template.py` define qué campos se indexan para la búsqueda. Cuando `displayDescription=True`, agrega **`description`** (campo HTML interno) a los `search_fields`.

En Guapante, el 94.9% de los productos (243 de 256) tienen el campo `description` populado con **textos largos de marketing** que contienen palabras genéricas como:

- **"bajo"** → matchea "ajo" via `ilike`
- **"manzana nevada"** → matchea "manzana"
- **"cultivado"**, **"sabor"**, etc.

### Dos flujos, misma raíz

| Flujo | Método | Campos buscados | ¿Problema? |
|-------|--------|----------------|:-----------:|
| Desktop (form GET) | `_get_shop_domain` | name, variant code, `website_description`, `description_sale` | ❌ No (campos vacíos) |
| Mobile/Fuzzy | `_search_get_detail` → `_search_build_domain` | name, default_code, variant code, **`description`**, `description_sale` | ✅ SÍ |

El campo `description` es HTML interno. El campo `description_sale` (que es el correcto para búsqueda de cliente) tiene **0 productos** con datos.

## Solución

### 1. Override de `_search_get_detail` en `product.template`

```python
def _search_get_detail(self, website, order, options):
    result = super()._search_get_detail(website, order, options)
    result['search_fields'] = [
        f for f in result['search_fields'] if f != 'description'
    ]
    return result
```

### 2. Ordenamiento por relevancia de nombre

```python
def _sort_by_name_relevance(self, search_result, search_term):
    # Tier 1: nombre empieza con el término
    # Tier 2: nombre contiene el término
    # Tier 3: match en otros campos
```

## Resultados

| Búsqueda | ANTES | DESPUÉS | Falsos positivos eliminados |
|----------|:-----:|:-------:|:--------------------------:|
| "ajo" | 20 | 2 | 18 (−90%) |
| "manzana" | 7 | 5 | 2 (−29%) |
| "banano" | — | 1 | 0 (no roto) |

## Lección Aprendida

> **Nunca confíes ciegamente en los campos que Odoo incluye por defecto en `_search_get_detail`.** El campo `description` (HTML) es para uso interno/admin, no para búsqueda de cliente. Siempre verifica qué campos tienen datos reales y si generan ruido.

> **El orden de los resultados importa tanto como la precisión.** Odoo ordena por `website_sequence`, no por relevancia. Si el usuario busca "ajo" y el producto "Ajo" aparece en la posición 19, la búsqueda se siente rota aunque técnicamente sí encontró el producto.

## Campos de Odoo 18 — Referencia rápida

| Campo | Tipo | Uso | ¿Buscar? |
|-------|------|-----|:--------:|
| `name` | char | Nombre del producto | ✅ Siempre |
| `default_code` | char | Referencia interna | ✅ Siempre |
| `description` | HTML | Descripción interna (admin) | ❌ Genera ruido |
| `description_sale` | text | Descripción para cliente | ✅ Si tiene datos |
| `website_description` | HTML | Descripción eCommerce | ✅ Si tiene datos |
| `description_ecommerce` | HTML | Descripción adicional eCommerce | ✅ Si tiene datos |
