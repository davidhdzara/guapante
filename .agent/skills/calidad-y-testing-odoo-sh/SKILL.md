---
name: Calidad de Código, Testing y Estándares Odoo V19 (sh)
description: Skill avanzada para asegurar que el desarrollo en Odoo V19 cumpla con los estándares de linting, tipado, arquitectura OWL y CI/CD de Odoo.sh, garantizando builds exitosos y código mantenible.
---

# Calidad de Código, Linting y Pruebas en Odoo V19.sh

Esta skill define el protocolo obligatorio para revisar, analizar y construir código que pase las validaciones automatizadas de Odoo.sh. En la V19, la rigurosidad en el tipado de Python y la estructura de componentes OWL es crítica para evitar fallos en el despliegue.

## 1. Reglas de Backend (Python & Tipado)

Odoo.sh utiliza Pylint con el plugin `pylint-odoo`. Además de PEP8, se aplican estas reglas:

* **Identación y Estilo**: 4 espacios (no tabs). Máximo 120 caracteres por línea para legibilidad, aunque el linter prefiera 88. Usa paréntesis `()` para romper líneas largas.
* **Type Hinting (V19)**: Siempre que sea posible, usa anotaciones de tipo para argumentos y retornos (ej. `def action_confirm(self) -> bool:`). Esto mejora el análisis estático y la documentación.
* **Imports y Dependencias**: 
    * Elimina imports no usados (F401).
    * Los imports deben estar ordenados: 1. Librerías estándar, 2. Librerías externas, 3. Odoo (api, fields, models), 4. Otros módulos de Odoo.
* **Manejo de Variables**: Prohibido el "shadowing" de built-ins (`id`, `list`, `type`).
* **Decoradores API**: Asegura el uso correcto de `@api.model`, `@api.depends`, y `@api.onchange`. Un `depends` con un path erróneo romperá el registro del modelo en Odoo.sh.

## 2. Reglas de Frontend (OWL & Assets)

En V19, el ecosistema OWL es el estándar absoluto.

* **Arquitectura de Componentes**: Cada componente OWL debe estar en su propio archivo. Valida que el archivo `.js` y el `.xml` (si es independiente) estén vinculados correctamente.
* **Gestión de Assets**: Todas las rutas de JS/CSS deben declararse en el `__manifest__.py` bajo la clave `'assets'`. Un archivo fuera del bundle causará errores `404` o `undefined` en el cliente.
* **JS Moderno**: Usa `es6` o superior. Prefiere `const` y `let` sobre `var`. Elimina variables no utilizadas para pasar el linter de JS de Odoo.sh.
* **Documentación JSDoc**: Comenta brevemente la función de los componentes complejos y sus `props`.

## 3. Pruebas Automatizadas (Python)

Un módulo sin tests no se considera terminado.

* **Ubicación y Carga**: Directorio `tests/`, archivos iniciados con `test_`, e importados en `tests/__init__.py`.
* **Clases de Test**:
    * `TransactionCase`: Para lógica de negocio estándar (aislado por transacción).
    * `HttpCase`: Para flujos que involucren controladores web o ejecución de Tours.
* **Datos de Prueba**: Crea registros mínimos necesarios en el `setUpTestData` o `setUp` para garantizar la independencia del test. No asumas que existen datos de la base de datos de producción.

## 4. Pruebas de Interfaz (Tours & QUnit)

* **Tours**: Cruciales para validar el flujo de usuario. Deben ser deterministas. Ubicación: `static/src/tests/tours/`.
* **OWL Mocking**: Para componentes aislados, utiliza `makeTestEnv` para simular servicios de Odoo (orm, action, notification) sin cargar todo el backend.

## 5. Archivos de Datos y XML

Errores comunes que detienen el Build en Odoo.sh:

* **Seguridad Obligatoria**: Todo modelo nuevo requiere su línea en `ir.model.access.csv`. Si falta, el test fallará con un error de acceso.
* **Dependencias de Vistas**: Si heredas una vista (`inherit_id`), el módulo que la contiene **debe** estar listado en la clave `depends` del `__manifest__.py`.
* **Nodos XPath**: Usa selectores específicos. Evita usar índices (`/div[3]`) que pueden cambiar con actualizaciones de Odoo; prefiere atributos (`@name`, `@class`).

---

## Directiva de Acción
Cada vez que finalices de maquetar código, vistas o componentes:
1. **Auto-Linter**: Revisa identación, espacios y retira imports redundantes antes de sugerir el commit.
2. **Validación de Manifest**: Comprueba que cada nuevo archivo (.py, .js, .xml, .csv) esté registrado en el `__manifest__.py` en la sección correcta.
3. **Escritura de Tests**: Si la lógica es crítica (ej. cálculos de nómina, estados de venta), genera automáticamente el esqueleto del `TransactionCase`.
4. **Cero Deuda Técnica**: No uses `# noqa`. Si el linter marca un error, corrige la estructura del código siguiendo las mejores prácticas de Odoo.
