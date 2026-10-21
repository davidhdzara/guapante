# CHANGELOG – Liquidación Definitiva de Contrato

## Módulo: `l10n_co_nomina_electronica`
## Fecha: 2026-05-22
## Autor: InSoTech - Infinity Solutions Technology S.A.S

---

## Descripción General

Implementación del cálculo automático de **liquidación definitiva** cuando un
empleado se retira de la empresa, conforme al Código Sustantivo del Trabajo
(CST) de Colombia.

---

## Archivos Creados

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `models/hr_liquidacion.py` | Modelo | Modelo principal `l10n.co.hr.liquidacion` |
| `wizard/hr_liquidacion_wizard.py` | Wizard | Asistente `l10n.co.hr.liquidacion.wizard` |
| `views/hr_liquidacion_views.xml` | Vistas | Form, Tree, Search + Menú |
| `wizard/hr_liquidacion_wizard_views.xml` | Vistas | Form del wizard + Action |
| `CHANGELOG_liquidacion.md` | Doc | Este documento |

---

## Fórmulas de Cada Concepto

### 1. Salario Pendiente

Días trabajados del último mes que no se han pagado:

```
salario_pendiente = (salario_mensual / 30) × días_del_mes_trabajados
```

### 2. Prima de Servicios Proporcional (Art. 306–308 CST)

Proporcional al semestre laborado (ene–jun o jul–dic):

```
prima_proporcional = base_prestacional × días_semestre / 360
```

Donde `base_prestacional = salario + auxilio_de_transporte`.

### 3. Cesantías Proporcionales (Art. 249 CST)

Proporcional al tiempo laborado en el año en curso (desde 1 de enero o inicio
del contrato si es posterior):

```
cesantias_proporcionales = base_prestacional × días_año / 360
```

### 4. Intereses sobre Cesantías (Ley 52 de 1975)

12% anual sobre las cesantías proporcionales:

```
intereses_cesantias = cesantias_proporcionales × 0.12 × días_año / 360
```

### 5. Vacaciones Proporcionales (Art. 186 CST)

15 días hábiles de vacaciones por año trabajado = salario / 24 por mes:

```
vacaciones_proporcionales = salario_mensual × días_laborados / 720
```

### 6. Vacaciones Pendientes

Valor monetario de los días de vacaciones acumulados y **no disfrutados**.
Se ingresa manualmente según el historial del empleado.

### 7. Indemnización por Despido sin Justa Causa (Art. 64 CST)

Solo aplica cuando `cause = 'sin_justa_causa'`.

---

## Tabla de Indemnización por Tipo de Contrato

| Tipo de Contrato | Rango Salarial | Primer Año | Años Adicionales |
|------------------|---------------|------------|------------------|
| **Término Fijo** | Cualquiera | Salario × días restantes del contrato (mín. 15 días) | N/A |
| **Indefinido** | < 10 SMMLV | 30 días de salario | 20 días por año adicional |
| **Indefinido** | ≥ 10 SMMLV | 20 días de salario | 15 días por año adicional |
| **Obra/Labor** | Cualquiera | No aplica indemnización estándar | N/A |
| **Aprendizaje** | Cualquiera | No aplica indemnización estándar | N/A |

### Fórmulas Detalladas

#### Contrato Fijo
```python
indemnizacion = max(salario / 2, salario / 30 * 15)
```

#### Contrato Indefinido – Salario < 10 SMMLV
```python
if años <= 1:
    indemnizacion = salario  # 30 días
else:
    indemnizacion = salario + (salario / 30 * 20 * (años - 1))
```

#### Contrato Indefinido – Salario ≥ 10 SMMLV
```python
if años <= 1:
    indemnizacion = salario / 30 * 20
else:
    indemnizacion = (salario / 30 * 20) + (salario / 30 * 15 * (años - 1))
```

---

## Ejemplo Completo

### Datos del Empleado

| Campo | Valor |
|-------|-------|
| Empleado | María García |
| Contrato | Término Indefinido |
| Fecha inicio | 2024-03-15 |
| Fecha retiro | 2026-05-22 |
| Salario mensual | $2,500,000 COP |
| Auxilio transporte | $162,000 COP |
| Causa | Despido sin Justa Causa |
| SMMLV | $1,300,000 COP |

### Cálculos

| Concepto | Fórmula | Cálculo | Resultado |
|----------|---------|---------|-----------|
| **Días laborados** | `date_end - date_start` | `2026-05-22 - 2024-03-15` | **798 días** |
| **Base prestacional** | `salario + aux_transporte` | `2,500,000 + 162,000` | **$2,662,000** |
| **Salario pendiente** | `(salario/30) × día_mes` | `(2,500,000/30) × 22` | **$1,833,333** |
| **Prima proporcional** | `base × días_sem/360` | `2,662,000 × 142/360` (desde ene 1) | **$1,049,789** |
| **Cesantías proporcionales** | `base × días_año/360` | `2,662,000 × 142/360` (desde ene 1) | **$1,049,789** |
| **Intereses cesantías** | `cesantías × 0.12 × días/360` | `1,049,789 × 0.12 × 142/360` | **$49,690** |
| **Vacaciones proporcionales** | `salario × días/720` | `2,500,000 × 798/720` | **$2,770,833** |
| **Vacaciones pendientes** | Manual | (asumiendo 0) | **$0** |
| **Indemnización** | Art. 64 CST, < 10 SMMLV, > 1 año | `2,500,000 + (2,500,000/30 × 20 × 1.19)` | **$4,480,556** |
| | | | |
| **TOTAL LIQUIDACIÓN** | Suma de todo | | **$11,233,989** |

### Detalle de la Indemnización

```
Salario = $2,500,000 (< $13,000,000 = 10 SMMLV)
Años = 798 / 365 = 2.19 años
Indemnización = salario + (salario/30 × 20 × (2.19 - 1))
             = 2,500,000 + (83,333 × 20 × 1.19)
             = 2,500,000 + 1,980,556
             = $4,480,556
```

---

## Flujo de Estados

```
┌──────────┐    Calcular    ┌────────────┐    Aprobar    ┌──────────┐    Pagar    ┌────────┐
│ Borrador │ ──────────────→ │ Calculado  │ ────────────→ │ Aprobado │ ──────────→ │ Pagado │
└──────────┘                └────────────┘               └──────────┘            └────────┘
     ↑                           │                            │
     └───────────────────────────┴────────────────────────────┘
                        Volver a Borrador
```

---

## Modelo de Seguridad (ACL)

Los accesos están definidos en `security/ir.model.access.csv`:

| Modelo | Grupo | Leer | Escribir | Crear | Eliminar |
|--------|-------|------|----------|-------|----------|
| `l10n.co.hr.liquidacion` | Payroll Manager | ✅ | ✅ | ✅ | ✅ |
| `l10n.co.hr.liquidacion` | Payroll User | ✅ | ❌ | ❌ | ❌ |
| `l10n.co.hr.liquidacion.wizard` | Payroll Manager | ✅ | ✅ | ✅ | ✅ |

---

## Notas Técnicas

- El campo `company_id.l10n_co_ne_smmlv` se usa para determinar el rango
  salarial en el cálculo de indemnización. Valor por defecto: `1,300,000`.
- El auxiliar de transporte aplica solo si el salario ≤ 2 SMMLV y el contrato
  no es de salario integral (`l10n_co_ne_integral_salary = False`).
- El tipo de contrato se mapea automáticamente desde el campo DIAN
  (`l10n_co_ne_contract_type`) del contrato.
- Los campos monetarios usan `digits='Account'` para precisión contable.
- El wizard crea el registro de liquidación y lo abre directamente en
  modo formulario para revisión y cálculo.
