# Parametrización SMMLV, Auxilio Transporte, UVT y Exoneración Ley 1607

## Resumen del cambio

Se implementó un sistema configurable a nivel de compañía para los parámetros
de nómina colombiana. Los valores de SMMLV, Auxilio de Transporte, UVT y la
exoneración de aportes (Ley 1607/2012) ya **no están hardcodeados** y pueden
ser actualizados desde la configuración de la empresa.

---

## Archivos modificados / creados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `models/res_company.py` | Modificado | Se agregaron 4 campos nuevos al modelo `res.company` |
| `views/res_company_views.xml` | Modificado | Se agregó sección "Parámetros Nómina Colombia" en la vista |
| `data/hr_payroll_params_data.xml` | Creado | Datos por defecto con `noupdate="1"` para la compañía principal |

---

## Campos agregados a `res.company`

| Campo técnico | Tipo | Valor por defecto | Descripción |
|---------------|------|-------------------|-------------|
| `l10n_co_ne_smmlv` | `Float` | 1.300.000 | Salario Mínimo Mensual Legal Vigente |
| `l10n_co_ne_aux_transporte` | `Float` | 162.000 | Auxilio de Transporte mensual |
| `l10n_co_ne_uvt` | `Float` | 47.065 | Unidad de Valor Tributario vigente |
| `l10n_co_ne_exoneration_1607` | `Boolean` | `False` | Exoneración aportes SENA/ICBF (Art. 114-1 ET) |

---

## Valores por defecto (2024)

Los valores se precargan vía `data/hr_payroll_params_data.xml` con `noupdate="1"`:

- **SMMLV**: $1.300.000 COP
- **Auxilio de Transporte**: $162.000 COP
- **UVT**: $47.065 COP
- **Tope Auxilio de Transporte**: 2 × SMMLV (se calcula dinámicamente)
- **Exoneración Ley 1607/2012**: Deshabilitada

> **Nota**: El atributo `noupdate="1"` asegura que si el usuario modifica estos
> valores manualmente, NO serán sobrescritos al actualizar el módulo.

---

## Cómo actualizar los valores cada año

Cada **1 de enero** el gobierno colombiano publica los nuevos valores de SMMLV,
Auxilio de Transporte y UVT. Para actualizarlos:

1. Ir a **Ajustes → Empresas → [Su Empresa]**
2. Abrir la pestaña **"Nómina Electrónica DIAN"**
3. Buscar la sección **"Parámetros Nómina Colombia"**
4. Actualizar los campos:
   - **SMMLV Vigente** → Nuevo salario mínimo
   - **Auxilio de Transporte** → Nuevo valor de auxilio
   - **Valor UVT** → Nuevo valor publicado por la DIAN
5. Guardar los cambios

> **Importante**: Estos cambios aplican **hacia adelante**. Las nóminas ya
> generadas conservan los valores con los que fueron calculadas.

---

## Exoneración Ley 1607/2012 (Art. 114-1 ET)

Si la empresa es persona jurídica del régimen contributivo y cumple los
requisitos legales, puede activar la casilla **"Exoneración Ley 1607/2012"**.
Esto indica que la empresa queda exonerada de aportes a:

- **SENA** (2%)
- **ICBF** (3%)

Para empleados con salario inferior a **10 SMMLV**.

---

## Uso programático

Para acceder a estos valores desde código Python en otros modelos:

```python
company = self.env.company
smmlv = company.l10n_co_ne_smmlv
aux_transporte = company.l10n_co_ne_aux_transporte
uvt = company.l10n_co_ne_uvt
tope_aux = 2 * smmlv  # Tope para auxilio de transporte
exonerada = company.l10n_co_ne_exoneration_1607
```

---

*Fecha de implementación: 2026-05-22*
*Módulo: l10n_co_nomina_electronica*
