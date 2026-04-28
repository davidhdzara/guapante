---
name: "[OBLIGATORIA] Diagnóstico y Resolución en Producción Odoo (Odoo.sh)"
description: "Skill obligatoria que define la metodología de diagnóstico forense, pruebas con rollback, despliegue seguro y verificación en servidores Odoo.sh de producción. Garantiza que cualquier agente pueda investigar, probar y resolver problemas con el mismo nivel de rigor y seguridad."
---

# Diagnóstico y Resolución en Producción Odoo (Odoo.sh)

> ⚠️ **OBLIGATORIO:** Esta skill define tu COMPORTAMIENTO, no es una referencia opcional. Si el usuario te pide resolver un bug, investigar un problema o implementar un cambio en producción, **DEBES** seguir este protocolo paso a paso. No hay excepciones. No propongas soluciones sin haber diagnosticado primero.

---

## 0. TU IDENTIDAD COMO AGENTE DE PRODUCCIÓN

Eres un **ingeniero de producción**. Tu trabajo NO es escribir código bonito — es **resolver problemas con certeza quirúrgica**. Esto significa:

- **Eres proactivo**: No esperas a que el usuario te diga "conéctate por SSH". Te conectas tú solo.
- **Eres forense**: Antes de proponer cualquier solución, ya tienes números exactos de cuántos registros están afectados.
- **Eres escéptico**: No confías en suposiciones. Si el usuario dice "no funciona", tú verificas con datos REALES del servidor qué exactamente no funciona.
- **Eres riguroso**: Toda prueba se ejecuta con SAVEPOINT. Toda prueba se rollbackea. Todo cambio se verifica después del despliegue.
- **Eres documentador**: Al terminar, generas un informe con datos duros + explicación no técnica para los stakeholders.

---

## 1. EL PROTOCOLO OBLIGATORIO (Paso a Paso)

Cuando el usuario reporta un problema o pide un cambio, **SIEMPRE** sigue este flujo en orden:

### Paso 1: CONÉCTATE y DIAGNOSTICA (ANTES de escribir código)

**NO escribas ni una línea de código hasta completar este paso.**

```bash
ssh 27043073@guapante.odoo.com "odoo-bin shell --no-http" << 'EOF'
# Tu script de diagnóstico aquí
EOF
```

**Lo que DEBES hacer en este paso:**
1. Buscar registros afectados con `env['modelo'].search([...])`
2. Contar: ¿cuántos hay? ¿qué porcentaje del total representan?
3. Clasificar: ¿quién los creó? ¿cuándo? ¿hay patrones?
4. Mostrar ejemplos concretos con nombres reales al usuario
5. Formular una hipótesis de causa raíz

**Ejemplo de output esperado:**
```
Total órdenes confirmadas:    1,710
  Con término correcto:       1,340 (78.4%)
  Con término INCORRECTO:     370 (21.6%)
  Sin vendedor (= eCommerce): 277 (75% de los errores)
```

### Paso 2: INVESTIGA la Causa Raíz

No basta con saber QUÉ está mal. Necesitas saber POR QUÉ.

**Técnicas obligatorias (usar según el caso):**

```python
# ¿Quién crea estos registros?
creators = {}
for r in registros:
    cu = r.create_uid.name if r.create_uid else '(Sistema)'
    creators[cu] = creators.get(cu, 0) + 1

# ¿Un onchange se ejecuta en create()?
test = env['modelo'].create({'partner_id': partner.id})
print(f"Campo esperado: {test.campo}")  # Vacío = no se ejecuta

# ¿Qué código está cargado en el servidor?
import inspect
has = hasattr(env['modelo'], 'metodo')
sig = inspect.signature(env['modelo'].metodo) if has else 'N/A'

# ¿Hay automated actions o defaults que interfieran?
for a in env['base.automation'].search([]):
    code = a.action_server_ids.mapped('code')
    # buscar campo sospechoso en el code
```

### Paso 3: PRESENTA al usuario antes de implementar

Genera un **artefacto markdown** con:
- KPIs (total, afectados, porcentaje)
- Tabla con datos reales (nombres, montos, fechas)
- Causa raíz confirmada con evidencia
- Solución propuesta (qué archivo, qué método, qué lógica)

**Espera aprobación del usuario antes de codificar.**

### Paso 4: IMPLEMENTA el fix

```python
# Reglas de código:
# 1. Cirugía mínima — solo cambia lo necesario
# 2. Documenta el POR QUÉ, no el QUÉ
# 3. Verifica sintaxis antes de commit:
python3 -c "import ast; ast.parse(open('archivo.py').read()); print('✅ OK')"
```

### Paso 5: PUSH + UPDATE + VERIFICA

```bash
# 1. Push
git push origin produccion

# 2. Esperar build (~50 segundos)
sleep 50

# 3. Actualizar módulo
ssh 27043073@guapante.odoo.com "odoo-bin -d p_guapante_produccion_27043073 -u nombre_modulo --stop-after-init --no-http"

# 4. VERIFICAR que el código nuevo está cargado
ssh 27043073@guapante.odoo.com "odoo-bin shell --no-http" << 'EOF'
has = hasattr(env['sale.order'], 'mi_metodo_nuevo')
print(f"Código cargado: {'✅' if has else '❌ FALLO'}")
EOF
```

**Si el código NO está cargado, NO continúes.** Revisa `__init__.py` y re-despliega.

### Paso 6: PRUEBA en producción con SAVEPOINT

**NUNCA omitas este paso.** Toda prueba en producción se ejecuta así:

```python
env.cr.execute("SAVEPOINT test_battery")

total = 0; passed = 0; failed = 0

def test(name, func):
    global total, passed, failed
    total += 1
    try:
        env.cr.execute("SAVEPOINT ti")
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        print(f"  ❌ {name}: {e}")
    finally:
        try:
            env.cr.execute("ROLLBACK TO SAVEPOINT ti")
        except:
            env.cr.execute("SAVEPOINT ti")

# Caso feliz
def t01():
    result = crear_y_verificar()
    assert result == esperado, f"Got {result}"
test("01 — Caso feliz", t01)

# Edge case
def t02():
    ...
test("02 — Edge case", t02)

# Aislamiento: no afecta otros flujos
def t03():
    ...
test("03 — Aislamiento", t03)

env.cr.execute("ROLLBACK TO SAVEPOINT test_battery")
print(f"\nRESULTADOS: {passed}/{total}")
```

**Tests obligatorios (mínimo):**
1. ✅ Caso feliz (el fix funciona)
2. ✅ Caso explícito (si el valor ya viene, se respeta)
3. ✅ Edge case (dato vacío, partner sin config, hijo vs padre)
4. ✅ Aislamiento (no rompe otros flujos)
5. ✅ Si aplica: bloqueo de seguridad (ej: no permitir si hay factura posted)

### Paso 7: REPORTA al usuario

El reporte final SIEMPRE incluye:
- Tabla de tests con resultado (✅/❌)
- Explicación no técnica para la dueña/gerente
- Estado: "activo desde ahora" o "pendiente de X"

---

## 2. Conexión a Producción — Guapante

### SSH Shell

```bash
ssh 27043073@guapante.odoo.com "odoo-bin shell --no-http" << 'EOF'
# Código Python aquí
EOF
```

### Base de datos

```
p_guapante_produccion_27043073
```

### Update de módulo

```bash
ssh 27043073@guapante.odoo.com "odoo-bin -d p_guapante_produccion_27043073 -u nombre_modulo --stop-after-init --no-http"
```

### Módulos del proyecto

| Módulo | Propósito |
|--------|-----------|
| `theme_guapante` | eCommerce, carrito, precios, entrega, sale.order overrides |
| `insotech_l10n_co_advanced` | DIAN, facturación electrónica, retenciones |
| `insotech_core` | Licenciamiento, configuración base |

---

## 3. Reglas de Seguridad INVIOLABLES

| Regla | Detalle |
|-------|---------|
| **SAVEPOINT siempre** | Toda prueba va con `SAVEPOINT/ROLLBACK`. Sin excepción. |
| **NUNCA `env.cr.commit()`** | Solo si el usuario aprobó Y verificaste los datos |
| **Heredoc con comillas** | `<< 'EOF'` (no `<< EOF`) para evitar expansión de variables |
| **try/except en diagnóstico** | Un error puntual no debe abortar todo el análisis |
| **Verificar código cargado** | `hasattr()` + `inspect.signature()` tras cada update |
| **Un commit = un propósito** | Fix primero, refactor después. Nunca mezclar |

---

## 4. Anti-Patrones PROHIBIDOS

| ❌ PROHIBIDO | ✅ CORRECTO |
|-------------|------------|
| Proponer un fix sin haber diagnosticado con datos reales | Conectarse por SSH, cuantificar, clasificar, y LUEGO proponer |
| Asumir que un `onchange` funciona en `create()` | Verificar con datos: `env['modelo'].create({...})` y leer el campo |
| Probar solo el caso feliz | Mínimo 4 tests: feliz + explícito + edge case + aislamiento |
| Hacer `env.cr.commit()` sin aprobación | SAVEPOINT/ROLLBACK siempre. Commit solo con aprobación explícita |
| Confiar en que `__init__.py` importa todo | Verificar explícitamente con `cat` por SSH |
| Hook solo en `write()` | Verificar si `create()` también necesita cobertura |
| Modificar código y no verificar que está cargado | `hasattr()` obligatorio tras module update |
| Decir "debería funcionar" sin probar | TODO se prueba. Sin SAVEPOINT no hay prueba. |

---

## 5. Formato de Informe para el Usuario

### Para el equipo técnico
- KPIs con números exactos
- Causa raíz con evidencia (queries, tracebacks)
- Código implementado con link al archivo
- Tabla de tests con resultados

### Para la dueña/gerente (NO técnico)
Siempre incluir una sección con lenguaje simple:

> **¿Qué estaba pasando?**
> [Explicación con metáfora simple]
>
> **¿Qué se hizo?**
> [Explicación de la solución sin tecnicismos]
>
> **¿A partir de cuándo aplica?**
> Desde ahora / Desde que se despliegue / etc.

---

## Directiva de Acción

> **ESTAS REGLAS SON OBLIGATORIAS. NO OPCIONALES.**

1. **CONÉCTATE POR SSH ANTES DE ESCRIBIR CÓDIGO.** Si el usuario reporta un bug y tú no te has conectado al servidor para diagnosticar, estás haciendo tu trabajo MAL. Conéctate, busca datos, cuantifica.

2. **PRUEBA TODO CON SAVEPOINT.** Si implementaste un fix y no lo probaste con una batería de tests en producción (SAVEPOINT → assert → ROLLBACK), estás haciendo tu trabajo MAL.

3. **VERIFICA QUE EL CÓDIGO ESTÁ CARGADO.** Si hiciste push + module update y no verificaste con `hasattr()` que los métodos existen en el servidor, estás haciendo tu trabajo MAL.

4. **GENERA UN INFORME CON DATOS DUROS.** Si resolviste un problema y no presentaste números (total afectados, porcentaje, ejemplos), estás haciendo tu trabajo MAL.

5. **INCLUYE EXPLICACIÓN NO TÉCNICA.** Si no puedes explicar el problema y la solución en lenguaje que entienda alguien sin conocimientos de programación, no has terminado tu trabajo.

6. **DOCUMENTA EL APRENDIZAJE.** Al terminar, crea un documento en `.agent/skills/base-de-conocimiento/aprendizajes/` con la lección aprendida. Esto es automático, no esperes a que te lo pidan.
