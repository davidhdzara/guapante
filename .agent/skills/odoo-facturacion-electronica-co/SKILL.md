---
name: Facturación Electrónica Colombia Avanzada (Odoo 18)
description: Skill obligatoria de diseño arquitectónico y buenas prácticas para agentes desarrolladores que intervengan, construyan o debuggeen el módulo de facturación electrónica (DIAN) en Odoo 18. Garantiza la regla de oro del consecutivo desacoplado y flujos de contingencia.
---

# Modelo de Facturación Electrónica "TOP" para Colombia (Odoo 18)

Esta skill es **OBLIGATORIA** para cualquier agente o desarrollador que modifique el flujo de `account.move` o actúe sobre las secuencias de `l10n_co_dian`. Has sido invocado para garantizar que la rigidez de la DIAN se respete sin romper la simplicidad nativa de Odoo.

## 1. La Regla de Oro (El problema del Consecutivo)
**NUNCA**, bajo ninguna circunstancia, Odoo debe consumir (quemar) el número legal de resolución de la DIAN (Ej. `FE-0125`) al hacer clic en "Confirmar".
El Odoo nativo lo hace y eso destruye la contabilidad cuando la DIAN rechaza el XML.

**La Cura Obligatoria:**
La arquitectura de cualquier módulo custom (como `guapante_l10n_co_simple_edi`) debe intervenir en el método `_post()` de `account.move` para que:
1.  La confirmación asigne una secuencia *borrador_interna* temporal.
2.  Se realice el envío HTTP (POST) a la DIAN con un Payload tipo UBL 2.1.
3.  **SÓLO SI** la DIAN devuelve `StatusCode 200` y `ApplicationResponse` aceptado, Odoo puede hacer el `ir.sequence.next_by_id(...)` tomando el número legal `FE-XXX` y asignándolo definitivamente a la factura y al PDF impreso.
4.  Si la DIAN rechaza, se levanta un `UserError()`. Esto forza a Postgres a hacer Rollback; el número no se toca, la factura vuelve a Borrador.

## 2. Los "Edge Cases" Sagrados que debes Programar
Si estás escribiendo código para este módulo, DEBES incluir estas tres protecciones lógicas:

1.  **Timeouts DIAN (La Red Lenta):**
    *   Toda petición HTTP (Requests) a los web services de la DIAN en Odoo debe llevar `timeout=8` (o máximo 10) segundos.
    *   Captura la excepción `TimeoutException / ConnectionError` y conviértela en un `UserError("La DIAN no responde")` para triggerear el Rollback de postgres y **NO CONGELAR** la pantalla de la cajera en el TPV o mostrador.
2.  **Concurrencia (Bloqueo de Base de Datos):**
    *   Asegúrate de que la extracción del consecutivo legal (`ir.sequence`) se haga lo más tarde posible en el bloque atómico, y se use el `sudo()` o el patrón de bloqueo estándar de Odoo para que si 2 vendedores de Mostrador "Confirman" al mismo milisegundo, la base de datos no les entregue el mismo `FE-0125` a ambos.
3.  **Modo Contingencia (Tipo 04):**
    *   El código debe respetar un `boolean` en el `account.journal` (`is_dian_contingency`). Si esto es TRUE, sáltate la DIAN. No intentes llamar al web service. Ve directo a confirmar la factura usando la secuencia de contingencia parametrizada (Ej: `PC-0001`).

## 3. Automatización (El Cron de Reintentos)
Si estás automatizando el sistema de resolución de fallos DIAN:
*   Crea una acción planificada `ir.cron`.
*   Solo intenta reenviar facturas cuyo rechazo fue **Técnico** (ej. Timeout, saturación MUISCA).
*   **NO** automatices el reenvío de rechazos por Reglas de Negocio (ej. FAJ44b - NIT Inválido). Estas requieren que un humano hable con el cliente y edite el registro de "Contactos" antes de reintentar. Si el Cron intenta enviar un NIT malo ciegamente, saturarás la API de la DIAN y podrán banear la IP del servidor de Odoo.

## 4. Referencias
Si necesitas entender el origen de esta arquitectura, lee los documentos en la carpeta del proyecto:
*   `/home/david/odoo-projects/guapante/Plan de trabajo contable/10_Propuesta_Simplicidad_Facturacion.md`
*   `/home/david/odoo-projects/guapante/Plan de trabajo contable/11_Guia_Implementacion_Factura_Simple.md`
