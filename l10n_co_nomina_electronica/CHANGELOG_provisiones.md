# CHANGELOG — Provisiones Automáticas de Prestaciones Sociales

## Versión 18.0.2.0.0 — 2026-05-22

### Descripción

Implementación del módulo de cálculo mensual automático de provisiones para
prestaciones sociales colombianas. Incluye prima de servicios, cesantías,
intereses a las cesantías y vacaciones.

---

## Modelos Creados

### `l10n.co.hr.provision` (Cabecera)
Registro mensual que agrupa las provisiones de todos los empleados activos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char (computed) | "Provisión MM/YYYY" |
| `year` | Char | Año de la provisión |
| `month` | Selection (01-12) | Mes de la provisión |
| `company_id` | Many2one (res.company) | Compañía |
| `line_ids` | One2many | Líneas por empleado |
| `state` | Selection | draft → confirmed → posted |
| `total_prima` | Float (computed) | Suma de primas |
| `total_cesantias` | Float (computed) | Suma de cesantías |
| `total_intereses` | Float (computed) | Suma de intereses |
| `total_vacaciones` | Float (computed) | Suma de vacaciones |

### `l10n.co.hr.provision.line` (Línea por Empleado)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `provision_id` | Many2one | Referencia a la cabecera |
| `employee_id` | Many2one (hr.employee) | Empleado |
| `contract_id` | Many2one (hr.contract) | Contrato activo |
| `wage` | Float | Salario base del contrato |
| `aux_transporte` | Float | Auxilio de transporte (si aplica) |
| `base_prestacional` | Float (computed) | wage + aux_transporte |
| `prima` | Float | Provisión de prima |
| `cesantias` | Float | Provisión de cesantías |
| `intereses_cesantias` | Float | Provisión de intereses |
| `vacaciones` | Float | Provisión de vacaciones |
| `total` | Float (computed) | Suma de todas las provisiones |

### `l10n.co.hr.provision.wizard` (Wizard)
Asistente para crear provisiones seleccionando año y mes.

---

## Fórmulas Utilizadas

### 1. Prima de Servicios (Art. 306 CST)
```
prima_mensual = base_prestacional / 12
```
Corresponde a 30 días de salario por año de servicio, provisionado mensualmente.

### 2. Cesantías (Art. 249 CST)
```
cesantias_mensual = base_prestacional / 12
```
Corresponde a 30 días de salario por año de servicio.

### 3. Intereses a las Cesantías (Ley 52 de 1975)
```
intereses_mensual = cesantias_mensual × 0.12
```
12% anual sobre el saldo de cesantías acumuladas.

### 4. Vacaciones (Art. 186 CST)
```
vacaciones_mensual = salario_base / 24
```
15 días hábiles de descanso remunerado por año. **No incluye auxilio de transporte.**

### Base Prestacional
```
Si salario ordinario:
    base_prestacional = salario + auxilio_transporte

Si salario integral:
    base_prestacional = salario × 70%
```

### Auxilio de Transporte
```
Aplica SI:
    salario <= 2 × SMMLV  Y  contrato NO es integral

No aplica SI:
    salario > 2 × SMMLV  O  contrato es integral
```

---

## Ejemplo: Empleado con Salario de $2,200,000

### Datos
| Parámetro | Valor |
|-----------|-------|
| SMMLV 2026 | $1,300,000 |
| Auxilio Transporte 2026 | $162,000 |
| Salario empleado | $2,200,000 |
| Tope 2 SMMLV | $2,600,000 |

### Cálculo
El salario ($2,200,000) es **menor** que 2 SMMLV ($2,600,000), por lo tanto **SÍ aplica** auxilio de transporte.

```
Base prestacional = $2,200,000 + $162,000 = $2,362,000

Prima mensual         = $2,362,000 / 12 = $196,833.33
Cesantías mensual     = $2,362,000 / 12 = $196,833.33
Intereses cesantías   = $196,833.33 × 0.12 = $23,620.00
Vacaciones mensual    = $2,200,000 / 24 = $91,666.67
────────────────────────────────────────────────
Total provisión mes   = $508,953.33
```

---

## Ejemplo: Salario Integral de $13,000,000

### Datos
| Parámetro | Valor |
|-----------|-------|
| Salario integral | $13,000,000 |
| Factor prestacional | 70% |

### Cálculo
Salario integral: **no aplica** auxilio de transporte. La base prestacional es el 70% del salario.

```
Base prestacional = $13,000,000 × 0.70 = $9,100,000

Prima mensual         = $9,100,000 / 12 = $758,333.33
Cesantías mensual     = $9,100,000 / 12 = $758,333.33
Intereses cesantías   = $758,333.33 × 0.12 = $91,000.00
Vacaciones mensual    = $13,000,000 / 24 = $541,666.67
────────────────────────────────────────────────
Total provisión mes   = $2,149,333.33
```

---

## Frecuencia Recomendada

| Aspecto | Recomendación |
|---------|---------------|
| **Periodicidad** | Mensual — ejecutar al cierre de cada mes |
| **Momento** | Después de procesar la nómina del mes |
| **Responsable** | Responsable de nómina o contador |
| **Flujo** | Generar → Revisar → Confirmar → Contabilizar |

### Proceso sugerido:
1. **Nómina → Provisiones → Generar Provisión** (wizard)
2. Seleccionar año y mes
3. Se calcula automáticamente para todos los contratos activos
4. Revisar el detalle por empleado en la pestaña de líneas
5. Si hay ajustes, recalcular con el botón "Calcular Provisiones"
6. Una vez conforme, hacer clic en "Contabilizar"

---

## Archivos Creados

| Archivo | Descripción |
|---------|-------------|
| `models/hr_provision.py` | Modelos `l10n.co.hr.provision` y `l10n.co.hr.provision.line` |
| `wizard/hr_provision_wizard.py` | Wizard `l10n.co.hr.provision.wizard` |
| `wizard/hr_provision_wizard_views.xml` | Vista del wizard |
| `views/hr_provision_views.xml` | Vistas tree, form, search + menús |
| `CHANGELOG_provisiones.md` | Esta documentación |

## Seguridad (ACL)

Los permisos ya están configurados en `security/ir.model.access.csv`:

| Modelo | Manager | User |
|--------|---------|------|
| `l10n.co.hr.provision` | CRUD | R |
| `l10n.co.hr.provision.line` | CRUD | R |
| `l10n.co.hr.provision.wizard` | CRUD | — |

---

## Notas Técnicas

- Los campos `l10n_co_ne_smmlv` y `l10n_co_ne_aux_transporte` se leen
  de `res.company`. Si no están configurados, se usan valores por defecto
  de $1,300,000 y $162,000 respectivamente.
- El campo `l10n_co_ne_integral_salary` en `hr.contract` determina si
  el contrato es integral.
- Solo se procesan contratos en estado `open` (En Proceso).
- Existe una restricción SQL `UNIQUE(year, month, company_id)` para evitar
  duplicados por período.
