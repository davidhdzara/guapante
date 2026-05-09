---
name: Identidad de Marca Guapante
description: Guía oficial de identidad visual, tono de comunicación y directrices estéticas para el desarrollo frontend y UX del sitio web y eCommerce de Guapante.
---

# Identidad de Marca y UI/UX - Guapante

Esta skill define las pautas visuales y comunicacionales que todo agente debe seguir estrictamente al desarrollar, modificar o proponer cambios en el frontend del sitio web y eCommerce de Guapante. El objetivo es mantener una experiencia de usuario consistente, moderna y de nivel "Premium".

## 1. Tipografía

La tipografía oficial del proyecto es **Inter** (Google Fonts), elegida por su legibilidad y aspecto moderno y limpio.
- **Pesos permitidos:** 400 (Regular), 500 (Medium), 600 (Semi-bold), 700 (Bold).
- **Jerarquía:** 
  - Los títulos (h1-h6) suelen usar peso 600 o 700.
  - El texto base utiliza 400.
  - Los botones y etiquetas de navegación (navbar) utilizan 500 o 600.
- *Nota Técnica:* En SCSS, forzar la fuente si Odoo la sobreescribe usando `font-family: 'Inter', sans-serif !important;`.

## 2. Paleta de Colores

Evitar el uso de colores genéricos de Bootstrap a menos que coincidan con la identidad. Preferir el uso de variables SCSS o colores hex específicos:

- **Brand Dark Green (Verde Oscuro):** `#155724` — Utilizado para títulos principales, contrastes fuertes y elementos de confianza. (Clase de utilidad sugerida: `.text-dark-green`).
- **Brand Success / Primary (Verde Vibrante):** Se utiliza el verde `success` de Bootstrap de Odoo como color principal de acción (Botones "Agregar al carrito", radios seleccionados, badges de ofertas).
- **Texto Principal (Soft Black):** `#1A1A1A` — Evitar el negro puro (`#000000`) para reducir la fatiga visual.
- **Fondos Neutros:** `#f3f4f6` o `bg-light` — Para separar secciones, tarjetas o campos de búsqueda sin usar bordes pesados.
- **Bordes Suaves:** `#e5e7eb` — Para divisores sutiles (`dropdown-divider`, borders de tarjetas).

## 3. Tono de Comunicación (Copywriting)

Guapante atiende tanto a clientes finales (hogares) como a clientes corporativos B2B (restaurantes, mayoristas).
- **Personalidad:** Profesional, fresco, transparente y cercano.
- **Mensaje Central:** *"Llevamos lo mejor del campo colombiano a tu hogar o negocio con transparencia, frescura y sostenibilidad."*
- **Tuteo vs. Ustedeo:** Se utiliza un **tuteo respetuoso** y directo (ej. "Ingresa a tu cuenta", "Llevamos a tu hogar").
- **Palabras Clave:** Frescura, Campo, Sostenibilidad, Agro, Mayorista, Calidad Premium.
- **Evitar:** Jerga técnica, lenguaje burocrático o mensajes de error genéricos del sistema. (ej. Cambiar "Internal Server Error" por algo amigable si es posible a nivel de interfaz).

## 4. Estética de Diseño (Premium UI)

Todo desarrollo frontend debe apuntar a una experiencia de usuario que diga "Premium":
- **Sombras (Shadows):** Usar sombras muy suaves y amplias, nunca duras. (Ejemplo: `box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08)`).
- **Bordes Redondeados (Border Radius):** Los botones, tarjetas y dropdowns no deben ser cuadrados. Utilizar `rounded-3`, `rounded-4` o `rounded-pill` (`50rem`).
- **Transiciones (Micro-interacciones):** Todo elemento interactivo (hover en botones, enlaces, tarjetas) debe tener una transición suave. (Ejemplo: `transition: all 0.2s ease` o `0.3s ease`).
- **Espaciado (Whitespace):** Diseños aireados. Usar generosamente los paddings y margins de Bootstrap (`p-3`, `pt-5`, `gap-3`) en lugar de amontonar la información.
- **Limpieza visual:** Ocultar elementos innecesarios mediante menús desplegables (drawers, dropdowns, accordions) en móvil en lugar de mostrar listas interminables.

## 5. Elementos de UI Propios del eCommerce

- **Unit Selector (Selector de unidad):** Es el corazón de la compra en Guapante (Kg, g, Unidad). Debe verse como un control nativo, destacando claramente la selección activa (usualmente botones radio estilizados).
- **Botón "Agregar al Pedido":** Debe ser grande, de alto contraste (verde success), con icono descriptivo, e invitar a la acción.
- **Skeletons (Cargas de estado):** Preferir animaciones de esqueleto pulsante (pulse) en lugar de spinners giratorios genéricos al cargar catálogos o variaciones.

---

## Directiva de Acción

- **Diseño sin placeholders:** Si construyes un layout, utiliza los colores de la marca, no colores genéricos como fondo rojo o azul para "probar".
- **Coherencia tipográfica:** Asegúrate de importar e instanciar `Inter` en cualquier nuevo componente de Odoo que desarrolles.
- **Auditoría visual:** Antes de entregar un desarrollo frontend, verifica que existan transiciones (hover effects), sombras sutiles y bordes redondeados acordes a la guía.
- **Copywriting alineado:** Si creas textos de prueba o mensajes de error estáticos en las vistas QWeb, asegúrate de que suenen amigables y enfocados en la calidad/sostenibilidad del campo.
