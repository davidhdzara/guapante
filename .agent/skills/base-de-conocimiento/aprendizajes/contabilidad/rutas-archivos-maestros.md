# 📂 Ubicación de Archivos Maestros y de Parametrización (Guapante)

**Fecha de Registro:** 2026-03-13
**Contexto del Problema:**
Para garantizar la agilidad en integraciones futuras y evitar búsquedas largas, se hace necesario un registro exacto de las rutas, nombres de archivos y hojas correspondientes a cada maestro del proyecto.

## 🚨 El Problema o Error
Durante las validaciones contables y operativas, es frecuente necesitar revisar en crudo la data maestra (listas de precios, plan de cuentas, clientes/proveedores). No conocer su ubicación exacta genera retrasos, y utilizar bases desactualizadas podría inducir a errores graves de importación a Odoo.

## ✅ Solución Adoptada (Mapa de Ubicaciones)
Se consolida a continuación el mapa estático de los archivos oficiales del proyecto para Odoo 18.

### 1. Módulo Contable (PUC)
* **Ruta Absoluta:** `/home/david/odoo-projects/guapante/Documentacion Proyecto/Maestros/03 - Modulo Contable/PUC/Maestro Contable Odoo 18.xlsx`
* **Hoja Principal:** `PUC FINAL Consolidado`
* **Contenido:** Plan Único de Cuentas (PUC) depurado y homologado para Colombia. Contiene Códigos (ID), Nombre, Tipo de Cuenta, y la Moneda (COP) necesarios para Odoo.

### 2. Módulo de Inventario (Productos)
* **Ruta Absoluta:** `/home/david/odoo-projects/guapante/Documentacion Proyecto/Maestros/04 - Modulo Inventario/Maestro de Productos.xlsx`
* **Hojas Principales:** `Categorias`, `productos`
* **Contenido:** Árbol de categorías anglosajonas con cuentas amarradas, productos con códigos de barra, precio de venta, costo, referencias internas (SKU) e impuestos.

### 3. Módulo Inventario (Gastos y Servicios Operativos)
* **Ruta Absoluta:** `/home/david/odoo-projects/guapante/Documentacion Proyecto/Maestros/04 - Modulo Inventario/Nuevos_Maestros_Gastos.xlsx`
* **Hojas Principales:** `Categorías de Gastos`, `Productos de Gastos`
* **Contenido:** Catálogo para crear facturas de proveedores relacionados al core operativo (gasolina, arriendo, peajes, honorarios contables), parametrizados con las cuentas correspondientes del Grupo 5.

### 4. Módulo de Contactos (Clientes y Proveedores)
* **Ruta Absoluta:** `/home/david/odoo-projects/guapante/Documentacion Proyecto/Maestros/02 - Contactos/03-Clientes/Main - Maestro de clientes.xlsx`
* **Contenido:** Listado de NIT/CC, Nombres, Responsabilidad Fiscal, Códigos CIIU, Teléfonos, Direcciones. *(Este será el archivo que usaremos para la Fase 3).*

## 💡 Buenas Prácticas / Cómo evitarlo
Antes de ejecutar cualquier script o script de Node/Python que edite o lea excel, **se debe consultar obligatoriamente este documento** para asegurar que se está extrayendo información de la URL absoluta correcta. Si un archivo cambia de nombre o ubicación, este md debe actualizarse inmediatamente.
