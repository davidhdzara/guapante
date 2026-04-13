# Sincronización de Plantillas WhatsApp: Push desde Odoo a Meta

**Fecha de Registro:** 2026-04-08
**Contexto del Problema:**
Estamos configurando la integración de WhatsApp Business API con Odoo 18. Inicialmente, se pensó que el flujo de plantillas era únicamente *Pull* (traer de Meta a Odoo).

## 🚨 El Problema o Error
Creer que las plantillas solo podían crearse en el panel de Meta y luego sincronizarse en Odoo, lo cual generaba una fricción operativa de doble configuración.

## 🔍 Causa Raíz
Desconocimiento de la capacidad de "Push" nativa del módulo de WhatsApp de Odoo 18. Odoo puede actuar como el orquestador principal del contenido de las plantillas.

## ✅ Solución Adoptada
Las plantillas se pueden crear directamente desde la interfaz de Odoo (WhatsApp > Plantillas). Al usar el botón **"Enviar para aprobación"**, Odoo realiza una petición API a Meta para crear la plantilla automáticamente en el Business Manager.

## 💡 Buenas Prácticas / Cómo evitarlo
- Utilizar el catálogo de Odoo como fuente de verdad para el contenido de las plantillas.
- Verificar el estado de la plantilla en Odoo periódicamente después de enviarla; una vez aprobada por Meta, el estado se actualizará automáticamente en Odoo tras la próxima sincronización o mediante el webhook.
