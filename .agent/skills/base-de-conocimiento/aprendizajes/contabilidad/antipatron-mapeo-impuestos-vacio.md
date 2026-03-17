---
title: "Antipatrón: Mapeo de Impuestos Vacío en Posiciones Fiscales (Odoo 18)"
date: "2026-03-16"
tags: ["odoo18", "contabilidad", "posiciones-fiscales", "retenciones", "colombia"]
author: "Antigravity & David"
---

# Antipatrón: Mapeo de Impuestos Vacío en Posiciones Fiscales (Odoo 18)

## ❌ El Antipatrón
Intentar crear una Posición Fiscal en Odoo (versiones recientes como v18) dejando **vacía** la columna "Impuesto en el producto" (izquierda) y colocando un impuesto en la columna "Impuestos a aplicar" (derecha) para tratar de "agregar" un impuesto de la nada a un tercero (Ej. Intentar agregar Retención en la Fuente a un Régimen Común partiendo de la nada).

## 🚨 El Síntoma / Error
Odoo arrojará una alerta restrictiva en rojo al intentar guardar:
`Campos no válidos: Mapeo de impuestos`

## 💡 La Explicación Técnica (Causa)
Las Posiciones Fiscales en Odoo están diseñadas como motores de **reemplazo o eliminación**, no de adición espontánea. Odoo exige estrictamente conocer cuál es el impuesto de origen (el que trae el producto o la categoría) para saber *qué* debe sustituir o borrar. Si no hay un desencadenante (impuesto origen), la regla falla.

## ✅ La Mejor Práctica (Solución)

### Escenario 1: Eliminar un impuesto (Ej: Compras a un Gran Contribuyente)
Para evitar retenerle a un autorretenedor:
- **Impuesto en el producto (Izquierda):** Seleccionar el impuesto que trae el producto (Ej: `2.5% RteFte Dec (Compras)`).
- **Impuestos a aplicar (Derecha):** Dejar **vacío**.
*Odoo leerá: "Si ves este impuesto base, bórralo".*

### Escenario 2: Reemplazar un impuesto (Ej: Clientes B2B Retenedores)
Para agregar una retención pre-calculada en ventas:
- **Impuesto en el producto (Izquierda):** `19% IVA (Ventas)` (O el impuesto base que dispare la regla).
- **Impuestos a aplicar (Derecha):** Seleccionar **AMBOS**: `19% IVA (Ventas)` **Y** `2.5% RteFte (Ventas)`.
*Odoo leerá: "Si ves el IVA, mantenlo, pero añádele esta retención al cálculo".*

### Escenario 3: Proveedor Estándar (Régimen Común)
Para operaciones estándar donde sí se cobra IVA y sí se aplica la retención predeterminada de la empresa (según el producto), **NO se requiere crear una Posición Fiscal**. Odoo calculará los impuestos tal cual vienen parametrizados desde la ficha del producto/categoría.

## 📝 Nota sobre "Mapeo de Cuentas"
En implementaciones estándar para Colombia (como Guapante), la pestaña **Mapeo de Cuentas** dentro de Posiciones Fiscales debe dejarse **vacía**. La asignación de cuentas de ingresos y gastos se rige por la Categoría del Producto (Ingresos, Gastos, Inventario), no por el tipo de contacto.
