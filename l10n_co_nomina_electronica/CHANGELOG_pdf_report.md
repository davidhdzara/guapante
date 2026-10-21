# CHANGELOG - Reporte PDF Comprobante de Nómina Electrónica

## [1.0.0] - 2026-05-22

### Descripción

Reporte QWeb para la generación del **Comprobante de Nómina Electrónica** en formato PDF,
conforme a la Resolución 000013 de 2021 de la DIAN (Colombia).

Este reporte se entrega al empleado como representación gráfica del documento de nómina
electrónica transmitido ante la DIAN.

---

### Archivo creado

| Archivo | Descripción |
|---|---|
| `report/hr_payslip_ne_report.xml` | Plantilla QWeb del reporte PDF y registro `ir.actions.report` |

---

### Secciones del Reporte

El PDF generado contiene las siguientes secciones:

#### 1. Encabezado
- Título: **COMPROBANTE DE NÓMINA ELECTRÓNICA**
- Datos de la empresa: nombre, NIT, dirección
- Número consecutivo de la nómina electrónica (`l10n_co_ne_consecutive`)
- Fecha de la nómina
- CUNE (Código Único de Nómina Electrónica)

#### 2. Datos del Empleado
- Nombre completo del empleado
- Número de documento de identificación
- Cargo actual
- Período de liquidación (fecha inicio - fecha fin)
- Salario base del contrato
- Días trabajados (código `WORK100`)

#### 3. Tabla de Conceptos
Tabla detallada con todas las líneas de nómina visibles (`appears_on_payslip = True`):

| Columna | Descripción |
|---|---|
| **Código** | Código de la regla salarial |
| **Concepto** | Nombre descriptivo de la regla |
| **Devengado** | Monto positivo (ingresos del empleado) |
| **Deducción** | Monto negativo en valor absoluto (descuentos) |

#### 4. Totales
- **Total Devengados**: suma de todas las líneas con valor ≥ 0
- **Total Deducciones**: suma en valor absoluto de líneas con valor < 0
- **Neto a Pagar**: suma total de todas las líneas visibles (resaltado en verde)

#### 5. Información de Nómina Electrónica
- Estado de la nómina electrónica (`l10n_co_ne_state`)
- CUNE completo
- Referencia legal: Resolución 000013 de 2021 - DIAN

#### 6. Firma del Empleado
- Espacio designado con línea para firma manual
- Nombre y cédula del empleado debajo de la línea de firma

---

### Cómo se imprime

El reporte está vinculado al modelo `hr.payslip` mediante `binding_model_id`, lo que significa
que aparece automáticamente en el **botón "Imprimir"** de la vista formulario del comprobante
de nómina (`hr.payslip`).

**Pasos para imprimir:**

1. Navegar a **Nómina → Comprobantes de Nómina**
2. Abrir el comprobante de nómina deseado
3. Hacer clic en el botón **Imprimir** (menú de impresión)
4. Seleccionar **"Comprobante Nómina Electrónica"**
5. El PDF se descarga automáticamente

También es posible imprimir múltiples comprobantes seleccionándolos desde la vista lista
y utilizando la opción de impresión masiva.

---

### Detalles Técnicos

| Propiedad | Valor |
|---|---|
| **ID del reporte** | `action_report_payslip_ne` |
| **Modelo** | `hr.payslip` |
| **Tipo** | `qweb-pdf` |
| **Nombre del template** | `l10n_co_nomina_electronica.report_payslip_ne` |
| **Binding** | `report` (aparece en menú Imprimir) |
| **Layout** | `web.external_layout` (incluye encabezado y pie de página de la empresa) |

---

### Notas de Diseño

- Se utilizan **entidades XML** (`&gt;=`, `&lt;`) para las comparaciones numéricas dentro
  de las expresiones QWeb, garantizando la validez del XML.
- Los montos se formatean con separador de miles y sin decimales: `'{:,.0f}'.format(...)`.
- Las deducciones se muestran en **valor absoluto** para facilitar la lectura.
- El diseño usa colores corporativos: azul oscuro (`#2c3e50`) para encabezados de tabla,
  gris claro (`#ecf0f1`) para fondos de secciones, y verde (`#27ae60`) para el neto a pagar.
- El layout utiliza `web.external_layout` para incluir automáticamente el logo y datos
  de la empresa configurados en Odoo.
