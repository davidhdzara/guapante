---
name: Buenas Prácticas Odoo V19 y Odoo.sh
description: Una skill que define las mejores prácticas, convenciones de calidad de código y directrices específicas para el desarrollo en Odoo V19 sobre la plataforma Odoo.sh.
---

# Buenas Prácticas de Desarrollo en Odoo V19 y Odoo.sh

Esta skill proporciona una guía de referencia estricta para el desarrollo de módulos en Odoo V19, asegurando la calidad del código, el cumplimiento de los estándares de Odoo.sh y la mantenibilidad a largo plazo.

## 1. Directrices Específicas de Odoo V19

Al desarrollar para Odoo V19, es obligatorio tener en cuenta los siguientes cambios arquitectónicos y requerimientos:

*   **Python 3.10+**: Odoo V19 requiere Python 3.10 o superior. Aprovecha las características modernas de Python y asegúrate de la compatibilidad.
*   **Manejo del Contexto**: El uso legacy de `self._context` está obsoleto. Utiliza siempre `self.env.context` para garantizar consistencia y facilitar actualizaciones seguras.
*   **Desarrollo Frontend (OWL)**: Siempre prioriza el uso de componentes OWL y sus mejoras en la gestión del ciclo de vida.
*   **Motor de Plantillas (QWeb)**:
    *   Utiliza la nueva estructura de `inheritance mode="inner"` para una sobreescritura más fácil del contenido de las plantillas.
    *   Migra cualquier uso de `t-esc` a `t-out` y asegúrate de su correcto uso.
*   **Grupos de Seguridad**: La arquitectura de los grupos de seguridad se ha renovado. Presta especial atención a la correcta implementación de las reglas de registro y los derechos de acceso en la nueva versión.

## 2. Desarrollo y Calidad de Código en Odoo.sh

Odoo.sh impone validaciones de linting estrictas en cada commit. Para evitar que las compilaciones (builds) fallen o se marquen con advertencias amarillas (Warning), sigue estas reglas:

### 2.1. Python (PEP8 modificado para Odoo)

*   **Líneas largas (E501)**: Aunque el linter oficial a veces lo ignora, **siempre** divide las líneas excesivamente largas (más de 80-88 caracteres) por mantenibilidad, usando paréntesis para agrupar expresiones.
*   **Imports no utilizados (F401)**: Nunca dejes dependencias no utilizadas en el código. Esto ensucia el espacio de nombres. Elimínalos siempre.
*   **Estructura de Imports**: Agrúpalos en 3 bloques separados por una línea en blanco y ordenados alfabéticamente:
    1. Librerías estándar/externas de Python.
    2. Importaciones del core de Odoo.
    3. Importaciones de módulos custom de Odoo.
*   **Indentación**: Obligatorio el uso de 4 espacios exactos por nivel. Nunca uses tabulaciones.
*   **Líneas en blanco**: Usa dos líneas en blanco para separar definiciones de clases, y una línea en blanco para separar los métodos en una clase.

### 2.2. JavaScript (Frontend)

*   **Modo Estricto**: Asegúrate de incluir `'use strict';` al principio de los archivos JS si el entorno de Odoo no lo hace o si usas directrices legacy.
*   **Convención CamelCase**: En JavaScript utiliza *siempre* `camelCase` para variables, en contraste con el `snake_case` de Python. Alinear con el ecosistema global de JavaScript es imprescindible al usar OWL.

### 2.3. Estructura y Convenciones de los Modelos (Python)

*   **Nomenclatura**:
    *   Variables comunes: `snake_case` (ej. `partner_count = 10`).
    *   Recordsets: `CamelCase` (ej. `Partners = self.env['res.partner']`).
    *   Campos relacionales: sufijo `_id` para `Many2one` y `_ids` para `One2many`/`Many2many`.
    *   Métodos: Usar `_compute_<campo>`, `_default_<campo>`, `action_<accion>`.
*   **Orden de Atributos en Modelos**:
    Para una máxima legibilidad, los atributos dentro de una clase deben seguir este orden estricto:
    1. Atributos privados (`_name`, `_inherit`, `_description`).
    2. Métodos de valores por defecto (`_default_<field_name>`).
    3. Declaraciones de campos.
    4. Métodos compute (`@api.depends`).
    5. Métodos constrains (`@api.constrains`) y onchange (`@api.onchange`).
    6. Métodos CRUD sobreescritos (`create`, `write`, `unlink`).
    7. Métodos de acción (`action_`).
    8. Otros métodos de negocio.
*   **Transacciones**: ¡**NUNCA** utilices `self.env.cr.commit()`! Deja que el framework de Odoo gestione las transacciones para evitar inconsistencias graves de datos. Romper la atomicidad conlleva consecuencias severas.

## 3. El Patrón Arquitectónico y Estructura del Módulo

Para mantener la coherencia y facilitar el mantenimiento, todos los módulos de InSoTech deben seguir estrictamente la siguiente **Estructura Completa de un Módulo Odoo**:

### 3.1. Archivos Obligatorios en la Raíz
*   `__manifest__.py`: Define la identidad del módulo (Nombre, Autor, Dependencias, archivos XML a cargar y status de aplicación).
*   `__init__.py`: Realiza los imports de Python hacia las carpetas `models`, `wizard`, y `controllers`.

### 3.2. Estructura de Carpetas Clave
1.  **`models/` (Lógica de negocio)**: El "Heart" del negocio. Contiene `__init__.py` y tus modelos (`.py`). Aquí van los *Fields*, *Methods*, *Constraints*, *Overrides* (create, write), y métodos *Compute/Onchange*.
2.  **`views/` (Interfaz / UI)**: Vistas de formulario (`form`), vistas de árbol (`tree`/list), acciones de ventana, menús y botones (Archivos `.xml`).
3.  **`security/` (Permisos y Reglas)**: 
    *   `ir.model.access.csv`: Permisos básicos CRUD (Leer, Crear, Escribir, Borrar).
    *   `security.xml`: Definición de Grupos, Reglas de registro (Record Rules) y Reglas de dominio.
4.  **`data/` (Datos auto-cargados)**: Secuencias, parámetros, configuraciones, plantillas de correo y automatizaciones que se cargan al instalar (Archivos `.xml`).
5.  **`demo/` (Datos de demostración)**: Datos que se cargan solo si se selecciona la opción de "Load demo data" (Archivos `.xml`).
6.  **`wizard/` (Asistentes Temporales)**: Uso de `TransientModel` para procesos temporales, confirmaciones emergentes o flujos paso a paso.
7.  **`report/` (Generación de Documentos)**: Informes QWeb PDF, plantillas de impresión, acciones de reporte y diseños (Archivos `.xml`).
8.  **`controllers/` (Rutas Web/HTTP)**: Endpoints HTTP, Webhooks, Portales e Integraciones de API externas (`@http.route`).
9.  **`static/` (Frontend y Assets)**: Componentes JS OWL, CSS/SCSS, e imágenes. Utilizado para TPV, el Sitio Web y personalización dinámica en el cliente.
10. **`tests/` (Garantía y Estabilidad)**: Tests automatizados de Python para asegurar que tu código no rompa flujos existentes.

### 3.3. Estructura Mínima Realista
Incluso el módulo más pequeño debería aspirar a tener este núcleo funcional: 
*   **Form** (Vista de Formulario para editar)
*   **Tree views** (Vista de Lista para visualizar múltiples registros)
*   **Interfaz** y **Menús** para acceder a las vistas
*   **Integraciones** (Opcional, si afecta otros módulos)
*   **List Izidas opcionales** (Vistas alternativas como Kanban o Pivot si aplica)

### 3.4. Resumen Mental y Flujo de Ejecución (Odoo V19)
Mentalmente, piensa en un módulo así: **Identidad** (`manifest`) > **Lógica** (`models`) > **Interfaz** (`views`) > **Permisos** (`security`) > **Datos base** (`data`).

**El flujo del sistema se comporta así:**
1.  **Acción del Usuario**: El usuario interactúa con la vista (ej. Hace clic en un botón).
2.  **Llamada Python**: La vista llama al método en el backend python.
3.  **Interactúa ORM**: El método procesa y consulta la BD a través del ORM.
4.  **Validación de Seguridad**: El sistema verifica permisos y reglas de registro.
5.  **Resultado a Vista**: Devuelve los datos procesados.
6.  **Genera reporte/acción**: Activa una transacción, descarga un informe o abre un Wizard.

## 3. Mejores Prácticas en XML y Datos

Todos los cambios estructurales e iniciales en Odoo dependen de archivos XML o CSV correctamente formados:

*   **Permisos de Acceso (`ir.model.access.csv`)**: Es vital definir e incluir explícitamente este archivo en la clave `data` del archivo `__manifest__.py`. Su omisión genera errores de permisos en la interfaz y modelos inaccesibles.
*   **Estructura XML**: En etiquetas `<record>`, siempre coloca el atributo `id` primero, seguido de `model`. Al usar `<field>`, el atributo `name` debe declararse primero por consistencia.
*   **Modificación de Vistas**: Al extender/modificar atributos existentes en XML heredados, utiliza `position="attributes"` en lugar de `position="replace"` para evitar sobreescribir lógica originada de otros módulos sin intención.
*   **IDs XML**: Usa identificadores XML (XML IDs) externos constantes en tu código en lugar de IDs fijos de base de datos para garantizar la portabilidad e integridad en futuras actualizaciones.

### Convenciones de Nomenclatura para IDs XML:

*   **Vista XML id**: `<model_name>_view_<view_type>` (ej. `res_partner_view_form`)
*   **Acción**: `<model_name>_action` (ej. `sale_order_action`)
*   **Menú**: Prefijados con módulo/modelo (ej. `account_menu_root`, o `account_menu_action`)
*   **Grupo (Seguridad)**: `<module_name>_group_<group_name>` (ej. `sales_team_group_user`)
*   **Regla (Record Rules)**: `<model_name>_rule_<concerned_group>` (ej. `sale_order_rule_company`)

## 4. Odoo.sh - Gestión del Entorno

1.  **Advertencias (Warnings)**: Ante una advertencia en el linter de Odoo.sh, corrige siempre el código en lugar de usar pragma hooks (como `# noqa: E501`). Ocultar advertencias es generar deuda técnica.
2.  **Entornos Separados**: Odoo.sh ofrece stages separados (Development, Staging, Production). Nunca confirmes código subdesarrollado directo a `Production`. Trabaja en ramas `Development` y pruébalo con una copia de dados en `Staging` antes de enviar al master.
3.  **Modularidad Constante**: Al implementar, usa un diseño de módulos personalizados que no toquen nunca el core de Odoo. Un diseño modular debilmente acoplado te preparará para cambios del roadmap hacia Odoo >= 20.

---
## Directiva de Acción

Cuando el usuario pida programar algo en el entorno de Odoo:
1. **Claridad sobre el entorno y requerimientos**: Si no tienes claridad total sobre cómo abordar el desarrollo o falta información del entorno, **siempre solicita la información necesaria al usuario antes de asumir**. Por ejemplo:
    - Solicita acceso al código o a la vista de alguna sección en modo desarrollador.
    - Pide que se ejecute algún script de diagnóstico.
    - Solicita que se ejecute algo en la consola (logs, comandos de Odoo, etc.).
2. Revisa de manera activa que el código Python u XML cumpla con todas las reglas mencionadas.
3. Organiza las validaciones importando un estándar como primer paso al hacer revisiones automáticas.
4. Corrige cualquier mala práctica sin esperar instrucciones adicionales.
