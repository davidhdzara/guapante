# Aprendizajes Técnicos - Desarrollo Theme Guapante (Odoo 18)

Este documento recopila las lecciones aprendidas y mejores prácticas identificadas durante el proceso de desarrollo y depuración del tema Guapante.

---

## 1. Precisión en XPaths (Inyección de Vistas)

**El Desafío:** Intentar inyectar contenido en vistas existentes basándose en IDs de versiones anteriores (`snippet_structure` como `div`, `snippets_menu`) provocó errores de `ValueError: Element cannot be located`.

**El Aprendizaje:**
- No asumir la estructura del DOM de Odoo.
- En Odoo 18, el contenedor de la barra lateral de snippets es una etiqueta `<snippets id="snippet_structure">`, no un `<div>`.
- **Mejor Práctica:** Antes de escribir un XPath, consultar siempre la vista original en **Ajustes > Técnico > Interfaz de Usuario > Vistas** (buscar por `External ID`). Copiar la estructura real es la única garantía de éxito.

---

## 2. Gestión de Estilos SCSS (The "Odoo Way")

**El Desafío:** El uso de `@import` explícitos (ej: `@import "../primary_variables";`) causó errores de compilación (`Style compilation failed`) debido a problemas de resolución de rutas en el entorno de Odoo.sh.

**El Aprendizaje:**
- El sistema de assets de Odoo concatena automáticamente todos los archivos listados en el bundle `web.assets_frontend`.
- **Solución:** Eliminar los `@import` manuales.
- **Mejor Práctica:** Registrar los archivos SCSS en el `__manifest__.py` en el orden correcto de dependencia (variables primero). Esto hace que las variables (`$primary`, etc.) estén disponibles globalmente para todos los archivos siguientes sin necesidad de importarlas, evitando errores de "File not found".

---

## 3. Persistencia de la Página de Inicio (Home)

**El Desafío:** A pesar de definir la estructura de la Home en `views/pages/home.xml`, los cambios no se reflejaban automáticamente al actualizar el módulo, mostrando la página por defecto.

**El Aprendizaje:**
- Odoo protege el registro `website.homepage` para evitar sobrescribir contenido personalizado por el usuario durante una actualización de módulo.
- **Mejor Práctica:** Para visualizar la plantilla completa durante el desarrollo:
    1. Crear una página de prueba nueva (ej: `<field name="url">/demo-home</field>`).
    2. O forzar la recreación de la vista eliminando la página actual en la base de datos de desarrollo (no recomendado en producción).

---

## 4. Estructura Modular

**El Aprendizaje:** La separación estricta de componentes (un archivo XML y un SCSS por cada snippet) facilita enormemente la depuración. Si un snippet falla, se puede aislar fácilmente sin afectar al resto del tema. Es crucial mantener el `__manifest__.py` sincronizado con cada nuevo archivo añadido.

---

## 5. Herencia de Vistas y Layouts

### El Conflicto `web` vs `website`

**Situación:** Al intentar personalizar páginas de sistema (como `/web/login`), la herencia estándar de `web.login_layout` puede ser ignorada o envuelta incorrectamente si el módulo `website` está instalado.

**Comportamiento:** El módulo `website` inyecta su propio layout (`website.layout`) que incluye encabezado y pie de página de navegación, rompiendo diseños "limpios" o de pantalla completa.

**Solución:**
- Verificar siempre qué plantilla está activa usando el **Modo Desarrollador > Editar Vista**.
- Si el sistema está en contexto de sitio web, heredar de `website.login_layout` (ID externo) en lugar de `web.login_layout`.

### Control de "Chrome" (Header/Footer)

**Situación:** Necesidad de ocultar completamente el menú de navegación y el pie de página para un diseño de Login "Split-Screen" (Pantalla Partida).

**Intento Fallido:** Usar CSS (`display: none`) o intentar inyectar variables `<t t-set="no_header" t-value="True"/>` dentro del contenido del formulario. Esto falla porque el layout padre ya se ha renderizado para cuando se procesa el contenido.

**Solución Correcta (Best Practice):**

Reemplazar la llamada al layout padre usando XPath:

```xml
<xpath expr="//t[@t-call='website.layout']" position="replace">
    <t t-call="website.layout">
        <t t-set="no_header" t-value="True"/>
        <t t-set="no_footer" t-value="True"/>
        <!-- Contenido personalizado -->
    </t>
</xpath>
```

Esto garantiza que el layout padre reciba las instrucciones de ocultar elementos antes de renderizarse.

---

## 6. Debugging de Templates QWeb en Odoo 18

### Problema: XPath y Herencia de Templates

#### Error Típico
```
ValueError: Element '<xpath expr="//div[@id='products_grid_before']">' cannot be located in parent view
```

#### Causa
- El elemento buscado **no existe** en la vista base que se está heredando
- Puede ser un contenedor dinámico o pertenecer a otro template
- El error ocurre al heredar de una vista incorrecta

#### Metodología de Resolución (Trabajo en Equipo)

**🔍 Fase de Investigación:**
1. **NO asumir**: Nunca confiar en que un ID/clase CSS existe en el template QWeb
2. **Pedir ayuda al usuario**: Solicitar acceso al modo desarrollador
3. **Inspeccionar juntos**: 
   - Usuario navega: Settings > Technical > Views
   - Usuario filtra por nombre del template
   - Usuario comparte el código XML real

**✅ Soluciones Probadas:**

##### Intento 1: Heredar de `website_sale.products_categories`
❌ **Resultado**: `//ul` no encontrado (estructura encapsulada)

##### Intento 2: Heredar de `website_sale.products`
❌ **Resultado**: `#products_grid_before` no existe en esa vista

##### Intento 3: Usar `hasclass()` con div dinámico
❌ **Resultado**: `o_wsale_products_categories_collapse` solo existe condicionalmente

##### ✅ Solución Final
**Colaboración clave**: Usuario compartió el código fuente exacto de `website_sale.products_categories_list`

```xml
<!-- 1. Template standalone (reutilizable) -->
<template id="sidebar_extras_content" name="Sidebar Extras">
    <!-- Contenido de extras -->
</template>

<!-- 2. Inyección usando template base correcto -->
<template inherit_id="website_sale.products_categories_list">
    <xpath expr="//ul" position="after">
        <t t-call="theme_guapante.sidebar_extras_content"/>
    </xpath>
</template>
```

**Por qué funcionó:**
- Heredamos del template **base** correcto (no de modificaciones posteriores)
- Usamos `//ul` que está garantizado en el código fuente
- Template standalone permite reutilización

---

## 7. Iconos de Categorías: El Caso del `<span>` Fantasma

### Problema Inicial

**Error 500:**
```
ValueError: Element '<xpath expr="//span[@t-field='c.name']">' cannot be located
```

**Intento Fallido #1:**
```xml
<template inherit_id="website_sale.categories_recursive">
    <xpath expr="//span[@t-field='c.name']" position="before">
        <!-- Icono -->
    </xpath>
</template>
```

**Causa:** El template `categories_recursive` usa `<t t-call="website_sale.categorie_link"/>` - NO contiene `<span>` directamente.

### La Investigación Colaborativa

**Paso 1:** Usuario compartió estructura de `categories_recursive` → Descubrimos el `t-call`

**Paso 2:** Pedimos el template `website_sale.categorie_link` → Usuario lo encontró en Views:

```xml
<a t-att-href="..." t-field="c.name"/>
```

**Revelación:** ¡No hay `<span>`! El nombre se renderiza directamente en el `<a>` con `t-field`.

### ✅ Solución Final

```xml
<template id="categorie_link_guapante" inherit_id="website_sale.categorie_link">
    <xpath expr="//a[@t-field='c.name']" position="replace">
        <a t-att-href="keep('/shop/category/' + slug(c), category=0)" 
           t-attf-class="{{c.id == category.id and 'text-decoration-underline'}} p-0 d-flex align-items-center">
            <!-- Icono -->
            <t t-if="c.image_128">
                <span t-field="c.image_128" t-options="{'widget': 'image', ...}"/>
            </t>
            <t t-else="">
                <i class="fa fa-leaf me-2 text-muted opacity-50"/>
            </t>
            <!-- Nombre -->
            <span t-field="c.name"/>
        </a>
    </xpath>
</template>
```

**Beneficio:** Reemplazo completo del enlace = control total de la estructura.

---

## 8. Lecciones de Trabajo en Equipo

### 🤝 Colaboración Efectiva

**Lo que funcionó:**
1. **Pedir ayuda temprano**: En lugar de hacer 10 intentos ciegos, solicitar acceso al código fuente real
2. **Usuario como co-investigador**: David navegó el modo desarrollador y compartió templates exactos
3. **Iteración rápida**: Confirmación antes de cada cambio = menos commits fallidos

**Herramientas Clave:**
- **Modo Desarrollador** de Odoo (acceso a Views)
- **Inspector HTML** (ver estructura renderizada vs. template)
- **Git branches** (prueba y error sin romper main)

### 📋 Checklist de Debugging de Templates

Antes de escribir un XPath:

- [ ] ¿Tengo acceso al código fuente del template padre?
- [ ] ¿He verificado que el elemento existe en ESE template específico?
- [ ] ¿Estoy heredando del template BASE o de una modificación posterior?
- [ ] ¿El elemento es estático o se genera condicionalmente?
- [ ] Si no encuentro el elemento, ¿he pedido ayuda al usuario para inspeccionarlo?

**Regla de Oro:** Cuando dudes, pregunta. El usuario tiene acceso a información que el asistente no puede inferir.

---

## 9. Scoped CSS y Desarrollo de Temas

**Mejor Práctica:** Encapsular estilos personalizados para evitar conflictos con backend o formularios del sitio.

**Ejemplo:** Usar contenedor `.auth-form-col` y anidar estilos en SCSS:

```scss
.auth-form-col {
    input.form-control {
        // Estilos específicos
    }
}
```

---

## 10. Flujo de Trabajo (Git Flow & Staging)

### Validación Visual
- Los cambios visuales complejos (layouts, templates) deben probarse en staging si el entorno local difiere (Enterprise vs Community)
- **No Asumir**: Validar IDs de vistas en el entorno de destino ahorra ciclos de prueba y error

### Commits Atómicos
- Un commit = una funcionalidad o fix
- Mensajes descriptivos: `"Fix: Category icons using categorie_link inheritance"`
- Facilita el rollback si algo falla

---

## Recursos y Referencias

- [Documentación Oficial Odoo 18 - QWeb](https://www.odoo.com/documentation/18.0/developer/reference/frontend/qweb.html)
- [Modo Desarrollador - Guía](https://www.odoo.com/documentation/18.0/applications/general/developer_mode.html)
- **Path a Views en Odoo**: Settings > Technical > User Interface > Views

---

**Última actualización:** Enero 2026  
**Autor:** Equipo Guapante (David + AI Assistant)

---

## 11. Sidebar en Ficha de Producto (Enero 2026)

### ❌ CRÍTICO: `position="move"` NO está soportado en Odoo 18 (esta instancia)

**Error recibido:**
```
ValueError: Atributo de posición no válido: 'move'
```

**Contexto:** Intentamos usar `<xpath expr="//section[@id='product_detail']" position="move">` para reubicar el section dentro de un wrapper.

**Aprendizaje:**
- El atributo `position="move"` **NO está disponible** en todas las instalaciones de Odoo 18.
- Aunque está documentado en versiones recientes, depende de la versión específica del servidor.
- **Regla:** Si un comando XPath causa Error 500, **preguntar inmediatamente al usuario** en lugar de seguir iterando.

---

### ❌ VIOLACIÓN BOOTSTRAP: NO mezclar `row` y `col` en el mismo nodo

**Error cometido:**
```xml
<!-- ❌ INCORRECTO -->
<xpath expr="//section[@id='product_detail']" position="attributes">
    <attribute name="class" add="row"/>
</xpath>
<!-- Luego intentar insertar col-3 y col-9 como hermanos -->
```

**Problema:** 
- `section#product_detail` ya contiene estructura interna propia (containers, rows).
- Convertirlo en `.row` rompe la jerarquía de Bootstrap.
- Un elemento NO puede ser `row` y `col` simultáneamente.

**Solución correcta:**
- Crear un **wrapper externo** con `container > row` ANTES del section original.
- NO modificar las clases internas del section.
- Insertar columnas (`col-3` sidebar, `col-9` contenido) dentro del nuevo row.

**Documentado en:** `sidebar.md` sección "Hallazgos Críticos".

---

### ✅ SOLUCIÓN IMPLEMENTADA: Wrapper + JS Fallback

**Estrategia final (debido a limitación de `move`):**

1. **XML:** Crear wrapper vacío con estructura correcta:
```xml
<div class="container guapante-product-container">
    <div class="row">
        <aside id="products_grid_before" class="col-lg-3">
            <!-- Sidebar -->
        </aside>
        <div class="col-lg-9 guapante-product-content">
            <!-- Vacío inicialmente -->
        </div>
    </div>
</div>
```

2. **XML:** Ocultar section original con `d-none` (prevención FOUC):
```xml
<xpath expr="//section[@id='product_detail']" position="attributes">
    <attribute name="class" add="d-none"/>
</xpath>
```

3. **JS:** Mover el DOM al cargar (`product_layout_fix.js`):
```javascript
$('.guapante-product-content').append($('#product_detail'));
$('#product_detail').removeClass('d-none');
```

**Ventajas:**
- Cumple Bootstrap (estructura válida en el DOM final).
- Evita Error 500 (no usa `move` de XML).
- Previene FOUC (Flash of Unstyled Content).

**Desventajas:**
- **Dependencia crítica de JS:** Si el asset falla, el layout se rompe completamente.
- Mayor complejidad de debugging.

---

### ⚠️ Templates Sidebar: `products_categories` vs `products_categories_list`

**Error recibido al intentar `products_categories`:**
```
File "<2432>", line 5, in not_found_template
```

**Aprendizaje:**
- `website_sale.products_categories` → NO existe en esta instalación.
- `website_sale.products_categories_list` → Existe, pero es lista plana (sin colapsado).

**Regla de Oro:**
- **NUNCA asumir** que un template existe.
- **SIEMPRE preguntar al usuario** qué template se usa en `/shop` antes de replicarlo en `/shop/product`.
- Si un `t-call` falla con 500, reportar el error de inmediato y pedir al usuario que confirme el nombre correcto del template.

---

### 📋 Checklist Antes de Iterar en el Mismo Problema

**Si llevo más de 3 intentos fallidos:**

1. ✅ ¿He pedido al usuario que me comparta el HTML renderizado?
2. ✅ ¿He pedido logs del servidor o mensaje de error completo?
3. ✅ ¿He preguntado explícitamente si la funcionalidad X está disponible en su versión?
4. ✅ ¿He actualizado `Aprendizajes_Tecnicos.md` con el bloqueo?

**Si la respuesta a cualquiera es NO → DETENERME y pedir ayuda al usuario.**

---

### 🎯 Reglas de Trabajo Confirmadas

1. **Generar desarrollos** según sea encargado.
2. **Leer TODA la documentación** en `Documentacion_de_valor` antes de empezar.
3. **Actualizar `Aprendizajes_Tecnicos.md`** con cada descubrimiento importante.
4. **NO adivinar:** Preguntar dudas y pedir información (HTML, vistas, errores, logs).
5. **Máximo 3 intentos** en el mismo problema sin pedir ayuda al usuario.

