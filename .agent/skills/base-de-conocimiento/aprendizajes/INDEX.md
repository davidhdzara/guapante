# Índice de Aprendizajes

Este directorio contiene documentos detallados sobre problemas complejos, errores recurrentes y buenas prácticas descubiertas durante el desarrollo del proyecto.

> Nota: Cuando agregues un nuevo documento a esta carpeta, por favor incluye un enlace aquí para mantener el índice actualizado.

---

## 📦 Contabilidad (`contabilidad/`)

| Documento | Descripción |
|-----------|-------------|
| `antipatron-eliminar-diarios-nativos.md` | No eliminar diarios nativos de Odoo; causa errores en vistas |
| `antipatron-mapeo-impuestos-vacio.md` | Mapeo de impuestos vacío en posiciones fiscales causa errores |
| `catalogo-gastos-servicios.md` | Guía del catálogo de gastos y servicios |
| `parametrizacion-anglosajona-categorias.md` | Configuración de categorías de productos anglosajona |
| `rutas-archivos-maestros.md` | Rutas a archivos maestros de configuración contable |

---

## 🛒 eCommerce (`ecommerce/`)

| Documento | Descripción |
|-----------|-------------|
| `duplicacion-carrito-doble-evento-js.md` | **CRÍTICO** — Bug de duplicación en carrito por doble binding de evento JS. Señal: siempre exactamente 2 líneas. |
| `odoo18-cart-find-product-line-list-vs-set.md` | Bug en Odoo 18: `_cart_find_product_line` usa comparación de lista para atributos (falla si el orden difiere). Fix con `set()`. |
| `diagnostico-sin-acceso-logs-odoo-sh.md` | Técnicas para diagnosticar bugs en Odoo.sh sin acceso a logs del servidor. Técnica "Note Spy". |

---

## 📋 General

| Documento | Descripción |
|-----------|-------------|
| `responsabilidades-fiscales-dian-1-9.md` | Responsabilidades fiscales DIAN Colombia (códigos 1-9) |
