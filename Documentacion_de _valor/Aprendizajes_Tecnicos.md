# Aprendizajes Técnicos - Desarrollo Theme Guapante (Odoo 18)

Este documento recopila las lecciones aprendidas y mejores prácticas identificadas durante el proceso de desarrollo y depuración del tema Guapante.

## 1. Precisión en XPaths (Inyección de Vistas)
**El Desafío:** Intentar inyectar contenido en vistas existentes basándose en IDs de versiones anteriores (`snippet_structure` como `div`, `snippets_menu`) provocó errores de `ValueError: Element cannot be located`.

**El Aprendizaje:**
*   No asumir la estructura del DOM de Odoo.
*   En Odoo 18, el contenedor de la barra lateral de snippets es una etiqueta `<snippets id="snippet_structure">`, no un `<div>`.
*   **Mejor Práctica:** Antes de escribir un XPath, consultar siempre la vista original en **Ajustes > Técnico > Interfaz de Usuario > Vistas** (buscar por `External ID`). Copiar la estructura real es la única garantía de éxito.

## 2. Gestión de Estilos SCSS (The "Odoo Way")
**El Desafío:** El uso de `@import` explícitos (ej: `@import "../primary_variables";`) causó errores de compilación (`Style compilation failed`) debido a problemas de resolución de rutas en el entorno de Odoo.sh.

**El Aprendizaje:**
*   El sistema de assets de Odoo concatena automáticamente todos los archivos listados en el bundle `web.assets_frontend`.
*   **Solución:** Eliminar los `@import` manuales.
*   **Mejor Práctica:** Registrar los archivos SCSS en el `__manifest__.py` en el orden correcto de dependencia (variables primero). Esto hace que las variables (`$primary`, etc.) estén disponibles globalmente para todos los archivos siguientes sin necesidad de importarlas, evitando errores de "File not found".

## 3. Persistencia de la Página de Inicio (Home)
**El Desafío:** A pesar de definir la estructura de la Home en `views/pages/home.xml`, los cambios no se reflejaban automáticamente al actualizar el módulo, mostrando la página por defecto.

**El Aprendizaje:**
*   Odoo protege el registro `website.homepage` para evitar sobrescribir contenido personalizado por el usuario durante una actualización de módulo.
*   **Mejor Práctica:** Para visualizar la plantilla completa durante el desarrollo:
    1.  Crear una página de prueba nueva (ej: `<field name="url">/demo-home</field>`).
    2.  O forzar la recreación de la vista eliminando la página actual en la base de datos de desarrollo (no recomendado en producción).

## 4. Estructura Modular
**El Aprendizaje:** La separación estricta de componentes (un archivo XML y un SCSS por cada snippet) facilita enormemente la depuración. Si un snippet falla, se puede aislar fácilmente sin afectar al resto del tema. Es crucial mantener el `__manifest__.py` sincronizado con cada nuevo archivo añadido.

Aprendizajes Técnicos - Desarrollo de Temas Odoo 18
Este documento recopila lecciones clave aprendidas durante el desarrollo del tema 
theme_guapante
, específicamente en Odoo 18 (Enterprise/Community) con el módulo de Website/Ecommerce instalado.

1. Herencia de Vistas y Layouts
El Conflicto 
web
 vs website
Situación: Al intentar personalizar páginas de sistema (como /web/login), la herencia estándar de web.login_layout puede ser ignorada o envuelta incorrectamente si el módulo website está instalado.
Comportamiento: El módulo website inyecta su propio layout (website.layout) que incluye encabezado y pie de página de navegación, rompiendo diseños "limpios" o de pantalla completa.
Solución:
Verificar siempre qué plantilla está activa usando el Modo Desarrollador > Editar Vista.
Si el sistema está en contexto de sitio web, heredar de website.login_layout (ID externo) en lugar de web.login_layout.
Control de "Chrome" (Header/Footer)
Situación: Necesidad de ocultar completamente el menú de navegación y el pie de página para un diseño de Login "Split-Screen" (Pantalla Partida).
Intento Fallido: Usar CSS (display: none) o intentar inyectar variables <t t-set="no_header" t-value="True"/> dentro del contenido del formulario. Esto falla porque el layout padre ya se ha renderizado para cuando se procesa el contenido.
Solución Correcta (Best Practice):
Reemplazar la llamada al layout padre usando XPath:
<xpath expr="//t[@t-call='website.layout']" position="replace">
    <t t-call="website.layout">
        <t t-set="no_header" t-value="True"/>
        <t t-set="no_footer" t-value="True"/>
        <!-- Contenido personalizado -->
    </t>
</xpath>
Esto garantiza que el layout padre reciba las instrucciones de ocultar elementos antes de renderizarse.
2. Desarrollo de Temas y CSS
Scoped CSS (Estilos Encapsulados)
Para evitar conflictos con el backend o con otros formularios del sitio, es vital encapsular estilos personalizados.
Ejemplo: Usar un contenedor .auth-form-col y anidar todos los estilos de inputs y botones dentro de él en el SCSS (
theme_guapante/static/src/scss/pages/_auth.scss
).
3. Flujo de Trabajo (Git Flow & Staging)
Validación Visual: Los cambios visuales complejos (como layouts) deben probarse en un entorno lo más cercano a producción (staging) si el entorno local no tiene los mismos módulos (ej. Enterprise vs Community).
No Asumir: Antes de escribir herencias complejas, validar el ID de la vista en el entorno de destino ahorra ciclos de prueba y error.
