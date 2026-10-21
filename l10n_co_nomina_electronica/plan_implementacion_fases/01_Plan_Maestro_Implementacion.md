# Plan Maestro de Implementación: Nómina Electrónica InSoTech

Este documento es la **Guía Maestra y Plan de Ruta** para la implementación de la Nómina Electrónica (DIAN) bajo los estándares de InSoTech. Está diseñado para ser leído y ejecutado por múltiples agentes de IA independientes en la plataforma Antigravity.

---

## 1. Contexto y Arquitectura de Negocio

El proyecto debe satisfacer un modelo de negocio dual y soportar múltiples versiones de Odoo, protegiendo la Propiedad Intelectual (algoritmos de firma y comunicación con la DIAN).

### 1.1 Modelo Dual
*   **Camino A (Comercial / SaaS):** Venta de la solución a otros Partners. El partner instala un módulo "Conector" que solo recopila datos y los envía a una API de InSoTech. El código de la firma electrónica, generación XML y transmisión a la DIAN reside en nuestros servidores (propiedad intelectual protegida).
*   **Camino B (Clientes Propios):** Instalación *On-Premise* o en Odoo.sh. En este caso, el motor completo puede residir en el servidor del cliente si así se comercializa, o conectarse a nuestro SaaS.

### 1.2 Compatibilidad de Entornos
El sistema final debe operar sobre:
1.  Odoo 18 Enterprise (Nativo `hr_payroll`)
2.  Odoo 19 Enterprise (Nativo `hr_payroll`)
3.  Odoo Community (Sin motor nativo - se manejará en fase independiente).

Para aislar las versiones de Odoo de la normativa de la DIAN, **la comunicación entre la captura de datos y el motor generador de XML será siempre a través de un payload JSON estandarizado.**

---

## 2. Metodología de Agentes Antigravity

Para asegurar que cualquier agente de IA pueda tomar una fase sin romper el trabajo previo, se implementará el siguiente marco:

1.  **Skills Maestras:** Se creará una *Skill* en `.agent/skills/nomina_electronica_core` que contendrá el Diccionario de Datos DIAN, las reglas del Payload JSON y el workflow del estado de la nómina. Todos los agentes DEBEN leer esta skill antes de escribir código.
2.  **Aislamiento de Tareas:** Cada fase (o sub-fase) será un *ticket* o instrucción separada.
3.  **Fuentes de Verdad:**
    *   **Catálogos y XML:** Archivos `.md` convertidos de las resoluciones en las carpetas `DIAN` y `UGPP`.
    *   **Estructura Base:** Carpeta `Caja-de-Herramientas-Nomina-Electronica-V1-0`.

---

## 3. Fases de Implementación

### Fase 0: Preparación del Entorno Local de Desarrollo
*   **Objetivo:** Configurar los ambientes de desarrollo locales para las distintas versiones exigidas.
*   **Tareas:**
    1.  Despliegue local de Odoo 18 Enterprise.
    2.  Despliegue local de Odoo 19 Enterprise.
    3.  Despliegue local de Odoo Community (última versión).
*   **Encargado:** Desarrollador Humano / Agente de Infraestructura.

### Fase 1: Arquitectura Core y Estandarización de Datos
*   **Objetivo:** Definir el modelo de datos agnóstico a Odoo y los catálogos normativos.
*   **Tareas:**
    1.  Extraer catálogos de los `.md` (Tipo de Documento, Municipio, Tipo de Contrato, Códigos de Novedades DIAN/UGPP) y convertirlos en modelos `l10n_co_edi.*`.
    2.  Definir la estructura estricta del **"JSON Payload InSoTech"**.
    3.  Crear la Skill de Antigravity con esta estructura.

### Fase 2: Desarrollo del Motor Core DIAN (Backend API)
*   **Objetivo:** Crear el motor que recibe el JSON, ensambla el XML y firma.
*   **Tareas:**
    1.  Motor de transformación de JSON a XML (UBL 2.1 - Anexo Técnico V1.0).
    2.  Lógica de generación del **CUNE** (SHA-384).
    3.  Módulo de integración para firma digital y certificado `.p12`.
    4.  Cliente WebService para conexión con los endpoints DIAN (Habilitación / Producción - Sincrónico y Asincrónico).

### Fase 3: Conector Odoo 18 Enterprise (Native Payroll)
*   **Objetivo:** Extraer la información de Odoo y enviarla al Motor Core.
*   **Tareas:**
    1.  Scaffolding del módulo `l10n_co_edi_payroll_connector`.
    2.  Heredar `hr.payslip`, `hr.employee`, `res.company` para añadir campos requeridos.
    3.  Desarrollar el mapeo: Reglas Salariales (`hr.salary.rule`) -> Conceptos Devengados/Deducidos del Anexo Técnico.
    4.  Desarrollar la acción "Enviar a DIAN" que genera el JSON y lo dispara al Motor Core.

### Fase 4: Conector Odoo 19 Enterprise
*   **Objetivo:** Migración y adaptación funcional del Conector de la Fase 3 hacia Odoo 19.
*   **Tareas:**
    1.  Revisión de cambios en OWL o en el ORM de `hr_payroll` para V19.
    2.  Refactorización y testing.

### Fase 5: Conector Odoo Community
*   **Objetivo:** Dar soporte a clientes sin Odoo Enterprise.
*   **Tareas:**
    1.  Definir el origen de los datos (Módulo OCA `hr_payroll`, importación Excel, o modelo de captura básico propio).
    2.  Adaptar el transformador para que genere el mismo **JSON Payload InSoTech** esperado por el Motor Core.

---

## 4. Reglas Globales (Workflow Antigravity)

1.  **NO MONOLITOS:** Ningún agente programará lógica de firma XML directamente dentro de `hr.payslip`. La lógica Odoo y la lógica EDI/Criptográfica deben estar en clases/módulos separados.
2.  **VALIDACIÓN TEMPRANA:** Todo conector debe validar que los campos obligatorios del empleado (Ej. Tipo de contrato, Ciudad, NIT) existan ANTES de generar el JSON.
3.  **TOLERANCIA A FALLOS:** Todas las peticiones al WebService de la DIAN deben gestionarse mediante colas asíncronas (`ir.cron` o similar en Odoo) para evitar bloqueos en la interfaz de usuario en caso de caída de la DIAN.
