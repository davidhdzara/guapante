---
title: Parametrización del Catálogo de Gastos y Servicios (Odoo)
date: 2026-03-12
tags: [Contabilidad, Odoo18, Compras, Facturacion, Servicios]
author: Antigravity AI
---

# Catálogo de Gastos y Servicios Operativos (B2B Agro)

## 📌 Contexto y Problema
En empresas del sector agrícola y distribuidor recurrían al error de exigir conocimientos contables al personal operativo cada vez que necesitaban clasificar facturas de servicios, peajes, arrendamientos y fletes, llevando a que los auxiliares mapearan con cuentas directas del PUC en el módulo financiero o de caja, aumentando errores y rompiendo el flujo nativo de Compras -> Pagos en Odoo.

## 💡 Solución Odoo
Para aprovechar nativamente Odoo, las facturas y pagos operativos se mapean utilizando **Productos Tipo "Servicio"** o **"Consumible"**, los cuales heredan de una **Categoría Superior** que tiene amarrada la cuenta de gasto del proveedor (Grupo 5 de Colombia). De esta forma el operario simplemente busca "Peaje" como producto sin interactuar con contabilidad.

## 📋 Estructura Diseñada (Aprendizaje)
A continuación, se documenta la matriz de parametrización estándar para gastos operativos dividida por la naturaleza financiera del gasto:

### 1. Transporte y Logística (Grupo 52 - Operacional Ventas)
Gastos asociados a mover la mercancía.

| Producto Odoo (Servicio) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Combustible y Lubricantes | Transporte y Logística | `529535` |
| Pago de Peajes | Transporte y Logística | `529545` (Taxis/buses u homóloga de peajes) |
| Fletes a Terceros | Transporte y Logística | `524540` |
| Mantenimiento Carros | Transporte y Logística | `524545` |
| Seguros SOAT/Todo Riesgo | Transporte y Logística | `523025` |

### 2. Instalaciones Mantenimiento (Grupo 51 - Administración)
Gastos fijos de la bodega/punto comercial.

| Producto Odoo (Servicio) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Arrendamiento Bodega/Local | Instalaciones y Mantenimiento | `512010` |
| Energía y Acueducto (EPM) | Instalaciones y Mantenimiento | `513525` |
| Internet y Telefonía | Instalaciones y Mantenimiento | `513530` |

### 3. Insumos Operativos (Productos Consumibles)
Productos que físicamente entran pero no se venden, se gastan inmediatamente (sin seguimiento de tracking/cardex).

| Producto Odoo (Consumible) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Canastillas y Empaques | Insumos Operativos | `519525` / `519530` |
| Dotación y Uniformes | Insumos Operativos | `510524` |
| Papelería (Resmas) | Insumos Operativos | `519530` |

### 4. Honorarios y Asesorías
Gastos por servicios prestados donde se recibe Factura Electrónica e incurrenced de tramitología recurrente.

| Producto Odoo (Servicio) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Honorarios Contador | Honorarios y Asesorías | `511030` |
| Honorarios Abogado | Honorarios y Asesorías | `511025` |
| SST / Exámenes Médicos | Honorarios y Asesorías | `519595` |
| Renovación Cámara Comercio| Honorarios y Asesorías | `514010` |
| Suscripción Software (Odoo) | Honorarios y Asesorías | `513550` |

### 5. Gastos de Empleados y Viáticos (Caja Menor futura)
Están estructurados para ser rendidos usualmente por el módulo de **Gastos (Expenses)** por conductores o administrativos de planta.

| Producto Odoo (Servicio) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Almuerzos y Alimentación | Gastos de Empleados | `519560` |
| Taxis y Transporte Urbano | Gastos de Empleados | `519545` |
| Parqueaderos y Lavaderos | Gastos de Empleados | `529595` (o `529545`) |
| Caja Menor (Varios) | Gastos de Empleados | `519595` |

### 6. Gastos Específicos Sector Alimentos (B2B Agro)
Servicios críticos para mantener la operación a flote comercial sin perder cadenas de frío y cumplir normatividad del INVIMA.

| Producto Odoo (Servicio) | Categoría Superior | Cuenta Odoo Recomendada |
| :--- | :--- | :--- |
| Mantenimiento Cuartos Fríos | Instalaciones y Mantenimiento | `514515` |
| Fumigación y Control Plagas | Instalaciones y Mantenimiento | `513595` |
| Calibración de Básculas | Instalaciones y Mantenimiento | `514515` |

## 🚀 Buenas Prácticas y Reglas
1. **Pólizas de Seguros / Vehículos Específicos**: Si a futuro se requiere medir rentabilidad unitaria por camión (ejemplo: El camión de placas ABC-123 suma cuántos peajes se comió y cuántos fletes facturó), esta estructura se mantiene intacta, pero se debe activar y asignar una **Cuenta Analítica (Centro de Costo)** en la orden de compra que represente la placa de dicho camión.
2. **Caja Menor / Empleados**: Los gastos como almuerzos y viáticos reembolsables (Grupo 519560) deben estructurarse creando los productos equivalentes y activando el flag `Puede ser gastado (Can be Expensed)` para usar con el módulo *Gastos de empleados*.
