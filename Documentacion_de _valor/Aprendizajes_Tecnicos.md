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
