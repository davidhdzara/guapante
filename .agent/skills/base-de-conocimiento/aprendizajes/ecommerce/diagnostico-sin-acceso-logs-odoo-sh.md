# Diagnóstico de Bugs en Odoo.sh Sin Acceso a Logs del Servidor

**Fecha de Registro:** 2026-03-17
**Contexto del Problema:**
Al debuggear bugs de comportamiento en Odoo.sh (producción/staging), los agentes pueden caer en bucles de diagnóstico sin fin porque no tienen acceso directo a los logs del servidor Odoo. Sin poder ver los prints/logs del servidor, es imposible saber si el código Python está siendo ejecutado o no.

## 🚨 El Problema o Error

El agente pasó múltiples iteraciones modificando código Python sin saber si ese código se estaba ejecutando en el servidor. Señales de que esto está ocurriendo:

- El agente hace cambios al backend (Python), los sube, pero el comportamiento NO cambia.
- No hay acceso a `odoo.log` ni `journalctl` del servidor.
- El agente asume que su código sí se ejecuta pero no puede verificarlo.

## 🔍 Causa Raíz

En Odoo.sh (PaaS), los desarrolladores no tienen shell al servidor web. Los logs solo son accesibles via el panel de Odoo.sh, que el agente no puede ver. Esto crea un punto ciego crítico para el diagnóstico.

## ✅ Solución Adoptada: Técnica de "Note Spy"

Escribir valores de depuración directamente en campos de texto de la BD que sí sean visibles:

```python
# En ANY método Python que quieras verificar que se ejecuta:
debug_msg = f"[EJECUTADO] método=_cart_update, product_id={product_id}, kwargs={kwargs}\n"
if self.note:
    self.note += debug_msg
else:
    self.note = debug_msg
```

Luego el usuario ejecuta el script `analyze_cart.py` (shell de Odoo) y el campo `note` de la orden muestra si el método fue invocado y con qué parámetros.

**Script de diagnóstico en Odoo shell (`analyze_cart.py`):**

Siempre tener disponible el script `analyze_cart.py` en la raíz del proyecto para ejecutar en el shell de Odoo:
```bash
# En el servidor Odoo.sh o via rpc
odoo-bin shell -d database_name < analyze_cart.py
```

## 💡 Buenas Prácticas / Cómo evitarlo

### Señales de que el código Python NO se está ejecutando:

1. **La Nota Debug nunca aparece** en la BD después de la acción del usuario → el método no fue llamado.
2. **El comportamiento no cambia** a pesar de múltiples pushes con cambios al mismo método.
3. El error ocurre en otro método/archivo según el traceback del navegador.

### Checklist de diagnóstico (orden de prioridad):

1. **Lee el traceback del navegador primero.** Es la fuente más confiable. Muestra el archivo exacto y línea exacta que falló en el servidor.
2. **Verifica qué método realmente llama Odoo.** El nombre del método puede haber cambiado entre versiones (ej. `_cart_update` → `_cart_add` en Odoo 19).
3. **Usa "Note Spy"** para confirmar ejecución.
4. **Busca el código fuente de la versión correcta.** El código local puede ser de versión diferente al servidor.
5. **Busca en JS primero si el bug es de "duplicación exacta".** Un duplicado perfecto (mismo producto, misma cantidad, 2 veces) casi siempre es un problema de frontend, no backend.

### Verificar versión del código local vs servidor:

```bash
# Ver versión de Odoo en el código local
cat /home/david/odoo-projects/insotech/tmp_odoo/odoo/release.py | grep version_info

# IMPORTANTE: La carpeta insotech/tmp_odoo es Odoo 19, pero el servidor usa Odoo 18.
# Nunca usar ese código como referencia de APIs o firmas de métodos.
```
