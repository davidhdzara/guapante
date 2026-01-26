INFORME TÉCNICO
Implementación Sidebar de Categorías en Ficha de Producto

Odoo v18 – Website / eCommerce

1. Objetivo del Desarrollo

Implementar una barra lateral de categorías (sidebar) en la vista de detalle de producto (/shop/product) reutilizando el componente estándar del catálogo (website_sale.products_categories_list), manteniendo:

coherencia visual con /shop,

navegación funcional entre categorías,

compatibilidad con responsive (desktop / mobile),

estabilidad ante actualizaciones de Odoo.

2. Alcance Funcional

✔ Mostrar árbol de categorías públicas en la ficha del producto (desktop).
✔ Resaltar la categoría activa.
✔ Al hacer clic en una categoría, redirigir al catálogo filtrado (/shop/category/...).
✔ No modificar comportamiento estándar del producto ni del carrito.
✔ No afectar breadcrumbs, SEO ni performance.

❌ No se requiere lógica de búsqueda avanzada.
❌ No se requiere sidebar visible en mobile (se oculta).

3. Componentes Técnicos Afectados
Capa	Componente	Acción
Backend	WebsiteSale.product()	Extensión (override controlado)
Frontend	website_sale.product	Herencia QWeb (XPath)
UI	Bootstrap Grid	Reestructuración layout
Assets	SCSS frontend	Ajustes visuales mínimos
4. Puntos Críticos del Desarrollo (⚠️ MUY IMPORTANTE)
4.1 Override del Controlador (CRÍTICO)

El método product() NO se puede sobrescribir sin redefinir explícitamente la ruta.

🔴 Error común a evitar:

@http.route()
def product(...)


Esto NO registra ninguna ruta → el código nunca se ejecuta.

✅ Acción requerida:

Copiar exactamente las rutas declaradas en website_sale.controllers.main.WebsiteSale.product

Mantener type='http', auth='public', website=True, sitemap=True

4.2 Normalización de la variable category (CRÍTICO)

El parámetro category puede llegar como:

product.public.category (recordset)

str / int (id o slug)

None

⚠️ El template products_categories_list espera un recordset.

✅ Acción requerida:

Convertir siempre category a product.public.category (recordset)

Si no existe categoría activa, usar la primera categoría pública del producto

4.3 Dominio correcto de categorías

No se deben mostrar categorías privadas o de otros websites.

✅ Acción requerida:

Usar siempre request.website.website_domain()

Buscar solo categorías raíz (parent_id = False)

4.4 No usar replace sobre product_detail (ALTO RIESGO)

Reemplazar completamente el nodo #product_detail:

rompe futuras actualizaciones,

duplica código core,

aumenta deuda técnica.

❌ Evitar:

position="replace"


✅ Usar:

inserción controlada (before)

ajuste de clases (position="attributes")

mantener el contenido core intacto

4.5 Bootstrap Grid válido (CRÍTICO UI)

Nunca insertar una columna (col-lg-*) fuera de un .row.

⚠️ Si el sidebar se inserta fuera del grid → layout roto.

✅ Acción requerida:

Verificar que product_detail esté dentro de un .row

Si no, crear el row envolvente correctamente

5. Lógica Backend Requerida (Resumen)

El controlador debe:

Ejecutar la lógica estándar (super().product)

Acceder a response.qcontext

Inyectar:

categories: categorías raíz públicas del website

category: categoría activa (recordset)

No modificar lógica de precios, variantes ni carrito

6. Lógica Frontend (QWeb)
Sidebar

Usar template estándar:

<t t-call="website_sale.products_categories_list"/>

Layout Desktop

Grid 12 columnas:

Sidebar: col-lg-3 d-none d-lg-block

Producto: col-lg-9

Mobile

Sidebar oculto (d-none d-lg-block)

Producto ocupa 100%

7. Estilos (SCSS)

Estilos mínimos

Scopeado por clase (.o_wsale_product_sidebar)

Sin overrides globales de Bootstrap

Ejemplo:

.o_wsale_product_sidebar {
    padding-right: 20px;
    border-right: 1px solid #e9ecef;
}

8. Registro de Assets y Vistas

En __manifest__.py:

Registrar XML de vistas

Registrar SCSS en web.assets_frontend

No incluir JS innecesario

9. Checklist de Validación Técnica (QA)

Antes de entregar:

 Sidebar visible solo en desktop

 Categoría activa resaltada correctamente

 Click en categoría → redirige a /shop

 Breadcrumbs siguen funcionando

 No errores en logs (NameError, AttributeError)

 No warnings de Bootstrap grid

 Compatible con modo incógnito / cache limpio

10. Riesgos y Mitigaciones
Riesgo	Mitigación
Override no ejecuta	Copiar rutas exactas del core
Category mal tipada	Normalizar siempre a recordset
Layout roto	Validar estructura .row
Deuda técnica	Evitar replace
11. Nivel de Complejidad Estimado

Media

No requiere JS

No requiere cambios en base de datos

Compatible con Odoo SH

12. Recomendación Final

Este desarrollo es técnicamente viable y alineado con buenas prácticas Odoo, siempre que:

se respete la estructura del controlador,

se mantenga el DOM core intacto,

se priorice herencia sobre reemplazo.


📄 INFORME TÉCNICO
Corrección y Optimización – Sidebar de Categorías en Ficha de Producto

Proyecto: Guapante
Plataforma: Odoo v18 – Website / eCommerce
Estado: Funcional con fallas estructurales de layout y UI
Prioridad: Alta (impacta UX y estabilidad visual)

1. Objetivo del Desarrollo

Implementar correctamente un sidebar de categorías en la ficha de producto (/shop/product) con el mismo comportamiento visual y funcional del catálogo (/shop), garantizando:

Layout en dos columnas (Sidebar izquierda + Producto derecha)

Comportamiento correcto de colapsado/estilos de categorías

Reutilización de estilos existentes (SCSS de shop)

Compatibilidad con Bootstrap y estructura core de Odoo

Ausencia de errores 500 o fallos QWeb

2. Estado Actual (Diagnóstico)

Actualmente:

✅ El sidebar se renderiza

❌ Las categorías aparecen todas desglosadas

❌ El producto no queda a la derecha, sino debajo

⚠️ El DOM queda inestable por mezcla incorrecta de row y col-*

⚠️ Existe riesgo alto de rotura en futuras actualizaciones

3. Hallazgos Críticos (Root Cause)
3.1 Error estructural Bootstrap (CRÍTICO)

Se identificaron los siguientes problemas en el XML:

❌ Hallazgo 1 – Uso incorrecto de .row en section#product_detail
<section id="product_detail" class="row guapante-product-layout">


Problema:

#product_detail ya contiene una estructura interna propia (containers/rows).

Convertirlo en .row rompe la jerarquía Bootstrap.

Sus hijos no son columnas directas (.col-*).

👉 Resultado: el sidebar y el producto no pueden convivir en la misma fila.

❌ Hallazgo 2 – Un nodo con row + col-* simultáneamente
<div class="row col-12">


Problema:

En Bootstrap, un elemento no puede ser row y col al mismo tiempo.

Esto rompe el cálculo de ancho y provoca saltos de línea.

👉 Resultado: el contenido principal cae debajo del sidebar.

❌ Hallazgo 3 – Forzar col-lg-9 sobre nodos que no son columnas reales
<div id="product_detail_main" class="col-lg-9">


Problema:

Si el nodo ya es un row o tiene layout interno, agregar col-* no lo convierte en columna válida.

Se generan “columnas fantasma”.

👉 Resultado: layout inconsistente e impredecible.

3.2 Categorías no colapsadas (CAUSA REAL)
<t t-call="website_sale.products_categories_list"/>


Problema:

products_categories_list suele ser una lista plana

El sidebar del /shop no usa ese template, sino:

website_sale.products_categories, o

un template heredado del tema Guapante

👉 Resultado: se pierde comportamiento visual (colapsado, iconos, contadores).

3.3 Sticky duplicado (RIESGO MEDIO)

Sticky aplicado en SCSS:

#products_grid_before { position: sticky; top: 90px; }


Sticky aplicado también en XML:

class="sticky-top" style="top:90px"


👉 Resultado: comportamiento errático en scroll y dificultad de mantenimiento.

4. Impacto Técnico
Impacto	Nivel
UX inconsistente	Alto
Layout Bootstrap roto	Alto
Deuda técnica	Alta
Riesgo en upgrades	Medio–Alto
Performance	Bajo
5. Estrategia de Corrección (RECOMENDADA)
Principio clave

No modificar la estructura interna de #product_detail.
Envolver y mover, nunca forzar.

6. Solución Técnica Aprobada (WRAP + MOVE)
6.1 Estrategia

Crear un wrapper externo propio

Definir correctamente:

Sidebar (col-lg-3)

Contenido (col-lg-9)

Mover el section#product_detail completo dentro del col-lg-9

Reutilizar IDs/clases de shop (#products_grid_before)

6.2 XML Final Recomendado (Estable)
<template id="product_guapante_sidebar_layout"
          inherit_id="website_sale.product"
          name="Guapante Product Sidebar Layout">

    <!-- 1) Crear wrapper correcto -->
    <xpath expr="//section[@id='product_detail']" position="before">
        <div class="container guapante-product-container">
            <div class="row guapante-product-row">
                
                <!-- Sidebar -->
                <aside id="products_grid_before"
                       class="col-lg-3 d-none d-lg-block">
                    <!-- IMPORTANTE: usar el MISMO template que /shop -->
                    <t t-call="website_sale.products_categories"/>
                </aside>

                <!-- Contenido -->
                <div class="col-12 col-lg-9 guapante-product-content">
                    <!-- aquí irá el section -->
                </div>

            </div>
        </div>
    </xpath>

    <!-- 2) Mover el section completo -->
    <xpath expr="//section[@id='product_detail']" position="move">
        <xpath expr="//div[hasclass('guapante-product-content')]" position="inside"/>
    </xpath>

</template>

7. Reglas Obligatorias para el Desarrollador
❌ NO HACER

No convertir section#product_detail en .row

No agregar col-* a nodos que ya son row

No usar position="replace" sobre vistas core

No adivinar el template de categorías

✅ SÍ HACER

Usar WRAP + MOVE

Mantener Bootstrap válido (row → col)

Usar el mismo template de categorías que /shop

Centralizar sticky solo en SCSS

8. Ajustes SCSS Requeridos

El SCSS actual es correcto

Eliminar sticky duplicado del XML

Mantener #products_grid_before como punto de anclaje

#products_grid_before {
    position: sticky;
    top: 90px;
    max-height: 80vh;
    overflow-y: auto;
}

9. Validaciones Obligatorias (QA)

 Sidebar y producto en la misma fila (desktop)

 Sidebar oculto en mobile

 Categorías colapsan igual que en /shop

 Categoría activa resaltada

 Sin errores QWeb / 500

 Sin nodos con row col-*

 Scroll sticky funciona correctamente