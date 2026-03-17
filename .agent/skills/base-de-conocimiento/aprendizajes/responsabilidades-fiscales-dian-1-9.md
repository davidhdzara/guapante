# Responsabilidades Fiscales DIAN y Anexo Técnico 1.9 (2025-2026)

**Fecha de Registro:** 2026-03-16
**Contexto del Problema:**
Durante la Fase 3.1 de carga del Maestro de Proveedores, intentábamos mapear todas las responsabilidades del RUT (Casilla 53) hacia el campo "Obligaciones y Responsabilidades" de la localización colombiana en Odoo 18. El cliente notaba que faltaban opciones como la O-48 (Responsable de IVA), O-05 (Renta), entre otras.

## 🚨 El Problema o Error
Odoo 18, por defecto, solo muestra 5 opciones en el desplegable de Responsabilidades Fiscales (`l10n_co.fiscal.responsability`): O-47, O-13, O-15, O-23 y R-99-PN. Intentar forzar la creación e importación de otras responsabilidades tributarias (como O-42, O-14) para replicar el RUT exactamente llenaría la base de datos de información irrelevante para el XML.

## 🔍 Causa Raíz
El Anexo Técnico versión 1.9 de la DIAN (Resolución 000165 de 2023 y modificatorias hasta la Resolución 000202 de 2025) especifica que el campo `cbc:TaxLevelCode` del XML de la factura electrónica y documento soporte **SOLO** debe contener responsabilidades que afecten la liquidación de impuestos. 
Las responsabilidades meramente informativas o formales (llevar contabilidad, declarar renta, exógena) **no se envían** en el XML. Por su parte, la O-48 (Responsable de IVA) no se envía como responsabilidad fiscal, sino que se parametriza a través del `TaxScheme` (Régimen Fiscal) del tercero.

## ✅ Solución Adoptada
Se estableció la siguiente directriz inamovible para la parametrización de Odoo 18 Colombia:

1. **Régimen Común / Responsable de IVA:** Se selecciona "IVA" en el campo Régimen Fiscal. El campo "Obligaciones y Responsabilidades" se deja **vacío** (lo que equivale a `R-99-PN No aplica`).
2. **Excepciones:** El campo "Obligaciones y Responsabilidades" solo se llena si el RUT del tercero contiene explícitamente `O-13` (Gran Contribuyente), `O-15` (Autorretenedor), `O-23` (Agente Retenedor IVA) u `O-47` (Régimen Simple).

## 💡 Buenas Prácticas / Cómo evitarlo
Nunca intentes recrear el catálogo completo de la Casilla 53 de la DIAN en Odoo. Limítate a las 5 responsabilidades que Odoo trae por defecto. Para integraciones masivas (Excel o API), todos los clientes y proveedores normales deben importar dicho campo en blanco para evitar rechazos técnicos por parte de la DIAN o del proveedor tecnológico al emitir documentos electrónicos.
