# CHANGELOG — Retención en la Fuente (l10n.co.retefuente.uvt)

## Versión 18.0.2.0.0 — 2026-05-22

### Descripción

Implementación del cálculo automático de **Retención en la Fuente** para nómina colombiana, según el **Art. 383 del Estatuto Tributario** (Procedimiento 1) y Art. 386 ET (Procedimiento 2).

---

## Archivos Creados

| Archivo | Descripción |
|---|---|
| `models/hr_retefuente.py` | Modelo `l10n.co.retefuente.uvt` con lógica de cálculo |
| `data/hr_retefuente_data.xml` | Datos iniciales: UVT 2024 ($47.065) y UVT 2025 ($49.799) |
| `views/hr_retefuente_views.xml` | Vistas tree, form, acción y menú |
| `CHANGELOG_retefuente.md` | Este documento |

---

## Fórmula de Depuración — Paso a Paso

La depuración de la base gravable sigue el siguiente procedimiento:

```
 PASO   CONCEPTO                                         FÓRMULA / LÍMITE
─────── ──────────────────────────────────────────────── ────────────────────────────────
  1.    Ingreso bruto mensual                            Salario + otros ingresos
  2.    (-) Aportes obligatorios salud empleado           IBC_salud × 4%
  3.    (-) Aportes obligatorios pensión empleado         IBC_pensión × 4%
  4.    (-) Aportes voluntarios pensión                   Máximo 25% del ingreso bruto
  5.    (-) AFC (Ahorro Fomento Construcción)             Máximo 30% del ingreso bruto
  6.    (-) Deducción por dependientes                    10% del ingreso, máx 32.5 UVT/mes
        ────────────────────────────────────────────────
  7.    = Subtotal depurado
  8.    (-) Renta exenta 25%                              25% del subtotal, máx 240 UVT/mes
        ────────────────────────────────────────────────
  9.    = BASE GRAVABLE
 10.    Convertir a UVT:  base_gravable ÷ valor_UVT
 11.    Aplicar tabla marginal (Art. 383 ET)
 12.    Convertir retención de UVT a pesos:  ret_UVT × valor_UVT
```

---

## Tabla Marginal — Art. 383 del Estatuto Tributario

| Rango en UVT | Tarifa Marginal | Instrucción |
|---|---|---|
| > 0 hasta 95 | 0% | 0 |
| > 95 hasta 150 | 19% | (Ingreso UVT − 95) × 19% |
| > 150 hasta 360 | 28% | (Ingreso UVT − 150) × 28% + 10 UVT |
| > 360 hasta 640 | 33% | (Ingreso UVT − 360) × 33% + 69 UVT |
| > 640 hasta 945 | 35% | (Ingreso UVT − 640) × 35% + 162 UVT |
| > 945 hasta 2300 | 37% | (Ingreso UVT − 945) × 37% + 268 UVT |
| > 2300 | 39% | (Ingreso UVT − 2300) × 39% + 770 UVT |

---

## Ejemplo Numérico — Salario de $5.000.000

**Supuestos:**
- Salario bruto mensual: **$5.000.000**
- IBC salud = IBC pensión = $5.000.000
- Sin aportes voluntarios a pensión
- Sin AFC
- Sin dependientes
- UVT 2024: **$47.065**
- Procedimiento: **1** (Art. 383 ET)

### Cálculo Paso a Paso

```
 CONCEPTO                              VALOR ($)        NOTAS
────────────────────────────────────── ──────────────── ──────────────────────────────
 1. Ingreso bruto                       5.000.000,00
 2. (-) Aporte salud (4%)                (200.000,00)   = 5.000.000 × 4%
 3. (-) Aporte pensión (4%)              (200.000,00)   = 5.000.000 × 4%
 4. (-) Aportes vol. pensión                    0,00    No aplica
 5. (-) AFC                                     0,00    No aplica
 6. (-) Dependientes                            0,00    Sin dependientes
    ────────────────────────────────────────────────
 7. = Subtotal depurado                 4.600.000,00

 8. (-) Renta exenta 25%              (1.150.000,00)   = 4.600.000 × 25%
                                                        Límite: 240 × 47.065 = 11.295.600
                                                        1.150.000 < 11.295.600 → OK
    ────────────────────────────────────────────────
 9. = BASE GRAVABLE                    3.450.000,00

10. Conversión a UVT:
    3.450.000 ÷ 47.065 = 73,2967 UVT

11. Tabla marginal:
    73,2967 UVT está en rango [0 – 95] → Tarifa 0%
    Retención = 0 UVT

12. Retención en pesos:
    0 UVT × $47.065 = $0
```

### Resultado Final

| Concepto | Valor |
|---|---|
| **Base gravable** | $3.450.000 |
| **Base en UVT** | 73,2967 UVT |
| **Retención en UVT** | 0 UVT |
| **★ Retención en pesos** | **$0** |

> **Nota:** Con un salario de $5.000.000, la base gravable depurada resulta en 73,30 UVT, que está por debajo del umbral de 95 UVT. Por lo tanto, no se genera retención en la fuente.

---

## Ejemplo Adicional — Salario de $10.000.000 (genera retención)

**Supuestos:** Mismo que anterior, pero con salario de $10.000.000 y con dependientes.

```
 CONCEPTO                              VALOR ($)        NOTAS
────────────────────────────────────── ──────────────── ──────────────────────────────
 1. Ingreso bruto                      10.000.000,00
 2. (-) Aporte salud (4%)                (400.000,00)   = 10.000.000 × 4%
 3. (-) Aporte pensión (4%)              (400.000,00)   = 10.000.000 × 4%
 4. (-) Aportes vol. pensión                    0,00
 5. (-) AFC                                     0,00
 6. (-) Dependientes (10%, máx 32.5 UVT)
         10% × 10.000.000 = 1.000.000
         Máx: 32,5 × 47.065 = 1.529.613
         1.000.000 < 1.529.613 → OK
                                        (1.000.000,00)
    ────────────────────────────────────────────────
 7. = Subtotal depurado                 8.200.000,00

 8. (-) Renta exenta 25%              (2.050.000,00)   = 8.200.000 × 25%
                                                        Límite: 240 × 47.065 = 11.295.600
                                                        2.050.000 < 11.295.600 → OK
    ────────────────────────────────────────────────
 9. = BASE GRAVABLE                    6.150.000,00

10. Conversión a UVT:
    6.150.000 ÷ 47.065 = 130,6617 UVT

11. Tabla marginal:
    130,6617 UVT está en rango [95 – 150] → Tarifa 19%
    Retención = (130,6617 − 95) × 19% = 35,6617 × 0,19 = 6,7757 UVT

12. Retención en pesos:
    6,7757 UVT × $47.065 = $318.919
```

### Resultado Final

| Concepto | Valor |
|---|---|
| **Base gravable** | $6.150.000 |
| **Base en UVT** | 130,6617 UVT |
| **Retención en UVT** | 6,7757 UVT |
| **★ Retención en pesos** | **$318.919** |

---

## Referencias Legales

- **Estatuto Tributario, Art. 383** — Tabla de retención en la fuente para ingresos laborales.
- **Estatuto Tributario, Art. 386** — Procedimiento 2 de retención (porcentaje fijo semestral).
- **Estatuto Tributario, Art. 387** — Deducciones por dependientes y vivienda.
- **Decreto 1070 de 2013** — Reglamentación del Procedimiento 2.
- **Resolución DIAN 001264 del 18/11/2023** — Valor UVT 2024: $47.065.
- **Resolución DIAN 001312 del 22/11/2024** — Valor UVT 2025: $49.799.

---

## Modelo de Datos

### `l10n.co.retefuente.uvt`

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `year` | Char | ✅ | Año fiscal (4 dígitos) |
| `uvt_value` | Float | ✅ | Valor de la UVT en pesos |
| `procedure` | Selection | ✅ | Procedimiento 1 o 2 |
| `percentage_procedure2` | Float | | % fijo para Proc. 2 |
| `active` | Boolean | | Permite archivar registros |
| `company_id` | Many2one | | Compañía (multi-company) |
| `notes` | Text | | Notas internas |

### Métodos Principales

| Método | Descripción |
|---|---|
| `compute_retefuente(employee, gross_salary, ibc_pension, ibc_salud, company)` | Cálculo completo con depuración y tabla marginal |
| `_apply_marginal_table(base_uvt)` | Aplica tabla marginal Art. 383 ET |
| `get_uvt_for_year(year, company)` | Busca el registro de UVT vigente |
| `action_compute_example()` | Cálculo de prueba con salario de $5M |
