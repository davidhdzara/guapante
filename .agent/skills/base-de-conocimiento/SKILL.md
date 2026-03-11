---
name: Base de Conocimiento y Aprendizajes
description: Skill obligatoria para documentar y consultar lecciones aprendidas, errores comunes y buenas prácticas dictadas por la experiencia en el proyecto. Actúa como memoria a largo plazo.
---

# Base de Conocimiento y Lecciones Aprendidas

Esta skill es **crítica y de lectura obligatoria** antes de proponer soluciones o escribir código, y de escritura obligatoria después de resolver problemas complejos o descubrir nuevas convenciones.

Su objetivo es evitar que cometamos el mismo error dos veces y asegurar que los nuevos desarrollos hereden el conocimiento previo del proyecto.

## 1. Regla de Consulta Obligatoria (Antes de Desarrollar)

Antes de comenzar a programar una nueva funcionalidad, de proponer una arquitectura o de intentar solucionar un bug, **estás obligado a**:

1. Analizar si el problema actual o requerimiento se relaciona con integraciones complejas, quirks del framework (Odoo) o decisiones arquitectónicas previas.
2. Utilizar comandos de búsqueda (ej. `grep` o `fd`) en la carpeta `.agent/skills/base-de-conocimiento/aprendizajes/` para buscar palabras clave relacionadas con tu tarea actual.
3. Si encuentras un documento relevante, **léelo por completo** usando `view_file`.
4. Aplica estrictamente las directrices y soluciones documentadas allí. **No reinventes la rueda ni propongas soluciones que ya han fallado en el pasado.**

## 2. Regla de Documentación Obligatoria (Después de Resolver)

Si durante tu trabajo descubres:
* Un comportamiento indocumentado o contraintuitivo del framework.
* Un error recurrente y su solución definitiva.
* Una limitación técnica que nos obligó a cambiar el enfoque del diseño.
* Una convención de código estricta que no estaba documentada en otras skills.

**Estás obligado a**:

1. **PROACTIVAMENTE Y DE FORMA AUTOMÁTICA**, sin que el usuario te lo pida, crear un nuevo archivo Markdown en el directorio `.agent/skills/base-de-conocimiento/aprendizajes/`. **Esto debe ser un paso final en tu flujo normal de trabajo cada vez que finalices un desarrollo complejo o resuelvas un bug desafiante.**
2. El nombre del archivo debe ser descriptivo, en minúsculas y separado por guiones (ej. `error-cache-invalidation-odoo19.md`).
3. El contenido del archivo **debe** seguir estrictamente la siguiente plantilla:

### Plantilla Obligatoria para Nuevos Aprendizajes

```markdown
# [Título Descriptivo y Corto del Aprendizaje]

**Fecha de Registro:** [YYYY-MM-DD]
**Contexto del Problema:**
[Breve descripción de qué estábamos intentando hacer y en qué módulo/componente]

## 🚨 El Problema o Error
[Describe el error exacto, pega el log de consola relevante o explica la limitación técnica encontrada. Sé específico.]

## 🔍 Causa Raíz
[Explica *por qué* sucedía esto. Fue un fallo de sintaxis, una limitación de Odoo, un problema de asincronía, etc.]

## ✅ Solución Adoptada
[Proporciona el snippet de código exacto, comando o configuración que resolvió el problema permanentemente. Explica paso a paso si es necesario.]

## 💡 Buenas Prácticas / Cómo evitarlo
[Añade una regla heurística, advertencia o paso de validación para asegurar que este problema no vuelva a ocurrir en el futuro.]
```

## 3. Mantenimiento del Índice (Opcional pero Recomendado)

Si creas múltiples documentos relacionados con la misma categoría (ej. Frontend, Backend, Despliegue, OWL), es una buena práctica mantener un archivo `INDEX.md` en la carpeta de lecciones o agruparlos mediante etiquetas en el título.

---

## Directiva de Acción

> **Directiva de Acción Inmediata:**
> 1. Al iniciar una tarea, buscar proactivamente en `aprendizajes/`.
> 2. Al finalizar una tarea (especialmente si hubo bugs, iteraciones o se encontraron detalles técnicos específicos), **DEBES crear automáticamente un nuevo documento en `aprendizajes/`** detallando lo ocurrido antes de dar por terminada tu intervención con el usuario, sin esperar a que el usuario te indique que lo documentes.
> 3. Al documentar, asegúrate de mantener actualizado cualquier archivo `INDEX.md` correspondiente.
