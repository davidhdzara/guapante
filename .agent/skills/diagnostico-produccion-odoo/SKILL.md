---
name: "Diagnóstico y Resolución en Producción Odoo (Odoo.sh)"
description: "Skill obligatoria que define la metodología de diagnóstico forense, pruebas con rollback, despliegue seguro y verificación en servidores Odoo.sh de producción. Garantiza que cualquier agente pueda investigar, probar y resolver problemas con el mismo nivel de rigor y seguridad."
---

# Diagnóstico y Resolución en Producción Odoo (Odoo.sh)

Esta skill codifica la metodología exacta para diagnosticar bugs, implementar fixes y verificar cambios en un servidor Odoo.sh de producción **sin romper nada**. Todo agente que intervenga en debugging o fixes de producción **DEBE** seguir este protocolo.

---

## 1. Principio Fundamental: NUNCA Asumir, SIEMPRE Verificar

**Antes de escribir una sola línea de código, debes probar con datos reales que el problema existe y entender su alcance.**

### ¿Por qué?

- El usuario reporta un síntoma ("las facturas quedan pendientes"), no la causa.
- Un problema puede parecer generalizado pero afectar solo al 2% de los registros.
- Un problema puede parecer puntual pero afectar al 21% de los registros.
- Sin datos, cualquier fix es una apuesta ciega.

### Regla de Oro

> **Diagnostica con shell → Cuantifica el impacto → Propón fix → Prueba con SAVEPOINT → Despliega → Verifica con shell**

---

## 2. Acceso al Servidor: SSH + odoo-bin shell

### Conexión

```bash
ssh <usuario>@<instancia>.odoo.com "odoo-bin shell --no-http" << 'EOF'
# Código Python con acceso completo al ORM
# env, self, cr están disponibles
EOF
```

### Reglas de Seguridad

1. **SIEMPRE usar heredoc** (`<< 'EOF'`) para scripts multi-línea.
2. **SIEMPRE envolver en SAVEPOINT/ROLLBACK** cuando se prueban cambios:
   ```python
   env.cr.execute("SAVEPOINT test_safe")
   # ... pruebas ...
   env.cr.execute("ROLLBACK TO SAVEPOINT test_safe")
   ```
3. **NUNCA hacer `env.cr.commit()`** a menos que el usuario haya aprobado el cambio Y los datos sean correctos.
4. **SIEMPRE usar `try/except`** en scripts de diagnóstico para no interrumpir el análisis por un error puntual.

---

## 3. Fase 1: Diagnóstico Forense

### Objetivo

Entender el problema con datos reales, cuantificar su alcance y clasificar los registros afectados.

### Patrón de Script de Diagnóstico

```python
# ── Cabecera descriptiva ──
print("=" * 70)
print("  DIAGNÓSTICO: [Nombre del problema]")
print("=" * 70)

# ── Buscar registros afectados ──
afectados = env['modelo'].search([
    ('campo_problematico', '=', 'valor_incorrecto'),
    ('state', '=', 'posted'),
])

print(f"\nTotal afectados: {len(afectados)}")

# ── Clasificar por tipo ──
tipo_a = []  # Descripción
tipo_b = []  # Descripción

for r in afectados:
    if condicion_tipo_a:
        tipo_a.append(r)
    else:
        tipo_b.append(r)

print(f"  Tipo A: {len(tipo_a)}")
print(f"  Tipo B: {len(tipo_b)}")

# ── Mostrar ejemplos concretos ──
for r in tipo_a[:10]:
    print(f"  {r.name} | {r.campo} | {r.otro_campo}")
```

### Lo que debes entregar al usuario

1. **Número exacto** de registros afectados.
2. **Clasificación** por tipo/severidad.
3. **Ejemplos concretos** con nombres reales.
4. **Porcentaje** respecto al total.
5. **Hipótesis** de causa raíz (solo hipótesis, aún no fix).

---

## 4. Fase 2: Investigación de Causa Raíz

### Técnicas de Investigación

#### A. Verificar qué código está cargado

```python
import inspect

Model = env['modelo']
sig = inspect.signature(Model.metodo_sospechoso)
params = list(sig.parameters.keys())
has_method = hasattr(Model, 'metodo_esperado')

print(f"Método existe: {has_method}")
print(f"Parámetros: {params}")
```

#### B. Verificar importaciones en __init__.py

```python
# Desde SSH:
ssh usuario@servidor "cat /home/odoo/src/user/modulo/models/__init__.py"
```

#### C. Verificar flujo de ejecución (quién crea/modifica registros)

```python
# ¿Quién crea estos registros?
registros = env['modelo'].search([], order='id desc', limit=50)
creators = {}
for r in registros:
    cu = r.create_uid.name if r.create_uid else '(Sistema)'
    creators[cu] = creators.get(cu, 0) + 1

for k, v in sorted(creators.items(), key=lambda x: -x[1]):
    print(f"  {v:4d}x | {k}")
```

#### D. Verificar si un hook/onchange se ejecuta

```python
# ¿El onchange dispara en create() o solo en UI?
# Crear un registro por ORM y verificar si el campo esperado se llenó
test = env['modelo'].create({'partner_id': partner.id})
print(f"Campo esperado: {test.campo_que_deberia_llenarse}")
# Si es vacío → el onchange NO dispara en create()
```

#### E. Verificar defaults y automated actions

```python
# Buscar defaults
defaults = env['ir.default'].search([
    ('field_id.model', '=', 'sale.order'),
    ('field_id.name', '=', 'campo_sospechoso'),
])

# Buscar automated actions
for a in env['base.automation'].search([]):
    code = a.action_server_ids.mapped('code')
    for c in code:
        if c and 'campo_sospechoso' in str(c):
            print(f"⚠️ Action: {a.name}")
```

---

## 5. Fase 3: Implementación del Fix

### Reglas de Código

1. **Cirugía mínima**: Cambia solo lo necesario. No refactorices código que funciona.
2. **Documentación inline**: Explica el POR QUÉ del cambio, no el QUÉ.
3. **try/except con logging**: Nunca dejes que un error en el fix bloquee el sistema.
4. **Verificar sintaxis antes de commit**:
   ```bash
   python3 -c "import ast; ast.parse(open('archivo.py').read()); print('✅ OK')"
   ```

### Patrón de Override Seguro (create/write)

```python
@api.model_create_multi
def create(self, vals_list):
    """[Descripción del fix y POR QUÉ es necesario]."""
    for vals in vals_list:
        if vals.get('campo_objetivo'):
            continue  # Ya viene explícito — respetar
        # Lógica de inyección
        valor = self._calcular_valor(vals)
        if valor:
            vals['campo_objetivo'] = valor
    return super().create(vals_list)
```

### Commit Granular

```bash
git add archivo_modificado.py
git commit -m "fix(componente): descripción concisa del fix

Causa raíz: [explicación breve]
Impacto: [N registros afectados, X% del total]
Cambio: [qué hace el código nuevo]"
git push origin rama
```

---

## 6. Fase 4: Pruebas en Producción con SAVEPOINT

### Patrón de Batería de Tests

```python
env.cr.execute("SAVEPOINT test_battery")

results = []; total = 0; passed = 0; failed = 0

def test(name, func):
    global total, passed, failed
    total += 1
    try:
        env.cr.execute("SAVEPOINT ti")
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        if 'SKIP' in str(e):
            total -= 1
            print(f"  ⏭️  {name}: {e}")
        else:
            failed += 1
            print(f"  ❌ {name}: {e}")
    finally:
        try:
            env.cr.execute("ROLLBACK TO SAVEPOINT ti")
        except:
            env.cr.execute("SAVEPOINT ti")

# ── Tests ──
def t01():
    # Descripción del test
    registro = crear_registro_de_prueba()
    assert registro.campo == 'valor_esperado', f"Got {registro.campo}"
test("01 — Descripción del escenario", t01)

# ── Cleanup ──
env.cr.execute("ROLLBACK TO SAVEPOINT test_battery")

print(f"\nRESULTADOS: {passed}/{total} | {failed} fallaron")
```

### Reglas de Testing

1. **Cada test tiene su propio SAVEPOINT** (aislamiento total).
2. **Probar el caso feliz Y el edge case** (ej: Regla 90 CON doc previo vs SIN doc previo).
3. **Probar idempotencia**: ejecutar dos veces no debe romper nada.
4. **Probar aislamiento**: el fix no afecta otros flujos (ej: facturas de compra).
5. **Todo se rollbackea**: NUNCA persistir datos de test en producción.

---

## 7. Fase 5: Despliegue y Actualización

### Flujo Completo

```bash
# 1. Push del código
git push origin produccion

# 2. Esperar que Odoo.sh haga el build (~45-60 segundos)
sleep 50

# 3. Actualizar el módulo
ssh usuario@servidor "odoo-bin -d base_datos -u nombre_modulo --stop-after-init --no-http"

# 4. Verificar que el código nuevo está cargado
ssh usuario@servidor "odoo-bin shell --no-http" << 'EOF'
has_method = hasattr(env['modelo'], 'metodo_nuevo')
print(f"Código nuevo: {'✅' if has_method else '❌'}")
EOF

# 5. Re-ejecutar la batería de tests
```

### ⚠️ Si el módulo no actualiza

El update con `-u` solo crea columnas nuevas y carga data files. Si el `__init__.py` no importa un archivo, los métodos de ese archivo **no existen para el ORM** aunque el archivo esté en disco.

---

## 8. Fase 6: Informe al Usuario

### Formato de Informe

Todo diagnóstico debe generar un **artefacto markdown** con:

1. **KPIs generales**: Números duros (total, afectados, porcentaje).
2. **Tablas con datos reales**: Nombres de contactos, montos, fechas.
3. **Clasificación por responsable**: ¿Quién genera el problema? (usuario, OdooBot, API).
4. **Causa raíz confirmada**: No hipótesis — datos que la prueban.
5. **Solución implementada**: Archivo, líneas, qué hace.
6. **Pruebas ejecutadas**: Tabla de tests con resultado.
7. **Explicación no técnica**: Para que la dueña/gerente entienda sin saber Python.

### Ejemplo de Explicación No Técnica

> **¿Qué estaba pasando?**
> Cuando un cliente hace pedido por la tienda online, el sistema no miraba qué plazo de pago tenía ese cliente configurado.
>
> **¿Qué se hizo?**
> Se le enseñó al sistema a siempre revisar el plazo de pago del cliente al crear cualquier pedido.
>
> **¿A partir de cuándo aplica?**
> Desde ahora. Todos los pedidos nuevos ya traerán el plazo correcto.

---

## 9. Patrones de Conexión Específicos — Guapante

### SSH

```bash
ssh 27043073@guapante.odoo.com "odoo-bin shell --no-http"
```

### Base de datos

```
p_guapante_produccion_27043073
```

### Update de módulos

```bash
ssh 27043073@guapante.odoo.com "odoo-bin -d p_guapante_produccion_27043073 -u nombre_modulo --stop-after-init --no-http"
```

### Módulos principales del proyecto

| Módulo | Propósito |
|--------|-----------|
| `theme_guapante` | eCommerce, carrito, precios, entrega |
| `insotech_l10n_co_advanced` | DIAN, PRE-INV, facturación electrónica |
| `insotech_core` | Licenciamiento, configuración base |

---

## 10. Anti-Patrones (Lo que NUNCA debes hacer)

| ❌ Anti-Patrón | ✅ Correcto |
|----------------|-------------|
| Hacer `env.cr.commit()` sin verificar datos | Usar SAVEPOINT/ROLLBACK, solo commit tras validación |
| Asumir que un onchange se ejecuta en create() | Verificar con datos: crear por ORM y revisar el resultado |
| Probar solo el caso feliz | Probar caso feliz + edge case + aislamiento + idempotencia |
| Modificar código sin verificar que está cargado en el servidor | Siempre verificar con `hasattr()` + `inspect.signature()` tras el update |
| Hacer un fix basado en el reporte del usuario sin diagnosticar | Primero cuantificar: ¿cuántos registros? ¿qué porcentaje? ¿desde cuándo? |
| Hook solo en `write()` sin verificar si `create()` también necesita cobertura | Revisar el flujo nativo: ¿el estado se asigna en create() o write()? |
| Confiar en que `__init__.py` importa todos los archivos | Verificar cada archivo explícitamente |
| Hacer refactoring masivo junto con el fix | Un commit = un propósito. Fix primero, refactor después |

---

## Directiva de Acción

1. **SIEMPRE diagnostica ANTES de codificar**: Conecta al servidor por SSH, busca registros afectados, cuantifica el impacto con números exactos.
2. **SIEMPRE prueba con SAVEPOINT**: Toda prueba en producción debe estar envuelta en SAVEPOINT/ROLLBACK. Nunca persistir datos de test.
3. **SIEMPRE verifica que el código nuevo está cargado**: Tras push + module update, verifica con `hasattr()` e `inspect.signature()` antes de correr tests.
4. **SIEMPRE genera un informe con datos duros**: KPIs, tablas, porcentajes, causa raíz confirmada, y una explicación no técnica para stakeholders.
5. **SIEMPRE prueba el flujo REAL, no un flujo inventado**: Si el eCommerce crea con `create()`, tu test debe usar `create()`, no simular un `write()`.
