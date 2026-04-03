---
name: "[OBLIGATORIA] Metodología de Trabajo y Perfil del Usuario InSoTech"
description: Documento maestro que define la dinámica de trabajo, el nivel de exigencia visual (SaaS B2B) y las preferencias arquitectónicas del usuario principal del proyecto InSoTech. Todo agente debe leer esto ANTES de escribir código.
---

# Perfil del Usuario y Metodología de Trabajo InSoTech

Este documento es una **guía obligatoria** para cualquier agente de IA que interactúe en el proyecto `theme_insotech`. Define cómo piensa el usuario, qué espera recibir y cuál es el estándar de calidad innegociable.

## 1. El Estándar Visual: "Ultra Premium B2B SaaS"

El usuario no está construyendo un sitio web genérico ni una plantilla básica de Odoo. Está construyendo el front-end de un **ERP SaaS de Próxima Generación** (InSoTech).

*   **Mindset del Usuario:** Tiene un "ojo afilado" para el diseño UI/UX. Nota detalles como la falta de contraste (ej. texto negro sobre fondo oscuro), secciones monótonas ("Ceguera de Sección") e inconsistencias en los padding/margins.
*   **Lo que ABORRECE:**
    *   Diseños anticuados, genéricos o que parezcan el "por defecto" de Bootstrap/Odoo.
    *   "HTML Spaghetti" (código desordenado).
    *   Uso de fotos de stock de oficinistas sonriendo (prefiere iconografía vectorial fina y limpia).
    *   Colores que no respeten la paleta corporativa estricta (`#003498` - Azul Primario).
*   **Lo que ESPERA (El factor "Wow"):**
    *   Diseños limpios, con mucho espacio en blanco (breathing room).
    *   Uso estratégico de **Zebra Striping** (intercalar fondos blancos y grises claros `bg-light`).
    *   Implementación de sombras suaves (`shadow-sm`, `box-shadow` fino), bordes redondeados (`rounded-3`, `rounded-4`) y efectos de hover elegantes (ej. transiciones suaves `transform: translateY()`).
    *   Secciones de **Dark Mode** estratégicas (ej. CTA final en azul profundo con texto blanco) para generar urgencia.

## 2. Metodología de Interacción (Flujo de Trabajo)

El usuario prefiere un flujo de trabajo de **"Co-creación Dirigida"**. No ejecutes acciones masivas a ciegas.

1.  **Analiza e Imagina Primero:** Cuando el usuario pide una nueva sección o snippet, espera que el agente actúe como un "Product Designer / Arquitecto de Software". 
2.  **Propón un Plan (Implementation Plan):** Antes de escribir 100 líneas de XML, descríbele brevemente cómo lo vas a estructurar (ej. *"Voy a hacer 4 columnas, usar estos iconos y aplicarle un hover B2B"*).
3.  **Espera Aprobación (Procede):** El usuario evalúa la lógica. Si le hace sentido, te dará la orden ("procede"). Si detecta una incongruencia (ej. prometer una certificación ISO 27001 que la empresa no tiene), te corregirá (InSoTech es muy honesto en su propuesta de valor B2B).
4.  **Ejecuta con Precisión Quirúrgica:** Escribe el código, haz los commits granulares (`[ADD]`, `[FIX]`, `[IMP]`) en la rama actual (`dev_index` u otra), y notifícale para que revise en pantalla.

## 3. Filosofía Arquitectónica: Reusabilidad (Snippets First)

El usuario tiene una visión a largo plazo para InSoTech. No quiere páginas estáticas; quiere un **ecosistema de Odoo puro**.

*   **NUNCA "hardcodees" (escribas en crudo) HTML en vistas de páginas.** (Revisa la skill *[OBLIGATORIA] Ensamblaje de Páginas Odoo V19*).
*   **Regla de Oro:** Todo diseño visual nuevo **DEBE** convertirse en un Snippet (`s_nombre_del_bloque.xml`), registrarse en el Website Builder y luego ser inyectado (llamado) en la página correspondiente.
*   **CSS Aislado:** El usuario detesta que el SCSS global se rompa. Prefiere inyectar etiquetas `<style type="text/css">` "aisladas" (scoped) directamente dentro del XML del snippet para manejar efectos hover específicos sin contaminar el `theme.scss`.

## 4. Honestidad y Feedback

*   **Reconoce los errores:** Si como agente cometes un fallo (ej. usar un XPath antiguo de Odoo V16 en V19), el usuario valora que lo reconozcas, lo corrijas y, sobre todo, **que documentes el aprendizaje en la Base de Conocimiento** para que los futuros agentes no repitan el error.
*   **Aporta Valor Consultivo:** El usuario espera que tú le digas *"Esto que me pides funciona, pero en un entorno B2B SaaS, lo más profesional sería hacerlo de esta otra manera..."*. ¡Sé proactivo en el diseño UI/UX!

---
**Recuerda, futuro agente:** Estás trabajando con un emprendedor/arquitecto tecnológico que busca calidad empresarial y estética premium. Tu código y tu diseño deben estar a la altura de un producto que vale miles de dólares anuales.
