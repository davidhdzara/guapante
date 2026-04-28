# Perfil Comercial y Tributario de Guapante

**Fecha de Registro:** 2026-04-25
**Contexto del Proyecto:**
Reglas de negocio fundamentales para el desarrollo de módulos comerciales, contables y de facturación electrónica en el ERP de Guapante S.A.S.

## 🚨 Reglas de Negocio Obligatorias

1. **Modelo de Negocio:** B2B (Business to Business). Guapante vende al por mayor.
2. **Productos Core:** Frutas y Verduras.
3. **Manejo de Impuestos (IVA):** Los productos (frutas y verduras frescas) están **exentos de impuestos** (IVA 0% o Exento).
4. **Manejo de Retenciones (ReteFuente):** Se les debe aplicar invariablemente la tarifa del **1.5%** de retención en la fuente bajo el concepto tributario de **"productos agrícolas no procesados"**.

## 💡 Implicaciones para el Desarrollo

- Al generar motores de facturación, carritos de compras o inyección de impuestos, el IVA predeterminado debe ser siempre Exento, y no se debe forzar IVA del 19% en productos agrícolas.
- El concepto de ReteFuente agrícola (1.5%) es el escenario principal de facturación, por lo que las bases UVT y el mapeo de este impuesto deben ser prioridad en pruebas y despliegues.
