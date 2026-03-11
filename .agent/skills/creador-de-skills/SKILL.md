---
name: Creador de Skills
description: Una skill diseñada para guiar en la creación de nuevas skills de forma estructurada, siguiendo la documentación oficial de Antigravity.
---

# Creador de Skills

Esta skill tiene como propósito principal guiarte en el proceso de creación de nuevas skills para Antigravity.

## Estructura de una Skill

Las skills son carpetas que contienen instrucciones, scripts y recursos para extender las capacidades en tareas especializadas. Cada skill debe contener al menos:

1. **`SKILL.md` (Obligatorio)**: El archivo principal de instrucciones. Debe incluir:
   - Frontmatter en formato YAML con `name` y `description`.
   - Instrucciones detalladas en formato Markdown sobre cómo la skill debe ser utilizada.

Las skills más complejas pueden incluir directorios adicionales, por ejemplo:
- **`scripts/`**: Scripts auxiliares y utilidades que extienden las capacidades.
- **`examples/`**: Implementaciones de referencia y patrones de uso.
- **`resources/`**: Archivos adicionales, plantillas o recursos que la skill pueda referenciar.

## Pasos para crear una nueva Skill

Cuando el usuario solicite crear una nueva skill, sigue estos pasos rigorosamente:

1. **Definir el propósito**: Comprende exactamente qué problema resolverá la skill y qué herramientas o scripts necesitará.
2. **Crear el directorio de la skill**: Crea una nueva carpeta para la skill dentro del directorio `.agent/skills/` (o el directorio de skills correspondiente del proyecto). El nombre de la carpeta debe ser descriptivo, en minúsculas y separado por guiones (ejemplo: `mi-nueva-skill`).
3. **Crear el archivo `SKILL.md`**: En la raíz de la nueva carpeta, crea el archivo `SKILL.md` con el siguiente contenido base:
   ```yaml
   ---
   name: [Nombre de la Skill]
   description: [Breve descripción de lo que hace la skill]
   ---
   ```
   A continuación del frontmatter, redacta las instrucciones en Markdown detallando cómo utilizar la skill, qué pasos seguir y qué advertencias o reglas aplicar.
   **Obligatorio:** Finaliza siempre el documento con una sección llamada `## Directiva de Acción` que contenga un listado rápido de 3 a 5 puntos resumiendo cómo el asistente debe actuar cuando se encuentre en el contexto de esa skill.
4. **Directorios opcionales**: Si la skill es compleja, crea las carpetas `scripts/`, `examples/` y/o `resources/` según corresponda y agrega los archivos necesarios.
5. **Revisar y validar**: Asegúrate de que las instrucciones en `SKILL.md` sean claras, precisas y accionables para el asistente.

## Reglas importantes

- Siempre utiliza rutas absolutas al referenciar archivos dentro de la skill.
- Las instrucciones en `SKILL.md` deben ser directas. Describe *qué* debe hacer el agente y *cómo* debe hacerlo.
- Mantén el contenido en el idioma solicitado por el usuario (por defecto asume el idioma en el que se hizo la petición).

## Directiva de Acción

- Comprende el propósito de la skill solicitada antes de crear cualquier archivo.
- Crea el directorio de la skill y el archivo `SKILL.md` con el formato YAML frontmatter esperado.
- Redacta instrucciones directas y con rutas absolutas, detallando el qué y el cómo.
- Incluye siempre una sección "Directiva de Acción" al final del `SKILL.md` recién creado.
- Si es necesario, crea los directorios adicionales (`scripts`, `examples`, `resources`).

---
*Nota: Esta base sigue las directrices oficiales de creación de skills de Antigravity.*
