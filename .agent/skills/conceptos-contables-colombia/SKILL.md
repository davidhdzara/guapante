---
name: Conceptos Contables Colombia
description: Diccionario, glosario y guía normativa para que cualquier agente de la plataforma entienda los conceptos de la localización colombiana (DIAN, Impuestos, Facturación Electrónica, Odoo).
---

# Conceptos Contables y Tributarios de Colombia (Odoo)

Esta skill es una guía de referencia rápida para comprender la lógica tributaria colombiana aplicable a Odoo, la Facturación Electrónica y la normatividad fiscal de la DIAN.

## 📘 1. Facturación Electrónica y Documento Soporte

En Colombia, la DIAN exige la transmisión de transacciones comerciales mediante XML. El **Anexo Técnico vigente** rige las especificaciones técnicas.
*   **Versión 2024-2026:** Anexo Técnico 1.9 (Instaurado por la Resolución 000165 de 2023 y sus posteriores ajustes como la Resolución 000202 de 2025).
*   **Fuentes de Investigación Normativa:** Siempre se debe consultar `dian.gov.co/normatividad`, o portales legales como `actualicese.com`, `gerencie.com` buscando siempre explícitamente el año en curso.

### Regla de Oro del XML (TaxLevelCode vs TaxScheme)
*   **TaxLevelCode (Responsabilidades Fiscales):** Solo deben transmitirse al XML las obligaciones que **alteran el cálculo del impuesto** (O-13 Gran Contribuyente, O-15 Autorretenedor, O-23 Agente Retenedor IVA, O-47 Régimen Simple). Obligaciones meramente informativas o formales (O-42 Llevar Contabilidad o la declaratoria general de IVA) no se transmiten en este bloque.
*   **TaxScheme (Régimen Fiscal):** Define el nivel macro del contribuyente. En Odoo, el Régimen Común (O-48) se maneja asignando el Régimen Fiscal como "IVA" directamente desde la interfaz de Contactos.

## 📗 2. Glosario de Impuestos y Términos (Localización Odoo)

*   **RUT (Registro Único Tributario):** Identificación tributaria que contiene la verdad absoluta legal (Casilla 53) de un tercero en Colombia.
*   **NIT:** Tipo de Identificación ("rut" en Odoo). *Importante:* El dígito de verificación suele manejarse en el campo separado `l10n_co_verification_code`.
*   **Responsable de IVA (Antiguo Régimen Común):** Quien cobra y declara IVA. Se representa con la obligación O-48 en el RUT, pero en Odoo se gestiona a nivel de Régimen (`IVA`).
*   **No Responsable de IVA (Antiguo Régimen Simplificado):** Personas naturales que no cobran IVA.
*   **Régimen Simple de Tributación (RST - O-47):** Un modelo de tributación opcional que reemplaza la renta por un impuesto unificado. Tienen tarifas diferentes y no están sujetos a la retención en la fuente tradicional.
*   **ReteFuente (Retención en la Fuente por Renta):** Un anticipo del impuesto de renta que el comprador le retiene al vendedor en el momento del pago. Existen múltiples bases mínimas (topes en UVT) y tarifas (ej: 2.5%, 3.5%, 11%) dependiendo del concepto.
*   **ReteICA (Retención de Industria y Comercio):** Impuesto municipal sobre los ingresos de la actividad comercial. Su tarifa depende de la actividad económica (CIIU) y se expresa en milajes (ej: 4x1000, 11.04x1000). En Odoo se activa según factores locales.
*   **ReteIVA (Retención en la Fuente por IVA):** Retención parcial sobre el IVA facturado (normalmente el 15%). Aplica cuando el comprador es de un "rango tributario" superior al vendedor (ej. Gran Contribuyente le compra a un Régimen Común).
*   **Documento Soporte:** Documento electrónico que debe emitir el adquiriente (comprador) para legalizar un gasto o compra hecha a una persona **no obligada a expedir factura electrónica** (ej: servicios de un contratista independiente, compras a Régimen Simplificado).
*   **Posición Fiscal (Odoo):** Un motor de reglas de Odoo que intercepta los impuestos predeterminados del producto y los reemplaza o les añade retenciones basándose en la configuración tributaria del tercero (ej: Añadir ReteFuente del 2.5% a la compra).

## 🗃️ 3. Reglas Heurísticas para Futuros Agentes

1.  **Duda sobre Responsabilidades?** Deja el campo "Obligaciones y Responsabilidades" de Odoo en blanco a menos que veas explícitamente en el RUT del usuario los códigos O-13, O-15, O-23, O-47. 
2.  **Impuestos faltantes?** Antes de crear un impuesto manualmente, verifica el catálogo `l10n_co.tax` instalado en los submódulos de localización. La mayoría de los retefuentes y porcentajes de IVA (19%, 5%, 0%) ya existen.
3.  **Auditoría de Bases?** En Colombia, todos los años cambia la UVT (Unidad de Valor Tributario). Al auditar un entorno en enero o febrero, lo primero que se debe validar son las reglas de importes mínimos de los impuestos de retención para que cumplan con la normativa DIAN de ese año fiscal.
4.  **Cuentas de Retención Odoo:** Se prefiere dividir la cuenta estándar genérica (Ej. 236540) en subcuentas de 8 dígitos según porcentajes y grupos tributarios (Ej. 23654001 para el 2.5%, y 23654002 para el 3.5%) siempre validando el Plan Único de Cuentas (PUC) de la empresa.

---

## Directiva de Acción

1. Al enfrentar requerimientos o dudas funcionales sobre Colombia en Odoo, busca palabras clave contenidas en esta guía.
2. Si un cliente solicita replicar la Casilla 53 del RUT íntegramente en Odoo, recuérdale con autoridad normativa la regla de oro del Anexo Técnico 1.9.
3. Al crear o auditar contactos masivamente (Plantillas Excel), nunca intentes enviar códigos formales (ej O-42) en el campo `l10n_co_fiscal_responsability_ids`.
4. Si la duda normativa no se resuelve aquí, busca en internet información relacionada a "Facturación Electrónica DIAN" y el respectivo "Anexo Técnico" vigente al año de la consulta.
