# Antipatrón: Eliminar Diarios Nativos de Odoo

**Fecha:** 2026-03-13
**Categoría:** Contabilidad / Arquitectura del Sistema
**Contexto:** Implementación de Diarios Contables (Journals) en la Localización Colombiana.

## El Problema
Al iniciar una implementación de Odoo y visualizar el módulo de Contabilidad, es común encontrar diarios predeterminados instalados de fábrica por la Localización (ej. *Facturas de cliente (INV)*, *Facturas de proveedores (BILL)*, *Banco (BNK1)*). 

Muchos contadores y consultores junior sienten la tentación de **borrar** estos diarios nativos de la interfaz para crear los suyos propios "desde cero", buscando que calcen estrictamente con los nombres de su Plan Único de Cuentas interno. **Esta práctica es un Antipatrón de Arquitectura que puede corromper la base de datos y romper automatizaciones críticas.**

## ¿Por qué es un error fatal de diseño?
1. **Motores y Dependencias de Bajo Nivel:** Odoo amarra internamente estos diarios predeterminados a rutinas automatizadas muy complejas. Por ejemplo, los motores que calculan las *Diferencias en Cambio (TRM)* o las rutinas que disparan la liquidación de impuestos están programadas en el backend (Python) para buscar ciegamente las referencias de estos diarios originales.
2. **Cascada de Errores Silenciosos:** Si un implementador inexperto elimina estos diarios, las automatizaciones fallan. El usuario empezará a ver errores inexplicables al momento de facturar mercancía, cruzar pagos internacionales o conciliar extractos. Reparar esto en etapas avanzadas del proyecto exige intervenir directamente y con muchísima precaución las tablas de la base de datos (PostgreSQL).

## La Solución Profesional: "La Estrategia de Reciclaje" ♻️
En lugar de someter al sistema al trauma de borrar objetos fundamentales, la regla de oro en implementaciones expertas (Especialmente en B2B) es **Reciclar (Renombrar y Editar)** los diarios existentes para que se ajusten al requerimiento visual y contable del cliente.

### Ejemplo Práctico de Reciclaje:
*   Si Odoo trae el diario `Facturas de cliente (INV)`, pero la empresa tradicionalmente lo llama `Ventas` y lo usa en la cuenta "413505":
    *   ❌ **Camino Erróneo:** Eliminar el diario INV y crear uno nuevo titulado "Ventas".
    *   ✅ **Camino Óptimo:** Entrar a la configuración del diario nativo INV, **sobrescribir el nombre** a "Ventas", y en la pestaña de asientos contables cambiar su cuenta de ingresos predeterminada apuntándola hacia la cuenta correcta (NIIF).

### Diarios Intocables (De Sólo Lectura)
Dentro del entorno Odoo, existen diarios operativos 100% mecánicos que **jamás** deben renombrarse ni alterarse bajo ninguna circunstancia, ya que actúan como "puentes" invisibles:
*   `Diferencia de cambio (EXCH)`
*   `Traslado y acreditación de Impuestos (CABA)` o `Tax Cash Basis`.

> **💡 Conclusión Estratégica para el Blog:** Odoo es un ERP orgánico, no un simple repositorio de Excel. Adaptar su cáscara visual (nombres, códigos cortos e interfaces) manteniendo intacto y respetado el núcleo de la base de datos garantizará a las empresas estabilidad financiera a largo plazo y actualizaciones sin fricción en versiones futuras.
