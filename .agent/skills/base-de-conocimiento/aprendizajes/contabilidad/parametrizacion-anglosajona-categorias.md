# Parametrización Contable de Categorías (Método Anglosajón Automatizado)

**Fecha de Registro:** 2026-03-12
**Contexto del Problema:**
Durante la configuración inicial del Maestro de Productos y Categorías para el sector B2B de alimentos, nos encontramos con que Odoo 18 (Enterprise) ocultaba los campos contables avanzados (Cuentas Transitorias y de Valoración) en la vista del formulario de la Categoría.

## 🚨 El Problema o Error
Al entrar a `Inventario > Configuración > Categorías de Productos` y seleccionar "Costo Promedio (AVCO)", la interfaz no desplegaba las propiedades de cuentas de existencias (Valoración, Entrada y Salida). Además, el usuario referenció las cuentas globales en la pantalla de *Ajustes de Contabilidad/Inventario*, lo cual representa un riesgo enorme de mezclar saldos de distintas categorías (ej. Frutas con Verduras) en una sola cuenta.

## 🔍 Causa Raíz
1. **El campo "Manual":** En la esquina inferior derecha de la categoría, el campo `Valuación de inventario` estaba configurado en "Manual". Odoo oculta las cuentas de stock si asume que la empresa no registrará los asientos automáticamente en su ERP.
2. **Cuentas Globales vs Cuentas de Categoría:** En Odoo, llenar las propiedades de la cuenta desde *Ajustes Generales* fuerza a todas las transacciones sin cuenta específica a heredar esos valores genéricos, estropeando el mapeo específico del PUC por tipo de alimento (143505 Frutas, 143510 Verduras, etc.).

## ✅ Solución Adoptada
**1. Activar la automatización exacta:**
En la vista de cada Categoría, se debe cambiar el campo `Valuación de inventario` a **"Automatizada"**. Esto hace aparecer de inmediato la sección "Propiedades de la cuenta de existencias".

**2. Mapeo Correcto (Modelo Anglosajón):**
Siguiendo la UI de la Categoría, el mapeo estándar para B2B es:
*   **Cuenta de diferencia de precio:** `613510 - Ajustes de inventario`
*   **Cuenta de ingresos:** `413505 - Ingresos por ventas` (NO usar devoluciones aquí)
*   **Cuenta de gastos:** `613538 - Costo de mercancía vendida` 
*   **Cuenta de valoración de existencias:** `1435xx` (Variable: 143505 Frutas, 143510 Verduras, etc.)
*   **Diario de existencias:** `Valuación de inventario` (Diario misceláneo)
*   **Cuenta de entrada de existencias:** `220595 - Cuenta transitoria facturas por recibir` (Puente de Recepciones de Compra)
*   **Cuenta de salida de existencias:** `613595 - Cuenta transitoria mercancía por facturar` (Puente de Entregas de Venta)

## 💡 Buenas Prácticas / Cómo evitarlo
*   **Nunca:** Configurar las cuentas puente o de inventario en la vista de *Ajustes Generales* de Contabilidad/Inventario si la empresa requiere balances detallados por tipo de producto.
*   **Beneficios Anglosajón:** Educar siempre al cliente de que esta configuración le proveerá Costo de Ventas en tiempo real por cada factura emitida y un control total sobre las Cuentas Transitorias (`220595` / `613595`) para conciliar qué proveedores no han facturado entregas recibidas o qué despachos no se han facturado al cliente B2B.
