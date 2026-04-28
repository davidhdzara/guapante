# Estructura Tributaria: Antioquia y Municipios (Medellín, Itagüí, Sabaneta, El Retiro)

**Fecha de Registro:** 2026-04-26
**Contexto del Problema:**
Al parametrizar el motor de retenciones (`insotech.retention.concept`), es necesario mapear la realidad tributaria local de Colombia. Cada municipio tiene un Estatuto Tributario propio con tarifas de ICA diferentes según la actividad económica (CIIU). Este documento guarda la base de datos investigada sobre Antioquia para futuras inyecciones en Odoo.

## 🚨 El Problema o Reto
El ERP requiere precargar las tarifas correctas de ICA para que el usuario no tenga que investigarlas. Además, se debe diferenciar entre "Impuestos Directos" (gastos de la empresa) y "Retenciones" (dinero retenido a proveedores).

## 🔍 Datos y Tarifas de Referencia (Vigencia 2025-2026)

### 1. Impuestos Departamentales (Gobernación de Antioquia)
*Estos son gastos directos, no retenciones.*
- **Impuesto de Registro:**
  - 1,0%: Actos con cuantía sobre inmuebles.
  - 0,7%: Actos con cuantía en Cámaras de Comercio.
  - 0,3%: Aportes a capital o prima en colocación de acciones.
- **Degüello de Ganado Mayor:** 1,0 SMDLV por cabeza.

### 2. Impuestos Municipales (Retenciones y Directos)

#### Medellín (Acuerdo 066 de 2017 / 023 de 2020)
- **ReteICA (Retención aplicable en Odoo):**
  - Industrial: 2,0 a 7,0 por mil.
  - Comercial y Servicios: 2,0 a 10,0 por mil.
  - Financiero: 14,0 por mil.
- **Beneficios (Distrito CTI - Acuerdo 093 de 2023):** Exoneración progresiva para empresas TIC o IED > 2M USD (100% año 1, 60% año 2, 30% año 3, etc.).
- **Régimen Simple (RST):** Tarifas consolidadas entre 8,05 y 11,50 por mil.

#### Itagüí (Acuerdo 030 de 2012)
- **ReteICA (Retención aplicable en Odoo):**
  - Industrial: 3 a 7 por mil (Químicos: 4, Textiles: 5).
  - Comercial: 2,5 a 10 por mil (Alimentos: 2,5, Combustibles: 10).
  - Servicios: 5 a 10 por mil (Alojamiento: 8-10, Financiero: 10).
  - Régimen Simplificado: Mínimo 0,7 UVT mensual.
  - *Agentes de retención practicantes en Itagüí:* Entidades públicas, grandes contribuyentes, PN con ingresos > 30.000 UVT.
  - *Base Mínima ReteICA:* Servicios = 4 UVT / Compras = 27 UVT.
- **Avisos y Tableros:** 15% sobre el ICA.
- **Sobretasa Bomberil:** 1,5% sobre ICA + Avisos.
- **Estampillas:** Procultura (1%), Probienestar Anciano (2%) en contratos estatales.

#### El Retiro
- **ReteICA:** Industrial (4 por mil), Comercial (6 a 7 por mil), Servicios (8 a 9 por mil).

## ✅ Solución Adoptada en Odoo
*   Los impuestos como **Predial, Delineación, Alumbrado y Registro** se configurarán únicamente si InSoTech/Guapante desarrolla un módulo de gastos directos.
*   Las tarifas de **Industria y Comercio (ICA)** se transforman en registros de `insotech.retention.concept` tipo `reteica` y dirección `purchase` (si retenemos) o `sale` (si nos retienen).
*   Se anidan obligatoriamente bajo las carpetas auto-generadas del modelo geográfico (Ej. `Departamentales > Antioquia > Itagüí`).

## 💡 Buenas Prácticas / Cómo evitarlo
*   **Base Mínima UVT:** Siempre configurar la validación de UVT mínima por ciudad (Ej. Itagüí: 4 UVT para servicios, 27 UVT para compras) en los conceptos de retención creados en Odoo.
*   **Autorretenedores locales:** Añadir alertas (warnings) si el partner de la factura es autorretenedor municipal, ya que la tarifa o aplicación de ReteICA cambia drásticamente.
