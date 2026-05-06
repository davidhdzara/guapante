# Bug: Ajustes de Retención No Se Concilian en Pagos Agrupados

**Fecha de Registro:** 2026-05-05
**Contexto del Problema:**
Al registrar un pago de múltiples facturas de proveedor con retenciones (módulo `insotech_account_colombia`), las facturas quedaban en estado "not_paid" o "partial" a pesar de que el ajuste contable de retenciones se creaba correctamente.

## 🚨 El Problema o Error
El método `_create_insotech_retention_adjustments` en `account_payment_register.py` creaba el asiento de ajuste (Debit CxP, Credit Retención), lo publicaba, pero la llamada final `(lines + cp_line).reconcile()` **fallaba silenciosamente**, dejando el ajuste sin conciliar.

**Impacto:** 6 de 8 ajustes de retenciones en producción quedaron sin conciliar, con facturas mostrando saldos incorrectos.

## 🔍 Causa Raíz
Después de `super().action_create_payments()`:

1. **Cache ORM stale:** El TransientModel `account.payment.register` puede perder o invalidar sus relaciones `line_ids` después del `super()` que crea y reconcilia pagos. Las líneas de factura tienen datos cacheados (residuales, estado de reconciliación) que no reflejan el estado post-pago.

2. **Facturas canceladas en grupo:** Si una factura del grupo está `cancel`, `(lines + cp_line).reconcile()` lanza `"You can only reconcile posted entries"` y aborta TODO el grupo, incluyendo las facturas válidas.

3. **Sin manejo de errores:** La llamada `.reconcile()` no tenía try/except, por lo que cualquier error abortaba silenciosamente (no se mostraba al usuario porque la excepción ocurría después del return del super).

## ✅ Solución Adoptada
Archivo: `insotech_account_colombia/models/account_payment_register.py`

1. **Capturar `line_ids` como IDs antes de `super()`:**
   ```python
   captured_line_ids = self.line_ids.ids
   ```

2. **Re-browse y invalidar caché después del super:**
   ```python
   lines = aml_model.browse(captured_line_ids).exists()
   lines.invalidate_recordset(['amount_residual', 'reconciled'])
   ```

3. **Filtrar líneas ya reconciliadas:**
   ```python
   lines_to_reconcile = lines.filtered(lambda l: not l.reconciled)
   ```

4. **Fallback de conciliación individual:**
   ```python
   try:
       (lines_to_reconcile + cp_line).reconcile()
   except Exception:
       self._reconcile_adjustment_fallback(cp_line, lines_to_reconcile)
   ```

5. **Logging completo** para debugging futuro.

## 💡 Buenas Prácticas / Cómo evitarlo
- **NUNCA confiar en `self.field` de un TransientModel después de un `super()` que modifica datos.** Siempre capturar IDs antes.
- **SIEMPRE invalidar caché ORM** (`invalidate_recordset`) después de operaciones que modifican registros relacionados (pagos, reconciliaciones).
- **SIEMPRE envolver `.reconcile()` en try/except** — Odoo puede fallar por múltiples razones (facturas canceladas, líneas ya reconciliadas, multi-moneda).
- **Implementar fallback:** Si la conciliación en bloque falla, intentar línea por línea.
