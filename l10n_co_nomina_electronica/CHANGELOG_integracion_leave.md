# Integración hr.leave → Nómina Electrónica

## Descripción General

Este módulo extiende `hr.payslip` para detectar automáticamente las ausencias aprobadas
(`hr.leave`) del empleado durante el período de la nómina y convertirlas en novedades
para la nómina electrónica DIAN (Resolución 000013 de 2021).

**Archivo:** `models/hr_leave_ne.py`  
**Modelo extendido:** `hr.payslip` (herencia `_inherit`, sin modelo nuevo)

---

## Campos Agregados a `hr.payslip`

| Campo técnico                      | Etiqueta                       | Tipo      | Descripción                                              |
|------------------------------------|--------------------------------|-----------|----------------------------------------------------------|
| `l10n_co_ne_leave_summary`         | Resumen Novedades Detectadas   | Text      | Resumen textual de todas las ausencias procesadas        |
| `l10n_co_ne_dias_incapacidad`      | Días Incapacidad               | Integer   | Total días de incapacidad en el período                  |
| `l10n_co_ne_dias_licencia_mat`     | Días Licencia Mat/Pat          | Integer   | Total días de licencia maternidad/paternidad             |
| `l10n_co_ne_dias_licencia_rem`     | Días Licencia Remunerada       | Integer   | Total días de licencia remunerada                        |
| `l10n_co_ne_dias_vacaciones`       | Días Vacaciones                | Integer   | Total días de vacaciones                                 |
| `l10n_co_ne_dias_licencia_nr`      | Días Licencia No Remunerada    | Integer   | Total días de licencia no remunerada                     |

Todos los campos son de solo lectura y se actualizan exclusivamente mediante el botón
**"Detectar Novedades"**.

---

## Mapeo de Códigos de Ausencia → Novedades NE

El sistema busca el campo `code` del tipo de ausencia (`hr.leave.type`) y lo clasifica
según la siguiente tabla:

### Incapacidad

| Código           | Uso recomendado                            |
|------------------|--------------------------------------------|
| `INCAPACIDAD`    | Incapacidad general                        |
| `SICK`           | Compatibilidad con Odoo estándar           |
| `INC_COMUN`      | Incapacidad por enfermedad común           |
| `INC_LABORAL`    | Incapacidad por accidente laboral / ATEP   |

### Licencia Maternidad / Paternidad

| Código           | Uso recomendado                            |
|------------------|--------------------------------------------|
| `MATERNIDAD`     | Licencia de maternidad                     |
| `MATERNITY`      | Compatibilidad con Odoo estándar           |
| `PATERNIDAD`     | Licencia de paternidad                     |
| `PATERNITY`      | Compatibilidad con Odoo estándar           |
| `LIC_MAT`        | Abreviación licencia maternidad            |
| `LIC_PAT`        | Abreviación licencia paternidad            |

### Vacaciones

| Código           | Uso recomendado                            |
|------------------|--------------------------------------------|
| `VACACIONES`     | Vacaciones                                 |
| `VACATION`       | Compatibilidad con Odoo estándar           |
| `VAC`            | Abreviación vacaciones                     |

### Licencia Remunerada

| Código           | Uso recomendado                            |
|------------------|--------------------------------------------|
| `LICENCIA_REM`   | Licencia remunerada general                |
| `LIC_REM`        | Abreviación licencia remunerada            |
| `PERMISO`        | Permiso remunerado                         |

### Licencia No Remunerada

| Código           | Uso recomendado                            |
|------------------|--------------------------------------------|
| `LICENCIA_NR`    | Licencia no remunerada general             |
| `LIC_NR`         | Abreviación licencia no remunerada         |
| `UNPAID`         | Compatibilidad con Odoo estándar           |
| `SIN_SUELDO`     | Suspensión sin sueldo                      |

> **Nota:** Las ausencias con códigos no reconocidos se incluyen en el resumen textual
> como *"Otra ausencia (no mapeada)"* pero **no suman días** a ningún contador.

---

## Cómo Funciona el Botón "Detectar Novedades"

### Flujo de operación

1. El usuario abre una nómina (`hr.payslip`) con fechas `date_from` y `date_to` definidas.
2. Pulsa el botón **"Detectar Novedades"** (acción `action_detect_leaves`).
3. El sistema busca en `hr.leave` todas las ausencias que cumplan:
   - Mismo empleado (`employee_id`).
   - Estado **validado** (`state = 'validate'`).
   - Solapamiento con el período: `date_from ≤ payslip.date_to` **Y** `date_to ≥ payslip.date_from`.
4. Para cada ausencia encontrada:
   - Recorta las fechas al período de la nómina (no cuenta días fuera del período).
   - Clasifica según el `code` del tipo de ausencia.
   - Acumula los días en el contador correspondiente.
5. Escribe los totales y el resumen en los campos de la nómina.
6. Muestra una notificación al usuario con el número de ausencias procesadas.

### Ejemplo

Si una nómina cubre del 1 al 30 de junio y el empleado tiene:
- Una incapacidad del 5 al 8 de junio (código `INC_COMUN`) → 4 días incapacidad
- Vacaciones del 15 al 25 de junio (código `VACACIONES`) → 11 días vacaciones
- Una licencia no remunerada del 28 de junio al 3 de julio (código `LICENCIA_NR`) → 3 días (solo los que caen en junio)

El resultado sería:
- `l10n_co_ne_dias_incapacidad` = 4
- `l10n_co_ne_dias_vacaciones` = 11
- `l10n_co_ne_dias_licencia_nr` = 3
- Resumen:
  ```
  Incapacidad: 4 días (Incapacidad Común)
  Vacaciones: 11 días (Vacaciones)
  Lic. No Remunerada: 3 días (Licencia No Remunerada)
  ```

---

## Configuración Recomendada de Tipos de Ausencia

Para que la detección automática funcione correctamente, configure los tipos de ausencia
en **Ausencias → Configuración → Tipos de ausencia** con los códigos recomendados en el
campo `Código`:

| Nombre del tipo              | Código recomendado | Categoría NE              |
|------------------------------|--------------------|---------------------------|
| Incapacidad Común            | `INC_COMUN`        | Incapacidad               |
| Incapacidad Laboral (ATEP)   | `INC_LABORAL`      | Incapacidad               |
| Licencia de Maternidad       | `LIC_MAT`          | Licencia Mat/Pat          |
| Licencia de Paternidad       | `LIC_PAT`          | Licencia Mat/Pat          |
| Vacaciones                   | `VACACIONES`       | Vacaciones                |
| Licencia Remunerada          | `LIC_REM`          | Licencia remunerada       |
| Permiso Remunerado           | `PERMISO`          | Licencia remunerada       |
| Licencia No Remunerada       | `LIC_NR`           | Licencia no remunerada    |
| Suspensión Sin Sueldo        | `SIN_SUELDO`       | Licencia no remunerada    |

> **Importante:** No se crearon datos XML precargados (`hr.leave.type`) porque los tipos
> de ausencia deben ser configurados por cada cliente según su realidad operativa. La
> tabla anterior es solo una guía de códigos recomendados.

---

## Notas Técnicas

- El modelo usa `_inherit = 'hr.payslip'` (herencia por extensión), por lo que **no requiere
  reglas de acceso (ACL) adicionales** — se aplican las del modelo base.
- El mapeo de códigos se define como constante de clase `_LEAVE_CODE_MAP` para facilitar
  su extensión por módulos hijos.
- Los días se calculan con recorte al período de la nómina para evitar contar días fuera del
  rango.
- El campo `code` de `hr.leave.type` es nativo de Odoo 18 y se usa directamente para la
  clasificación.
